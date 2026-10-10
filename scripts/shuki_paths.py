#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
shuki_paths.py — 実行環境ごとに変わる絶対パスの単一情報源（公開リポジトリ対応・2026-08-06新設）。

背景：dashboard_server.py 等が vault の場所や Radio フォルダ、個人環境の絶対パスを直書きして
いたため、公開版リポジトリではコードを書き換えないと動かなかった。このモジュールが
`shuki_paths.json`（このファイルと同じディレクトリ・.gitignore対象・リポジトリにはコミットしない）
を読み、無ければ汎用プレースホルダーにフォールバックする。各自の環境の値は
`shuki_paths.example.json` をコピーして `shuki_paths.json` を作り、そこに書く（コード変更不要）。
vault-scripts 配下の自己参照パス（このスクリプト自身の隣のファイル等）は対象外＝
`Path(__file__).resolve().parent` で足りるものはここに含めない。
"""
import json
import os
import re
import sys
import tempfile
from pathlib import Path

_HERE = Path(__file__).resolve().parent


def _find_secrets_dir():
    """資格情報ディレクトリ（shuki-secrets/）を親方向に探す。

    環境固有の値（絶対パス・ntfyトピック・Tailscaleホスト名）と OAuth トークンは、コードの
    ディレクトリが公開リポジトリの作業ツリーになった以上そこに置けない（2026-09-28）。
    置き場は「リポジトリの外側のどこか」なので、**階層の深さを決め打ちしない**
    （scripts/ が SHUKI/scripts に移った時に ../ 決め打ちが外れた実績がある）。
    環境変数 SHUKI_SECRETS があればそれが最優先。
    """
    import os
    env = os.environ.get("SHUKI_SECRETS")
    if env and Path(env).is_dir():
        return Path(env)
    for base in (_HERE, *_HERE.parents):
        cand = base / "shuki-secrets"
        if cand.is_dir():
            return cand
    # Beside the repository, like the data root. _HERE.parent is the repository itself
    # (2026-10-07: a fresh public clone wrote shuki-secrets/ into its own working tree).
    return _HERE.parent.parent / "shuki-secrets"


_SECRETS_DIR = _find_secrets_dir()
# 設定ファイルは shuki-secrets/ を優先し、無ければ従来どおりスクリプトの隣（移行前の環境）。
_CONFIG_FILE = (_SECRETS_DIR / "shuki_paths.json") if (_SECRETS_DIR / "shuki_paths.json").exists() \
    else (_HERE / "shuki_paths.json")

# 汎用プレースホルダー（shuki_paths.json が無い＝未設定の環境向けフォールバック）。
# 実際の環境の値は各自 shuki_paths.json に書く（shuki_paths.example.json がテンプレート）。
_DEFAULTS = {
    "vault": r"C:\path\to\your\Obsidian_Vault",
    "radio_dir": r"C:\path\to\your\Radio",
    "message_base": r"C:\path\to\your\workspace",
    "code_cli": "",
    "stt_venv_python": "",
    "stt_script": "",
}

# 値が無い（キー自体を省略、または null）場合に None を返してよいキー。
# 対応する機能（音声入力・VS Codeで開く・メッセージ取込）は、公開版では動かなくてよい
# ＝存在しないパスでも壊れない設計に各呼び出し元がなっている前提。
_OPTIONAL_KEYS = {"code_cli", "stt_venv_python", "stt_script", "message_base"}


def _load_overrides():
    try:
        return json.loads(_CONFIG_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


_overrides = _load_overrides()


def get_path(key):
    """キーに対応する Path を返す（shuki_paths.json の値 > 既定値の順）。
    optional キーで json 側が明示的に null を指定した場合は None を返す（機能を無効化する合図）。"""
    if key == "vault" and os.environ.get("SHUKI_VAULT"):
        root = Path(os.environ["SHUKI_VAULT"]).expanduser()
        if not root.is_absolute():
            raise ValueError("SHUKI_VAULT must be an absolute path")
        return root
    if key in _overrides:
        raw = _overrides[key]
        if raw is None and key in _OPTIONAL_KEYS:
            return None
        if raw:
            return Path(raw)
    return Path(_DEFAULTS[key])


def get_value(key, default=None):
    """Scalar, non-path settings (notification topic, remote base URL, ...).
    Exists so secrets never sit in code that gets published: if shuki_paths.json
    doesn't define it, the caller gets `default` and the feature stays off."""
    val = _overrides.get(key)
    return val if isinstance(val, str) and val else default


