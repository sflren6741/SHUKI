#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
shuki_profile.py — 「この人は誰か」の単一情報源（2026-09-27 新設）。

背景：SHUKI は「システム（公開できる骨格）」と「個人情報」が地の文とコードに混ざっており、
公開リポジトリは publish_sync.py が正規表現で個人名を消した**複製**だった。実測で
利用者の名前がコード239箇所／100ファイル、Area の11値が21ファイルにハードコードされており、
公開のたびに人間が禁止語スキャンを目視する運用になっていた（漏洩事故2回）。

このモジュールは3層構造のうち **L2（個人）** を担う：

  L1 システム … コード・agent/skill/rule 定義。個人文字列ゼロ（＝そのまま公開できる）
  L2 個人     … このモジュールが読む profile.json。氏名・Area・人物の別名・非公開パス
  L3 コンテンツ … vault の .md と 99_System 配下のデータ

`shuki_paths.py` との棲み分け：
  shuki_paths  = 「この機械のどこに何があるか」（環境ごとに変わる絶対パス・アカウント）
  shuki_profile = 「この人は誰か」（環境を移しても変わらない個人の設定）

profile.json の置き場は **vault の 99_System/profile.json**（個人データは個人データと同居させ、
コードのリポジトリには個人ファイルを1つも置かない）。見つからなければ汎用の既定値に
フォールバックするので、設定なしでも公開版はそのまま動く。

読み込み順:
  1. 環境変数 SHUKI_PROFILE（明示パス）
  2. <vault>/99_System/profile.json
  3. <このファイルと同じディレクトリ>/shuki_profile.json（vault外に置きたい場合の逃げ道）
  4. 組み込みの既定値（汎用Area 8種。個人名は持たない）

使い方:
  import shuki_profile as profile
  profile.name()                 # 表示名
  profile.area_names()           # Area名のリスト（表示順）
  profile.area_color_map()       # {Area名: #hex}（ダーク。light=True で明色版）
  profile.private_paths()        # 非公開パス（vault相対）の集合
