#!/usr/bin/env python3
"""
vault_lint.py — vault の決定的QAチェッカー（LLM不使用・誤検出0%設計）

2026-07-02 導入。qwen3.5:9B の QAループ（local_qa_loop.py）を置き換える。
「正解がルールとして明文化されているチェック」だけを行う。スタイルの好み・文章の良し悪しには触れない。

チェック項目（すべて AGENTS.md と 00_Intranet の明文ルールに基づく）:
  1. frontmatter 構造（--- 開始・閉じ・1行潰れ・YAML実パース・重複キー）※YAML実パースは 2026-07-03 追加
  2. 未クォート wikilink（`parent: [[X]]` は YAML でネスト配列になり黙って壊れる）
  2.5. title の存在（frontmatter を持つ全ファイルで必須。Obsidian 外への移行可搬性・2026-07-03 導入）
  3. area 値が 11 Area のいずれか（または空）
  4. status 値がフォルダ別の許容セット内（archived は全DB共通で許容。03_Projects も対象）
  5. date / created の欠落＋形式（YYYY-MM-DD 開始でない値は要対応）
  5.5. 期間物の date は期間の最終日（ファイル名/period の範囲表記と比較。範囲表記の date も違反・2026-07-05 導入）
  6. frontmatter 完全欠落（DBフォルダ配下・参考枠）
  7. デッドwikilink（参考情報・エラー扱いしない）
  8. nullバイト／不正UTF-8（ripgrep 不可視＝他エージェントから取りこぼされる・2026-09-03 追加）

出力: 99_System/qa/YYYY-MM-DD.md（従来と同じ場所・朝の orchestrator トリアージ互換）
"""
import re
import sys
import unicodedata
from collections import Counter
from posixpath import normpath
from datetime import datetime, date as date_t
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import shuki_paths  # noqa: E402  (vault の場所。以前はここに絶対パスを直書きしていた)
import shuki_profile  # noqa: E402  (area の有効値。2026-09-27)

VAULT = shuki_paths.VAULT
OUT_DIR = shuki_paths.reports_dir("qa", VAULT)

EXCLUDE_DIRS = {".git", ".obsidian", ".smart-env", ".claude", ".codex", ".trash",
                "08_Archive", "agent-runs", "assets", "_ocr_out", "raw",
                "qa", shuki_paths.REPORT_FOLDERS["qa"]}  # qa＝自レポートの走査でデッドリンクが自己参照になるのを防ぐ（2026-07-03。2026-10-07 07_Logs/レポート/QA へ移動）。.codex＝スキルの自動生成ミラー（title を持たない設計）

# frontmatter の `area:` に書いてよい値。個人ごとに違うので 99_System/profile.json が正
# （2026-09-27。display:false のAreaも「値としては有効」なのでここには含まれる）。
AREAS = set(shuki_profile.valid_area_names())

STATUS_SETS = {
    "04_Tasks": {"todo", "in-progress", "done", "on-hold", "cancelled"},
    "01_Inbox": {"new", "routing", "done", "pending", "on-hold", "rejected"},
    "06_Resources": {"inbox", "in-progress", "done", "archived", "draft"},
    "03_Projects": {"todo", "in-progress", "done", "on-hold", "cancelled"},
}
UNIVERSAL_STATUS = {"archived"}

DATE_REQUIRED_PREFIXES = (  # 末尾 / 必須（"07_Logs/ログ.md" ハブへの前方一致誤爆を防ぐ・2026-07-03）
    "07_Logs/ログ/", "06_Resources/Resources/ナレッジ/",
    "04_Tasks/タスク管理/タスク/", "01_Inbox/インボックス/",
)

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}")
# 期間の範囲表記（区切りは vault 慣習の 〜/~ のみ。- は日付自体と衝突するため対象外＝誤検出防止）
RANGE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})\s*[〜~]\s*(\d{4}-\d{2}-\d{2})")
WIKILINK_RE = re.compile(r"\[\[([^\]\|#]+)")
# デッドwikilink走査から除外する「コード」領域（書式の例示を誤検出しないため・2026-09-26）
CODE_FENCE_RE = re.compile(r"```.*?```", re.S)
CODE_SPAN_RE = re.compile(r"`[^`\n]*`")

