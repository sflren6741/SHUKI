#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
dashboard_tutorial.py — 初回チュートリアルと画面ガイド（GET /tutorial.js・/tutorial/state の実体・2026-10-09）

2つの層を持つ:
  ① 基本操作（core）: 初回起動時だけ強制する、実際に操作させるツアー。
     対話パネルを開く → AIにタスクを頼む → タスクボードで確認 → カレンダー（Results）で確認。
     表示中は示した場所以外の操作をロックし、スキップは出さない。ただし AI が応答できない・
     タスクが増えない・対象が画面に出ない時だけ「このまま進む」を出す（行き止まりを作らない）。
  ② 画面ガイド（pages）: 各画面を初めて開いた時だけ出る数枚の説明。表示中はロックするが、
     いつでもスキップできる。設定 → チュートリアルから再表示・無効化できる。

状態は vault 外の <data>/core/tutorial_state.json（ダッシュボード1台につき1つ＝端末をまたいで共有）。
状態ファイルが無い時、ダッシュボードの使用歴（設定ファイル・対話履歴）があれば既存の利用者とみなし、
基本操作は強制しない（設定から再生できる）。判定は最初に読んだ時点で保存して固定する
（チュートリアル中の最初の対話で履歴ファイルができても、初回扱いが途中で変わらないように）。

自動操作のブラウザ（navigator.webdriver）では自動で始めない。テストやブラウザ自動化の操作を
塞がないため。`?tutorial=1` を付けると、そのタブでは自動操作でも始まる（確認用）。