"""
import json
import os
from pathlib import Path

import shuki_paths

_SCRIPTS_DIR = Path(__file__).resolve().parent

# ── 組み込みの既定値（profile.json が無い環境向け）──────────────────────
# ここに個人の値を書かないこと。公開リポジトリにそのまま載るのはこのファイルであり、
# 個人の値は profile.json 側にだけ存在する（＝コードを見ても誰のものか分からない状態を保つ）。
DEFAULT_PROFILE = {
    "schema_version": 1,
    "user": {"display_name": "あなた", "full_name": "", "romaji": "", "employer": "", "emails": []},
    "areas": [
        {"name": "仕事", "key": "work", "icon": "briefcase", "color": "#6C8AF2",
         "color_light": "#617CD9", "emoji": "💼"},
        {"name": "健康", "key": "health", "icon": "pulse", "color": "#46D6A5",
         "color_light": "#2F9170", "emoji": "💪"},
        {"name": "学び", "key": "learning", "icon": "globe", "color": "#4FA6E8",
         "color_light": "#4088BE", "emoji": "🌏"},
        {"name": "お金", "key": "money", "icon": "coin", "color": "#9BE05C",
         "color_light": "#638F3A", "emoji": "💰"},
        {"name": "人間関係", "key": "people", "icon": "people", "color": "#D96BE8",
         "color_light": "#BA5CC7", "emoji": "🤝"},
        {"name": "自己理解", "key": "self", "icon": "compass", "color": "#A87BF0",
         "color_light": "#976ED7", "emoji": "🧠"},
        {"name": "娯楽", "key": "fun", "icon": "gamepad", "color": "#63DD82",
         "color_light": "#419155", "emoji": "🎮"},
        {"name": "時間管理", "key": "time", "icon": "clock", "color": "#35BEDC",
         "color_light": "#278CA2", "emoji": "⏳"},
        {"name": "その他", "key": "other", "icon": "box", "color": "#9ca3af",
         "color_light": "#6b7280", "emoji": "📦", "fallback": True},
    ],
    "people": [],
    # ── 非公開（AIに読ませない）指定。4つの経路を用意しているのは多層防御のため：
    #    ファイル名を1件変え忘れても、prefix か area か語句のどれかで止まる。
    "private_paths": [],          # vault相対の完全一致
    "private_path_prefixes": [],  # 配下すべて（末尾 / のディレクトリ指定）
    "private_name_tokens": [],    # パスに含まれていたら非公開とみなす語
}

# Area 1件に必ず入っている前提のキー（profile.json 側で省略されたらここで補う）。
# display=False … frontmatter の値としては正しいが、画面のグルーピング・配色には出さない。
#                  （vault_lint の検証対象と、ボードの表示対象がズレている実態を素直に持つため）
_AREA_FIELD_DEFAULTS = {
    "key": "", "icon": "box", "color": "#9ca3af", "color_light": "#6b7280",
    "emoji": "📦", "private": False, "fallback": False, "display": True,
}


def _candidate_files():
    env = os.environ.get("SHUKI_PROFILE")
    if env:
        yield Path(env)
    try:
        yield shuki_paths.system_dir_for(shuki_paths.VAULT) / "profile.json"
    except Exception:  # noqa: BLE001 — vault未設定でも既定値で動く必要がある
        pass
    yield _SCRIPTS_DIR / "shuki_profile.json"


def _load():
    for path in _candidate_files():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(data, dict):
            return _normalize(data), path
    return _normalize(DEFAULT_PROFILE), None


def _normalize(raw):
    """欠けたキーを既定値で埋めて、以降のコードが存在チェックをしなくて済む形にする。"""
    data = dict(DEFAULT_PROFILE)
    data.update(raw)
    data["user"] = {**DEFAULT_PROFILE["user"], **(raw.get("user") or {})}

    areas = raw.get("areas") or DEFAULT_PROFILE["areas"]
    norm = []
    for a in areas:
        if not isinstance(a, dict) or not a.get("name"):
            continue
        entry = {**_AREA_FIELD_DEFAULTS, **a}
        # key（CSS変数名・JSONキーに使う英字スラッグ）は日本語不可。省略時は連番で補う。
        if not entry["key"]:
            entry["key"] = f"area{len(norm) + 1}"
        norm.append(entry)
    data["areas"] = norm
    data["people"] = raw.get("people") or []
    for key in ("private_paths", "private_path_prefixes", "private_name_tokens"):
        data[key] = raw.get(key) or []
    return data


_PROFILE, _SOURCE = _load()


def source_path():
    """実際に読み込んだ profile.json のパス（既定値にフォールバックした場合は None）。"""
    return _SOURCE


def get(dotted, default=None):
    """ドット区切りで値を引く（例: get("user.employer")）。"""
    cur = _PROFILE
    for part in dotted.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return default
        cur = cur[part]
    return cur


def user():
    return dict(_PROFILE["user"])


def name():
    """画面・文章に出す表示名。profile.json 未設定なら汎用の「あなた」。"""
    return _PROFILE["user"]["display_name"]


# ── Area（人生の領域）──────────────────────────────────────────
# 以前は achievements.py / concept_tree.py / dashboard_board.py / dashboard_control.py /
# dashboard_theme.py / dashboard_icons.py にそれぞれ別の写しがあり、色が食い違っていた
# （実測: 仕事 が #f59e0b と #3987e5 と #6C8AF2 の3種類）。ここが唯一の正。

def areas(include_fallback=False, display_only=True):
    """Area定義のリスト（profile.json の順＝表示順）。
    include_fallback=True で「その他」等の受け皿Areaも含める。
    display_only=False で、画面に出さないが frontmatter の値としては有効なAreaも含める
    （＝ vault_lint のような「値の検証」側はこちらを使う）。"""
    return [dict(a) for a in _PROFILE["areas"]
            if (include_fallback or not a.get("fallback"))
            and (not display_only or a.get("display", True))]


def area_names(include_fallback=False, display_only=True):
    return [a["name"] for a in areas(include_fallback, display_only)]


def valid_area_names():
    """frontmatter の `area:` に書いてよい値すべて（画面に出さないものも含む・受け皿は除く）。"""
    return area_names(include_fallback=False, display_only=False)


def area(name_):
    for a in _PROFILE["areas"]:
        if a["name"] == name_:
            return dict(a)
    return None


def area_key_map(include_fallback=False):
    """{Area名: 英字キー}。CSS変数名（--area-<key>）やJSONキーに使う。"""
    return {a["name"]: a["key"] for a in areas(include_fallback)}


def area_color_map(light=False, include_fallback=False):
    """{Area名: #hex}。light=True でライトテーマ用の暗色版を返す。"""
    field = "color_light" if light else "color"
    return {a["name"]: a[field] for a in areas(include_fallback)}


def area_emoji_map(include_fallback=False):
    return {a["name"]: a["emoji"] for a in areas(include_fallback)}


def area_icon_map(include_fallback=False):
    """{Area名: アイコンID}。IDの実体（SVGパス）は dashboard_icons.ICON_PATHS が持つ
    ＝アイコン素材はシステム側（公開）、どのAreaがどれを使うかは個人側（profile）。"""
    return {a["name"]: a["icon"] for a in areas(include_fallback)}


def area_label(name_, lang):
    """Area名の表示ラベル（その言語での見出し）。profile.json の `labels: {"en": "..."}`。
    未設定なら None を返し、呼び出し側が共有辞書へフォールバックする。

    個人固有のArea名（例: 誰かとの関係）は共有の i18n 辞書に入れてはいけない
    （辞書は公開リポジトリに載る）。**その訳語はこの人の設定**なので profile が持つ。"""
    a = area(name_)
    if not a:
        return None
    return (a.get("labels") or {}).get(lang) or None


def area_color(name_, light=False):
    a = area(name_)
    field = "color_light" if light else "color"
    if a:
        return a[field]
    for entry in _PROFILE["areas"]:
        if entry.get("fallback"):
            return entry[field]
    return _AREA_FIELD_DEFAULTS[field]


# ── 人物・非公開パス ─────────────────────────────────────────

def people(role=None):
    """人物エントリのリスト。role を指定するとその役割だけ返す。"""
    return [dict(p) for p in _PROFILE["people"]
            if role is None or p.get("role") == role]


def person(role):
    """役割に対応する人物エントリ1件（未設定なら None）。"""
    for p in _PROFILE["people"]:
        if p.get("role") == role:
            return dict(p)
    return None


def person_label(role, default=""):
    """画面・文面に出す呼び名。未設定なら default（公開版では汎用語を渡す想定）。"""
    p = person(role)
    return (p or {}).get("label") or default


def person_aliases(role):
    """役割に対応する呼称のゆらぎ（検出・除外の照合に使う）。未設定なら空リスト。"""
    out = []
    for p in _PROFILE["people"]:
        if p.get("role") == role:
            out.extend(p.get("aliases") or [])
    return out


def private_paths():
    """AIに読ませない vault 相対パス（完全一致）の集合。
    `.claude/settings.json` の permissions.deny と同じ対象をコード側でも再現するためのもの
    （deny は Claude のツール呼び出ししか塞がないので、サーバーが自前でパスを組み立てる
    経路＝ファイル添付などは、ここを見て同じだけ塞ぐ必要がある）。"""
    return {str(p).replace("\\", "/") for p in _PROFILE["private_paths"]}


def private_path_prefixes():
    return tuple(str(p).replace("\\", "/") for p in _PROFILE["private_path_prefixes"])


def private_areas():
    """`private: true` を立てた Area の名前。その Area に属するノートは非公開扱いになる。"""
    return [a["name"] for a in _PROFILE["areas"] if a.get("private")]


def is_private_note(rel_path, fm=None):
    """このノートをAIに渡してよいか（False=渡してよい）。多層防御で、
    ①完全一致 ②ディレクトリ ③frontmatterのarea ④パスに含まれる語 のどれかに当たれば非公開。
    値は profile.json 側にあり、判定ロジック（この関数）はシステム側にある。"""
    path = str(rel_path).replace("\\", "/")
    if path in private_paths() or path.startswith(private_path_prefixes()):
        return True
    area_val = (fm or {}).get("area")
    area_list = area_val if isinstance(area_val, list) else ([area_val] if isinstance(area_val, str) else [])
    private = private_areas()
    if any(a in private for a in area_list if isinstance(a, str)):
        return True
    return any(tok in path for tok in _PROFILE["private_name_tokens"])


def is_private_path(rel_path):
    return is_private_note(rel_path)


# ── 画面（JS）へ渡す形 ────────────────────────────────────

def display_profile():
    """ブラウザ側に渡してよい部分集合。**非公開パスや人物の呼称は含めない**
    （画面に配るものは「何を表示するか」だけでよく、除外リストはサーバー側の判断材料）。"""
    return {
        "areas": [
            {k: a[k] for k in ("name", "key", "color", "color_light", "emoji", "icon")}
            for a in areas(include_fallback=True)
        ],
        "area_order": area_names(),
        "area_key": area_key_map(),
    }


def profile_js():
    """GET /profile.js の本体。app.js より先に読ませて window.SHUKI_PROFILE を定義する
    （各 app.js は未定義でも汎用の既定値で動くよう書いてある＝この配線が切れても壊れない）。"""
    return ("/* 自動生成: shuki_profile.profile_js()。個人の Area 定義を画面へ渡す層。 */\n"
            "window.SHUKI_PROFILE = "
            + json.dumps(display_profile(), ensure_ascii=False, separators=(",", ":"))
            + ";\n")


if __name__ == "__main__":
    src = source_path()
    print(f"profile: {src if src else '(組み込みの既定値)'}")
    print(f"user   : {name()}")
    print(f"areas  : {len(areas())}件 → {', '.join(area_names())}")
    print(f"private: {len(private_paths())}件")