# 参考枠（date/created 欠落・デッドwikilink）を「新規作成分」だけに絞る境目。
# 2026-08-30 決裁 d-fc480ccb：レガシー債務（Notion移行前の山）はレポートから外し、
# 新規作成分だけを検出する。451件の山に埋もれて新規1件が見えないのを直すのが目的で、
# 一括補完はしない（元の日付が不明なファイルに推測日を打たないため）。
LEGACY_CUTOFF = "2026-07-01"

# Explicit categories only: an unfamiliar suffix must not hide a potential note.
ATTACHMENT_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".avif",
                       ".bmp", ".ico", ".pdf", ".mp3", ".wav", ".m4a", ".ogg",
                       ".mp4", ".mov", ".webm", ".csv", ".xlsx", ".docx", ".pptx"}
PROCEDURE_REFERENCES = {"skill.md", "agents.md", "claude.md"}
LINK_PLACEHOLDERS = {"...", "…", "ノート名", "ファイル名", "Area名"}


def normalized_link_pair(source, target):
    """Normalize spelling without collapsing different source or target paths."""
    source = normpath(nfc(source.strip().replace("\\", "/")))
    target = nfc(target.strip().replace("\\", "/"))
    target = target.split("|", 1)[0].split("#", 1)[0].strip()
    target = normpath(target) if target else ""
    name = target.rsplit("/", 1)[-1]
    if name.casefold() in PROCEDURE_REFERENCES:
        kind = "procedure"
    elif name in LINK_PLACEHOLDERS:
        kind = "placeholder"
    elif Path(name).suffix.casefold() in ATTACHMENT_SUFFIXES:
        kind = "attachment"
    else:
        kind = "note"
        if target.casefold().endswith(".md"):
            target = target[:-3]
    return source, target, kind


def partition_dead_links(dead_links):
    """Keep raw occurrence counts while handing off only unique note candidates."""
    counts = Counter(normalized_link_pair(source, target) for source, target in dead_links)
    groups = {"notes": [], "references": []}
    for (source, target, kind), count in sorted(counts.items()):
        groups["notes" if kind == "note" else "references"].append(
            {"source": source, "target": target, "kind": kind, "count": count})
    return {"raw_count": len(dead_links), "unique_count": len(counts),
            "duplicate_count": len(dead_links) - len(counts), **groups}


def dead_link_report(dead_links, legacy_hidden=0):
    if not dead_links:
        return []
    grouped = partition_dead_links(dead_links)
    lines = ["## Wikilink reference summary", "",
             f"> Since {LEGACY_CUTOFF}: raw occurrences={grouped['raw_count']}; "
             f"unique source/target pairs={grouped['unique_count']}; "
             f"duplicate occurrences={grouped['duplicate_count']}; "
             f"note candidates={len(grouped['notes'])}; "
             f"non-note references={len(grouped['references'])}.",
             f"> Legacy occurrences hidden under decision d-fc480ccb: {legacy_hidden}.", "",
             "### デッドwikilink — unique note candidates (knowledge handoff)", "",
             "> Candidates for review, not confirmed errors. Intentional links to future notes remain valid; "
             "do not automatically delete links, rename targets, or create notes.", ""]
    for entry in grouped["notes"]:
        lines.append(f"- `{entry['source']}` → `[[{entry['target']}]]` "
                     f"(occurrences: {entry['count']})")
    if not grouped["notes"]:
        lines.append("None.")
    lines.extend(["", "### Non-note references — excluded from knowledge handoff", "",
                  "> Attachment, procedure, and explicit placeholder references. "
                  "Their classification does not verify that referenced files exist.", ""])
    for entry in grouped["references"]:
        lines.append(f"- `{entry['source']}` → `{entry['target']}` "
                     f"({entry['kind']}; occurrences: {entry['count']})")
    if not grouped["references"]:
        lines.append("None.")
    lines.append("")
    return lines


