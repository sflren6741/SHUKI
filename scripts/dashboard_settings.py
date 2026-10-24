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
import os
import re
import tempfile
import threading
from pathlib import Path

import model_registry

import shuki_paths

SETTINGS_FILE = shuki_paths.code_store("core/dashboard_settings.json")
_SETTINGS_WRITE_LOCK = threading.Lock()

DEFAULT_NAME = "SHUKI"
DEFAULT_MASCOT_COLOR = "#d6336c"
DEFAULT_GRADIENT_SECONDARY = "#6550ae"
COLOR_THEMES = ("soft-light", "soft-dark", "gradient")
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
        "bg": "#f0f4f8", "fg": "#1a1a1a", "muted": "#495568",
        "accent": "#004f80", "card": "#ffffff", "line": "#8190a2",
        "red": "#a63c00", "teal": "#005a8d", "blue": "#62449b",
    }),
    "colorblind-dark": ("Color-blind friendly · Dark", {
        "bg": "#101820", "fg": "#f3f6fa", "muted": "#b4c2d1",
        "accent": "#80caff", "card": "#1a2633", "line": "#7d91a6",
        "red": "#ffb066", "teal": "#80caff", "blue": "#d4b6ff",
    }),
    "soft-light": ("Soft Light", {
        "bg": "#f5f4fa", "fg": "#292637", "muted": "#5f596b",
        "accent": "#6550ae", "card": "#ffffff", "line": "#e1deed",
        "red": "#b42318", "teal": "#146c43", "blue": "#0056b3",
    }),
    "soft-dark": ("Soft Dark", {
        "bg": "#101520", "fg": "#edf0f7", "muted": "#adb6c7",
        "accent": "#92b6ff", "card": "#1a2231", "line": "#303d55",
        "red": "#e2727a", "teal": "#4fd1c5", "blue": "#92b6ff",
    }),
    "gradient": ("Gradient", {
        "bg": "#faf1ee", "fg": "#292637", "muted": "#5f596b",
        "accent": "#a33a69", "card": "#ffffff", "line": "#ead7e0",
        "red": "#b42318", "teal": "#146c43", "blue": "#0056b3",
    }),
}
DEFAULT_THEME = "cool-dark"

# One picker maps presets to the existing stored theme/style fields.
# Only Matrix retains a separate style internally; legacy palettes stay available.
THEME_PRESETS = {
    "soft": ("Soft", "soft-light", "standard"),
    "soft-light": ("Soft Light", "soft-light", "standard"),
    "soft-dark": ("Soft Dark", "soft-dark", "standard"),
    "gradient": ("Gradient", "gradient", "standard"),
    "basic": ("Basic", "light", "standard"),
    "milky": ("Milky", "milky", "standard"),
    "light": ("Light", "light", "standard"),
    "cool-dark": ("Cool Dark", "cool-dark", "standard"),
    "colorblind": ("Color-blind friendly", "colorblind", "standard"),
    "colorblind-dark": ("Color-blind friendly · Dark", "colorblind-dark", "standard"),
    "matrix": ("Matrix", "cool-dark", "matrix"),
    "warm-dark": ("Warm Dark", "warm-dark", "standard"),
    "mono-dark": ("Monochrome", "mono-dark", "standard"),
    "forest": ("Forest", "forest", "standard"),
}
# Older palettes remain loadable and can be recalled from favorites.
PRIMARY_THEME_PRESETS = ("soft", "gradient", "basic", "colorblind", "matrix")
THEME_FAMILIES = {
    "soft": {"light": "soft-light", "dark": "soft-dark"},
    "gradient": {"light": "gradient", "dark": "gradient"},
    "basic": {"light": "light", "dark": "cool-dark"},
    "colorblind": {"light": "colorblind", "dark": "colorblind-dark"},
}


def theme_family(theme, style="standard"):
    if style in ("matrix", "matrix-hc"):
        return "matrix"
    return next((key for key, modes in THEME_FAMILIES.items() if theme in modes.values()), theme)


