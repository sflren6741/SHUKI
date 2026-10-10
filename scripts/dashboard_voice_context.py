"""Bounded, read-only note retrieval for conversation; no general filesystem tools."""
import fnmatch
import json
import re
import threading
from pathlib import Path

from dashboard_file_links import build_file_href

_index_lock = threading.Lock()
_index_cache = None


def search_index(vault):
    """Reuse the ranking index until its file changes; never cache note contents or permissions."""
    import vault_search
    global _index_cache
    stat = vault_search.INDEX_FILE.stat()
    key = (str(Path(vault).resolve()), stat.st_mtime_ns, stat.st_size)
    with _index_lock:
        if _index_cache is None or _index_cache[0] != key:
            _index_cache = (key, vault_search.SearchIndex(vault=vault))
        return _index_cache[1]


def allowed_path(vault, relative):
    root = Path(vault).resolve()
    rel = str(relative).replace('\\', '/')
    if not rel or ':' in rel or rel.startswith('/') or '..' in rel.split('/'):
        return None
    if any(p.startswith('.') or p == '_private' for p in rel.split('/')):
        return None
    if rel.split('/')[0] not in {'00_Intranet', '01_Inbox', '02_Home', '03_Projects',
                                '04_Tasks', '05_Areas', '06_Resources', '07_Logs'}:
        return None
    path = (root / rel).resolve()
    if not path.is_relative_to(root) or path.suffix.lower() != '.md':
        return None
    resolved = path.relative_to(root).as_posix()
    if resolved.split('/')[0] != rel.split('/')[0] or any(
            p.startswith('.') or p == '_private' for p in resolved.split('/')):
        return None
    # Both lexical and resolved paths must respect the vault's authoritative exclusions.
    settings = json.loads((root / '.claude/settings.json').read_text(encoding='utf-8-sig'))
    for rule in settings.get('permissions', {}).get('deny', []):
        match = re.fullmatch(r'(?:Read|Grep|Glob)\((.+)\)', rule)
        if match:
            pattern = match[1].replace('\\', '/').removeprefix('./').lstrip('/').casefold()
            if any(fnmatch.fnmatchcase(p.casefold(), pattern)
                   for p in (rel, path.relative_to(root).as_posix())):
                return None
    return path


def lookup(vault, request):
    """Read up to two notes, or search existing BM25 index then read relevant excerpts.

    Search uses the existing index without rebuilding it or reading excluded files.
    Actual contents are always read fresh; missing/oversize notes are reported.
    """
    if not isinstance(request, dict):
        raise ValueError('Invalid note lookup')
    query = request.get('query', '')
    paths = request.get('paths', [])
    if not isinstance(query, str) or len(query) > 300 or not isinstance(paths, list) or len(paths) > 2:
        raise ValueError('Lookup needs a short query or at most two note paths')
    if any(not isinstance(p, str) for p in paths):
        raise ValueError('Invalid note path')
    if not paths:
        if not query.strip():
            raise ValueError('A note name or search query is required')
        import vault_search
        index = search_index(vault)
        if not index.doc_meta:
            raise ValueError('Note search index is unavailable')
        ranked = vault_search.bm25f_search(index, vault_search.tokenize(query), k=20)
        paths = []
        for rel, _ in ranked:
            if allowed_path(vault, rel):
                paths.append(rel)
                if len(paths) == 2:
                    break
    notes, sources = [], []
    for relative in paths:
        path = allowed_path(vault, relative)
        if path is None:
            notes.append({'status': 'This note is unavailable to voice lookup.'})
            continue
        if not path.is_file():
            notes.append({'path': relative, 'status': 'Note no longer exists.'})
            continue
        if path.stat().st_size > 512000:
            notes.append({'path': relative, 'status': 'Note is too large for a quick lookup.'})
            continue
        content = path.read_text(encoding='utf-8-sig')
        start = 0
        if query and len(content) > 6000:
            terms = re.findall(r'\w{2,}', query.lower())
            positions = [content.lower().find(term) for term in terms]
            hits = [p for p in positions if p >= 0]
            start = max(0, min(hits) - 700) if hits else 0
        excerpt = content[start:start + 6000]
        line = content[:start].count('\n') + 1
        rel = path.relative_to(Path(vault).resolve()).as_posix()
        notes.append({'path': rel, 'start_line': line, 'excerpt': excerpt,
                      'truncated': len(excerpt) != len(content), 'modified': path.stat().st_mtime})
        sources.append({'path': rel, 'title': path.stem, 'url': build_file_href(rel),
                        'start_line': line})
    return {'notes': notes, 'sources': sources,
            'search_note': 'Search ranking uses the existing index; excerpts are current. No match is not proof of absence.'}


_CONTROL_MARKER_RE = re.compile(r'VOICE_(?:WORK|LOOKUP|SEND):')


def has_marker(text, name):
    """Whether a NAME: control marker appears anywhere in text (not just at line start).

    Models (especially fast/low-effort ones in voice mode) do not reliably keep the
    marker as the first thing on its own line; requiring a line-start anchor here made
    directives silently fail to fire (2026-09-25 bug report: work never started).
    """
    return re.search(re.escape(name + ':'), text) is not None


def directive(text, name):
    """Parse the JSON payload following a NAME: marker, wherever it appears in text.

    Uses raw_decode instead of a single-line regex capture so JSON the model wrapped
    across multiple lines is still parsed in full rather than truncated at the first
    newline. Rejects ambiguous input (marker appears more than once) rather than
    guessing which occurrence is the real directive.
    """
    matches = list(re.finditer(re.escape(name + ':'), text))
    if len(matches) != 1:
        return None
    start = matches[0].end()
    start += re.match(r'\s*', text[start:]).end()
    try:
        value, _ = json.JSONDecoder().raw_decode(text, start)
    except ValueError:
        return None
    return value if isinstance(value, dict) else None


def visible_text(text):
    """Strip everything from the first control marker onward, wherever it sits.

    This runs unconditionally, independent of whether `directive()` above could parse
    a payload: even a malformed or mid-sentence marker must never reach the user as
    literal text or speech (2026-09-25 bug report: raw 'VOICE_LOOKUP: {...}' text was
    read aloud when the model didn't format the directive exactly as instructed).
    """
    return _CONTROL_MARKER_RE.split(text, maxsplit=1)[0].strip()