文言は日本語の原文を i18n/<lang>.json の "tutorial|原文" で訳す（shuki_i18n の流儀）。
画面の色・角丸・タップ標的は 🖥 UIデザイン原則（トークン経由・44px・reduced-motion）に従う。
"""
import json
import os
import tempfile
import threading
from pathlib import Path

import dashboard_settings
import shuki_paths
from shuki_i18n import t

STATE_VERSION = 1
CORE_STATUSES = ("pending", "active", "done", "skipped")
CORE_STEPS = ("welcome", "chat-open", "chat-send", "task-wait", "board-find", "board-detail",
              "cal-results", "cal-today", "cal-detail", "finish")
# 画面ガイドを持つページ（キー → パス）。プラグインのページは対象外。
GUIDE_PAGES = {"home": "/", "board": "/board", "calendar": "/calendar", "decisions": "/decisions",
               "news": "/news", "files": "/files", "settings": "/settings"}
# ナビの表示名（nav の訳語をそのまま使う）。メニューから消されたページへの案内文に使う。
PAGE_NAMES = {"home": "ホーム", "board": "タスク", "calendar": "カレンダー", "decisions": "決裁カード",
              "news": "ニュース", "files": "ファイル", "settings": "設定"}
MAX_BASELINE = 5000   # 「頼む前にあったタスク」の id 数の上限（超える vault は新規検出を諦めるだけ）
MAX_TEXT = 300
MAX_BODY = 512 * 1024
_LOCK = threading.RLock()

# 基本操作・共通部品の文言（日本語が原文。訳は i18n/<lang>.json の "tutorial|原文"）。
# トーンは UIデザイン原則 §10：感嘆符・絵文字・「〜しよう」を使わず、事実と次の一歩だけを書く。
LABELS = {
    "kind_core": "基本操作",
    "kind_guide": "画面ガイド",
    "welcome_title": "SHUKIへようこそ",
    "welcome_body": "最初に基本操作を4つ、実際に試します（2分ほど）。\n"
                    "対話パネルを開く → AIにタスクを頼む → タスクボードで確認 → カレンダーで確認。",
    "welcome_note": "このチュートリアルは初回だけです。あとから「設定」で再生できます。",
    "start": "始める",
    "chat_open_title": "対話パネルを開く",
    "chat_open_body": "右下の丸いボタン（Omnipus）を押します。SHUKIへの依頼は、この対話パネルから。",
    "chat_missing": "この画面には対話パネルがありません。ホームで続けます。",
    "to_home": "ホームへ",
    "send_title": "タスクを頼む",
    "send_body": "やることを普通の言葉で書いて送信します。\n例：「タスクを追加して：金曜までに歯医者を予約」",
    "send_prefill": "タスクを追加して：",
    "wait_title": "AIがタスクを作成中",
    "wait_body": "Omnipusが vault にタスクのファイルを書いています。通常1分ほど。"
                 "質問が来たら、ここで答えて送信します。",
    "wait_status": "新しいタスクを確認しています…",
    "wait_none": "新しいタスクはまだ作られていません。もう一度頼むか、このまま先へ進めます。",
    "wait_error": "AIが応答できませんでした。Claude Code のインストールとログインを確認してください。"
                  "先へ進むこともできます。",
    "found_title": "タスクができました",
    "found_body": "「{title}」が追加されました。次はタスクボードで確認します。",
    "nav_title": "{page}を開く",
    "nav_body_group": "「{group}」→「{page}」の順に押します。",
    "nav_body_direct": "「{page}」を押します。",
    "nav_body_missing": "メニューに「{page}」が表示されていません。下のボタンから開きます。",
    "nav_chat_note": "対話パネルは最小化して、右下に残してあります。",
    "board_title": "タスクボード",
    "board_loading": "タスクを読み込んでいます…",
    "board_found": "追加したタスク「{title}」です。押すと詳細が開きます。",
    "board_hidden": "「{title}」は今の表示条件では出ていません。下のボタンで詳細を開きます。",
    "board_generic": "タスクはカードとして、Areaごとに並びます。",
    "open_details": "詳細を開く",
    "detail_title": "タスクの詳細",
    "detail_body": "締切や本文の確認、状態の変更（次の便で反映）はここから。",
    "cal_title": "カレンダー",
    "cal_results_body": "Schedule は予定、Results は日ごとの記録です。Results を押します。",
    "cal_unavailable": "記録を読み込めませんでした。再試行するか、このまま先へ進めます。",
    "cal_today_body": "今日の欄の数字が、今日の記録の件数です。色が濃いほど記録の多い日。",
    "cal_detail_found": "「{title}」が今日の Created tasks に入っています。作成・完了・ログは、こうして日付ごとに残ります。",
    "cal_detail_generic": "選んだ日に作成・完了したタスクとログが、ここに並びます。",
    "finish_title": "基本操作は以上です",
    "finish_body": "対話で頼み、タスクボードとカレンダーで確かめる。これがSHUKIの基本の流れです。\n"
                   "各画面を初めて開いた時は、短いガイドが出ます（スキップ可）。"
                   "このチュートリアルは「設定」からもう一度表示できます。",
    "finish": "完了",
    "next": "次へ",
    "back": "戻る",
    "done": "閉じる",
    "skip_guide": "スキップ",
    "continue_anyway": "このまま進む",
    "locked": "チュートリアル中は、示された場所だけ操作できます。",
    "guides_reset_msg": "画面ガイドを再表示します。各画面を開いた時に出ます。",
    "guides_on_msg": "画面ガイドを表示します。",
    "guides_off_msg": "画面ガイドを表示しません。",
    "save_failed": "保存できませんでした（サーバー未応答）",
}

# 画面ガイド: ページキー → [(候補セレクタ（先に見つかったものを照らす）, 見出し, 本文), ...]
GUIDES = {
    "home": [
        (["#hw-text"], "書く", "思いついたことを、ここに自由に書きます。下書きはこのブラウザに残ります。"),
        ([".hw-actions"], "記録だけ／AIに渡す",
         "「記録だけ」はそのまま保存します。「AIに渡す」は、次の便でAIがタスク化・整理します。"),
        (["#sb-trigger"], "メニュー", "通知・ニュース・決裁カード・設定と、会話の履歴はここから開きます。"),
        (["#chat-fab", "#result-mini"], "対話", "その場でAIに頼む時は、右下のボタンから対話パネルを開きます。"),
    ],
    "board": [
        (["#board-settings-toggle"], "一つのタスクボード",
         "「表示設定」で、表示するタスク・責任分担・グループ分け・並べ替えを選べます。閉じるとタスクを見る広さに戻ります。"),
        (["#f-search"], "探す・絞る", "タスク名で検索します。検索と今の表示条件は、設定を閉じても見えます。"),
        (["#wall-container .task-open", "#wall-container", "#wall-wrap"], "カード",
         "タイトルを押すと詳細が開きます。チェックで選択すると、完了や責任分担をまとめて操作できます。"),
    ],
    "calendar": [
        ([".cal-view-tabs"], "予定と記録",
         "Schedule は予定（Googleカレンダー連携時）とAIからの提案、Results は日ごとの記録です。"),
        (["#cal-month-grid"], "日付", "日付を押すと、その日の詳細が下に出ます。"),
        (["#cal-fab"], "予定を追加", "Googleカレンダーに予定を追加します（Googleカレンダーの連携が必要です）。"),
    ],
    "decisions": [
        (["#cardwrap > *", "#empty-state", "main"], "決裁カード",
         "AIが人の判断を必要としている事柄です。選択肢を選ぶか、「その他」に書いて答えます。"
         "答えは次の便でAIが反映します。"),
    ],
    "news": [
        (["#list > *", "#empty-state", "main"], "ニュース", "購読しているフィードの新着から、AIが選んだ記事です。"),
        (["#list .rbtn-n", "#list"], "評価", "記事の評価は、次からの記事の選び方に使われます。"),
    ],
    "files": [
        (["#f-search"], "ファイルを探す",
         "vault のノートをタイトルやパスで検索します。右に続く操作で、絞り込み・並べ替え・束ね方を選べます。"),
        (["#list > *", "#list"], "一覧", "項目を押すと、ノートの中身を表示します。"),
    ],
    "settings": [
        ([".setup-choice"], "表示の設定", "標準のままで使えます。見た目やメニューを変える時は「カスタマイズ」を選びます。"),
        (["#tutorial-settings"], "チュートリアル", "基本操作のチュートリアルと画面ガイドは、ここからもう一度表示できます。"),
    ],
}


# ── 状態（<data>/core/tutorial_state.json） ─────────────────────────────────
def state_file():
    return shuki_paths.data_dir("core") / "tutorial_state.json"


def _used_before():
    """このダッシュボードが既に使われているか（設定を保存した・対話した）。"""
    markers = (dashboard_settings.SETTINGS_FILE, shuki_paths.code_store("core/dashboard_history.json"))
    return any(Path(marker).exists() for marker in markers)


def _initial_state():
    return {"version": STATE_VERSION,
            "core": {"status": "skipped" if _used_before() else "pending", "step": "welcome"},
            "pages": {}, "guides": True}


def _clean_task(task):
    if not isinstance(task, dict) or not isinstance(task.get("id"), str) or not task["id"].strip():
        return None
    title = task.get("title") if isinstance(task.get("title"), str) and task.get("title").strip() else task["id"]
    return {"id": task["id"][:MAX_TEXT], "title": title[:MAX_TEXT]}


def _sanitize(raw):
    """保存値を正規化する。壊れた・不明な値は既定へ（基本操作は強制しない側＝skipped）。"""
    raw = raw if isinstance(raw, dict) else {}
    core_raw = raw.get("core") if isinstance(raw.get("core"), dict) else {}
    core = {"status": core_raw.get("status") if core_raw.get("status") in CORE_STATUSES else "skipped",
            "step": core_raw.get("step") if core_raw.get("step") in CORE_STEPS else "welcome"}
    task = _clean_task(core_raw.get("task"))
    if task:
        core["task"] = task
    baseline = core_raw.get("baseline")
    if isinstance(baseline, list):
        core["baseline"] = [item[:MAX_TEXT] for item in baseline if isinstance(item, str)][:MAX_BASELINE]
    pages_raw = raw.get("pages") if isinstance(raw.get("pages"), dict) else {}
    pages = {key: "done" for key, value in pages_raw.items() if key in GUIDE_PAGES and value == "done"}
    return {"version": STATE_VERSION, "core": core, "pages": pages, "guides": raw.get("guides") is not False}


def _write(state):
    path = state_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, prefix=path.name + ".",
                                     suffix=".tmp", delete=False) as handle:
        json.dump(state, handle, ensure_ascii=False, indent=1)
        temporary = handle.name
    os.replace(temporary, path)


def _read():
    try:
        raw = json.loads(state_file().read_text(encoding="utf-8"))
    except FileNotFoundError:
        state = _initial_state()
        _write(state)  # 判定を固定する（途中で履歴ファイルができても初回扱いが変わらない）
        return state
    except (OSError, ValueError):
        return _sanitize({})
    return _sanitize(raw)


def load_state():
    with _LOCK:
        return _read()


def update_state(patch):
    """POST /tutorial/state の部分更新。未知のキー・型違いは ValueError（何も書かない）。

    {"core": {"status", "step", "task", "baseline"}}  基本操作の進行（task/baseline は null で消す）
    {"page": "<key>"}                                画面ガイドを見た
    {"guides": true|false}                           画面ガイドの自動表示
    {"reset": "core"|"pages"}                        基本操作を最初から／画面ガイドをもう一度
    """
    if not isinstance(patch, dict) or not patch:
        raise ValueError("expected a non-empty object")
    unknown = set(patch) - {"core", "page", "guides", "reset"}
    if unknown:
        raise ValueError(f"unknown keys: {sorted(unknown)}")
    with _LOCK:
        state = _read()
        reset = patch.get("reset")
        if reset is not None:
            if reset == "core":
                state["core"] = {"status": "active", "step": "welcome"}
            elif reset == "pages":
                state["pages"] = {}
                state["guides"] = True
            else:
                raise ValueError("reset must be core or pages")
        if "core" in patch:
            core = patch["core"]
            if not isinstance(core, dict) or set(core) - {"status", "step", "task", "baseline"}:
                raise ValueError("bad core")
            merged = dict(state["core"])
            if "status" in core:
                if core["status"] not in CORE_STATUSES:
                    raise ValueError("bad core status")
                merged["status"] = core["status"]
            if "step" in core:
                if core["step"] not in CORE_STEPS:
                    raise ValueError("bad core step")
                merged["step"] = core["step"]
            if "task" in core:
                if core["task"] is None:
                    merged.pop("task", None)
                elif _clean_task(core["task"]):
                    merged["task"] = _clean_task(core["task"])
                else:
                    raise ValueError("bad task")
            if "baseline" in core:
                baseline = core["baseline"]
                if baseline is None:
                    merged.pop("baseline", None)
                elif isinstance(baseline, list) and all(isinstance(item, str) for item in baseline):
                    merged["baseline"] = [item[:MAX_TEXT] for item in baseline][:MAX_BASELINE]
                else:
                    raise ValueError("bad baseline")
            state["core"] = merged
        if "page" in patch:
            if not isinstance(patch["page"], str) or patch["page"] not in GUIDE_PAGES:
                raise ValueError("unknown page")
            state["pages"][patch["page"]] = "done"
        if "guides" in patch:
            if not isinstance(patch["guides"], bool):
                raise ValueError("guides must be true or false")
            state["guides"] = patch["guides"]
        state = _sanitize(state)
        _write(state)
        return state


# ── 画面へ渡すもの ─────────────────────────────────────────────────────────
def client_data():
    return {
        "labels": {key: t(text, ctx="tutorial") for key, text in LABELS.items()},
        "guides": {page: [{"sel": list(selectors), "title": t(title, ctx="tutorial"),
                           "body": t(body, ctx="tutorial")} for selectors, title, body in steps]
                   for page, steps in GUIDES.items()},
        "pages": dict(GUIDE_PAGES),
        "page_names": {key: t(name, ctx="nav") for key, name in PAGE_NAMES.items()},
        "core_steps": list(CORE_STEPS),
        "css": CSS,
    }


def tutorial_js():
    data = json.dumps(client_data(), ensure_ascii=False).replace("</", "<\\/")
    return JS.replace("__TUTORIAL_DATA__", data)


def settings_html():
    """設定ページの「チュートリアル」欄。操作はその場で POST /tutorial/state に保存する
    （設定ページ下部の「保存して反映」とは独立。webpush・MCP 欄と同じ流儀）。"""
    guides = load_state().get("guides", True)
    tx = lambda s: t(s, ctx="tutorial")  # noqa: E731
    return (
        '<details class="card settings-group" id="tutorial-settings">'
        f'<summary>{tx("チュートリアル")}</summary><div class="settings-body">'
        f'<p class="hint">{tx("基本操作のチュートリアルと、各画面を初めて開いた時の短いガイドです。")}</p>'
        '<p><button type="button" class="hbtn" id="tut-replay" '
        'onclick="window.ShukiTutorial &amp;&amp; ShukiTutorial.settings(\'replay\', this)">'
        f'{tx("基本操作をもう一度")}</button> '
        '<button type="button" class="hbtn" id="tut-reset-guides" '
        'onclick="window.ShukiTutorial &amp;&amp; ShukiTutorial.settings(\'reset\', this)">'
        f'{tx("画面ガイドをもう一度表示")}</button></p>'
        '<label class="ord-check" style="display:flex;margin-top:8px;">'
        f'<input type="checkbox" id="tut-guides"{" checked" if guides else ""} '
        'onchange="window.ShukiTutorial &amp;&amp; ShukiTutorial.settings(\'guides\', this)">'
        f'<span>{tx("画面を初めて開いた時にガイドを表示する")}</span></label>'
        '<p class="hint" id="tut-settings-msg" role="status" aria-live="polite"></p>'
        '</div></details>')


# 色はすべてトークン経由。暗幕だけは既存のオーバーレイ（.sb-overlay 等）と同じ黒の半透明。
# z-index は既存の最上位（#burst 9998）より上。
CSS = r"""
#shuki-tutorial { --tut-dim: rgba(0, 0, 0, .58); position: fixed; inset: 0; z-index: 10000;
  pointer-events: none; font-family: var(--font-ui, system-ui, sans-serif); }