def appearance_mode(settings):
    theme = settings.get("theme", DEFAULT_THEME)
    if theme == "gradient":
        return settings.get("gradient_mode", "light")
    return "light" if theme in ("light", "soft-light", "colorblind", "milky") else "dark"


MAX_THEME_FAVORITES = 24

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
NAV_KEY_RE = re.compile(r"[a-z][a-z0-9_-]{0,31}")
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
        "gradient_secondary": DEFAULT_GRADIENT_SECONDARY,
        "gradient_mode": "light",
        "theme_favorites": [],
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
    return {key: defaults[key] for key in ("theme", "style", "accent", "gradient_secondary",
                                         "gradient_mode", "sections", "order", "nav")}


def sanitize_theme_favorites(raw):
    """Keep bounded, appearance-only snapshots; never accept unrelated settings."""
    favorites = []
    seen = set()
    if not isinstance(raw, list):
        return favorites
    for item in raw[:MAX_THEME_FAVORITES]:
        if not isinstance(item, dict):
            continue
        theme, style = item.get("theme"), item.get("style", DEFAULT_STYLE)
        if not isinstance(theme, str) or theme not in THEMES:
            continue
        if not isinstance(style, str) or style not in STYLES:
            continue
        accent = item.get("accent", "")
        secondary = item.get("gradient_secondary", DEFAULT_GRADIENT_SECONDARY)
        if not isinstance(accent, str) or (accent and not HEX_RE.fullmatch(accent)):
            continue
        if not isinstance(secondary, str) or not HEX_RE.fullmatch(secondary):
            continue
        favorite = dict(theme=theme, style=style, accent=accent.lower(),
                        gradient_secondary=secondary.lower(),
                        gradient_mode="dark" if item.get("gradient_mode") == "dark" else "light")
        signature = tuple(favorite.values())
        if signature in seen:
            continue
        seen.add(signature)
        name = item.get("name", "")
        favorite["name"] = name.strip()[:60] if isinstance(name, str) and name.strip() else THEME_PRESETS["matrix" if style != "standard" else theme][0]
        favorites.append(favorite)
    return favorites


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
    secondary = str(raw.get("gradient_secondary", "")).strip()
    d["gradient_secondary"] = secondary.lower() if HEX_RE.fullmatch(secondary) else DEFAULT_GRADIENT_SECONDARY
    d["gradient_mode"] = "dark" if raw.get("gradient_mode") == "dark" else "light"
    if "theme_favorites" in raw:
        d["theme_favorites"] = sanitize_theme_favorites(raw["theme_favorites"])
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
        # 2026-10-11: ページ単位の表示切替。プラグインがページを足すため、キーは固定一覧でなく形式で検証する。
        d["nav"].update({k: bool(v) for k, v in navset.items()
                         if k not in d["nav"] and isinstance(k, str) and NAV_KEY_RE.fullmatch(k)})
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
    # Every menu shown counts as standard, whichever per-page keys are stored.
    is_standard = all(all(d[key].values()) if key == "nav" else d[key] == value
                      for key, value in standard_presentation().items())
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
    with _SETTINGS_WRITE_LOCK:
        return _save_settings(raw)


def _save_settings(raw):
    current = load_settings()
    raw_in = raw if isinstance(raw, dict) else {}
    if isinstance(raw, dict) and raw.get("reset"):
        raw = {"plugins": current["plugins"]}
    elif isinstance(raw, dict):
        # Autosave sends only edited fields; retain unrelated preferences and
        # changes made by another Settings tab or the conversation effort picker.
        raw = {**current, **raw}
        if isinstance(raw_in.get("model_effort"), dict):
            raw["model_effort"] = {**current["model_effort"], **raw_in["model_effort"]}
        if raw.get("presentation_mode") == "standard" and "sections" not in raw_in:
            # Standard restores the home layout the page can no longer edit.
            raw.update({k: standard_presentation()[k] for k in ("sections", "order")})
    d = sanitize(raw)
    SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=SETTINGS_FILE.parent,
                                         prefix=SETTINGS_FILE.name + ".", suffix=".tmp", delete=False) as handle:
            temporary = Path(handle.name)
            json.dump(d, handle, ensure_ascii=False, indent=1)
        os.replace(temporary, SETTINGS_FILE)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return d