def get_names_list(key):
    """パス以外の個人固有オーバーライド（呼称のゆらぎリスト等）。shuki_paths.json に無ければ None。
    既定値は持たない＝公開版のコードには実名を書かない（呼び出し側が空リスト時のフォールバックを持つ）。"""
    val = _overrides.get(key)
    return val if isinstance(val, list) else None


def _test_data_dir():
    """A throwaway data root for test runs that did not choose one.

    After the 2026-10-07 cutover the activation marker outranks the legacy paths
    that tests patch, so an unconfigured test reached the live databases. Under a
    test runner the default root is a temporary directory instead, shared with
    child processes through ``SHUKI_TEST_DATA_DIR``. Normal runs are unaffected.
    """
    inherited = os.environ.get("SHUKI_TEST_DATA_DIR")
    if inherited:
        return inherited
    main = sys.modules.get("__main__")
    spec = getattr(main, "__spec__", None)
    running_tests = ("pytest" in sys.modules
                     or (spec is not None and spec.name == "unittest.__main__")
                     or Path(sys.argv[0] if sys.argv else "").name.startswith("test_"))
    if not running_tests:
        return None
    os.environ["SHUKI_TEST_DATA_DIR"] = tempfile.mkdtemp(prefix="shuki-test-data-")
    return os.environ["SHUKI_TEST_DATA_DIR"]


def data_dir(owner=None):
    """Resolve an owned runtime-data directory outside the system code tree.

    The optional absolute ``data_dir`` setting overrides the default sibling
    ``shuki-data`` directory. Resolving a path never creates or migrates data;
    callers explicitly create their directories when they begin writing.
    """
    raw = os.environ.get("SHUKI_DATA_DIR") or _overrides.get("data_dir")
    if raw is None:
        raw = _test_data_dir()
    if raw is not None and (not isinstance(raw, str) or not raw.strip()):
        raise ValueError("data_dir must be an absolute path or null")
    root = Path(raw).expanduser() if raw else _HERE.parent.parent / "shuki-data"
    if not root.is_absolute():
        raise ValueError("data_dir must be an absolute path")
    root = root.resolve()
    if root.is_relative_to(_HERE.parent.resolve()):
        raise ValueError("data_dir must be outside the system code tree")
    if owner is None:
        return root
    if not isinstance(owner, str) or not re.fullmatch(r"[a-z][a-z0-9_-]*", owner):
        raise ValueError("data owner must be a lowercase identifier")
    owned = (root / owner).resolve()
    if not owned.is_relative_to(root):
        raise ValueError("data owner directory escapes data_dir")
    return owned


STORAGE_ACTIVATION = ".storage-activation.json"


def runtime_target(key, root=None):
    """Validate a relative store key and resolve it below the external root."""
    if not isinstance(key, str) or not re.fullmatch(
            r"[a-z][a-z0-9_-]*(?:/[A-Za-z0-9_.-]+)*", key):
        raise ValueError("invalid runtime store key")
    if any(part in {".", ".."} for part in key.split("/")):
        raise ValueError("runtime store key cannot traverse directories")
    root = Path(root).resolve() if root is not None else data_dir()
    target = (root / key).resolve()
    if not target.is_relative_to(root):
        raise ValueError("runtime store escapes data_dir")
    return target