#shuki-tutorial[hidden], #shuki-tutorial [hidden] { display: none !important; }
#shuki-tutorial .tut-dim { position: fixed; inset: 0; background: var(--tut-dim); }
#shuki-tutorial .tut-ring { position: fixed; border-radius: 10px;
  box-shadow: 0 0 0 2px var(--accent), 0 0 0 200vmax var(--tut-dim);
  transition: left .18s ease, top .18s ease, width .18s ease, height .18s ease; }
#shuki-tutorial .tut-card { position: fixed; left: 12px; top: 12px; box-sizing: border-box; pointer-events: auto;
  background: var(--card); color: var(--fg); border: 1px solid var(--line); border-radius: 12px;
  padding: 14px 16px 12px; box-shadow: 0 14px 36px rgba(0, 0, 0, .35);
  max-height: calc(100vh - 24px); overflow-y: auto; outline: none; text-align: left; }
#shuki-tutorial .tut-top { display: flex; align-items: center; gap: 8px; font-size: .72rem;
  font-weight: 700; color: var(--muted); letter-spacing: .02em; }
#shuki-tutorial .tut-count { margin-left: auto; color: var(--accent); font-variant-numeric: tabular-nums; }
#shuki-tutorial .tut-title { margin: 6px 0 4px; font-size: 1rem; line-height: 1.4; color: var(--fg); }
#shuki-tutorial .tut-body { margin: 0; font-size: .87rem; line-height: 1.65; white-space: pre-line;
  overflow-wrap: anywhere; color: var(--fg); }