def created_proxy(fm) -> str:
    """そのファイルが「いつできたか」の最良の手がかりを YYYY-MM-DD で返す（不明なら空）。

    mtime は使えない（Drive 同期が全ファイルを書き換えており、vault の mtime は
    作成日を表さない）。frontmatter の created を第一に、無ければ date で代用する。
    実測（2026-09-08）では欠落434件すべてが「date だけ欠落・created あり」で、
    両方欠落は0件だったため、この2段で全件に手がかりが付く。
    """
    for k in ("created", "date"):
        v = norm_str(fm.get(k))[:10]
        if DATE_RE.match(v):
            return v
    return ""


def nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s)


# --- 重複キーを検出する SafeLoader（YAML は仕様上、後勝ちで黙って上書きするため） ---
class DupKeyError(Exception):
    pass


class DupCheckLoader(yaml.SafeLoader):
    pass


def _construct_mapping(loader, node, deep=False):
    seen = set()
    for key_node, _ in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in seen:
            raise DupKeyError(f"キー `{key}` が重複している（後の値で黙って上書きされる）")
        seen.add(key)
    return yaml.SafeLoader.construct_mapping(loader, node, deep)


DupCheckLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _construct_mapping)


def iter_md_files():
    for p in VAULT.rglob("*.md"):
        rel_parts = {nfc(x) for x in p.relative_to(VAULT).parts}
        if rel_parts & EXCLUDE_DIRS:
            continue
        yield p


def parse_frontmatter(text: str):
    """(fm_dict_or_None, fm_block, errors) を返す。
    fm_dict=None は「frontmatter なし」。errors ありは「あるが壊れている」。"""
    errors = []
    if not text.startswith("---"):
        return None, "", errors
    first_line = text.split("\n", 1)[0]
    if first_line.strip() != "---" and first_line.count("---") >= 2:
        errors.append("frontmatter が1行に潰れている")
        return {}, "", errors
    m = re.match(r"^---\r?\n(.*?)\r?\n---", text, re.S)
    if not m:
        errors.append("frontmatter の閉じ `---` が見つからない")
        return {}, "", errors
    block = m.group(1)

    # YAML 実パース（Obsidian が読めるかの実質判定・2026-07-03 追加）
    try:
        fm = yaml.load(block, Loader=DupCheckLoader)
    except DupKeyError as e:
        errors.append(f"YAML 重複キー: {e}")
        return {}, block, errors
    except yaml.YAMLError as e:
        detail = str(e).split("\n")[0][:120]
        errors.append(f"YAML として壊れている（Obsidian でプロパティが読めない）: {detail}")
        return {}, block, errors

    if fm is None:
        fm = {}
    if not isinstance(fm, dict):
        errors.append("frontmatter が key: value 形式でない")
        return {}, block, errors

    # 未クォート wikilink（`key: [[X]]` はネスト配列にパースされ黙って壊れる）
    for k, v in fm.items():
        if isinstance(v, list) and any(isinstance(x, list) for x in v):
            errors.append(
                f"`{k}` の wikilink が未クォート（`{k}: \"[[...]]\"` と書く。"
                "今のままだと YAML 配列として解釈されリンクにならない）")

    return fm, block, errors


def norm_str(v) -> str:
    """YAML パース結果を比較用の素の文字列へ（date型・クォート・wikilink 껍질を剥がす）"""
    if v is None:
        return ""
    if isinstance(v, (date_t, datetime)):
        return v.strftime("%Y-%m-%d")
    return str(v).strip().strip('"').strip("'").strip()


def area_values(fm) -> list:
    v = fm.get("area")
    vals = v if isinstance(v, list) else [v]
    out = []
    for x in vals:
        if isinstance(x, list):  # 未クォート wikilink は別項目で検出済み
            continue
        s = norm_str(x).strip("[]").strip()
        if s:
            out.append(s)
    return out