def storage_activation(root=None):
    """Read the activation marker strictly; corrupt state must never fall back."""
    root = Path(root).resolve() if root is not None else data_dir()
    marker = root / STORAGE_ACTIVATION
    if marker.is_symlink() or not marker.resolve().is_relative_to(root):
        raise ValueError("activation marker escapes data_dir")
    try:
        state = json.loads(marker.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {"version": 1, "stores": {}}
    if (not isinstance(state, dict) or type(state.get("version")) is not int
            or state.get("version") != 1 or not isinstance(
            state.get("stores"), dict)):
        raise ValueError("invalid runtime storage activation marker")
    for key, entry in state["stores"].items():
        runtime_target(key, root)
        if (not isinstance(entry, dict)
                or entry.get("kind") not in {"sqlite", "file", "directory"}
                or type(entry.get("existed")) is not bool
                or not isinstance(entry.get("source"), str)
                or not Path(entry["source"]).is_absolute()
                or not isinstance(entry.get("run"), str)
                or not re.fullmatch(r"[0-9a-f]{32}", entry["run"])
                or (entry["kind"] == "sqlite" and not entry["existed"])):
            raise ValueError("invalid runtime storage activation entry")
    return state


def runtime_path(key, legacy):
    """Use the legacy path until the guarded migration explicitly activates it.

    Missing previously populated targets, changed source mappings and malformed
    markers raise instead of creating an empty replacement or reading stale data.
    No files are created by this resolver.
    """
    target = runtime_target(key)
    entry = storage_activation()["stores"].get(key)
    if entry is None:
        return Path(legacy)
    if Path(entry["source"]).resolve() != Path(legacy).resolve():
        raise ValueError("activation source does not match the requested store")
    expected = target.is_dir() if entry["kind"] == "directory" else target.is_file()
    if not expected and (entry["existed"] or target.exists()):
        raise FileNotFoundError("activated runtime store is missing or has the wrong kind")
    return target


# ── 資格情報の置き場（2026-09-28 新設）────────────────────────────
# コードのディレクトリは **公開リポジトリの作業ツリー**になったので、OAuthトークン・APIキーを
# そこに置かない。.gitignore は「追跡しない」だけで、ファイルは公開リポジトリの中に存在して
# しまう＝`git add -A` の事故1回で public に出る（取り消せない）。物理的に外へ出すのが唯一の
# 確実な対策。既定は「コードの親ディレクトリの shuki-secrets/」で、shuki_paths.json の
# "secrets_dir" で変更できる。
_DEFAULT_SECRETS_DIR = _SECRETS_DIR


def secrets_dir():
    raw = _overrides.get("secrets_dir")
    return Path(raw) if isinstance(raw, str) and raw else _DEFAULT_SECRETS_DIR



def bootstrap_path(key, legacy):
    """Use external storage for a fresh install; keep populated legacy stores.

    Activation always takes precedence and retains runtime_path's strict checks.
    This does not copy, delete or activate existing data. An unactivated target
    may be retained recovery material after rollback; the existing legacy store
    remains authoritative until an explicit activation marker selects the target.
    """
    legacy = Path(legacy)
    resolved = runtime_path(key, legacy)
    if resolved != legacy:
        return resolved
    target = runtime_target(key)
    if legacy.exists():
        return legacy
    return target

def secret_file(name):
    """資格情報ファイルの場所。secrets_dir に無く、旧位置（このスクリプトの隣）に実在する
    場合はそちらを返す＝移行前でも壊れない。新規作成は常に secrets_dir 側に作られる。"""
    new = secrets_dir() / name
    if new.exists():
        return new
    legacy = Path(__file__).resolve().parent / name
    if legacy.exists():
        return legacy
    return new


VAULT = get_path("vault")
RADIO_DIR = get_path("radio_dir")
MESSAGE_BASE = get_path("message_base")
CODE_CLI = get_path("code_cli")
STT_VENV_PYTHON = get_path("stt_venv_python")
STT_SCRIPT = get_path("stt_script")


# ── Code-tree runtime stores (Phase A, 2026-10-07) ─────────────────────────
# One table for every store that used to sit beside the code. Writers resolve
# through code_store(); runtime_data_migrate.py builds its file/directory
# relocations from the same table, so a key and its legacy path cannot drift.
#   file / directory : state worth keeping; relocated with digest parity
#   cache            : rebuilt in the new location, never migrated
#   scratch          : logs and run scratch; new writes go to the target and the
#                      existing files are archived unchanged
# Each value is (kind, legacy path relative to this directory, names left behind).
_JOURNAL_DB = ("journal_growth.sqlite3", "journal_growth.sqlite3-wal",
               "journal_growth.sqlite3-shm", "journal_growth.sqlite3-journal")
CODE_STORES = {
    "achievements/achievements_state.json": ("file", "achievements_state.json", ()),
    "achievements/achievements_summary.json": ("file", "achievements_summary.json", ()),
    "achievements/data": ("directory", "achievements/data", ()),
    "achievements/art": ("directory", "achievements/art", ()),
    "board/board_quests.json": ("file", "board_quests.json", ()),
    "core/dashboard_state.json": ("file", "dashboard_state.json", ()),
    "core/dashboard_history.json": ("file", "dashboard_history.json", ()),
    "core/dashboard_settings.json": ("file", "dashboard_settings.json", ()),
    "core/gcal_pushed_tasks.json": ("file", "gcal_pushed_tasks.json", ()),
    "core/calendar_suggest_dismissed.json": ("file", "calendar_suggest_dismissed.json", ()),
    "core/review_state.json": ("file", "review_state.json", ()),
    "core/mcp-health.json": ("file", "runner_state/mcp-health.json", ()),
    "core/dashboard_uploads": ("directory", "dashboard_uploads", ()),
    "operations/dashboard_rec_state.json": ("file", "dashboard_rec_state.json", ()),
    "operations/codex_maintenance_state.json": ("file", "codex_maintenance_state.json", ()),
    "visualize/dashboard_viz_runs.json": ("file", "dashboard_viz_runs.json", ()),
    "visualize/viz_scout_state.json": ("file", "viz_scout_state.json", ()),
    "visualize/motivation_map_summary.json": ("file", "motivation_map_summary.json", ()),
    "game/data": ("directory", "concept_game/data", _JOURNAL_DB),
    "game/art": ("directory", "concept_game/art", (".thumbs",)),
    "habit/data": ("directory", "habit_funnel/data", ()),
    "finance/data": ("directory", "finance_game/data", ()),
    "intake/processed_takeouts.json": ("file", "processed_takeouts.json", ()),
    "intake/takeout_report_state.json": ("file", "takeout_report_state.json", ()),
    "intake/fb_export_state.json": ("file", ".fb_export_state.json", ()),
    "intake/prompt_intake_state.json": ("file", "prompt_intake_state.json", ()),
    "intake/place_cache.json": ("file", "place_cache.json", ()),
    "intake/place_stats.json": ("file", "place_stats.json", ()),
    "runner/state": ("directory", "runner_state", ("mcp-health.json", "__pycache__")),
    "core/vault_index_cache.json": ("cache", "vault_index_cache.json", ()),
    "cache/vault_search_index.pkl": ("cache", "vault_search_index.pkl", ()),
    "cache/vault_index_cache_bench.json": ("scratch", "vault_index_cache_bench.json", ()),
    "cache/vault_search_index_bench.pkl": ("scratch", "vault_search_index_bench.pkl", ()),
    "cache/openrouter_models.json": ("cache", "openrouter/models_cache.json", ()),
    "operations/model_registry.before_update.json": ("scratch", "model_registry.before_update.json", ()),
    "runner/debug": ("scratch", "runner_debug", ()),
    "intake/temp_takeout": ("scratch", "temp_takeout", ()),
    "intake/chrome_history_tmp": ("scratch", "temp_History", ()),
    "trading/backtest_data": ("scratch", "backtest_data", ()),
    "logs/muse_proxy": ("scratch", "muse_proxy_logs", ()),
    "logs/dashboard_server_heartbeat.log": ("scratch", "dashboard_server_heartbeat.log", ()),
    "logs/nightly_backup.log": ("scratch", "nightly_backup.log", ()),
    "logs/process_takeout.log": ("scratch", "process_takeout.log", ()),
    "logs/resolve_places.log": ("scratch", "resolve_places.log", ()),
    "logs/sync_google_takeout.log": ("scratch", "sync_google_takeout.log", ()),
    "logs/sync_weekly_history.log": ("scratch", "sync_weekly_history.log", ()),
    "logs/server_start.log": ("scratch", "server_start.log", ()),
    "logs/voicevox_hook.log": ("scratch", "voicevox_hook.log", ()),
}
# Web apps whose data/ is a directory store while web/ stays code.
_SEEDED_APPS = {"concept_game": "game/data", "achievements": "achievements/data",
                "habit_funnel": "habit/data", "finance_game": "finance/data"}


def code_store_legacy(key):
    """The pre-migration location of a code-tree store (always beside the code)."""
    return _HERE / CODE_STORES[key][1]


def code_store(key):
    """Resolve a former code-tree store: activated target, kept legacy, or fresh target."""
    return bootstrap_path(key, code_store_legacy(key))


# ── Machine zone (Phase B, 2026-10-07) ───────────────────────────────────
# `<vault>/99_System` moves to `<data>/system` as one directory store. Until the
# migration activates it, the vault folder stays authoritative. The Drive copies of
# runtime data (snapshots, mirrors) live outside the vault in `backup_dir()`.
SYSTEM_KEY = "system"


def system_legacy():
    return VAULT / "99_System"


def system_dir():
    """The machine-zone folder: `<data>/system` once activated, else `<vault>/99_System`."""
    return runtime_path(SYSTEM_KEY, system_legacy())


def system_dir_for(vault):
    """`system_dir()` for the configured vault; `<vault>/99_System` for any other (tests)."""
    vault = Path(vault)
    try:
        same = vault.resolve() == VAULT.resolve()
    except OSError:
        same = False
    return system_dir() if same else vault / "99_System"


# Reports people read stay in the vault (Ren, 2026-10-07, option A): only machine data
# leaves with 99_System. Vault-relative, so prompts and links can name them directly.
REPORTS_REL = "07_Logs/レポート"
REPORT_FOLDERS = {"qa": "QA", "monitoring": "運用", "audition": "モデル評価", "quiz": "クイズ"}


def reports_dir(kind, vault=None):
    """`<vault>/07_Logs/レポート/<folder>` for qa, monitoring, audition or quiz."""
    return Path(vault or VAULT) / REPORTS_REL / REPORT_FOLDERS[kind]


def report_rel(kind):
    return f"{REPORTS_REL}/{REPORT_FOLDERS[kind]}"


def vault_rel(path, vault=None):
    """Vault-relative POSIX path; machine-zone files keep their old `99_System/...` name."""
    vault = Path(vault or VAULT)
    path = Path(path)
    resolved = path.resolve()
    for system in (system_dir_for(vault), system_dir()):
        if resolved.is_relative_to(Path(system).resolve()):
            return "99_System/" + resolved.relative_to(Path(system).resolve()).as_posix()
    return resolved.relative_to(vault.resolve()).as_posix()


def vault_path(rel, vault=None):
    """Inverse of vault_rel(): `99_System/...` resolves into the machine zone."""
    vault = Path(vault or VAULT)
    rel = str(rel).replace("\\", "/")
    if rel == "99_System" or rel.startswith("99_System/"):
        return system_dir_for(vault) / rel[len("99_System/"):]
    return vault / rel


def within_vault(path, vault=None):
    """True if `path` lies in the vault or in its machine zone."""
    vault = Path(vault or VAULT)
    resolved = Path(path).resolve()
    return any(resolved.is_relative_to(Path(root).resolve()) for root in (vault, system_dir_for(vault)))


def backup_dir():
    """Drive folder for verified copies of runtime data; outside the vault (Ren, 2026-10-07)."""
    raw = _overrides.get("backup_dir")
    if isinstance(raw, str) and raw:
        return Path(raw)
    return VAULT.parent / "SHUKI-backup"


def seed_missing_data_files(root=None):
    """`<app>/data/<name>.example.json` があって `<name>.json` が無ければコピーして作る。

    2026-09-28 新設。コードのディレクトリが公開リポジトリの作業ツリーになったので、
    Webアプリの実データ（図鑑のカード・デッキ・家計の目標額等）は**追跡しない**。
    公開されるのは `.example.json` の方だけ。clone した直後の環境ではこの関数が
    実データを最小形で作るので、読み手側のコードは今まで通り「ファイルはある」前提で書ける。
    既存ファイルには一切触れない（上書きしない）。
    2026-10-07: 実データの置き場は code_store() が決める（`root` を明示した時は従来どおり雛形の隣）。
    """
    if root is not None:
        return _seed_into(Path(root).glob("*/data/*.example.json"), lambda ex: ex.parent)
    made = []
    for app, key in _SEEDED_APPS.items():
        folder = code_store(key)
        made += _seed_into((_HERE / app / "data").glob("*.example.json"), lambda ex, folder=folder: folder)
    return made


def _seed_into(examples, folder_for):
    import shutil
    made = []
    for ex in examples:
        folder = folder_for(ex)
        real = folder / ex.name.replace(".example.json", ".json")
        if not real.exists():
            folder.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ex, real)
            made.append(real)
    return made


if __name__ == "__main__":
    # `shuki_paths.py store <key>` lets PowerShell launchers use the same resolver.
    if len(sys.argv) == 3 and sys.argv[1] == "store" and sys.argv[2] in CODE_STORES:
        print(code_store(sys.argv[2]))
    else:
        raise SystemExit("usage: shuki_paths.py store <key>")