#shuki-tutorial .tut-status { margin: 8px 0 0; font-size: .78rem; line-height: 1.5; color: var(--muted); }
#shuki-tutorial .tut-status:empty { display: none; }
#shuki-tutorial .tut-actions { display: flex; align-items: center; gap: 8px; margin-top: 12px; flex-wrap: wrap; }
#shuki-tutorial .tut-spacer { flex: 1 1 auto; }
#shuki-tutorial .tut-btn { min-height: 44px; min-width: 44px; padding: 8px 14px; border-radius: 8px;
  border: 1px solid var(--line); background: none; color: var(--fg); font: inherit; font-size: .86rem; cursor: pointer; }
#shuki-tutorial .tut-btn:hover { border-color: var(--accent); }
#shuki-tutorial .tut-btn:disabled { opacity: .6; cursor: default; }
#shuki-tutorial .tut-primary { background: var(--accent); border-color: var(--accent); color: var(--bg); font-weight: 700; }
#shuki-tutorial .tut-skip { border-color: transparent; color: var(--muted); padding-left: 6px; padding-right: 6px; }
#shuki-tutorial .tut-btn:focus-visible, #shuki-tutorial .tut-card:focus-visible {
  outline: 3px solid var(--accent); outline-offset: 2px; }
#shuki-tutorial .tut-card.tut-nudge { animation: shuki-tut-nudge .45s ease; }
@keyframes shuki-tut-nudge { 0%, 100% { transform: none; } 30% { transform: translateX(-5px); }
  70% { transform: translateX(5px); } }
