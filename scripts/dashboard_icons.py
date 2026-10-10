#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
dashboard_icons.py — 画面の意味的アイコン（ナビ・称号ランク）の単一情報源（SSOT）

絵文字はOS・フォントごとに描画が変わり配色トークン（var(--xxx)）にも乗らないため、
チープに見える主因になっていた（2026-08-03 ユーザーのフィードバック）。以後は画面の意味的アイコン
（ナビ・称号ランク・Area・期限状態等）を線アイコンSVGに統一する
（🖥 UIデザイン原則（画面編）.md §9）。

様式は「Minimal Line」：ストローク幅1.5、角丸小、線のみ（塗りつぶし・duotoneは使わない）。
1画面内でアイコンの様式を混在させないこと。

称号ランクの絵文字表現は、これまで achievements.py（RARITY辞書・svg_rank_bars内label/color）・
dashboard_server.py（RANK_ICONS）・achievements/web/app.js（RARITY_EMOJI）の3ファイル4箇所に
バラバラに定義されており、様式を変えても一部にしか反映されない不具合の温床だった。
サーバー画面（このモジュールの対象）はここを唯一の定義元とする。
achievements.py 側の RARITY 辞書は vault 本体（02_Home/🏆 アチーブメント.md・Obsidianで見る）
向けの絵文字表示なので対象外＝そちらは変更しない（vaultの絵文字運用とサーバーUIは別レイヤー）。
JS側（achievements/web/app.js）は別ランタイムのため定義を複製するが、コメントで
このファイルとの同期を明記し、色・形は必ずここに合わせる。
"""
import json

import shuki_profile

_STROKE = 'fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"'

# ── ナビゲーション10種（下部タブバー・上部ナビ共通。dashboard_ui.NAV_PAGES の key と対応） ──
NAV_PATHS = {
    "home":         '<path d="M3 11l9-7 9 7M5 10v10h14V10M10 20v-6h4v6"/>',
    "journal":      '<path d="M5 3.5h14v17H5z"/><path d="M8.5 8h7M8.5 12h7M8.5 16h4"/>',
    "review":       '<path d="M21 12h-5l-2 3h-4l-2-3H3"/>'
                    '<path d="M5.5 6.2L3 12v6a2 2 0 002 2h14a2 2 0 002-2v-6l-2.5-5.8A2 2 0 0016.6 5H7.4a2 2 0 00-1.9 1.2z"/>',
    "board":        '<rect x="4" y="4" width="16" height="16" rx="2"/><path d="M8 12l2.5 2.5L16 9"/>',
    "progress":     '<path d="M4 20V10M12 20V4M20 20v-7"/>',
    "english":      '<path d="M3 5h7a2 2 0 012 2v14a3 3 0 00-3-2H3zM21 5h-7a2 2 0 00-2 2v14a3 3 0 013-2h6z"/>',
    "activity":     '<rect x="3.3" y="3.3" width="4" height="4" rx="1"/><rect x="10" y="3.3" width="4" height="4" rx="1"/>'
                    '<rect x="16.7" y="3.3" width="4" height="4" rx="1"/><rect x="3.3" y="10" width="4" height="4" rx="1"/>'
                    '<rect x="10" y="10" width="4" height="4" rx="1"/><rect x="16.7" y="10" width="4" height="4" rx="1"/>'
                    '<rect x="3.3" y="16.7" width="4" height="4" rx="1"/><rect x="10" y="16.7" width="4" height="4" rx="1"/>',
    "habit":        '<path d="M17 2.5l4 4-4 4"/><path d="M3 11.5v-2a4 4 0 014-4h14"/>'
                    '<path d="M7 21.5l-4-4 4-4"/><path d="M21 12.5v2a4 4 0 01-4 4H3"/>',
    "trading":      '<path d="M3 17l6-6 4 4 8-8"/><path d="M17 7h4v4"/>',
    # 🧩クイズ（2026-08-24新設）。カード＋クエスチョンマークのモチーフ
    "quiz":         '<rect x="4" y="3" width="16" height="18" rx="2"/>'
                    '<path d="M9.2 8.6a2.8 2.8 0 115.2 1.4c-.5.9-1.4 1.1-1.4 2.4"/>'
                    '<circle cx="12" cy="15.6" r=".35" fill="currentColor" stroke="none"/>',
    # 🧩クロスワード（2026-09-07新設）。マス目グリッドのモチーフ（quizのカード形状と区別する）
    "crossword":    '<rect x="3" y="3" width="18" height="18" rx="1.5"/>'
                    '<path d="M3 9h18M3 15h18M9 3v18M15 3v18"/>'
                    '<rect x="9" y="9" width="6" height="6" fill="currentColor" stroke="none" opacity=".25"/>',
    # 🃏カード グループ（2026-08-28新設）。クイズ/クロスワード/決裁カードをまとめるナビの親項目。
    # 3枚重なったカードのモチーフ（quiz単体アイコンと視覚的に区別する）
    "cards":        '<rect x="3" y="7" width="14" height="14" rx="2"/>'
                    '<path d="M7 7V5a2 2 0 012-2h10a2 2 0 012 2v10a2 2 0 01-2 2h-2"/>',
    # ⚖️決裁カード（2026-08-28新設）。天秤のモチーフ（ui_icon_svgの"scale"と同形状）
    "decisions":    '<path d="M12 3v18M7 21h10M5 7h6M5 7L2.5 12.5a2.5 2.5 0 005 0L5 7zM19 7h-6M19 7l2.5 5.5a2.5 2.5 0 01-5 0L19 7z"/>',
    # ❓情報要求（旧 /gaps ページ用。現在は決裁カードの response_type に統合）。
    # ui_icon_svgの"question"と同形状
    "gaps":         '<circle cx="12" cy="12" r="9"/>'
                    '<path d="M9.2 9.2a2.8 2.8 0 115.2 1.4c-.5.9-1.4 1.1-1.4 2.4"/>'
                    '<circle cx="12" cy="16.8" r=".35" fill="currentColor" stroke="none"/>',
    # 📡データ管制室（2026-08-20新設）。円弧2本＋中心点＝レーダー画面のモチーフ
    "control":      '<circle cx="12" cy="12" r="1.6"/><path d="M8 8a5.7 5.7 0 018 0M5 5a10 10 0 0114 0"/>',
    "finance":      '<rect x="2.5" y="6" width="19" height="14" rx="2.5"/><path d="M2.5 10.5h19"/><circle cx="16.5" cy="14.5" r="1.1"/>',
    "game":         '<path d="M4 5v14a2 2 0 002 2h6V5a2 2 0 00-2-2H6a2 2 0 00-2 2z"/>'
                    '<path d="M20 5v14a2 2 0 01-2 2h-6V5a2 2 0 012-2h4a2 2 0 012 2z"/>',
    "achievements": '<circle cx="12" cy="8.3" r="4.3"/><path d="M9 12.2L7.3 21l4.7-2.8 4.7 2.8-1.7-8.8"/>',
    "visualize":    '<path d="M4 20V10M12 20V4M20 20v-13"/><path d="M2.5 20h19"/>',
    # UI_PATHS["folder"] と同形状（2026-08-18・/files ページ用。ナビは独立サイズ指定のため複製が要る）
    "files":        '<path d="M3 6.5a1.5 1.5 0 011.5-1.5H9l2 2h8.5A1.5 1.5 0 0121 8.5v9a1.5 1.5 0 01-1.5 1.5h-15A1.5 1.5 0 013 17.5v-11z"/>',
    "settings": '<circle cx="12" cy="12" r="3.2"/>'
                '<path d="M12 3v2.6M12 18.4V21M21 12h-2.6M5.6 12H3'
                'M18.1 5.9l-1.8 1.8M7.7 16.4l-1.8 1.8M18.1 18.1l-1.8-1.8M7.7 7.6L5.9 5.9"/>',
}


def nav_icon_svg(key, size=20):
    """ナビ・タブバー用アイコン。currentColor 継承なので呼び出し側の color で色が決まる。"""
    path = NAV_PATHS.get(key, NAV_PATHS["home"])
    return f'<svg viewBox="0 0 24 24" width="{size}" height="{size}" {_STROKE}>{path}</svg>'


# ── 称号ランク6種。achievements.py の RARITY と同じ並び・同じ色。形状は共通、色でランクを示す ──
RANK_COLOR = {
    "Bronze": "#cd7f32", "Silver": "#9ca3af", "Gold": "#eab308",
    "Platinum": "#06b6d4", "Legendary": "#f59e0b", "Hidden": "#a855f7",
}
_MEDAL_PATH = '<circle cx="12" cy="9" r="6"/><path d="M8.3 14.6L6.5 22l5.5-3.3 5.5 3.3-1.8-7.4"/>'


def _medal_svg(color, size):
    return (f'<svg viewBox="0 0 24 24" width="{size}" height="{size}" '
            f'fill="none" stroke="{color}" stroke-width="1.6" '
            f'stroke-linecap="round" stroke-linejoin="round">{_MEDAL_PATH}</svg>')


def rank_icon_svg(rank, size=16):
    """称号ランクバッジ。6ランクとも同じメダル形状、色だけレアリティ色で変える（様式統一）。"""
    return _medal_svg(RANK_COLOR.get(rank, "#8992a6"), size)


# ── 総合達成ランク5段階（dashboard_server.achievement_band_html の「ランク○○」表示用）。
# 「ランク　銀」がテキストだけで装飾がなくダサく見えていた実物（2026-08-03 ユーザーのフィードバックの発端）。
# RANK_COLOR と同系統の色でメダル形状を添える。
ACH_RANK_COLOR = {"白金": "#06b6d4", "金": "#eab308", "銀": "#9ca3af", "銅": "#cd7f32", "木": "#7d8471"}


def ach_rank_icon_svg(name, size=18):
    return _medal_svg(ACH_RANK_COLOR.get(name, "#8992a6"), size)


# ── Area用アイコン素材。形状は共通様式（Minimal Line）。
# **アイコンID（heart/people/…）で引く**（2026-09-27 変更）。以前はAreaの日本語名が直接キー
# だったため、Area名＝個人の人生設計がこのファイル（＝公開されるシステム側）に焼き付いていた。
# いまは「素材のカタログはシステム、どのAreaがどのIDを使うかは profile.json」に分かれている。
AREA_ICON_PATHS = {
    "heart": '<path d="M12 20.5s-7-4.2-9.3-8.6A5 5 0 0112 7a5 5 0 019.3 4.9C19 16.3 12 20.5 12 20.5z"/>',
    "people": '<circle cx="8" cy="8" r="3"/><path d="M2.5 20c0-3.3 2.5-5.5 5.5-5.5s5.5 2.2 5.5 5.5"/>'
              '<circle cx="17" cy="8" r="2.6"/><path d="M14.5 14.8c2.7.3 4.5 2.4 4.5 5.2"/>',
    "compass": '<circle cx="12" cy="12" r="9"/><path d="M15 9l-2 5-5 2 2-5z"/>',
    "briefcase": '<rect x="3" y="7.5" width="18" height="12" rx="2"/>'
                 '<path d="M8.5 7.5V6a2 2 0 012-2h3a2 2 0 012 2v1.5"/><path d="M3 13h18"/>',
    "globe": '<circle cx="12" cy="12" r="9"/><path d="M3 12h18"/>'
             '<path d="M12 3c2.5 2.7 2.5 15.3 0 18M12 3c-2.5 2.7-2.5 15.3 0 18"/>',
    "handball": '<circle cx="12" cy="8" r="3"/><path d="M6 21c1-5 3-7 6-7s5 2 6 7"/>',
    "pulse": '<path d="M3 12h4l2-6 3 12 2-9 2 3h5"/>',
    "gamepad": '<rect x="2.5" y="8" width="19" height="9.5" rx="4.5"/><path d="M7 11v3.5M5.2 12.7h3.5"/>'
               '<circle cx="15.5" cy="11.3" r=".9"/><circle cx="17.8" cy="13.6" r=".9"/>',
    "coin": '<circle cx="12" cy="12" r="9"/>'
            '<path d="M12 7.5v9M9.7 9.8c0-1.2.9-2 2.3-2s2.3.7 2.3 1.8-.9 1.6-2.3 1.9-2.3.7-2.3 1.9.9 1.9 2.3 1.9 2.3-.7 2.3-1.9"/>',
    "clock": '<circle cx="12" cy="12" r="9"/><path d="M12 7v5.5l3.5 2"/>',
    "cpu": '<rect x="7" y="7" width="10" height="10" rx="1.5"/><rect x="10.5" y="10.5" width="3" height="3"/>'
           '<path d="M10 7V4M14 7V4M10 20v-3M14 20v-3M7 10H4M7 14H4M20 10h-3M20 14h-3"/>',
    "box":'<path d="M3 8.5L12 4l9 4.5v7L12 20l-9-4.5z"/><path d="M3 8.5L12 13l9-4.5M12 13v7"/>',
}

# {Area名: SVGパス} … 画面側（dashboard_board.py の AREA_ICON_PATH）はこの形で json.dumps
# されるので、呼び出し側のコードは今まで通りAreaの名前で引ける。
AREA_PATHS = {
    name: AREA_ICON_PATHS.get(icon_id, AREA_ICON_PATHS["box"])
    for name, icon_id in shuki_profile.area_icon_map(include_fallback=True).items()
}


def area_icon_svg(area, color="currentColor", size=17):
    path = AREA_PATHS.get(area)
    if not path:
        return ""
    return (f'<svg viewBox="0 0 24 24" width="{size}" height="{size}" fill="none" stroke="{color}" '
            f'stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">{path}</svg>')


# ── 汎用UI部品（Phase3・2026-08-04）。ローディング・更新・チェック等、複数ファイルで
# 使い回される装飾絵文字の置き換え先。意味的アイコンと同じくSSOTとしてここに集約する。
UI_PATHS = {
    "copy": '<rect x="8" y="8" width="12" height="12" rx="2"/><path d="M16 8V5a2 2 0 00-2-2H5a2 2 0 00-2 2v9a2 2 0 002 2h3"/>',
    "loading":  '<circle cx="12" cy="12" r="8" stroke-dasharray="30 12"/>',
    "send":     '<path d="M3 11.5L21 3l-8 18-3-7.5z"/><path d="M10 13L21 3"/>',
    "refresh":  '<path d="M4 12a8 8 0 0114-5.3M20 12a8 8 0 01-14 5.3"/>'
                '<path d="M18 3v4h-4M6 21v-4h4"/>',
    "check":    '<path d="M4 12.5l5.5 5.5L20 7"/>',
    "cross":    '<path d="M6 6l12 12M18 6L6 18"/>',
    "warn":     '<path d="M12 3.5l9.5 16.5H2.5z"/><path d="M12 10v4.5"/><circle cx="12" cy="17.3" r=".2" fill="currentColor"/>',
    "trash":    '<path d="M4 7h16M9 7V5a2 2 0 012-2h2a2 2 0 012 2v2M6 7l1 13a2 2 0 002 2h6a2 2 0 002-2l1-13"/>',
    "search":   '<circle cx="10.5" cy="10.5" r="6.5"/><path d="M20 20l-4.8-4.8"/>',
    "comment":  '<path d="M4 5h16v11H8.5L4 20V5z"/>',
    "doc":      '<path d="M6 3h8l4 4v14H6z"/><path d="M14 3v4h4"/>',
    "celebrate": '<path d="M4 20l5-14 11 6-14 5z"/><path d="M13 5l1.5-2M18 8l2.5-1M15 11l2 2"/>',
    "pause":    '<path d="M8 5v14M16 5v14"/>',
    "fire":     '<path d="M12 3s5 4.5 5 9.5a5 5 0 01-10 0c0-1.4.6-2.4 1.3-3.4.3 1 .9 1.7 1.7 1.7-.3-3 1-5.3 2-6.8z"/>',
    "sparkle":  '<path d="M12 3v4M12 17v4M3 12h4M17 12h4M6 6l2.5 2.5M15.5 15.5L18 18M18 6l-2.5 2.5M8.5 15.5L6 18"/>',
    "attach":   '<path d="M8 13.5V7a4 4 0 018 0v9a2.5 2.5 0 01-5 0V8.5"/>',
    "mic":      '<rect x="9" y="3" width="6" height="11" rx="3"/><path d="M5 11a7 7 0 0014 0M12 18v3"/>',
    "speaker":  '<path d="M4 9v6h4l5 4V5L8 9z"/><path d="M17 9a4.5 4.5 0 010 6"/>',
    "brain":    '<circle cx="12" cy="12" r="8.5"/><path d="M12 4.5v15"/>'
                '<path d="M7.5 8c1.8 1 1.8 2.3 0 3.3s-1.8 2.3 0 3.3M16.5 8c-1.8 1-1.8 2.3 0 3.3s1.8 2.3 0 3.3"/>',
    "runway":   '<path d="M2 16l20-6M12 2l3 3-6 14-2-2 3-13-2-2z"/>',
    "doc-link": '<path d="M6 3h8l4 4v14H6z"/><path d="M14 3v4h4"/><path d="M9.5 13l2-2 3 3"/>',
    "pin":      '<path d="M12 2a5 5 0 015 5c0 3.5-5 8-5 8s-5-4.5-5-8a5 5 0 015-5z"/><circle cx="12" cy="7" r="1.6"/>',
    "target":   '<circle cx="12" cy="12" r="8.5"/><circle cx="12" cy="12" r="4.5"/><circle cx="12" cy="12" r=".6" fill="currentColor"/>',
    "play":     '<path d="M6 4.5l13 7.5-13 7.5z"/>',
    "pencil":   '<path d="M4 20l1-4.5L15.5 5 19 8.5 8.5 19 4 20z"/><path d="M13 7l3.5 3.5"/>',
    "calendar": '<rect x="3.5" y="5" width="17" height="15" rx="2"/><path d="M3.5 9.5h17M8 3v4M16 3v4"/>',
    "scale":    '<path d="M12 3v18M7 21h10M5 7h6M5 7L2.5 12.5a2.5 2.5 0 005 0L5 7zM19 7h-6M19 7l2.5 5.5a2.5 2.5 0 01-5 0L19 7z"/>',
    "toolbox":  '<rect x="2.5" y="9.5" width="19" height="11" rx="2"/><path d="M8 9.5V6a2 2 0 012-2h4a2 2 0 012 2v3.5"/>'
                '<path d="M2.5 14h19M10.5 14v2M13.5 14v2"/>',
    "clock":    '<circle cx="12" cy="12" r="9"/><path d="M12 7v5.3l4 2.3"/>',
    "hourglass": '<path d="M6 3h12M6 21h12"/><path d="M8 3c0 4 1.8 5.5 4 7.5-2.2 2-4 3.5-4 7.5M16 3c0 4-1.8 5.5-4 7.5 2.2 2 4 3.5 4 7.5"/>',
    "radio":    '<rect x="3.5" y="9" width="17" height="12" rx="2"/><circle cx="8.5" cy="15" r="2.2"/>'
                '<path d="M14 13h4M14 17h2.5"/><path d="M7 9l3-5.5M17 9l-3-5.5"/>',
    "sunrise":  '<path d="M4 18h16M6.5 18a5.5 5.5 0 0111 0"/><path d="M12 4.5v3.5M4.5 11l2 1.3M19.5 11l-2 1.3M2.5 18h2M19.5 18h2"/>',
    "stop":     '<rect x="6" y="6" width="12" height="12" rx="1.5"/>',
    "maximize": '<path d="M9 4H4v5M15 4h5v5M9 20H4v-5M15 20h5v-5"/>',
    # 最小化は最大化の反対方向を示す四隅記号ではなく、一般的なマイナス線で表す。
    # 対話パネルの最大化ボタンと見分けやすくし、意味を形だけで伝える（2026-09-13）。
    "minimize": '<path d="M5 12h14"/>',
    "shrink":   '<path d="M4 4l5 5M4 9h5V4M20 4l-5 5M15 4v5h5M4 20l5-5M4 15h5v5M20 20l-5-5M15 20v-5h5"/>',
    "letter":   '<rect x="3" y="5" width="18" height="14" rx="2"/><path d="M3.5 6.5L12 13l8.5-6.5"/>',
    "phone":    '<rect x="7" y="2.5" width="10" height="19" rx="2.2"/><path d="M11 18.3h2"/>',
    "salad":    '<path d="M4 12a8 8 0 0116 0z"/><path d="M2.5 12h19"/><path d="M12 12V6.5c1.8 0 3-1 3-2.5"/>',
    "map":      '<path d="M9 4L3.5 6v14L9 18l6 2 5.5-2V4L15 6 9 4z"/><path d="M9 4v14M15 6v14"/>',
    "microscope": '<path d="M9 20h9M11 20v-3.5a4.5 4.5 0 114.2-6"/><path d="M8 12.5h4M6.5 16.5h6L11 12.5"/>'
                  '<path d="M14.5 4.5l3 3"/>',
    "folder":   '<path d="M3 6.5a1.5 1.5 0 011.5-1.5H9l2 2h8.5A1.5 1.5 0 0121 8.5v9a1.5 1.5 0 01-1.5 1.5h-15A1.5 1.5 0 013 17.5v-11z"/>',
    "wrench":   '<path d="M14.5 6.5a4 4 0 00-5.4 4.9L3 17.5 6.5 21l6-6.1a4 4 0 004.9-5.4l-2.9 2.9-2.5-.5-.5-2.5 2.9-2.9z"/>',
    "stethoscope": '<path d="M6 3v6a4 4 0 008 0V3"/><path d="M10 13v2a5 5 0 0010 0v-1.5"/><circle cx="20" cy="12" r="1.6"/>'
                   '<circle cx="6" cy="4" r="1" fill="currentColor" stroke="none"/><circle cx="14" cy="4" r="1" fill="currentColor" stroke="none"/>',
    "film":     '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M8 4v16M16 4v16"/>'
                '<path d="M3 9h5M16 9h5M3 15h5M16 15h5"/>',
    "mail":     '<circle cx="12" cy="12" r="3.2"/><path d="M15.2 10.3V13a2.2 2.2 0 004.4 0v-1a7.5 7.5 0 10-3.2 6.2"/>',
    "box":      '<path d="M3 8l9-4.5L21 8l-9 4.5L3 8z"/><path d="M3 8v9l9 4.5V12.5M21 8v9l-9 4.5"/>',
    "coin":     '<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5.5"/>',
    "signal":   '<path d="M12 19v-6"/><circle cx="12" cy="19.5" r=".2" fill="currentColor"/>'
                '<path d="M8.5 10a5 5 0 017 0M5.5 7a9 9 0 0113 0"/>',
    "scroll":   '<path d="M6 3.5h13v13.5a3.5 3.5 0 01-3.5 3.5H6a3 3 0 01-3-3v-1h3"/>'
                '<path d="M6 3.5A2.5 2.5 0 003.5 6v11"/><path d="M9 8h6M9 11.5h6"/>',
    "monitor":  '<rect x="2.5" y="4" width="19" height="13" rx="2"/><path d="M8 20.5h8M12 17v3.5"/>',
    "yen":      '<circle cx="12" cy="12" r="9"/><path d="M12 12.5V19M7.5 6.5L12 12.5l4.5-6M9 15h6M9 12.5h6"/>',
    "cart":     '<circle cx="9.5" cy="20" r="1.3"/><circle cx="17" cy="20" r="1.3"/>'
                '<path d="M2.5 4h2.5l2 11.5h10.5l1.8-8H6"/>',
    "camera":   '<rect x="2.5" y="7" width="19" height="13" rx="2"/><path d="M8 7l1.5-3h5L16 7"/><circle cx="12" cy="13.5" r="3.5"/>',
    "mask":     '<path d="M4 9c0-3 3.5-6 8-6s8 3 8 6c0 5-3 10-8 10S4 14 4 9z"/>'
                '<path d="M8 9.5c0 1 .8 1.5 1.5 1.5S11 10.5 11 9.5M13 9.5c0 1 .8 1.5 1.5 1.5S16 10.5 16 9.5"/>',
    "compass":  '<circle cx="12" cy="12" r="9"/><path d="M15.5 8.5l-2.2 5-5 2.2 2.2-5z"/>',
    "book":     '<path d="M4 4.5h6a2.5 2.5 0 012.5 2.5v13A2 2 0 0010.5 18H4z"/>'
                '<path d="M20 4.5h-6a2.5 2.5 0 00-2.5 2.5v13A2 2 0 0113.5 18H20z"/>',
    "newspaper": '<rect x="3" y="4.5" width="14" height="15" rx="1.5"/>'
                '<path d="M17 8.5h2.5A1.5 1.5 0 0121 10v8a1.5 1.5 0 01-1.5 1.5H8"/>'
                '<path d="M6.3 8h7.4M6.3 11.3h7.4M6.3 14.6h4.5"/>',
    # 絞り込み・並べ替え・束ね（2026-08-08 追加。/board のツールバーで
    # 「これはフィルタなのかソートなのか」が見た目で分からなかったため役割の記号を用意した）
    "filter":   '<path d="M3.5 5h17l-6.5 7.5V20l-4-2.5v-5L3.5 5z"/>',
    "sort":     '<path d="M7 4v16M7 20l-3.5-3.5M7 4l3.5 3.5"/><path d="M14 6.5h7M14 12h5M14 17.5h3"/>',
    "layers":   '<path d="M12 3l9 4.5-9 4.5-9-4.5L12 3z"/><path d="M3 12.5l9 4.5 9-4.5"/>',
    "plus":     '<path d="M12 5v14M5 12h14"/>',
    # 表示プロパティ・密度切替（2026-08-16 追加。タスクボードのツールバー役割記号4つ目）。
    "eye":      '<path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7z"/><circle cx="12" cy="12" r="3"/>',
    # 「押すとその場でメニューが開く」印（2026-08-21 追加・ナビの管制室グループ）。
    "chevron-down": '<path d="M6 9.5l6 5.5 6-5.5"/>',
    # ❓情報要求（旧 /gaps 用。2026-09-09 に決裁カードへ統合）。quizのクエスチョンマークを
    # 丸枠に変え、決裁の scale と見た目で区別できるようにした。
    "question": '<circle cx="12" cy="12" r="9"/>'
                '<path d="M9.2 9.2a2.8 2.8 0 115.2 1.4c-.5.9-1.4 1.1-1.4 2.4"/>'
                '<circle cx="12" cy="16.8" r=".35" fill="currentColor" stroke="none"/>',
    # ☰ クイックアクセス・サイドバーの開閉トリガー（2026-09-26新設）
    "menu": '<path d="M4 6h16M4 12h16M4 18h16"/>',
    "barrier": '<path d="M4 8h16v7H4zM6 15v5M18 15v5M5 12l4-4M11 15l7-7"/>',
    "arrow-up": '<path d="M12 20V4M6 10l6-6 6 6"/>',
    "thumbs-up": '<path d="M8 10l4-7a2 2 0 012 2v4h4a2 2 0 012 2l-1 7a2 2 0 01-2 2H8zM3 10h5v10H3z"/>',
    "thumbs-down": '<path d="M8 14l4 7a2 2 0 002-2v-4h4a2 2 0 002-2l-1-7a2 2 0 00-2-2H8zM3 4h5v10H3z"/>',
    "lock": '<rect x="5" y="10" width="14" height="11" rx="2"/><path d="M8 10V7a4 4 0 018 0v3"/><path d="M12 14v3"/>',
    "image": '<rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8" cy="8" r="1.5"/><path d="M3 17l5-5 4 4 4-6 5 7"/>',
    "music": '<path d="M10 17V5l10-2v12M10 8l10-2"/><ellipse cx="7" cy="18" rx="3" ry="2"/><ellipse cx="17" cy="16" rx="3" ry="2"/>',
    "sliders": '<path d="M5 3v7M5 14v7M12 3v12M12 19v2M19 3v2M19 9v12M3 10h4v4H3zM10 15h4v4h-4zM17 5h4v4h-4z"/>',
    "star": '<path d="M12 3l2.8 5.7 6.2.9-4.5 4.4 1.1 6.2-5.6-3-5.6 3 1.1-6.2L3 9.6l6.2-.9z"/>',
    "sprout": '<path d="M12 21v-9M12 14C5 14 3 10 3 5c6 0 9 3 9 9zM12 11c0-5 3-8 9-8 0 5-3 8-9 8z"/>',
    "shield": '<path d="M12 3l8 3v6c0 5-8 9-8 9s-8-4-8-9V6z"/><path d="M8 12l3 3 5-6"/>',
    "bolt": '<path d="M13 3L5 13h6l-1 8 9-11h-6z"/>',
    "gem": '<path d="M7 4h10l5 6-10 11L2 10zM2 10h20M7 4l5 17 5-17"/>',
    "flask": '<path d="M9 3h6M10 3v6L4 18a2 2 0 001.7 3h12.6a2 2 0 001.7-3l-6-9V3M7 14h10"/>',
    "hypothesis": '<circle cx="12" cy="10" r="7"/><path d="M7 16l-2 5h14l-2-5M10 8a2 2 0 114 0c0 1-2 1.5-2 3M12 13h.01"/>',
    "moon": '<path d="M20 14a8 8 0 01-10-10 9 9 0 1010 10z"/>',
    "bulb": '<path d="M8 14a6 6 0 118 0l-1 2H9zM9 19h6M10 22h4"/>',
    "link": '<path d="M10 14l4-4M8 15l-1 1a4 4 0 01-6-6l4-4a4 4 0 016 0M16 9l1-1a4 4 0 016 6l-4 4a4 4 0 01-6 0"/>',
    "bell": '<path d="M5 17h14l-2-3V9a5 5 0 00-10 0v5zM10 20h4"/>',
    "person": '<circle cx="12" cy="7" r="4"/><path d="M4 21v-2a8 8 0 0116 0v2"/>',
    "handshake": '<path d="M3 8l4-3 5 2 5-2 4 3-3 9-4 3-7-3zM7 5l5 2-4 5 2 2 5-4 4 5M3 8l4 9M21 8l-3 9"/>',
    "sword": '<path d="M14 3h7v7L9 19l-4-4zM6 18l-3 3M3 13l8 8"/>',
    "tag": '<path d="M3 3h8l10 10-8 8L3 11z"/><circle cx="7.5" cy="7.5" r="1"/>',
    "truck": '<path d="M3 5h11v12H3zM14 9h4l3 4v4h-7M18 9v4h3"/><circle cx="6.5" cy="18" r="2.5"/><circle cx="17.5" cy="18" r="2.5"/>',
    "ticket": '<path d="M3 5h18v5a2 2 0 000 4v5H3v-5a2 2 0 000-4zM15 5v3M15 11v2M15 16v3"/>',
    "skull": '<path d="M7 16a8 8 0 1110 0v4H7zM10 20v-3M14 20v-3"/><circle cx="8.5" cy="10.5" r="1.5"/><circle cx="15.5" cy="10.5" r="1.5"/><path d="M11 14h2"/>',
    "broom": '<path d="M13 12l6-9M7 11l9 6-5 5-8-5zM5 18l4-5M8 20l4-5"/>',
    "dot": '<circle cx="12" cy="12" r="4"/>',
    "square": '<rect x="5" y="5" width="14" height="14" rx="2"/>',
    "cpu": AREA_ICON_PATHS["cpu"],
    "gamepad": AREA_ICON_PATHS["gamepad"],
    "briefcase": AREA_ICON_PATHS["briefcase"],
    "cards": NAV_PATHS["cards"],
    "inbox": NAV_PATHS["review"],
    "chart": NAV_PATHS["visualize"],
    "trend": NAV_PATHS["trading"],
    "wallet": NAV_PATHS["finance"],
    "home": NAV_PATHS["home"],
}


def ui_icon_svg(key, size=16, cls=""):
    """汎用UI部品アイコン。currentColor継承。spin等のCSSクラスをそのまま乗せられる。"""
    path = UI_PATHS.get(key)
    if not path:
        return ""
    cls_attr = f' class="shuki-icon {cls}"' if cls else ' class="shuki-icon"'
    return f'<svg{cls_attr} aria-hidden="true" focusable="false" viewBox="0 0 24 24" width="{size}" height="{size}" {_STROKE}>{path}</svg>'


UI_ICON_ALIASES = {
    "🚧": "barrier", "⚖": "scale", "✅": "check", "⬆": "arrow-up", "📄": "doc",
    "👍": "thumbs-up", "👎": "thumbs-down", "💬": "comment", "❌": "cross", "🔴": "dot", "🟡": "dot", "🔵": "dot", "⚪": "dot",
    "⛶": "maximize", "⤡": "shrink", "✕": "cross", "✓": "check", "✗": "cross", "✚": "plus", "✎": "pencil", "✏": "pencil", "★": "star", "⭐": "star",
    "📝": "pencil", "✨": "sparkle", "🔊": "speaker", "⚠": "warn", "🎯": "target", "🔒": "lock", "🎮": "gamepad", "💡": "bulb", "🖼": "image", "📋": "copy", "📎": "attach", "📊": "chart",
    "📡": "signal", "📌": "pin", "🕘": "clock", "🔥": "fire", "🎛": "sliders", "🏠": "home", "🎵": "music", "🔔": "bell", "🌱": "sprout", "🌰": "sprout", "⬜": "square", "🟢": "dot",
    "💵": "wallet", "💼": "briefcase", "🛡": "shield", "📈": "trend", "💸": "wallet", "📂": "folder", "📒": "doc", "📓": "doc", "📅": "calendar", "🔄": "refresh", "🔁": "refresh", "🎉": "celebrate",
    "🧍": "person", "🧑": "person", "⚡": "bolt", "⚙": "wrench", "📖": "book", "☠": "skull", "📁": "folder", "📚": "book", "📥": "inbox", "🎴": "cards", "🃏": "cards", "⚗": "flask", "🔮": "hypothesis",
    "💎": "gem", "⚔": "sword", "🌑": "moon", "🧠": "brain", "🧩": "question", "🧭": "compass", "🖥": "monitor", "🗂": "folder", "🗑": "trash", "📰": "newspaper", "💰": "coin", "🏆": "star", "🏷": "tag",
    "👀": "eye", "💭": "comment", "🔍": "search", "🔎": "search", "🔻": "chevron-down", "🔧": "wrench", "🤖": "cpu", "🤝": "handshake", "🙈": "eye", "🚚": "truck", "🛫": "runway", "🌅": "sunrise",
    "🟠": "dot", "🧹": "broom", "🩺": "stethoscope", "❓": "question", "🌪": "filter", "🎫": "ticket", "🔗": "link", "📍": "pin", "⏳": "hourglass", "⏰": "clock",
}


def legacy_ui_icon_svg(key, size=18):
    """Resolve older notice metadata without inserting arbitrary producer markup."""
    key = str(key or "cpu").replace("\ufe0f", "")
    key = UI_ICON_ALIASES.get(key, key)
    return ui_icon_svg(key if key in UI_PATHS else "cpu", size)


def browser_icons_script():
    """Serve the shared paths before page scripts; labels remain ordinary text."""
    paths = json.dumps(UI_PATHS, ensure_ascii=True)
    aliases = json.dumps(UI_ICON_ALIASES, ensure_ascii=True)
    return '''<script>
(function() {
  const paths = ''' + paths + ''';
  const aliases = ''' + aliases + ''';
  window.shukiIcon = function(key, size = 16) {
    key = String(key || '').replace(/\uFE0F/g, '');
    key = aliases[key] || key;
    if (!Object.prototype.hasOwnProperty.call(paths, key)) return '';
    const px = Math.max(8, Math.min(64, Number(size) || 16));
    return '<svg class="shuki-icon" aria-hidden="true" focusable="false" viewBox="0 0 24 24" width="' + px + '" height="' + px + '" ''' + _STROKE + '''>' + paths[key] + '</svg>';
  };
  window.shukiSetIconLabel = function(element, key, text) {
    element.innerHTML = shukiIcon(key);
    element.append(document.createTextNode(' ' + String(text)));
  };
})();
</script>'''