def mix_color(color, surface, amount):
    """Blend a chosen color into an opaque surface (amount is the color's share)."""
    return "#" + "".join(f"{round(int(color[i:i+2], 16) * amount + int(surface[i:i+2], 16) * (1-amount)):02x}"
                         for i in (1, 3, 5))


def _contrast(a, b):
    def luminance(color):
        channels = [int(color[i:i+2], 16) / 255 for i in (1, 3, 5)]
        return sum((v / 12.92 if v <= .04045 else ((v + .055) / 1.055) ** 2.4) * weight
                   for v, weight in zip(channels, (.2126, .7152, .0722)))
    high, low = sorted((luminance(a), luminance(b)), reverse=True)
    return (high + .05) / (low + .05)


def color_theme_surfaces(settings, palette=None):
    """Opaque gradient endpoints; a second hue is decoration, never a second action color."""
    pal = palette if palette is not None else effective_palette(settings)
    seed = settings.get("accent", "")
    if not HEX_RE.fullmatch(str(seed)):
        seed = THEMES[settings["theme"]][1]["accent"]
    secondary = settings.get("gradient_secondary", DEFAULT_GRADIENT_SECONDARY)
    if not HEX_RE.fullmatch(str(secondary)):
        secondary = DEFAULT_GRADIENT_SECONDARY
    gradient = settings.get("theme") == "gradient"
    return {
        "theme-start": mix_color(seed, pal["card"], .18),
        "theme-end": mix_color(secondary if gradient else seed, pal["card"], .18 if gradient else .04),
    }


def effective_palette(settings):
    """テーマ palette に accent 上書きを適用した 9 キーの dict を返す。"""
    pal = dict(THEMES.get(settings.get("theme"), THEMES[DEFAULT_THEME])[1])
    accent = settings.get("accent", "")
    if accent and HEX_RE.match(accent):
        pal["accent"] = accent
    if settings.get("theme") in ("colorblind", "colorblind-dark"):
        # User accents remain customizable, but readable; status hues stay independent.
        dark = settings["theme"] == "colorblind-dark"
        for step in range(101):
            candidate = mix_color(pal["accent"], "#ffffff" if dark else "#000000", 1 - step / 100)
            if min(_contrast(candidate, pal[key]) for key in ("bg", "card")) >= 4.6:
                pal["accent"] = candidate
                break
    if settings.get("theme") in COLOR_THEMES:
        seed = pal["accent"]
        dark = settings["theme"] == "soft-dark" or (
            settings["theme"] == "gradient" and settings.get("gradient_mode") == "dark")
        pal.update(bg=mix_color(seed, "#0e1118" if dark else "#ffffff", .06),
                   card=mix_color(seed, "#1a202b", .06) if dark else "#ffffff",
                   line=mix_color(seed, "#343c4a" if dark else "#ffffff", .22),
                   fg="#edf0f7" if dark else "#292637", muted="#adb6c7" if dark else "#5f596b")
        if dark:
            pal.update(red="#e2727a", teal="#4fd1c5", blue="#92b6ff")
        surfaces = [pal["bg"], pal["card"], *color_theme_surfaces(settings, pal).values()]
        # The 0.1 margin covers RGB rounding between gradient endpoints.
        # Surface hues stay chosen; ink shades adapt without changing their semantic role.
        for key in ("fg", "muted", "accent", "red", "teal", "blue"):
            for step in range(101):
                candidate = mix_color(pal[key], "#ffffff" if dark else "#000000", 1 - step / 100)
                if min(_contrast(candidate, surface) for surface in surfaces) >= 4.6:
                    pal[key] = candidate
                    break
    return pal


def dashboard_name(settings):
    return settings.get("name") or DEFAULT_NAME