@media (prefers-reduced-motion: reduce) {
  #shuki-tutorial .tut-ring { transition: none; }
  #shuki-tutorial .tut-card.tut-nudge { animation: none; box-shadow: 0 0 0 3px var(--accent), 0 14px 36px rgba(0, 0, 0, .35); }
}
"""


# 全ページの <head> が defer で読む（dashboard_ui.pwa_head）。ページ側の関数（openChat・
# minimizeResult・showDetail 等）は呼ぶ前に存在を確かめ、無くても壊れないようにする。
JS = r"""(() => {
  'use strict';
  if (window.ShukiTutorial) return;
  const DATA = __TUTORIAL_DATA__;
  const L = DATA.labels;
  const GUIDES = DATA.guides;
  const PAGES = DATA.pages;
  const NAMES = DATA.page_names;
  const CORE_ORDER = DATA.core_steps;
  const params = new URLSearchParams(location.search);
  let forced = params.get('tutorial') === '1';
  try {
    if (forced) sessionStorage.setItem('shuki-tutorial-force', '1');
    else forced = sessionStorage.getItem('shuki-tutorial-force') === '1';
  } catch (_) {}
  const AUTOMATED = !!navigator.webdriver && !forced;
  const REDUCED = !!(window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches);
  const PATH = location.pathname.replace(/\/+$/, '') || '/';
  const PAGE = Object.keys(PAGES).find(key => PAGES[key] === PATH) || '';
  // 示した場所以外では、押す・打つ・送るを止める。スクロール（wheel/touchmove）は止めない。
  const BLOCKED = ['click', 'dblclick', 'auxclick', 'contextmenu', 'pointerdown', 'pointerup', 'mousedown',
    'mouseup', 'touchend', 'submit', 'keydown', 'keypress', 'keyup', 'beforeinput', 'dragstart', 'drop'];
  const FOCUSABLE = 'a[href], button:not([disabled]), input:not([disabled]):not([type="hidden"]), '
    + 'select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

  let state = null;
  let ui = null;
  let run = null;
  let frame = 0;
  let lastPlace = '';
  let guarded = false;
  let task = null;
  let baseline = null;
  let saves = Promise.resolve();

  const $ = selector => document.querySelector(selector);
  const fmt = (text, values) => String(text || '').replace(/\{(\w+)\}/g,
    (match, key) => (values && values[key] != null ? values[key] : match));
  const clean = text => String(text || '').replace(/\s+/g, ' ').trim();
  const smooth = () => (REDUCED ? 'auto' : 'smooth');

  function visible(el) {
    if (!el || !el.isConnected || !el.getBoundingClientRect) return false;
    const rect = el.getBoundingClientRect();
    if (rect.width < 1 || rect.height < 1) return false;
    const style = getComputedStyle(el);
    return style.visibility !== 'hidden' && style.display !== 'none';
  }
  function resolve(list) {
    const out = [];
    for (const item of [].concat(list || [])) {
      if (typeof item === 'function') {
        let got = null;
        try { got = item(); } catch (_) {}
        [].concat(got || []).forEach(el => { if (el) out.push(el); });
        continue;
      }
      try { document.querySelectorAll(item).forEach(el => out.push(el)); } catch (_) {}
    }
    return out;
  }
  function firstVisible(list) {
    for (const item of [].concat(list || [])) {
      const found = resolve(item).find(visible);
      if (found) return found;
    }
    return null;
  }

  // ── 状態（サーバー保存。端末をまたいで共有） ──
  async function fetchState() {
    const response = await fetch('/tutorial/state', {cache: 'no-store'});
    if (!response.ok) throw new Error('HTTP ' + response.status);
    return response.json();
  }
  function saveState(patch) {
    const body = JSON.stringify(patch);
    const save = async () => {
      try {
        const response = await fetch('/tutorial/state', {method: 'POST', keepalive: body.length < 60000,
          headers: {'Content-Type': 'application/json'}, body});
        if (!response.ok) return null;
        state = await response.json();
        return state;
      } catch (_) { return null; }
    };
    // Keep step transitions and delayed snapshots in request order.
    saves = saves.then(save, save);
    return saves;
  }

  // ── 表示部品 ──
  function buildUi() {
    if (ui) return ui;
    const style = document.createElement('style');
    style.id = 'shuki-tutorial-style';
    style.textContent = DATA.css;
    document.head.appendChild(style);
    const root = document.createElement('div');
    root.id = 'shuki-tutorial';
    root.hidden = true;
    root.innerHTML = '<div class="tut-dim"></div><div class="tut-ring" hidden></div>'
      + '<section class="tut-card" role="dialog" aria-modal="true" aria-labelledby="tut-title"'
      + ' aria-describedby="tut-body" tabindex="-1">'
      + '<div class="tut-top"><span class="tut-kind"></span><span class="tut-count"></span></div>'
      + '<h2 class="tut-title" id="tut-title"></h2><p class="tut-body" id="tut-body"></p>'
      + '<p class="tut-status" role="status" aria-live="polite"></p>'
      + '<div class="tut-actions"><button type="button" class="tut-btn tut-skip" hidden></button>'
      + '<span class="tut-spacer"></span><button type="button" class="tut-btn tut-back" hidden></button>'
      + '<button type="button" class="tut-btn tut-alt" hidden></button>'
      + '<button type="button" class="tut-btn tut-primary" hidden></button></div></section>';
    document.body.appendChild(root);
    const q = selector => root.querySelector(selector);
    ui = {root, dim: q('.tut-dim'), ring: q('.tut-ring'), card: q('.tut-card'), kind: q('.tut-kind'),
      count: q('.tut-count'), title: q('.tut-title'), body: q('.tut-body'), status: q('.tut-status'),
      skip: q('.tut-skip'), back: q('.tut-back'), alt: q('.tut-alt'), primary: q('.tut-primary')};
    return ui;
  }
  function setButton(button, spec) {
    button.hidden = !spec;
    button.onclick = null;
    button.disabled = false;
    if (!spec) return;
    button.textContent = spec.label;
    button.onclick = event => { event.preventDefault(); spec.onClick(); };
  }
  function show(card) {
    buildUi();
    ui.root.hidden = false;
    ui.kind.textContent = card.kind || '';
    ui.count.textContent = card.count || '';
    ui.title.textContent = card.title || '';
    ui.body.textContent = card.body || '';
    ui.status.textContent = card.status || '';
    setButton(ui.skip, card.skip);
    setButton(ui.back, card.back);
    setButton(ui.alt, card.alt);
    setButton(ui.primary, card.primary);
    lastPlace = '';
    place();
    if (card.focus === 'none') return;
    const target = card.focus || (!ui.primary.hidden && ui.primary) || (!ui.alt.hidden && ui.alt) || ui.card;
    try { target.focus({preventScroll: true}); } catch (_) {}
  }

  // 照らす枠とカードの位置。対象が動く（スクロール・読み込み・パネルの開閉）ので毎フレーム追う。
  function place() {
    if (!run || !ui || ui.root.hidden) return;
    const target = run.target ? run.target() : null;
    const view = window.visualViewport;
    const vw = document.documentElement.clientWidth || innerWidth;
    const vh = view ? view.height : innerHeight;
    const vTop = view ? view.offsetTop : 0;
    const margin = 12;
    const width = Math.min(380, vw - margin * 2);
    const card = ui.card;
    if (card.style.width !== width + 'px') card.style.width = width + 'px';
    const height = card.offsetHeight;
    if (!target) {
      const key = ['c', vw, vh, vTop, height].join('|');
      if (key === lastPlace) return;
      lastPlace = key;
      ui.ring.hidden = true;
      ui.dim.hidden = false;
      card.style.left = Math.round((vw - width) / 2) + 'px';
      card.style.top = Math.round(vTop + Math.max(margin, (vh - height) / 2)) + 'px';
      return;
    }
    const r = target.getBoundingClientRect();
    const key = [Math.round(r.left), Math.round(r.top), Math.round(r.width), Math.round(r.height),
      vw, vh, vTop, height].join('|');
    if (key === lastPlace) return;
    lastPlace = key;
    const pad = 6, gap = 12;
    const left = Math.max(2, r.left - pad), top = Math.max(vTop + 2, r.top - pad);
    const right = Math.min(vw - 2, r.right + pad), bottom = Math.min(vTop + vh - 2, r.bottom + pad);
    ui.dim.hidden = true;
    ui.ring.hidden = false;
    Object.assign(ui.ring.style, {left: left + 'px', top: top + 'px',
      width: Math.max(0, right - left) + 'px', height: Math.max(0, bottom - top) + 'px'});
    const clampX = x => Math.min(Math.max(margin, x), vw - width - margin);
    const clampY = y => Math.min(Math.max(vTop + margin, y), vTop + vh - height - margin);
    const centerX = clampX(r.left + r.width / 2 - width / 2);
    let x, y;
    if (bottom + gap + height <= vTop + vh - margin) { x = centerX; y = bottom + gap; }
    else if (top - gap - height >= vTop + margin) { x = centerX; y = top - gap - height; }
    else if (right + gap + width <= vw - margin) { x = right + gap; y = clampY(r.top); }
    else if (left - gap - width >= margin) { x = left - gap - width; y = clampY(r.top); }
    else {
      x = centerX;
      const low = run.pin ? run.pin === 'bottom' : r.top + r.height / 2 < vTop + vh / 2;
      y = low ? vTop + vh - height - margin : vTop + margin;
    }
    card.style.left = Math.round(x) + 'px';
    card.style.top = Math.round(y) + 'px';
  }
  function track() {
    cancelAnimationFrame(frame);
    const tick = () => { if (!run) return; place(); frame = requestAnimationFrame(tick); };
    frame = requestAnimationFrame(tick);
  }

  // ── 操作のロック ──
  function allowed(node) {
    if (!run || !node || typeof node !== 'object') return false;
    if (ui && ui.root.contains(node)) return true;
    return resolve(run.allow).some(el => el === node || (el.contains && el.contains(node)));
  }
  function nudge() {
    if (!ui) return;
    ui.card.classList.remove('tut-nudge');
    void ui.card.offsetWidth;
    ui.card.classList.add('tut-nudge');
    if (!ui.status.textContent) {
      ui.status.textContent = L.locked;
      clearTimeout(nudge.timer);
      nudge.timer = setTimeout(() => { if (ui.status.textContent === L.locked) ui.status.textContent = ''; }, 2600);
    }
  }
  function cycleFocus(event) {
    const items = [];
    const add = el => { if (el && visible(el) && !items.includes(el)) items.push(el); };
    resolve(run.allow).forEach(el => {
      if (el.matches && el.matches(FOCUSABLE)) add(el);
      if (el.querySelectorAll) el.querySelectorAll(FOCUSABLE).forEach(add);
    });
    ui.card.querySelectorAll(FOCUSABLE).forEach(add);
    event.preventDefault();
    event.stopImmediatePropagation();
    if (!items.length) return;
    const index = items.indexOf(document.activeElement);
    const next = event.shiftKey ? (index <= 0 ? items.length - 1 : index - 1)
      : (index < 0 || index === items.length - 1 ? 0 : index + 1);
    items[next].focus();
  }
  function guard(event) {
    if (!run) return;
    if (event.type === 'keydown' && event.key === 'Escape') {
      event.preventDefault();
      event.stopImmediatePropagation();
      if (run.onEscape) run.onEscape();
      return;
    }
    if (event.type === 'keydown' && event.key === 'Tab') { cycleFocus(event); return; }
    if (allowed(event.target)) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    if (event.type === 'click') nudge();
  }
  function attachGuard() {
    if (guarded) return;
    guarded = true;
    BLOCKED.forEach(type => window.addEventListener(type, guard, {capture: true, passive: false}));
  }
  function detachGuard() {
    if (!guarded) return;
    guarded = false;
    BLOCKED.forEach(type => window.removeEventListener(type, guard, {capture: true}));
  }

  // ── 1ステップ分の後始末と待ち合わせ ──
  function resetStep() {
    if (!run) return;
    run.timers.forEach(id => clearInterval(id));
    run.cleanups.forEach(fn => { try { fn(); } catch (_) {} });
    run.timers = [];
    run.cleanups = [];
    run.allow = [];
    run.target = null;
    run.pin = '';
    run.token += 1;
  }
  function every(ms, fn) {
    const id = setInterval(fn, ms);
    run.timers.push(id);
    return id;
  }
  function later(ms, fn) {
    const token = run.token;
    run.timers.push(setTimeout(() => { if (run && run.token === token) fn(); }, ms));
  }
  function waitFor(test, then, ms = 250) {
    const token = run.token;
    const id = every(ms, () => {
      if (!run || run.token !== token) { clearInterval(id); return; }
      let ok = false;
      try { ok = test(); } catch (_) {}
      if (ok) { clearInterval(id); then(); }
    });
  }
  function listen(target, type, fn) {
    target.addEventListener(type, fn);
    run.cleanups.push(() => target.removeEventListener(type, fn));
  }
  function stop() {
    if (run) resetStep();
    run = null;
    cancelAnimationFrame(frame);
    detachGuard();
    if (ui) ui.root.hidden = true;
    lastPlace = '';
  }

  // ── 基本操作（初回だけ・強制） ──
  const chatOpen = () => {
    const panel = $('#result');
    return !!panel && !panel.hidden && !panel.classList.contains('mini') && visible(panel);
  };
  const userMessages = () => document.querySelectorAll('#chat-log .chat-msg.user').length;
  const detailOpen = () => { const panel = $('#detail-panel'); return !!panel && panel.classList.contains('open'); };
  function minimizeChat() {
    try {
      if (chatOpen() && typeof window.minimizeResult === 'function') { window.minimizeResult(); return true; }
    } catch (_) {}
    return false;
  }
  async function boardTasks() {
    try {
      const response = await fetch('/board/data', {cache: 'no-store'});
      if (!response.ok) return null;
      const data = await response.json();
      return Array.isArray(data.tasks) ? data.tasks : null;
    } catch (_) { return null; }
  }
  function newTask(tasks) {
    if (!tasks || !baseline) return null;
    const known = new Set(baseline);
    const fresh = tasks.filter(item => item && item.id && !known.has(item.id));
    if (!fresh.length) return null;
    fresh.sort((a, b) => String(b.created || '').localeCompare(String(a.created || '')));
    const pick = fresh.find(item => item.status !== 'done') || fresh[0];
    return {id: pick.id, title: pick.title || pick.id};
  }
  function findChip(id) {
    return Array.from(document.querySelectorAll('#wall-container .chip'))
      .find(el => el.dataset.goto === id && visible(el)) || null;
  }
  function findNav(href) {
    const mobile = window.matchMedia && matchMedia('(max-width: 700px)').matches;
    const groups = document.querySelectorAll(mobile ? '.bottom-nav .bn-grp' : '.hd-nav .navgrp-btn');
    for (const group of groups) {
      const pop = group._navpop || group.nextElementSibling;
      const link = pop && pop.querySelector ? pop.querySelector('a[href="' + href + '"]') : null;
      if (link) {
        return {group, pop, item: pop.classList.contains('on') ? link : null,
          groupText: (group.querySelector('.bn-label') || group).textContent, itemText: link.textContent};
      }
    }
    const direct = document.querySelector((mobile ? '.bottom-nav' : '.hd-nav') + ' a[href="' + href + '"]');
    return direct ? {group: null, pop: null, item: direct, groupText: '', itemText: direct.textContent} : null;
  }
  const coreCard = extra => Object.assign({kind: L.kind_core}, extra);

  function startCore(stepId) {
    stop();
    const core = (state && state.core) || {};
    task = core.task || null;
    baseline = core.baseline || null;
    run = {kind: 'core', timers: [], cleanups: [], allow: [], token: 0, step: '', onEscape: nudge};
    attachGuard();
    buildUi();
    track();
    goCore(CORE_ORDER.includes(stepId) ? stepId : 'welcome');
  }
  function goCore(stepId) {
    if (!run || run.kind !== 'core') return;
    resetStep();
    run.step = stepId;
    const step = CORE[stepId];
    const keepBaseline = stepId === 'chat-send' || stepId === 'task-wait';
    saveState({core: {status: 'active', step: stepId, task: task, baseline: keepBaseline ? baseline : null}});
    if (step.page && step.page !== PAGE) { navStep(step.page, step.count); return; }
    step.enter();
  }
  // 別の画面で行うステップ: ナビの該当箇所を照らして、そこだけ押せるようにする。
  function navStep(page, count) {
    const minimized = minimizeChat();
    const href = PAGES[page];
    const locate = () => findNav(href);
    run.allow = [() => { const nav = locate(); return nav ? [nav.group, nav.item] : []; }];
    run.target = () => {
      const nav = locate();
      if (!nav) return null;
      if (nav.item && visible(nav.item)) return nav.item;
      return nav.group && visible(nav.group) ? nav.group : null;
    };
    const nav = locate();
    if (!nav) {
      run.allow = [];
      show(coreCard({count, title: fmt(L.nav_title, {page: NAMES[page]}),
        body: fmt(L.nav_body_missing, {page: NAMES[page]}),
        primary: {label: fmt(L.nav_title, {page: NAMES[page]}), onClick: () => { location.href = href; }}}));
      return;
    }
    const name = clean(nav.itemText) || NAMES[page];
    const body = nav.group ? fmt(L.nav_body_group, {group: clean(nav.groupText), page: name})
      : fmt(L.nav_body_direct, {page: name});
    show(coreCard({count, title: fmt(L.nav_title, {page: name}),
      body: minimized ? body + '\n' + L.nav_chat_note : body, focus: nav.group || nav.item}));
  }

  const CORE = {
    'welcome': {enter() {
      show(coreCard({title: L.welcome_title, body: L.welcome_body, status: L.welcome_note,
        primary: {label: L.start, onClick: () => goCore('chat-open')}}));
    }},
    'chat-open': {count: '1 / 4', enter() {
      if (chatOpen()) { goCore('chat-send'); return; }
      run.allow = ['#chat-fab', '#result-mini'];
      run.target = () => firstVisible(['#chat-fab', '#result-mini']);
      show(coreCard({count: '1 / 4', title: L.chat_open_title, body: L.chat_open_body,
        focus: run.target() || undefined}));
      waitFor(chatOpen, () => goCore('chat-send'));
      later(5000, () => {
        if (run.target()) return;
        show(coreCard({count: '1 / 4', title: L.chat_open_title, body: L.chat_missing,
          primary: {label: L.to_home, onClick: () => { location.href = '/'; }}}));
      });
    }},
    'chat-send': {count: '2 / 4', enter() {
      if (!chatOpen()) { goCore('chat-open'); return; }
      run.allow = ['#chat-input', '#chat-send-btn'];
      run.target = () => firstVisible(['#chat-input-row', '#chat-input']);
      const input = $('#chat-input');
      if (input && !input.value.trim()) {
        input.value = L.send_prefill;
        input.dispatchEvent(new Event('input', {bubbles: true}));
      }
      show(coreCard({count: '2 / 4', title: L.send_title, body: L.send_body, focus: input || undefined}));
      if (input) { try { input.setSelectionRange(input.value.length, input.value.length); } catch (_) {} }
      const owner = run;
      const before = userMessages();
      let sent = false;
      listen(window, 'shuki:chat', event => { if (event.detail && event.detail.type === 'sent') sent = true; });
      // 頼む前にあったタスクを控える（このあと増えた1件が「頼んだタスク」）。
      boardTasks().then(tasks => {
        // A quick submission advances the step while this snapshot is still loading.
        if (run !== owner || !tasks || task || !['chat-send', 'task-wait'].includes(run.step)) return;
        baseline = tasks.map(item => item.id);
        saveState({core: {status: 'active', step: run.step, baseline}});
      });
      waitFor(() => sent || userMessages() > before, () => goCore('task-wait'));
    }},
    'task-wait': {count: '2 / 4', enter() {
      if (task) { taskFound(task); return; }
      run.allow = ['#chat-log', '#chat-input', '#chat-send-btn'];
      run.target = () => firstVisible(['#chat-log', '#result']);
      run.pin = 'top';
      const base = {count: '2 / 4', title: L.wait_title, focus: 'none'};
      show(coreCard(Object.assign({body: L.wait_body, status: L.wait_status}, base)));
      const token = run.token;
      const owner = run;
      const started = Date.now();
      let reply = null, fallback = false, busy = false;
      listen(window, 'shuki:chat', event => {
        const detail = event.detail || {};
        if (detail.type === 'reply') reply = {status: detail.status, at: Date.now()};
        if (detail.type === 'sent') reply = null;
      });
      const check = async () => {
        if (busy) return;
        busy = true;
        const tasks = await boardTasks();
        busy = false;
        if (run !== owner || run.token !== token) return;
        const found = newTask(tasks);
        if (found) { taskFound(found); return; }
        const now = Date.now();
        // 返答が終わってもタスクが増えない（索引の更新は約10秒ごと）・失敗・長すぎる時だけ、先へ進む道を出す。
        const settled = reply && (reply.status !== 'done' || now - reply.at > 15000);
        if (!fallback && (settled || now - started > 180000)) {
          fallback = true;
          show(coreCard(Object.assign({body: reply && reply.status === 'error' ? L.wait_error : L.wait_none,
            alt: {label: L.continue_anyway, onClick: () => { task = null; goCore('board-find'); }}}, base)));
        }
      };
      every(3000, check);
      check();
    }},
    'board-find': {page: 'board', count: '3 / 4', enter() {
      const base = {count: '3 / 4', title: L.board_title};
      show(coreCard(Object.assign({body: L.board_loading, focus: 'none'}, base)));
      const begin = Date.now();
      const ready = () => !visible($('#loading')) && (visible($('#wall-container')) || visible($('#empty-state')));
      let mode = '';
      // ボードは読み込み後にも描き直す（絞り込み・再取得）ので、カードの有無を追い続けて表示を合わせる。
      const render = () => {
        const chip = task ? findChip(task.id) : null;
        const next = chip ? 'chip' : (task ? 'hidden' : 'generic');
        if (next === mode) return;
        mode = next;
        if (chip) {
          try { chip.scrollIntoView({block: 'center', behavior: smooth()}); } catch (_) {}
          run.allow = [() => findChip(task.id)];
          run.target = () => findChip(task.id) || firstVisible(['#wall-container', '#wall-wrap']);
          show(coreCard(Object.assign({body: fmt(L.board_found, {title: task.title}), focus: chip}, base)));
        } else if (task) {
          run.allow = [];
          run.target = () => firstVisible(['#wall-container', '#wall-wrap']);
          show(coreCard(Object.assign({body: fmt(L.board_hidden, {title: task.title}),
            primary: {label: L.open_details, onClick: () => {
              try { if (typeof window.showDetail === 'function') window.showDetail(task.id); } catch (_) {}
            }},
            alt: {label: L.next, onClick: () => goCore('cal-results')}}, base)));
        } else {
          run.target = () => firstVisible(['#wall-container .chip', '#wall-container', '#wall-wrap']);
          show(coreCard(Object.assign({body: L.board_generic,
            primary: {label: L.next, onClick: () => goCore('cal-results')}}, base)));
        }
      };
      if (task) {  // 読み込み表示の間に押されても通す（カードが出た瞬間に押す人を止めない）
        run.allow = [() => findChip(task.id)];
        waitFor(detailOpen, () => goCore('board-detail'));
      }
      waitFor(() => (task && findChip(task.id)) || (ready() && Date.now() - begin > 2500)
        || Date.now() - begin > 12000, () => {
        render();
        if (task) every(500, render);
      });
    }},
    'board-detail': {page: 'board', count: '3 / 4', enter() {
      if (!detailOpen()) { goCore('board-find'); return; }
      run.target = () => firstVisible(['#detail-panel']);
      run.pin = 'top';
      show(coreCard({count: '3 / 4', title: L.detail_title, body: L.detail_body,
        primary: {label: L.next, onClick: () => {
          try { if (typeof window.closeDetail === 'function') window.closeDetail(); } catch (_) {}
          goCore('cal-results');
        }}}));
    }},
    'cal-results': {page: 'calendar', count: '4 / 4', enter() {
      const shown = () => {
        const tab = $('#cal-tab-results');
        return !!tab && tab.getAttribute('aria-selected') === 'true'
          && !!document.querySelector('#cal-month-grid .results-cell');
      };
      if (shown()) { goCore('cal-today'); return; }
      run.allow = ['#cal-tab-results', '#cal-day-detail [data-retry]'];
      run.target = () => firstVisible(['#cal-tab-results']);
      show(coreCard({count: '4 / 4', title: L.cal_title, body: L.cal_results_body,
        focus: $('#cal-tab-results') || undefined}));
      waitFor(shown, () => goCore('cal-today'));
      let fallback = false;
      const offerFallback = () => {
        if (fallback || shown()) return;
        fallback = true;
        show(coreCard({count: '4 / 4', title: L.cal_title, body: L.cal_unavailable,
          alt: {label: L.continue_anyway, onClick: () => goCore('finish')}}));
      };
      every(250, () => {
        if ($('#cal-tab-results') && $('#cal-tab-results').getAttribute('aria-selected') === 'true'
            && visible($('#cal-day-detail .cal-error'))) offerFallback();
      });
      later(12000, offerFallback);
    }},
    'cal-today': {page: 'calendar', count: '4 / 4', enter() {
      run.target = () => firstVisible(['#cal-month-grid .cal-cell.is-today', '#cal-month-grid']);
      const cell = run.target();
      if (cell) { try { cell.scrollIntoView({block: 'center', behavior: smooth()}); } catch (_) {} }
      show(coreCard({count: '4 / 4', title: L.cal_title, body: L.cal_today_body,
        primary: {label: L.next, onClick: () => goCore('cal-detail')}}));
    }},
    'cal-detail': {page: 'calendar', count: '4 / 4', enter() {
      const section = () => task ? Array.from(document.querySelectorAll('#cal-day-detail .cal-result-section'))
        .find(el => el.textContent.includes(task.title) && visible(el)) || null : null;
      const listed = !!section();
      run.target = () => section() || firstVisible(['#cal-day-detail']);
      const el = run.target();
      if (el) { try { el.scrollIntoView({block: 'center', behavior: smooth()}); } catch (_) {} }
      show(coreCard({count: '4 / 4', title: L.cal_title,
        body: listed ? fmt(L.cal_detail_found, {title: task.title}) : L.cal_detail_generic,
        primary: {label: L.next, onClick: () => goCore('finish')}}));
    }},
    'finish': {enter() {
      show(coreCard({title: L.finish_title, body: L.finish_body,
        primary: {label: L.finish, onClick: async () => {
          ui.primary.disabled = true;
          const saved = await saveState({core: {status: 'done', step: 'finish', task: null, baseline: null}});
          if (!saved) {
            ui.status.textContent = L.save_failed;
            ui.primary.disabled = false;
            return;
          }
          task = null;
          baseline = null;
          stop();
        }}}));
    }},
  };
  function taskFound(found) {
    task = found;
    baseline = null;
    resetStep();
    run.target = () => firstVisible(['#chat-log', '#result']);
    run.pin = 'top';
    saveState({core: {status: 'active', step: 'task-wait', task, baseline: null}});
    show(coreCard({count: '2 / 4', title: L.found_title, body: fmt(L.found_body, {title: task.title}),
      primary: {label: L.next, onClick: () => goCore('board-find')}}));
  }

  // ── 画面ガイド（各画面の初回だけ・スキップ可） ──
  function startGuide(page) {
    const steps = GUIDES[page];
    if (!steps || !steps.length) return;
    stop();
    run = {kind: 'guide', page, steps, index: 0, timers: [], cleanups: [], allow: [], token: 0,
      onEscape: () => endGuide()};
    attachGuard();
    buildUi();
    track();
    guideStep(0);
  }
  function guideStep(index) {
    resetStep();
    const steps = run.steps;
    const step = steps[index];
    const last = index === steps.length - 1;
    run.index = index;
    run.target = () => firstVisible(step.sel);
    const el = run.target();
    if (el) { try { el.scrollIntoView({block: 'nearest', behavior: smooth()}); } catch (_) {} }
    show({kind: L.kind_guide, count: (index + 1) + ' / ' + steps.length, title: step.title, body: step.body,
      skip: last ? null : {label: L.skip_guide, onClick: endGuide},
      back: index ? {label: L.back, onClick: () => guideStep(index - 1)} : null,
      primary: {label: last ? L.done : L.next, onClick: () => (last ? endGuide() : guideStep(index + 1))}});
  }
  function endGuide() {
    if (!run || run.kind !== 'guide') return;
    const page = run.page;
    stop();
    saveState({page});
  }
  function maybeGuide() {
    if (!PAGE || !GUIDES[PAGE] || !state || state.guides === false || (state.pages || {})[PAGE]) return;
    const first = GUIDES[PAGE][0];
    const begin = Date.now();
    const id = setInterval(() => {
      if (run) { clearInterval(id); return; }
      if (firstVisible(first.sel) || Date.now() - begin > 2500) { clearInterval(id); startGuide(PAGE); }
    }, 200);
  }

  window.ShukiTutorial = {
    async replayCore() {
      const next = await saveState({reset: 'core'});
      if (!next) return false;
      startCore('welcome');
      return true;
    },
    async resetGuides() { return !!(await saveState({reset: 'pages'})); },
    async setGuides(on) { return !!(await saveState({guides: !!on})); },
    startGuide(page) { startGuide(page || PAGE); },
    status() { return run ? {kind: run.kind, step: run.kind === 'core' ? run.step : run.index, page: PAGE} : null; },
    async settings(action, control) {
      const message = document.getElementById('tut-settings-msg');
      let ok = false;
      if (action === 'replay') { ok = await this.replayCore(); if (ok) return; }
      else if (action === 'reset') ok = await this.resetGuides();
      else if (action === 'guides') ok = await this.setGuides(control.checked);
      if (!ok && action === 'guides') control.checked = !control.checked;
      if (!message) return;
      message.textContent = !ok ? L.save_failed : action === 'reset' ? L.guides_reset_msg
        : (control.checked ? L.guides_on_msg : L.guides_off_msg);
    },
  };

  async function boot() {
    try { state = await fetchState(); } catch (_) { return; }
    if (AUTOMATED || run) return;
    const core = state.core || {};
    if (core.status === 'pending') { startCore('welcome'); return; }
    if (core.status === 'active') { startCore(core.step); return; }
    maybeGuide();
  }
  boot();
})();
"""