def main():
    today = datetime.now().strftime("%Y-%m-%d")
    findings = {}      # relpath -> [msg]（要対応）
    legacy_date = []   # (relpath, 欠落キー) 参考枠
    legacy_nofm = []   # frontmatter 完全欠落（DBフォルダ・参考枠）
    dead_links = []    # (relpath, target)
    legacy_hidden = {"date": 0, "dead": 0}  # カットオフより前として非表示にした件数
    basenames = set()

    files = list(iter_md_files())
    for p in files:
        basenames.add(nfc(p.stem))

    for p in files:
        rel = nfc(str(p.relative_to(VAULT)).replace("\\", "/"))
        try:
            raw = p.read_bytes()
        except OSError as e:
            findings.setdefault(rel, []).append(f"読み取り失敗: {e}")
            continue

        msgs = []
        # バイナリ健全性（nullバイト／不正UTF-8）。ripgrep から不可視になり
        # orchestrator の振り分け・knowledge のメンテからも取りこぼされる（2026-09-03 追加）
        _rg_note = ("（ripgrep 不可視のため orchestrator の振り分け・"
                    "knowledge のメンテからも取りこぼされる）")
        nul = raw.count(b"\x00")
        if nul:
            msgs.append(f"nullバイトを {nul} 個含む{_rg_note}")
        try:
            text = raw.decode("utf-8-sig")
        except UnicodeDecodeError as e:
            msgs.append(f"不正なUTF-8（{e.reason}・byte offset {e.start}）{_rg_note}")
            text = raw.decode("utf-8-sig", errors="replace")

        fm, fm_block, fm_errors = parse_frontmatter(text)
        msgs.extend(fm_errors)
        in_db = any(rel.startswith(pref) for pref in DATE_REQUIRED_PREFIXES)

        if fm is None:
            # frontmatter 完全欠落。DBフォルダ配下なら参考枠でカウント（大半レガシー）
            if in_db:
                legacy_nofm.append(rel)
        elif not fm_errors:
            # title チェック（移行可搬性ルール・2026-07-03 導入。frontmatter を持つ全ファイルで必須）
            if not norm_str(fm.get("title")):
                msgs.append("title がない（frontmatter には title を必ず入れる・2026-07-03 ルール）")

            # area チェック（wikilink 形式は剥がして判定）
            for v in area_values(fm):
                if v not in AREAS:
                    msgs.append(f"area `{v}` は 11 Area にない（正: {'/'.join(sorted(AREAS))} または空）")

            # status チェック
            status = norm_str(fm.get("status"))
            if status and status not in UNIVERSAL_STATUS:
                top = rel.split("/", 1)[0]
                allowed = STATUS_SETS.get(top)
                if allowed and status not in allowed:
                    msgs.append(f"status `{status}` は {top} の許容値 {sorted(allowed)} にない")

            # date / created: 欠落は参考枠（レガシー債務）、形式違反は要対応
            if in_db:
                missing = []
                for k in ("date", "created"):
                    val = norm_str(fm.get(k))
                    if not val:
                        missing.append(k)
                    elif not DATE_RE.match(val):
                        msgs.append(f"`{k}: {val}` が YYYY-MM-DD 形式で始まらない")
                if missing:
                    # 新規作成分だけを出す（2026-08-30 決裁 d-fc480ccb）。
                    # 手がかりが取れないファイルは「レガシー側」に倒す＝黙って山を積み直さない。
                    if created_proxy(fm) >= LEGACY_CUTOFF:
                        legacy_date.append((rel, "/".join(missing)))
                    else:
                        legacy_hidden["date"] += 1

                # 期間物の date は期間の最終日（2026-07-05 ルール）
                dval = norm_str(fm.get("date"))
                if dval:
                    range_m = (RANGE_RE.search(nfc(p.stem))
                               or RANGE_RE.search(norm_str(fm.get("period"))))
                    if RANGE_RE.search(dval):
                        msgs.append(
                            "`date` が範囲表記（期間物の date は期間の最終日を単一日付で記入・2026-07-05 ルール）")
                    elif range_m and DATE_RE.match(dval) and dval[:10] != range_m.group(2):
                        msgs.append(
                            f"期間物の `date: {dval[:10]}` が期間最終日 {range_m.group(2)} と不一致"
                            "（date は期間の最終日・2026-07-05 ルール）")

        # デッドwikilink（本文のみ・参考情報）。date/created 欠落と同じく新規作成分に絞る
        # （2026-08-30 決裁 d-fc480ccb）。判定はリンク自体でなく「リンク元ファイルの作成日」で、
        # レガシーノートに今日リンクを足した場合は拾えない — 決定的に取れる手がかりが
        # frontmatter しか無いことによる既知の限界（mtime は Drive 同期で使えない）。
        fm_m = re.match(r"^---\r?\n(.*?)\r?\n---", text, re.S)
        body = text[fm_m.end():] if fm_m else text
        recent_src = bool(fm) and created_proxy(fm) >= LEGACY_CUTOFF
        # 書式の例示（コードフェンス・インラインコード内の `"[[Area名]]"` 等）は
        # リンクではないので走査対象から外す（2026-09-26。ルール文書を 00_Intranet へ
        # 分割した際、AGENTS.md/CLAUDE.md にあった例示が一斉に誤検出された）。
        scan_body = CODE_SPAN_RE.sub("", CODE_FENCE_RE.sub("", body))
        for target in WIKILINK_RE.findall(scan_body):
            _, t, kind = normalized_link_pair(rel, target)
            name = t.rsplit("/", 1)[-1]
            if t and not t.startswith(("http", "assets")) and (kind != "note" or name not in basenames):
                if recent_src:
                    dead_links.append((rel, target))
                else:
                    legacy_hidden["dead"] += 1

        if msgs:
            findings[rel] = msgs

    # レポート出力
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / f"{today}.md"
    lines = [
        "---",
        f"date: {today}",
        f"created: {today}",
        "agent: vault-lint",
        "model: なし（Python決定的チェック）",
        "---",
        "",
        f"# Vault Lint レポート — {today}",
        "",
        f"> `vault_lint.py`（LLM不使用・YAML実パース版 2026-07-03〜）による決定的チェック。走査 {len(files)} ファイル、"
        f"要対応 {sum(len(v) for v in findings.values())} 件 / {len(findings)} ファイル。",
        "> ルール外の値・構造だけを報告する。スタイル・文章品質には触れない（誤検出0%設計）。",
        "",
    ]
    if findings:
        lines.append("## 要対応")
        lines.append("")
        for rel in sorted(findings):
            lines.append(f"### `{rel}`")
            for msg in findings[rel]:
                lines.append(f"- {msg}")
            lines.append("")
    else:
        lines.append("## 要対応: なし ✅")
        lines.append("")

    if legacy_date:
        lines.append(f"## date/created 欠落（参考・{len(legacy_date)}件・{LEGACY_CUTOFF} 以降の作成分のみ）")
        lines.append("")
        lines.append("> ここに出るのは AGENTS.md §📐違反の**新規分**。それ以前のレガシー債務 "
                     f"{legacy_hidden['date']} 件は 2026-08-30 決裁 d-fc480ccb により非表示"
                     "（一括補完はしない＝元の日付が不明なファイルに推測日を打たない）。")
        lines.append("")
        for rel, keys in legacy_date[:30]:
            lines.append(f"- `{rel}`（{keys} なし）")
        if len(legacy_date) > 30:
            lines.append(f"- …ほか {len(legacy_date) - 30} 件")
        lines.append("")

    if legacy_nofm:
        lines.append(f"## frontmatter なし（参考・{len(legacy_nofm)}件・DBフォルダ配下）")
        lines.append("")
        lines.append("> 大半はレガシー。**新規作成のファイルがここに出たら作成ルール違反**（テンプレ不通過の可能性）。")
        lines.append("")
        for rel in legacy_nofm[:15]:
            lines.append(f"- `{rel}`")
        if len(legacy_nofm) > 15:
            lines.append(f"- …ほか {len(legacy_nofm) - 15} 件")
        lines.append("")

    lines.extend(dead_link_report(dead_links, legacy_hidden["dead"]))

    if not legacy_date and not dead_links and any(legacy_hidden.values()):
        lines.append(f"## 参考枠: {LEGACY_CUTOFF} 以降の新規分は 0 件 ✅")
        lines.append("")
        lines.append(f"> レガシー債務（date/created 欠落 {legacy_hidden['date']} 件・"
                     f"デッドwikilink {legacy_hidden['dead']} 件）は決裁 d-fc480ccb により非表示。")
        lines.append("")

    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"lint done: {len(files)} files, {len(findings)} files with findings, "
          f"{len(legacy_nofm)} no-fm, {len(dead_links)} raw link references, "
          f"{len(partition_dead_links(dead_links)['notes'])} unique note candidates -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
