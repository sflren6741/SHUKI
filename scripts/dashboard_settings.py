#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
dashboard_settings.py — ダッシュボード（SHUKI）の表示設定（名前・配色テーマ・セクション表示/並び順）

GET/POST /settings（dashboard_server.py）から読み書きする。設定の実体は vault 外の
dashboard_settings.json（このスクリプトと同じディレクトリ）に持つ＝vault 本体には一切書かない
（dashboard_state.json / review_state.json と同じ流儀）。

第1段階: ホーム（/）にのみ配色テーマ・セクション設定が効く。管制室/家計/図鑑など他ページは
各ページの PALETTE のまま（テーマの全ページ横展開は将来の課題）。
"""
import json
import re
from pathlib import Path

import model_registry

import shuki_paths

SETTINGS_FILE = shuki_paths.code_store("core/dashboard_settings.json")

DEFAULT_NAME = "SHUKI"
DEFAULT_MASCOT_COLOR = "#d6336c"
HEX_RE = re.compile(r"^#[0-9a-fA-F]{6}$")

# 配色テーマ（key -> (表示名, palette 9キー)）。
# 2026-08-03 デザイン刷新：黒×マスタード黄色が「モダンさに欠ける」というユーザーのフィードバックを受け、
# 5テーマ全体を彩度低め・単色アクセントの設計原則で再設計（🖥 UIデザイン原則（画面編）.md §1）。
# キー名（warm-dark/cool-dark等）は既存設定ファイルとの後方互換のため維持し、値だけ差し替えた。
# 新既定は cool-dark（青みを残したニュートラル寄り・旧warm-darkの黄色主体から交代）。
THEMES = {
    "warm-dark": ("暖色ダーク", {
        "bg": "#100d0a", "fg": "#ece5d6", "muted": "#9c9280",
        "accent": "#d68a4a", "card": "#1a150f", "line": "#2d251a",
        "red": "#d96a56", "teal": "#4c9e8c", "blue": "#7a9bc4",
    }),
    "cool-dark": ("クールダーク（既定）", {
        "bg": "#0b0d12", "fg": "#e6e9f0", "muted": "#8992a6",
        "accent": "#7c8cf5", "card": "#12151c", "line": "#232734",
        "red": "#e2727a", "teal": "#4fd1c5", "blue": "#5aa9e6",
    }),
    "mono-dark": ("モノトーン", {
        "bg": "#0c0c0e", "fg": "#f0f0ef", "muted": "#8c8c90",
        "accent": "#7c8cff", "card": "#17171a", "line": "#28282c",
        "red": "#e2685f", "teal": "#3fae95", "blue": "#7a8aa6",
    }),
    "forest": ("フォレスト", {
        "bg": "#0a0f0c", "fg": "#e3ece6", "muted": "#859186",
        "accent": "#4fae82", "card": "#10160f", "line": "#232d24",
        "red": "#d97862", "teal": "#3f9e88", "blue": "#7a9fc4",
    }),
    "light": ("ライト", {
        "bg": "#f5f5f5", "fg": "#1a1a1a", "muted": "#595959",
        "accent": "#0056b3", "card": "#ffffff", "line": "#d1d1d1",
        "red": "#b42318", "teal": "#146c43", "blue": "#0056b3",
    }),
    # 2026-09-04 追加。白ベース＋SHUKIブランドのマゼンタピンク系。既存 light（青灰 #e3e6ee）は
    # 地がグレー寄りで硬く、accent も青紫のため「やわらかい白」にはならなかった。
    # ニュートラル（bg/line/muted）は accent と同系のピンク味をわずかに残す側で決め切っている（§1）。
    # accent は SHUKI ブランド #D6336C を白地 AA（4.5:1）に届くまでわずかに暗くした値
    # （#D6336C は card 比 4.62 でぎりぎり、bg 比 4.32 で不足だったため #CB2E63 に補正・実測）。
    "milky": ("ミルキー（白ベース）", {
        "bg": "#fbf6f8", "fg": "#3b3036", "muted": "#77666e",
        "accent": "#cb2e63", "card": "#ffffff", "line": "#ebdce3",
        "red": "#c8434b", "teal": "#237f70", "blue": "#3f72c4",
    }),
    "colorblind": ("Color-blind friendly", {
        "bg": "#f5f5f5", "fg": "#1a1a1a", "muted": "#595959",
        "accent": "#0056b3", "card": "#ffffff", "line": "#d1d1d1",
        "red": "#a63c00", "teal": "#005a8d", "blue": "#62449b",
    }),
}
DEFAULT_THEME = "cool-dark"

# One picker maps presets to the existing stored theme/style fields.
# Only Matrix retains a separate style internally; legacy palettes stay available.
THEME_PRESETS = {
    "milky": ("Milky", "milky", "standard"),
    "light": ("Light", "light", "standard"),
    "cool-dark": ("Cool Dark", "cool-dark", "standard"),
    "colorblind": ("Color-blind friendly", "colorblind", "standard"),
    "matrix": ("Matrix", "cool-dark", "matrix"),
    "warm-dark": ("Warm Dark", "warm-dark", "standard"),
    "mono-dark": ("Monochrome", "mono-dark", "standard"),
    "forest": ("Forest", "forest", "standard"),
}
PRIMARY_THEME_PRESETS = ("milky", "light", "cool-dark", "colorblind")

STYLES = {
    "standard": "標準",
    "matrix": "Matrix",
    # Preserve an existing high-contrast Matrix setting without a second choice.
    "matrix-hc": "Matrix・くっきり表示（視認性重視）",
}
DEFAULT_STYLE = "standard"

# Decoration is retired; loading old settings disables it.
DECORS = {"off": "なし"}
DEFAULT_DECOR = "off"

# 表示言語（設定メニューから切替・2026-09-13新設）。辞書は i18n/<lang>.json
# （shuki_i18n.py がこの設定ファイルの更新を検知して都度読み直す＝サーバー再起動なしで即反映）。
# 追加の翻訳辞書を用意したら、ここにキーを足すだけで選択肢に出る。
LANGS = {"ja": "日本語", "en": "English"}
DEFAULT_LANG = "ja"

# 並べ替え可能な上段セクション（key -> 表示名）。順序はユーザーが変更できる。
ORDERABLE_SECTIONS = [
    ("focus", "フォーカス帯（今日はこれ！）"),
    # accounts（Claudeアカウントパネル）は 2026-10-08 にサイドバーへ移した（全ページ共通・常時表示）。
    ("achievements", "称号バンド"),
    ("pages", "各ページの更新（1行サマリ）"),
    # launcher（主要スキル＋モデル選択）は 2026-08-16 の対話ドック化でホーム上段から撤去。
    # ここに残すと order に補完され render_html の section_blocks で KeyError になる。
    ("skills", "その他のスキル"),
    ("history", "実行履歴"),
]
# 下段固定セクション（並べ替え対象外・表示 ON/OFF のみ。2カラム版面を維持するため位置は固定）。
BOTTOM_SECTIONS = [
    ("board", "タスクボード"),
    ("standup", "今日の状況"),
]
ORDERABLE_KEYS = [k for k, _ in ORDERABLE_SECTIONS]
ALL_SECTION_KEYS = ORDERABLE_KEYS + [k for k, _ in BOTTOM_SECTIONS]

# ナビ（上部メニュー・スマホ下部タブ）の表示/非表示カスタマイズ（論点2・2026-08-30実装）。
# 表示設定はトップレベルの利用目的ごとに持つ。子ページの旧キーも内部で保持し、
# 既存の dashboard_settings.json と保存済みの非表示設定を壊さない。
NAV_TOGGLE_ITEMS = [
    ("do", "やる（タスク・習慣・決裁）"),
    ("reflect", "振り返る（進捗・可視化・称号）"),
    ("library", "ライブラリ（ファイル・図鑑・クイズ・クロスワード）"),
    ("life", "生活（生活・家計・トレード）"),
]
_LEGACY_NAV_KEYS = (
    "journal", "board", "files", "progress", "habit", "cards",
    "visualize", "control", "game", "achievements",
)
NAV_TOGGLE_KEYS = [k for k, _ in NAV_TOGGLE_ITEMS] + list(_LEGACY_NAV_KEYS)
_NAV_GROUP_LEGACY_KEYS = {
    "do": ("board", "habit", "cards"),
    "reflect": ("progress", "visualize", "achievements"),
    "library": ("files", "game", "cards"),
    "life": ("control",),
}

# モデルごとの思考量。Claude は --effort、Codex は model_reasoning_effort に対応する。
# "medium" は従来の既定動作を維持するための初期値。
EFFORT_LEVELS = ("low", "medium", "high", "xhigh", "max")


def model_effort_models():
    """Return (stable settings key, label, live CLI target) for effort settings."""
    return model_registry.dashboard_effort_models()


def model_effort_defaults():
    """Return effort defaults keyed to the current model registry."""
    return model_registry.effort_defaults()


# Backward-compatible import-time snapshot. Runtime settings paths use the
# functions above so registry edits appear without restarting the dashboard.
MODEL_EFFORT_DEFAULTS = model_effort_defaults()


def _defaults():
    return {
        "name": DEFAULT_NAME,
        "theme": DEFAULT_THEME,
        "style": DEFAULT_STYLE,
        "presentation_mode": "standard",
        "decor": DEFAULT_DECOR,
        "lang": DEFAULT_LANG,
        "accent": "",  # "" = テーマ既定のアクセント色。#RRGGBB なら上書き
        "mascot_enabled": True,
        "mascot_color": DEFAULT_MASCOT_COLOR,
        "sections": {k: True for k in ALL_SECTION_KEYS},
        "order": list(ORDERABLE_KEYS),
        "nav": {k: True for k in NAV_TOGGLE_KEYS},  # ナビ項目の表示/非表示（論点2・2026-08-30）
        "sfx_enabled": True,   # 操作フィードバックSE（GET /sfx.js・2026-08-21）
        "bgm_enabled": True,   # /game（概念図鑑）専用BGM。既定ONだがブラウザの自動再生制限で
                                # 実際の再生は必ずページ内の最初のクリック等ジェスチャ後になる
        "model_effort": model_effort_defaults(),
        "plugins": {},  # {"<plugin id>": {"enabled": false}}; unlisted plugins are enabled
    }


def standard_presentation():
    """The Standard preset changes appearance/layout, keeping personal preferences."""
    defaults = _defaults()
    return {key: defaults[key] for key in ("theme", "style", "accent", "sections", "order", "nav")}


def sanitize(raw, base=None):
    """外部入力（保存済み JSON / POST ペイロード）を既定で補正した dict にする。"""
    d = base if base is not None else _defaults()
    if not isinstance(raw, dict):
        return d
    name = str(raw.get("name", "")).strip()
    if name:
        d["name"] = name[:40]
    if raw.get("theme") in THEMES:
        d["theme"] = raw["theme"]
    d["style"] = raw["style"] if raw.get("style") in STYLES else DEFAULT_STYLE
    d["decor"] = DEFAULT_DECOR
    if raw.get("lang") in LANGS:
        d["lang"] = raw["lang"]
    accent = str(raw.get("accent", "")).strip()
    d["accent"] = accent if HEX_RE.match(accent) else ""
    # mascot_wander (chat-panel roaming) was removed on 2026-10-09; a stored value is dropped here.
    if isinstance(raw.get("mascot_enabled"), bool):
        d["mascot_enabled"] = raw["mascot_enabled"]
    mascot_color = str(raw.get("mascot_color", "")).strip()
    if HEX_RE.fullmatch(mascot_color):
        d["mascot_color"] = mascot_color.lower()
    sec = raw.get("sections")
    if isinstance(sec, dict):
        d["sections"] = {k: bool(sec.get(k, True)) for k in ALL_SECTION_KEYS}
    order = raw.get("order")
    if isinstance(order, list):
        uniq = []
        for k in order:
            if k in ORDERABLE_KEYS and k not in uniq:
                uniq.append(k)
        # 欠けた key は末尾に補う（新セクション追加時の前方互換）
        uniq += [k for k in ORDERABLE_KEYS if k not in uniq]
        d["order"] = uniq
    navset = raw.get("nav")
    if isinstance(navset, dict):
        # 新形式のグループキーがなければ、旧形式の子キーから表示状態を復元する。
        # 旧形式では cards がライブラリ側にも属するため、両方へ反映する。
        d["nav"] = {}
        for key, _label in NAV_TOGGLE_ITEMS:
            legacy = _NAV_GROUP_LEGACY_KEYS[key]
            d["nav"][key] = bool(navset[key]) if key in navset else any(
                bool(navset.get(child, True)) for child in legacy
            )
        d["nav"].update({k: bool(navset.get(k, True)) for k in _LEGACY_NAV_KEYS})
    if "sfx_enabled" in raw:
        d["sfx_enabled"] = bool(raw.get("sfx_enabled"))
    if "bgm_enabled" in raw:
        d["bgm_enabled"] = bool(raw.get("bgm_enabled"))
    effort = raw.get("model_effort")
    if not isinstance(effort, dict):
        effort = d.get("model_effort", {})
    defaults = model_effort_defaults()
    d["model_effort"] = {
        model: (str(effort.get(model)) if str(effort.get(model)) in EFFORT_LEVELS else default)
        for model, default in defaults.items()
    }
    plugins = raw.get("plugins")
    if isinstance(plugins, dict):
        d["plugins"] = {k: {"enabled": bool(v.get("enabled", True))} for k, v in plugins.items()
                        if isinstance(k, str) and re.fullmatch(r"[a-z][a-z0-9_]{0,31}", k) and isinstance(v, dict)}
    # Older custom layouts remain custom; reading settings never resets them.
    is_standard = all(d[key] == value for key, value in standard_presentation().items())
    d["presentation_mode"] = "custom" if raw.get("presentation_mode") == "custom" or not is_standard else "standard"
    return d


def load_settings():
    """設定を読み、欠損・不正値を既定で補正した dict を返す（壊れた JSON でも既定で動く）。"""
    try:
        raw = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return _defaults()
    return sanitize(raw)


def save_settings(raw):
    """POST /settings のペイロードを検証・正規化して保存し、正規化後の dict を返す。"""
    if isinstance(raw, dict) and "plugins" not in raw:
        # The Settings page does not send plugin activation; keep what is saved.
        raw = {**raw, "plugins": load_settings()["plugins"]}
    d = sanitize(raw)
    SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    SETTINGS_FILE.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    return d


def effective_palette(settings):
    """テーマ palette に accent 上書きを適用した 9 キーの dict を返す。"""
    pal = dict(THEMES.get(settings.get("theme"), THEMES[DEFAULT_THEME])[1])
    accent = settings.get("accent", "")
    if accent and HEX_RE.match(accent):
        pal["accent"] = accent
    return pal


def dashboard_name(settings):
    return settings.get("name") or DEFAULT_NAME
