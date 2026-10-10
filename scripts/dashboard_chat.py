"""対話ドック（チャットパネル）の CSS / HTML / JS。

2026-08-11 に dashboard_server.py のホームページから切り出し、**全ページ共通**にした。
各ページは head に assets_head()、body の bottom_nav_html() の直後に dock_html() を置くだけ
（配線は PWA_HEAD / bottom_nav_html と同じ流儀。静的ページは inject_shell が面倒を見る）。

SHUKI はページごとに完全なHTMLを返すMPAなので、遷移すればDOMは必ず破棄される。
「ドックが消えずに残る」のは、離脱時に会話を sessionStorage へ退避し遷移先で描き直しているから
（saveDockState / restoreDockState）。応答待ちのまま移ってもジョブIDを持ち越して
ポーリングを再開するので、結果を取りこぼさない。

body の先頭側（下部ナビの直後）に置くのが要点。ドックのスクリプトが各ページ自前のJSより
先に走る必要がある。逆に、グローバルの短い名前は一切奪わない（getElementById の短縮は
$ ではなく byId。$ は習慣・図鑑・家計・草の app.js が別の意味で使っている）。

MODELS をここに置いているのは、モデル一覧が「ドックがどのモデルで走ったか表示する」ために
必要で、かつ全ページのドックが参照するため。dashboard_server 側はエイリアスで参照している。
"""
import json
from pathlib import Path

import dashboard_icons
import dashboard_mascot
import dashboard_settings  # モデルごとのeffort設定（model_effort）。ドックのeffortセレクトが参照・更新する
import model_registry
import shuki_i18n  # 表示言語の切り替え（lang=ja なら素通し）

# fable のみ CLI にエイリアスが無く "fable" では 404 になるためフルID指定が必要（2026-07-19 判明）。
# Muse はローカル Ollama（local/ プレフィックス・cost=$0・PC外に出ない）。ollama launch claude で
# 疎通確認済みだが reasoning が長く一言の応答にも数十秒かかる（実測41秒・2026-08-14）。実験的。
MODELS = model_registry.dashboard_models()
MODEL_VALUES = model_registry.dashboard_values()
MODEL_RISK_WINDOW_JSON = json.dumps(model_registry.risk_windows(), ensure_ascii=False, separators=(",", ":"))
MODEL_USAGE_EXEMPT_JSON = json.dumps(model_registry.usage_exempt_dashboard_models(), ensure_ascii=False,
                                     separators=(",", ":"))

# 対話ドックの意味的アイコンは dashboard_icons.UI_PATHS を単一情報源にする。
# HTML の静的部分と JS の動的メッセージの両方が同じ SVG を使うため、ここで一度だけ組み立てる。
_CHAT_ICON_KEYS = ("play", "stop", "refresh", "speaker", "maximize", "minimize", "shrink", "cross", "attach",
                   "mic", "send", "hourglass", "check", "comment", "clock", "warn", "pencil", "settings", "copy")

# The server supplies its existing launcher catalog; the dock owns no duplicate list.
_skill_catalog_getter = lambda: []


def set_skill_catalog_getter(fn):
    global _skill_catalog_getter
    _skill_catalog_getter = fn


def _chat_icon(key, size=14, cls="chat-icon"):
    return dashboard_icons.ui_icon_svg(key, size, cls)


CHAT_ICON_JSON = json.dumps(
    {key: _chat_icon(key, 14, "chat-icon spin" if key == "loading" else "chat-icon")
     for key in _CHAT_ICON_KEYS + ("loading",)},
    ensure_ascii=False, separators=(",", ":"))

# ドックのモデルチップに「今のモデル」を反映するためのフック。dashboard_chat 自身は
# サーバーの状態を持たないので、dashboard_server.py が起動時に set_current_model_getter()
# で実体（CURRENT_MODEL を読む関数）を差し込む。未登録ならレジストリの既定値を使う。
_current_model_getter = lambda: model_registry.dashboard_model("dashboard_default")
_auto_model_mode_getter = lambda: False


def set_current_model_getter(fn):
    global _current_model_getter
    _current_model_getter = fn


def set_auto_model_mode_getter(fn):
    global _auto_model_mode_getter
    _auto_model_mode_getter = fn


CSS = r'''

  /* 💬 対話ドック（2026-08-07 ユーザーの投函メモ）: 画面右下に固定し、裏のページは自由にスクロール
     できる＝応答待ちの間にメモ投函や他セクション閲覧を並行できる。中でスクロールするのは
     #chat-log だけなので、ヘッダー（閉じる・読み上げ）と入力欄は文章量に関わらず常に見える
     （旧: ページフロー内に置いていたため長文だと両方とも画面外へ流れていた）。 */
  .result { background:var(--card); border:1px solid var(--accent); border-radius:12px;
    padding:14px 16px; margin-bottom:16px; }
  #result:not([hidden]) { position:fixed; right:16px; bottom:16px; z-index:1300; margin-bottom:0;
    width:min(560px, 46vw); max-height:min(74vh, 720px); box-sizing:border-box; min-width:0;
    display:flex; flex-direction:column; box-shadow:0 8px 32px #00000055; }
  #result.mini { display:none; }
  /* 最大化（2026-08-13 ユーザーの投函メモ）: ブラウザの最大化と同じ振る舞い＝ボタン1つが
     最大化⇄縮小に入れ替わる。長い対話を読む／集中して打ち込む時に、裏のページを
     気にせず画面を使い切るための状態。閉じる・最小化とは独立（畳んでも記憶する）。 */
  #result.maxi:not([hidden]) { left:16px; top:16px; right:16px; bottom:16px;
    width:auto; max-height:none; }
  .result-head { display:flex; align-items:center; gap:10px; margin-bottom:8px; font-weight:bold;
    flex:0 0 auto; flex-wrap:wrap; min-width:0; }
  #result-title { min-width:0; max-width:100%; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
  /* モデル選択（2026-09-27 チップ列→ドロップダウン化）: ドック常設。旧・ホーム画面専用の
     独立バーを吸収し、対話の途中（フォローアップ発言）はここで選んだモデルがそのまま次発言から
     効く。9モデル分のチップが折り返して3行を占め、スマホでチャットログの取り分を圧迫していた
     ため、単一の<select>1行に畳んだ（ユーザーのフィードバック）。同時にモデルごとのeffortも並べて
     置けるようになった＝従来は/settingsページでしか変えられなかった思考量を、対話中その場で
     切り替えられる（一発実行スキル（[data-exec-skill]）だけは、押した時点でドックが未オープンの
     ためこのUIに事前に触れる手段が無い → model-pick popup で補う（下記）。 */
  .model-row { display:flex; align-items:center; gap:6px; margin-bottom:6px; font-size:.78rem;
    flex:0 0 auto; }
  .model-select, .effort-select { border:1px solid var(--line); border-radius:8px; background:var(--bg);
    color:var(--fg); font-family:inherit; font-size:.78rem; padding:3px 6px; }
  .model-select { flex:1 1 auto; min-width:0; }
  .model-row label { flex:0 0 auto; color:var(--muted); }
  .effort-select { flex:0 0 auto; }
  .effort-select[hidden] { display:none; }
  .model-select:focus, .effort-select:focus { outline:none; border-color:var(--accent); }
  .model-select.mchip-risk { border-color:var(--red); color:var(--red); }
  .auto-model-status { color:var(--muted); font-size:.7rem; min-height:1em; flex:0 0 auto; }
  /* モデル選択ポップアップ（2026-08-16）: スキルボタン（[data-exec-skill]）を押した瞬間は
     まだドックが開いておらず常設チップに触れないため、ここでモデルだけ先に選ばせてから
     ドックへ実行結果を出す。選ぶと即実行＝確認ボタンを別途置かない（タップ数を増やさない）。 */
  /* board のデスクトップ詳細パネル(#detail-panel)が z-index:1200 で中央モーダル化した
     （2026-09-01）ため、その裏に隠れないよう、この一発実行ポップアップ・後続の対話ドック
     （#result・#result-mini）は詳細パネルより高いレイヤーに置く。 */
  .model-pick-overlay { position:fixed; inset:0; z-index:1300; background:#00000066;
    display:flex; align-items:center; justify-content:center; padding:16px; }
  .model-pick-overlay[hidden] { display:none; }
  .model-pick-card { background:var(--card); border:1px solid var(--accent); border-radius:14px;
    padding:20px 22px; box-shadow:0 8px 32px #00000055; max-width:min(360px, 88vw); text-align:center; }
  .mp-title { font-weight:bold; margin-bottom:14px; }
  /* 任意コメント欄（2026-09-05）: 「このタスクもう終わってたはず」「こういう方針で進めたい」等を
     実行前に添えられるようにする。フェーズA（方針提示→ユーザーの返答待ち）を素通りできる分だけ
     往復のクレジットを削れる、というユーザーの狙い通りの導線。空なら送らない＝既存の動きに影響しない。 */
  .mp-comment { width:100%; box-sizing:border-box; resize:vertical; min-height:52px; max-height:160px;
    margin-bottom:14px; padding:8px 10px; border:1px solid var(--line); border-radius:8px;
    background:var(--bg); color:var(--fg); font-family:inherit; font-size:.84rem; }
  .mp-comment:focus { outline:none; border-color:var(--accent); }
  .mp-chips { display:flex; flex-wrap:wrap; gap:8px; justify-content:center; margin-bottom:14px; }
  .mchip-pick { border:1px solid var(--line); border-radius:20px; padding:6px 16px; color:var(--fg);
    background:none; cursor:pointer; font-size:.9rem; font-family:inherit; }
  .mchip-pick:hover { border-color:var(--accent); }
  .mchip-pick.active { border-color:var(--teal); color:var(--teal); font-weight:bold; }
  .chat-icon { vertical-align:-3px; flex:none; }
  .rbtn .chat-icon { margin-right:3px; }
  /* クレジット残量エフェクト（2026-09-01）: 5時間枠/週次枠の使用率が高いのに reset がまだ遠い
     モデルだけ赤く「推奨しない」を示す（「おすすめ」でなく「非推奨」を効かせる方針・投函メモどおり）。
     2アカウントとも同時に苦しい時だけ点く＝片方に空きがあれば自動切替が拾うので実害が出ないため。
     .active より後ろに書いて選択中でも赤を優先させる。 */
  .mchip-pick.mchip-risk { border-color:var(--red); color:var(--red); }
  .mp-cancel { width:100%; }
  /* 最小化バー: 会話（chatSession・ポーリング）は生かしたまま見た目だけ畳む。裏のページを
     自由にスクロール・操作したい時に「閉じずに」逃がす場所（旧: 閉じる以外の選択肢が無く、
     戻るには実行履歴から選び直すしかなかった）。 */
  #result-mini[hidden] { display:none; }
  #result-mini:not([hidden]) { position:fixed; right:16px; bottom:16px; z-index:1300; display:flex; align-items:center;
    gap:8px; background:var(--card); border:1px solid var(--accent); border-radius:24px;
    padding:8px 14px; cursor:pointer; box-shadow:0 4px 16px #00000044; max-width:min(320px, 60vw); }
  #result-mini:hover { border-color:var(--teal); }
  #result-mini .rm-label { font-size:.82rem; font-weight:bold; overflow:hidden; text-overflow:ellipsis;
    white-space:nowrap; }
  #result-mini .rm-status { flex-shrink:0; }
  #result-mini .rm-close { flex-shrink:0; color:var(--muted); padding:0 2px; }
  #result-mini .rm-close:hover { color:var(--red); }
  #result-mini.unread { border-color:var(--teal); animation:achnewpulse 1.6s ease-in-out infinite; }
  .result-actions { margin-left:auto; display:flex; flex-wrap:wrap; gap:8px; max-width:100%; }
  .rbtn { background:none; border:1px solid var(--line); color:var(--muted); border-radius:8px;
    padding:3px 10px; cursor:pointer; font-size:.8rem; text-decoration:none; font-family:inherit; }
  .rbtn:hover { color:var(--fg); border-color:var(--accent); }
  .rbtn.on { color:var(--teal); border-color:var(--teal); }
  /* ヘッダーの操作ボタン列（2026-09-27）: スマホ幅ではラベル文字を隠しアイコンのみにする
     （下の @media 700px ブロックで .rbtn-label を display:none）。アイコンだけでは何のボタンか
     わからなくなるので title は必ず添える＝アイコンのみでもアクセシブルネームは保つ。 */
  #voice-bar { padding:8px 12px; display:flex; gap:8px; flex-wrap:wrap; align-items:center; }
  #voice-bar[hidden] { display:none; }
  /* 2026-09-14: 音声会話中の言語/宛先/ポーズ設定は常時展開だと縦に何段も積み上がり、
     モバイルでは「設定画面」がほぼ画面全体を占めて会話が見えなくなっていた。
     既定で畳んでおき、必要な時だけ開く（閉じるボタンの代わりに details で自己完結）。 */
  #voice-settings { flex-basis:100%; }
  #voice-settings > summary { cursor:pointer; color:var(--muted); font-size:.78rem; min-height:26px;
    display:flex; align-items:center; list-style:none; }
  #voice-settings > summary::-webkit-details-marker { display:none; }
  #voice-settings[open] > summary { color:var(--fg); }
  /* 2026-09-27: ラベルを短縮しフォントを一段落とし、開いた時に占める行数を減らした
     （「Recognition and replies」等の長い文言が折り返して2〜3行になっていた）。 */
  #voice-settings-fields { display:flex; gap:10px; flex-wrap:wrap; align-items:center; margin-top:4px;
    font-size:.74rem; color:var(--muted); }
  #voice-settings-fields label { display:flex; align-items:center; gap:4px; }
  #voice-settings-fields select { font-size:.76rem; padding:2px 4px; }
  #voice-work-card { margin:0 12px 8px; padding:10px; border:1px solid var(--line);
    border-radius:10px; overflow-wrap:anywhere; flex:1 1 auto; min-height:0; display:flex; overflow:hidden; }
  /* バックグラウンド作業カードは会話ログとは別の「作業」タブ（tab-tabs内）に切り出す
     （2026-09-26 ユーザーのフィードバック：音声会話中に毎回この幅広カードが会話を圧迫していた）。
     表示/非表示は #conversation-view と #voice-work-card の hidden 属性を
     toggleWorkTab()/exitWorkTab() が排他的に切り替えるだけで、CSS側の特別な分岐は不要。 */
  #conversation-view { display:flex; flex-direction:column; flex:1 1 auto; min-height:0; min-width:0; }
  #conversation-view[hidden] { display:none; }
  #voice-work-card[hidden], #voice-proposal[hidden], #voice-work-progress[hidden] { display:none; }
  #voice-work-card button { min-height:44px; margin-top:6px; }
  #voice-work-progress { display:flex; flex-direction:column; gap:4px; flex:1; min-height:0; min-width:0; }
  #voice-work-progress > :not(#voice-work-messages) { flex:0 0 auto; }
  #voice-work-messages { flex:1 1 auto; min-height:0; overflow:auto; font-size:.86rem; line-height:1.7; }
  .work-message { margin:8px 0; padding:8px; border:1px solid var(--line); border-radius:8px; }
  .work-message-label { font-size:.78rem; font-weight:600; color:var(--muted); }
  .work-message-user { background:var(--bg); }
  .work-message-body { overflow-wrap:anywhere; }
  .work-message-body pre, .work-message-body .cm-table-wrap { overflow-x:auto; }
  .work-message-body img { max-width:100%; }
  #voice-work-send-state { font-size:.8rem; color:var(--muted); }
  #voice-work-send-state[data-error="true"] { color:var(--danger); }
  #voice-work-question { max-height:100px; overflow:auto; white-space:pre-wrap; }
  #voice-work-extra { margin-top:1px; }
  #voice-work-extra > summary { cursor:pointer; color:var(--muted); font-size:.78rem; min-height:30px;
    display:flex; align-items:center; }
  #voice-work-model, #voice-work-latest { white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
  @media (max-width:700px) {
    #voice-work-card { margin:0 8px 4px; padding:6px 8px; border-radius:8px; }
    #voice-work-card button { min-height:36px; margin-top:2px; padding:2px 8px; }
    #voice-work-status { font-size:.84rem; }
    #voice-work-model, #voice-work-latest { font-size:.72rem; line-height:1.3; }
    #voice-work-extra[open] { padding-top:1px; }
    #voice-work-extra > summary { min-height:30px; }
    #voice-work-detail { max-height:120px; }
    #voice-work-reply { min-height:38px; }
  }
  #voice-work-latest, #voice-work-question, #voice-work-model { overflow-wrap:anywhere; }
  #voice-work-reply { min-height:44px; max-height:100px; box-sizing:border-box; resize:vertical; font:inherit; }
  #voice-work-summary { white-space:pre-wrap; max-height:140px; overflow:auto; }
  #voice-work-detail { max-height:180px; overflow:auto; }
  #voice-work-status { font-weight:600; }
  #voice-work-note, #voice-proposal-error { font-size:.8rem; margin-top:4px; }
  #voice-work-approval-hint { color:var(--muted); font-size:.8rem; margin-top:4px; }
  #voice-conversation-hint { margin:0 12px 6px; color:var(--muted); font-size:.8rem; }
  #voice-conversation-hint[hidden], #voice-result[hidden] { display:none; }
  #voice-ielts-finish[hidden], #voice-ielts-answer[hidden] { display:none; }
  #voice-result > summary { cursor:pointer; min-height:44px; display:flex; align-items:center;
    color:var(--accent); font-weight:600; }
  .voice-sources { display:flex; flex-wrap:wrap; gap:6px; margin-top:8px; font-size:.78rem; }
  .voice-sources a { border:1px solid var(--line); border-radius:8px; padding:6px 9px;
    color:var(--muted); text-decoration:underline; overflow-wrap:anywhere; }
  #voice-status { flex:1 1 150px; font-size:.8rem; overflow-wrap:anywhere; }
  #voice-language { font-weight:600; color:var(--teal); white-space:nowrap; }
  #result [hidden] { display:none !important; }
  #voice-bar button, #voice-bar select, #voice-btn { min-height:44px; }
  @keyframes pulse { 50% { opacity:.4; } }
  .msg-actions { display:flex; align-items:center; gap:4px; margin-top:4px; }
  .msg-copy, .msg-speak { display:inline-flex; align-items:center; justify-content:center; gap:4px;
    min-height:28px; box-sizing:border-box; padding:2px 6px; border:0; border-radius:6px;
    background:none; color:var(--muted); font:inherit; font-size:.74rem;
    text-decoration:none; cursor:pointer; }
  .msg-actions .chat-icon { margin:0; display:block; }
  .msg-copy:hover, .msg-speak:hover { color:var(--fg); background:var(--line); }
  .msg-copy:focus-visible, .msg-speak:focus-visible { outline:2px solid var(--accent); outline-offset:2px; }
  .msg-copy[data-state="copied"] { color:var(--ok); }
  .msg-copy[data-state="error"] { color:var(--danger); }
  @media (pointer:coarse) {
    .msg-copy, .msg-speak { min-height:44px; min-width:44px; }
  }
  /* 🗂 タブ帯（2026-09-25）: 複数の対話セッションを切り替える。1本しか無くても常設して
     「＋」で増やせることを常に見せる。非アクティブなタブのDOM(.tab-pane)は消さず隠すだけ
     （poll() が背後で書き込み続けられるようにするため）。 */
  .chat-tabs { display:flex; gap:4px; margin-bottom:6px; overflow-x:auto; flex:0 0 auto; }
  .chat-tab { display:flex; align-items:center; gap:5px; padding:4px 8px 4px 10px; border-radius:14px;
    border:1px solid var(--line); background:none; color:var(--muted); font-size:.76rem;
    cursor:pointer; white-space:nowrap; flex:0 0 auto; max-width:150px; font-family:inherit; }
  .chat-tab .ct-label { overflow:hidden; text-overflow:ellipsis; white-space:nowrap; max-width:100px; }
  .chat-tab .ct-text { display:flex; flex-direction:column; min-width:0; text-align:left; }
  .chat-tab .ct-model { overflow:hidden; text-overflow:ellipsis; font-size:.65rem;
    font-weight:normal; color:var(--muted); }
  .chat-model-status { flex:0 0 auto; margin-bottom:6px; font-size:.72rem;
    color:var(--muted); overflow-wrap:anywhere; }
  .chat-model-status[hidden] { display:none; }
  .chat-tab .ct-status { display:flex; flex:none; }
  .chat-tab .ct-status .chat-icon { vertical-align:-2px; }
  .chat-tab.active { border-color:var(--teal); color:var(--teal); font-weight:bold; }
  .chat-tab.unread:not(.active) { border-color:var(--accent); color:var(--fg); }
  /* 作業タブ（2026-09-26）: バックグラウンドで進む作業（音声会話から承認して開始したスコープ作業）
     専用の1本。会話タブと見分けがつくよう破線にする。会話タブと違い閉じるボタンは持たない
     （作業が無くなれば renderTabBar() が自然に消す）。 */
  .chat-tab.work-tab { border-style:dashed; }
  .chat-tab.work-tab.active { border-color:var(--accent); color:var(--accent); border-style:solid; }
  .chat-tab .ct-close { display:flex; opacity:.55; border-radius:50%; }
  .chat-tab .ct-close:hover { opacity:1; color:var(--red); }
  .chat-tab-add { flex:0 0 auto; border:1px dashed var(--line); border-radius:14px; padding:3px 11px;
    background:none; color:var(--muted); cursor:pointer; font-size:.9rem; font-family:inherit; line-height:1.4; }
  .chat-tab-add:hover:not(:disabled) { border-color:var(--accent); color:var(--fg); }
  .chat-tab-add:disabled { opacity:.4; cursor:default; }
  #chat-log { font-size:.86rem; line-height:1.7; margin-bottom:10px;
    flex:1 1 auto; min-height:0; min-width:0; overflow-y:auto; overflow-x:hidden; }
  .tab-pane { display:flex; flex-direction:column; gap:10px; min-width:0; }
  .tab-pane[hidden] { display:none; }
  #chat-log code { background:var(--line); border-radius:4px; padding:0 4px; font-size:.8rem; }
  /* AI応答内の markdown ブロック（mdlite が組む・2026-08-11） */
  #chat-log .cm-p { margin:0 0 6px; }
  #chat-log .cm-p:last-child { margin-bottom:0; }
  #chat-log .cm-h { font-weight:bold; margin:8px 0 4px; }
  #chat-log .cm-h:first-child { margin-top:0; }
  #chat-log .cm-list { margin:4px 0 6px; padding-left:1.4em; }
  #chat-log .cm-list li { margin:2px 0; }
  #chat-log .cm-hr { border:none; border-top:1px solid var(--line); margin:8px 0; }
  #chat-log .cm-table-wrap { overflow-x:auto; margin:6px 0; }  /* 幅の広い表はメッセージ内で横スクロール */
  #chat-log .cm-table { border-collapse:collapse; font-size:.78rem; }
  #chat-log .cm-table th, #chat-log .cm-table td { border:1px solid var(--line); padding:3px 7px;
    text-align:left; vertical-align:top; }
  #chat-log .cm-table th { background:var(--line); white-space:nowrap; }
  /* mermaid図・コードブロック・画像・リンク（2026-09-26追加） */
  #chat-log pre.mermaid { background:none; margin:8px 0; text-align:center; overflow-x:auto; }
  #chat-log pre.cm-code { background:var(--line); border-radius:6px; padding:8px 10px; margin:6px 0;
    overflow-x:auto; font: .78rem/1.5 ui-monospace, SFMono-Regular, Consolas, monospace; }
  #chat-log pre.cm-code code { background:none; padding:0; }
  #chat-log .cm-p img { max-width:100%; border-radius:6px; margin:4px 0; display:block; }
  #chat-log .cm-p a { color:var(--accent); }
  /* Long paths and URLs must wrap without widening the shared scroll area. */
  .chat-msg { padding:8px 10px; border-radius:10px; min-width:0; max-width:100%;
    box-sizing:border-box; overflow-wrap:anywhere; }
  .chat-msg.assistant { background:var(--card); border:1px solid var(--line); }
  .chat-msg.user { background:color-mix(in srgb, var(--accent) 12%, transparent); border:1px solid color-mix(in srgb, var(--accent) 33%, transparent); align-self:flex-end; }
  .chat-cursor { opacity:.5; animation:blink 1s step-start infinite; }
  .chat-acct { margin-top:6px; font-size:.68rem; color:var(--muted); }  /* どのClaudeアカウントで走ったか */
  /* ⏹ 停止ボタン（2026-08-18）: 実行中だけ見せる。押すと claude -p プロセスを kill する。 */
  #chat-send-btn.stop-mode { color:var(--red); border-color:color-mix(in srgb, var(--red) 45%, var(--line)); }
  #chat-send-btn.stop-mode:disabled { opacity:.45; cursor:default; }
  .stop-note { margin-top:6px; font-size:.74rem; color:var(--muted); font-style:italic; }
  .chat-msg.user.queued { opacity:.7; border-style:dashed; }
  .queued-note { margin-top:6px; font-size:.74rem; color:var(--muted); display:flex; flex-wrap:wrap; gap:6px; align-items:center; }
  .queued-note button { background:none; border:1px solid var(--line); border-radius:6px; color:var(--fg);
    font-size:.72rem; padding:2px 8px; cursor:pointer; }
  .queued-note button:hover { border-color:var(--accent); }
  @keyframes blink { 50% { opacity:0; } }
  .chat-input-row { display:flex; flex-wrap:nowrap; gap:6px; flex:0 0 auto; position:relative; }
  .chat-input-row > .rbtn { flex:0 0 auto; width:44px; min-height:44px; padding:6px;
    box-sizing:border-box; display:inline-flex; align-items:center; justify-content:center; }
  .chat-input-row > .rbtn .chat-icon, .result-actions .rbtn .chat-icon { margin:0; display:block; }
  .result-actions .rbtn { display:inline-flex; align-items:center; justify-content:center; gap:3px; }
  .result-actions .rbtn[hidden] { display:none; }
  .chat-history { position:absolute; inset:10px; z-index:2; display:flex; flex-direction:column;
    gap:8px; min-width:0; min-height:0; padding:12px; box-sizing:border-box;
    background:var(--card); border:1px solid var(--line); border-radius:10px; }
  .chat-history[hidden] { display:none; }
  .chat-history-head { display:flex; align-items:center; justify-content:space-between; gap:8px; }
  .chat-history-head .rbtn, #history-btn { min-width:44px; min-height:44px; }
  .chat-history input { width:100%; min-width:0; min-height:44px; box-sizing:border-box;
    background:var(--bg); color:var(--fg); border:1px solid var(--line); border-radius:8px;
    padding:8px; font:inherit; font-size:.82rem; }
  .chat-history-results { overflow-y:auto; min-height:0; display:flex; flex-direction:column; gap:4px; }
  .chat-history-item { flex:none; width:100%; min-height:44px; box-sizing:border-box; text-align:left;
    background:none; color:var(--fg); border:1px solid var(--line); border-radius:8px;
    padding:8px; font:inherit; font-size:.82rem; cursor:pointer; overflow-wrap:anywhere; }
  .chat-history-item:hover { border-color:var(--accent); }
  .chat-history-title { display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical; overflow:hidden; }
  .chat-history-item small { display:block; color:var(--muted); margin-top:3px; }
  .chat-history-message { margin:0; color:var(--muted); font-size:.76rem; }
  .chat-history :focus-visible { outline:2px solid var(--accent); outline-offset:-2px; }
  .chat-input-row input { flex:1 1 0; min-width:0; background:var(--bg); border:1px solid var(--line); border-radius:8px;
    color:var(--fg); padding:8px 10px; font-size:.86rem; font-family:inherit; }
  .chat-input-row input:focus { outline:none; border-color:var(--accent); }
  .chat-attach { display:flex; flex-wrap:wrap; gap:6px; margin-bottom:6px; }
  .attach-chip { display:inline-flex; align-items:center; gap:6px; background:var(--card);
    border:1px solid var(--line); border-radius:14px; padding:2px 10px; font-size:.76rem; color:var(--fg);
    min-width:0; max-width:100%; box-sizing:border-box; }
  .attach-chip .attach-name { min-width:0; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
  .attach-chip.up { opacity:.6; }
  .attach-chip .ax { cursor:pointer; color:var(--muted); flex:none; }
  .attach-chip .ax:hover { color:var(--red); }
  .msg-att { font-size:.74rem; color:var(--blue); margin-bottom:4px; }
  /* 🗂 Vault内ファイルを添付ソースに選ぶピッカー（2026-09-14 P1／添付機能の拡張）。
     ローカルアップロード(/upload)と同じ pendingAttachment 経由で送信するため、
     送信ロジック(sendFollowup)は一切変更しない＝ソースが増えるだけ。 */
  /* The picker panels live inside .chat-input-row, so bottom:100% anchors them to the controls
     instead of the fixed #result dock (whose top can move above the viewport on tall conversations). */
  .vault-picker { position:absolute; bottom:100%; left:0; right:0; margin-bottom:6px; z-index:1;
    background:var(--card); border:1px solid var(--line); border-radius:10px;
    padding:8px; max-height:280px; display:flex; flex-direction:column; gap:6px;
    box-shadow:0 6px 20px #00000040; }
  .vault-picker[hidden] { display:none; }
  .vault-picker input { background:var(--bg); border:1px solid var(--line); border-radius:8px;
    color:var(--fg); padding:6px 9px; font-size:.82rem; font-family:inherit; }
  .vault-picker input:focus { outline:none; border-color:var(--accent); }
  .vp-results { overflow-y:auto; display:flex; flex-direction:column; gap:2px; }
  .vp-item { text-align:left; background:none; border:none; color:var(--fg); font-family:inherit;
    padding:6px 7px; border-radius:6px; cursor:pointer; font-size:.8rem; }
  .vp-item:hover { background:var(--bg); }
  .vp-item .vp-folder { display:block; font-size:.68rem; color:var(--muted); margin-top:1px; }
  .vp-empty { font-size:.76rem; color:var(--muted); padding:6px 7px; }
  .skill-picker { position:absolute; bottom:100%; left:0; right:0; margin-bottom:6px; z-index:1;
    background:var(--card); border:1px solid var(--line); border-radius:10px;
    padding:8px; max-height:min(360px, 55dvh); display:flex; flex-direction:column; gap:6px;
    box-sizing:border-box; min-width:0; }
  .skill-picker[hidden] { display:none; }
  .skill-picker p { margin:0; color:var(--muted); font-size:.74rem; }
  .skill-filters { display:flex; flex-wrap:wrap; gap:4px; flex:none; }
  .skill-filter { background:var(--bg); color:var(--fg); border:1px solid var(--line);
    border-radius:8px; padding:6px 8px; min-height:32px; font:inherit; font-size:.74rem; cursor:pointer; }
  .skill-filter[aria-pressed="true"] { border-color:var(--accent); color:var(--accent); }
  .skill-results { overflow-y:auto; min-height:0; }
  .skill-item { display:block; width:100%; box-sizing:border-box; text-align:left; background:none;
    border:none; color:var(--fg); font-family:inherit; padding:8px; border-radius:6px;
    cursor:pointer; font-size:.8rem; min-height:44px; overflow-wrap:anywhere; }
  .skill-item:hover { background:var(--bg); }
  .skill-item small { display:block; color:var(--muted); font-size:.72rem; margin-top:2px; }
  .skill-picker :focus-visible { outline:2px solid var(--accent); outline-offset:-2px; }
  .spin { display:inline-block; animation:spin 1.2s linear infinite; }
  @keyframes spin { to { transform:rotate(360deg); } }
  .result.err { border-color:var(--red); }
  /* 💭 思考ログ（2026-08-16）: 最終応答時に消さず折りたたみで保持。本文より一段沈めた色で
     「主役ではない」ことを示す。既定で閉じておく（毎回読む前提ではなく、必要な時に開く）。 */
  .think-block { margin-bottom:8px; font-size:.78rem; color:var(--muted); border:1px solid var(--line);
    border-radius:8px; padding:4px 8px; }
  .think-block summary { cursor:pointer; user-select:none; }
  .think-block .think-body { margin-top:6px; white-space:pre-wrap; line-height:1.6; }
  /* 選択肢・承認ボタン（2026-08-16）: NTFY_CHOICES を通知だけでなく対話パネル内にも出す。
     押す行為そのものを人間確認とみなし、そのジョブに限り改札フック(CLAUDE_UNMANNED)を外して
     送信する（sendChoice → /exec?confirm=1）。押した後は連打防止のため全ボタンを disable する。 */
  .choice-btns { display:flex; flex-wrap:wrap; gap:6px; margin-top:8px; }
  .choice-btn { background:var(--card); border:1px solid var(--accent); color:var(--fg);
    border-radius:16px; padding:5px 14px; font-size:.82rem; cursor:pointer; font-family:inherit; }
  .choice-btn:hover:not(:disabled) { background:var(--accent); color:#1a1408; }
  .choice-btn:disabled { opacity:.45; cursor:default; }
  /* 💬 常設の丸ボタン（2026-08-13 ユーザーの投函メモ）: ホーム以外のページでは対話パネルを開く
     導線がホームの「Claude」チップにしかなく、毎回ホームへ戻る必要があった。全ページの
     右下に常時置き、押せば openChat() でその場から自由入力を始められる。ドックが開いて
     いる／畳んでいる間は #result・#result-mini と重なるので隠す（同じ右下の一等地は
     一つしか使わない）。 */
  #chat-fab { position:fixed; right:16px; bottom:16px; z-index:1000;
    width:52px; height:52px; border-radius:50%; background:var(--card); color:var(--accent);
    border:1px solid var(--accent); cursor:pointer; display:flex; align-items:center; justify-content:center;
    box-shadow:0 4px 16px #00000055; transition:transform .15s; }
  #chat-fab:hover { transform:scale(1.06); }
  #chat-fab[hidden] { display:none; }

  /* スマホ幅（2026-08-11 追加）。デスクトップ用の width:46vw をそのまま当てると 390px 幅の端末で
     ドックが 179px の縦長になり、ヘッダーのボタンが縦積みに潰れる。さらに bottom:16px だと
     下部タブバー（約70px）と重なって送信ボタンが隠れた（実測: 53px 重なり）。
     ブレークポイントは下部タブバーが現れる 700px に合わせる。
     #chat-fab は同じ理由に加え、下部タブバーの右端項目（図鑑・称号）の真上に重なって
     ラベルを隠していた（2026-08-13 実測: bottom:16px のままだと nav に41px食い込む）。
     ベース定義（無条件の #chat-fab ルール）をこのブロックより前に移動したのもこのため
     ＝CSSは同詳細度なら後勝ちなので、@media 内の上書きはソース順で後方に置く必要がある。 */
  @media (max-width: 700px) {
    #result:not([hidden]) {
      left:10px; right:10px; width:auto;
      bottom:calc(78px + env(safe-area-inset-bottom));
      max-height:min(64vh, 520px);
    }
    #result-mini:not([hidden]) {
      bottom:calc(78px + env(safe-area-inset-bottom));
      max-width:min(260px, 72vw);
    }
    /* スマホでは横幅は元から画面いっぱい。最大化で効くのは縦（上まで伸ばす） */
    #result.maxi:not([hidden]) {
      left:10px; right:10px; top:10px;
      bottom:calc(78px + env(safe-area-inset-bottom));
    }
    /* 下部タブバー（11項目均等割り）の右端カラムの真上を避けるため、bottom で上に逃がすだけ
       でなく right も広げて右端カラムの中心から外す（項目境界あたりに落ち着く実測値）。 */
    #chat-fab { bottom:calc(78px + env(safe-area-inset-bottom)); right:16px; }
    /* ヘッダーのボタン列（2026-09-27）: 「再取得」「自動読み上げ」等のラベル文字を隠しアイコンのみ
       にする。6個のフルラベル付きボタンが2〜3行に折り返し、モデル行のドロップダウン化と合わせて
       これでチャットログの取り分がスマホで大きく増える（title属性はそのまま残すのでアイコンのみ
       でも押せるボタンの意味は伝わる）。 */
    .rbtn-label { display:none; }
    .result-head .rbtn { padding:5px 8px; }
    .result-head { gap:6px; }
  }

'''

HTML = r'''

<div id="result" class="result" hidden>
  <div class="result-head">
    __MASCOT_HEADER__
    <span id="result-title">__ICON_PLAY__ 実行結果</span>
    <span class="result-actions">
      <button id="history-btn" class="rbtn" type="button" onclick="toggleChatHistory()"
        aria-label="Session history" aria-controls="chat-history" aria-expanded="false"
        title="Open a saved session in a new conversation tab">__ICON_CLOCK__<span class="rbtn-label"> History</span></button>
      <button id="refetch-btn" class="rbtn" onclick="refetchDock()"
        title="通信が切れて応答が出ない時に、ページを再読み込みせずこの会話の最新状態だけを取り直します">__ICON_REFRESH__<span class="rbtn-label"> 再取得</span></button>
      <button id="tts-toggle" class="rbtn" onclick="toggleAutoSpeak()"
        title="ONにすると新しい返答をずんだもんが自動で読み上げます">__ICON_SPEAKER__<span class="rbtn-label"> 自動読み上げ</span></button>
      <button id="tts-stop" class="rbtn" onclick="stopSpeak()" hidden title="読み上げを停止">__ICON_STOP__<span class="rbtn-label"> 停止</span></button>
      <button id="maxi-btn" class="rbtn" onclick="toggleMaximize()"
        title="画面いっぱいに広げて集中して対話する">__ICON_MAXIMIZE__<span class="rbtn-label"> 最大化</span></button>
      <button class="rbtn" onclick="minimizeResult()" title="会話は続けたまま畳んで、裏の画面を操作する">__ICON_MINIMIZE__<span class="rbtn-label"> 最小化</span></button>
      <button class="rbtn" onclick="closeResult()" title="閉じる">__ICON_CROSS__<span class="rbtn-label"> 閉じる</span></button>
    </span>
  </div>
  <section id="chat-history" class="chat-history" aria-label="Session history" hidden>
    <div class="chat-history-head">
      <strong>Session history</strong>
      <button class="rbtn" type="button" onclick="closeChatHistory();byId('history-btn').focus()"
        aria-label="Close session history" title="Close session history">__ICON_CROSS__</button>
    </div>
    <input id="chat-history-search" type="search" aria-label="Search session history"
      placeholder="Search sessions" oninput="renderChatHistory()">
    <p id="chat-history-message" class="chat-history-message" role="status" aria-live="polite"></p>
    <div id="chat-history-results" class="chat-history-results"></div>
  </section>
  <div class="model-row" id="model-row">
    <label for="model-select" title="Shared setting for the next reply in any tab">Next reply</label>
    __MODEL_SELECT__ __EFFORT_SELECT__
    <span id="auto-model-status" class="auto-model-status" role="status" aria-live="polite"></span>
  </div>
  <div id="chat-tabs" class="chat-tabs"></div>
  <div id="chat-model-status" class="chat-model-status" role="status" aria-live="polite"></div>
  <div id="conversation-view">
    <div id="chat-log"></div>
    <div id="voice-conversation-hint" hidden>Talk it through. Ask me to check a note, make something, or change what we’re working on.</div>
    <div id="voice-proposal" hidden>
      <strong>Here’s what I’ll make</strong>
      <div id="voice-work-summary"></div>
      <div id="voice-work-approval-hint" role="status"></div>
      <div id="voice-proposal-error" role="status"></div>
      <button id="voice-work-start" class="rbtn" aria-label="Start approved work" onclick="voiceChat.startWork()">Go ahead</button>
    </div>
    <div id="voice-bar" hidden>
      <span id="voice-status" role="status" aria-live="polite">Microphone off</span>
      <span id="voice-language" title="Active voice language">English</span>
      <button class="rbtn" onclick="voiceChat.end()">End voice</button>
      <button id="voice-ielts-finish" class="rbtn" hidden onclick="finishIELTSSpeaking()">Finish &amp; score</button>
      <button id="voice-ielts-answer" class="rbtn" hidden onclick="voiceChat.sendPracticeAnswer()">Send answer</button>
      <details id="voice-settings">
        <summary>__ICON_SETTINGS__ 設定</summary>
        <div id="voice-settings-fields">
          <label title="Recognition and replies language">Lang <select id="voice-language-select" onchange="voiceChat.setLanguage(this.value)">
            <option value="en">EN</option><option value="ja">JA</option></select></label>
          <span title="Voice: GPT-5.6 Luna">🔊 Luna</span>
          <label>Pause <select id="voice-pause"><option value="1500" selected>1.5 s</option>
            <option value="2500">2.5 s</option><option value="4000">4 s</option></select></label>
        </div>
      </details>
    </div>
    <div id="chat-attach" class="chat-attach" hidden></div>
    <div id="chat-input-row" class="chat-input-row" hidden>
      <div id="vault-picker" class="vault-picker" hidden>
        <input id="vp-query" type="text" placeholder="Vault内を検索（空欄なら最近作成のファイルから選べます）"
          oninput="vpSearch(this.value)">
        <div id="vp-results" class="vp-results"></div>
      </div>
      <div id="skill-picker" class="skill-picker" aria-label="Choose a skill" hidden>
        <input id="skill-query" type="search" aria-label="Search skills" placeholder="What would you like to do?"
          oninput="renderSkillResults()" onkeydown="skillSearchKey(event)">
        <div id="skill-filters" class="skill-filters" aria-label="Skill categories"></div>
        <p id="skill-hint">Choose a skill, add details, then send.</p>
        <div id="skill-results" class="skill-results"></div>
        <p id="skill-count" role="status" aria-live="polite"></p>
      </div>
      <div id="chat-add-menu" class="vault-picker" hidden>
        <button id="attach-btn" type="button" class="vp-item" onclick="toggleAttachmentMenu()"
          aria-expanded="false" aria-controls="attachment-menu">__ICON_ATTACH__ Attachments</button>
        <button id="skill-btn" type="button" class="vp-item" onclick="toggleSkillPicker()"
          aria-expanded="false" aria-controls="skill-picker">__ICON_LAYERS__ Skills</button>
      </div>
      <div id="attachment-menu" class="vault-picker" hidden>
        <button class="vp-item" onclick="closeAttachmentMenu();byId('chat-file').click()">__ICON_ATTACH__ ファイルを添付</button>
        <button class="vp-item" onclick="closeAttachmentMenu();toggleVaultPicker()">__ICON_FOLDER__ Vault内のファイルを探す</button>
      </div>
      <input id="chat-file" type="file" accept="image/*,.pdf,.txt,.md,.csv" hidden
        onchange="onFilePick(this)">
      <input id="chat-input" type="text" placeholder="続きを入力…（Enterで送信）"
        oninput="updateSendBtn()" onfocus="updateSendBtn()"
        onkeydown="if(event.key==='Enter'){sendFollowup();return false;}">
      <button id="chat-add-btn" type="button" class="rbtn" onclick="toggleChatAddMenu()"
        title="Add attachments or skills" aria-label="Add attachments or skills"
        aria-expanded="false" aria-controls="chat-add-menu">__ICON_PLUS__</button>
      <button id="voice-btn" class="rbtn" onclick="toggleVoiceConversation()" title="Start voice conversation" aria-label="Start voice conversation">__ICON_MIC__</button>
      <button id="chat-send-btn" class="rbtn" onclick="sendOrStop()" title="送信" aria-label="送信">__ICON_SEND__</button>
    </div>
  </div>
  <!-- バックグラウンド作業の進捗（2026-09-26: 会話ログとは別の「作業」タブに切り出し。
       表示は toggleWorkTab() が #conversation-view と排他的に切り替える） -->
  <div id="voice-work-card" hidden>
    <div id="voice-work-progress" hidden>
      <div id="voice-work-status" role="status" aria-live="polite"></div>
      <div id="voice-work-model"></div>
      <div id="voice-work-latest" role="status"></div>
      <button id="voice-work-stop" class="rbtn" onclick="voiceChat.stopWork()">Stop work</button>
      <div id="voice-work-messages" role="log" aria-label="Work conversation" tabindex="0"></div>
      <div id="voice-work-question"></div>
      <button id="voice-work-approve" class="rbtn" hidden onclick="voiceChat.approveScope()">Start revised work</button>
      <label for="voice-work-reply">Message this work thread</label>
      <div style="display:flex;gap:6px;align-items:flex-end">
        <textarea id="voice-work-reply" rows="2" style="min-width:0;flex:1;width:100px" maxlength="8000"
          placeholder="Ask a question or send a follow-up"
          onkeydown="if(event.key==='Enter' &amp;&amp; !event.shiftKey &amp;&amp; !event.isComposing){event.preventDefault();voiceChat.replyToWork();}"></textarea>
        <button id="voice-work-send" class="rbtn" onclick="voiceChat.replyToWork()">Send</button>
      </div>
      <div id="voice-work-send-state" role="status" aria-live="polite"></div>
      <details id="voice-result" hidden><summary>Open result</summary><div id="voice-work-detail"></div></details>
      <details id="voice-work-extra">
        <summary>Details</summary>
        <div id="voice-work-note"></div>
      </details>
    </div>
  </div>
</div>
<div id="result-mini" hidden onclick="restoreResult()">
  <span class="rm-status" id="rm-status">__ICON_HOURGLASS__</span>
  <span class="rm-label" id="rm-label"></span>
  <span class="rm-close" onclick="event.stopPropagation();closeResult();" title="閉じる">__ICON_CROSS__</span>
</div>
<button id="chat-fab" onclick="openChat('Omnipus')" title="Chat with Omnipus" aria-label="Chat with Omnipus">
  __MASCOT_SPRITE__
</button>
<div id="model-pick-overlay" class="model-pick-overlay" hidden
  onclick="if(event.target===this) cancelModelPick()">
  <div class="model-pick-card">
    <div class="mp-title" id="model-pick-title">モデルを選んで実行</div>
    <textarea id="model-pick-comment" class="mp-comment"
      placeholder="任意コメント（例: このタスクもう終わってたはず／こういう方針で進めたい）"></textarea>
    <div class="mp-chips">__MODEL_CHIPS_PICK__</div>
    <button class="rbtn mp-cancel" onclick="cancelModelPick()">キャンセル</button>
  </div>
</div>

'''

JS = r'''

  function flash(el) { el.classList.add('ok'); setTimeout(() => el.classList.remove('ok'), 1200); }
  // ── スキルのヘッドレス実行（/exec → /job ポーリング → 結果パネルにチャット表示） ──
  // 各スキルボタンはここで claude -p を裏実行し、結果パネル内のチャットで続きも入力できる。
  // chatSession/chatLabel は「今アクティブなタブ」の鏡（既存コードの大半はこの2変数を
  // 直接読み書きし続けてよい）。tab切替の瞬間（switchTab）と保存の瞬間（saveDockState）
  // だけ pushMirrorToTab/pullMirrorFromTab で TABS[] と同期する（2026-09-25 タブ機能新設）。
  let chatSession = '';
  let chatLabel = '';
  // ntfy通知の選択肢ボタンはブラウザ外（スマホ→サーバー）から直接 /exec?session= を叩いて
  // 会話を継続するため、poll() が完了して止まった後もタブがそれに気づける仕組みが要る。
  // watchTimer は低頻度で /job?session= を見張り、想定外の新規ジョブ（＝ntfy経由の返信）が
  // 始まっていたら通常の poll() に引き継ぐ（2026-07-28 追加）。アクティブタブ限定（タブ切替で張り直す）。
  // 「直近まで表示済みのジョブID」はタブごとに持つ（tab.watchLastJobId・2026-09-25）。
  // 以前はここのグローバル変数1本だったため、タブを切り替えると「別タブの最後のジョブID」を
  // 引きずったまま新しいタブの/job?session=を見張ることになり、そのタブで既に表示済みの
  // 最後のやり取りを「新規ジョブ」と誤検知してもう一度 addMsg してしまう＝同じ発言が
  // 2回表示されるバグの原因だった（タブ機能新設2026-09-25で発生・同日判明）。
  let watchTimer = null;
  let watchStartTs = 0;
  const WATCH_MAX_MS = 10 * 60 * 1000;  // 10分で自動停止（開けっぱなし放置の電池対策）
  const WATCH_INTERVAL_MS = 4000;
  let pendingAttachment = null;  // {name, path} または {name, uploading:true}
  // 各ページの静的アプリJS（activity/concept_game/finance_game/habit_funnel）が別の意味の $ を
  // const 宣言しているため、ドック側は名前を分けて衝突を避ける（2026-08-11）。
  const byId = id => document.getElementById(id);
  const UI_ICONS = __CHAT_ICONS__;
  const SKILL_CATALOG = __SKILL_CATALOG__;

  // ── 🗂 複数セッションタブ（2026-09-25 新設） ──────────────────────────────
  // 1つの対話ドックの中に、独立した会話を最大 MAX_TABS 本まで持てる。それぞれ自前の
  // ログ表示領域（.tab-pane、非表示でも常にDOMに残る＝poll() が書き込み先を見失わない）
  // と pollTimer/jobId を持つので、他のタブに切り替えて操作している間も、裏で走っている
  // 応答生成は止まらずそのタブの中で完結する（切り替えて戻ると続きが見える）。
  // 入力欄・音声・添付・停止ボタン等の「ドック共通UI」は今表示中のタブ1本分だけを指す
  // （元々そういう設計のため）。音声中に他タブへ切り替えたら voiceChat.end() で音声を終える。
  let TABS = [];
  let activeTab = 0;
  const MAX_TABS = 4;
  let tabSeq = 0;
  // 🛠 作業タブ（2026-09-26）: バックグラウンドで進む承認済み作業（voiceChat.work）の状態表示は
  // 会話タブ配列(TABS)には入れず、この1本のフラグで #conversation-view と #voice-work-card を
  // 排他的に切り替えるだけにする（作業は会話とは独立に生き続けるため、TABS[]の1本として
  // 扱うと閉じる/切替のたびに作業自体を巻き込みかねない）。
  let workTabActive = false;
  let workTabError = '';  // voiceChat.work 自体には error が永続化されない（work()コールバックの
                          // 引数だけに一時的に乗る）ため、タブバーの警告アイコン表示用に別途持つ。
  function exitWorkTab() {
    if (!workTabActive) return;
    workTabActive = false;
    byId('conversation-view').hidden = false;
    byId('voice-work-card').hidden = true;
  }
  function toggleWorkTab() {
    workTabActive = !workTabActive;
    byId('conversation-view').hidden = workTabActive;
    byId('voice-work-card').hidden = !(workTabActive && voiceChat.work);
    renderTabBar();
    if (!workTabActive) scrollChatToLatest();
  }

  function tabById(id) { return TABS.find(t => t.id === id); }
  function activeTabObj() { return TABS[activeTab] || null; }
  function tabModelStatus(tab) {
    if (!tab) return '';
    const model = MODEL_LABELS[tab.model] || tab.model || 'Model not reported';
    if (tab.jobId || tab.pollTimer || tab.voiceBusy) {
      return 'Responding: ' + model;
    }
    return tab.model ? 'Latest model: ' + model : tab.session ? model : 'No reply yet';
  }
  function setTabModel(tab, model) {
    if (!tab || typeof model !== 'string' || tab.model === model) return;
    tab.model = model;
    renderTabBar();
  }
  function activePane() {
    const t = activeTabObj();
    return (t && document.getElementById('pane-' + t.id)) || byId('chat-log');
  }
  function paneOf(tabId) { return document.getElementById('pane-' + tabId); }

  function scrollChatToLatest() {
    const tab = activeTabObj();
    const scroll = () => {
      const log = byId('chat-log');
      if (!tab || activeTabObj() !== tab || workTabActive ||
          !log || !log.getClientRects().length) return;
      // The shared log owns scrolling; tab panes only hold messages.
      log.scrollTo({ top: log.scrollHeight, behavior: 'instant' });
    };
    scroll();
    requestAnimationFrame(scroll);  // Recheck after the opening layout settles.
  }

  // 保存/切替の瞬間だけ、鏡変数(chatSession/chatLabel)とTABS[]配列を同期する。
  function pushMirrorToTab() {
    const t = activeTabObj();
    if (t) { t.session = chatSession; t.label = chatLabel; }
  }
  function pullMirrorFromTab() {
    const t = activeTabObj();
    chatSession = t ? t.session : '';
    chatLabel = t ? t.label : '';
  }

  function makeTabObj(label) {
    tabSeq += 1;
    return { id: 't' + Date.now() + '_' + tabSeq, session: '', label: label || '対話',
             model: '', voiceBusy: false, pollTimer: null, jobId: '', unread: false, watchLastJobId: '',
             queue: [], starting: false };
  }

  function makePane(tabId) {
    const wrap = byId('chat-log');
    const pane = document.createElement('div');
    pane.className = 'tab-pane';
    pane.id = 'pane-' + tabId;
    pane.hidden = true;
    wrap.appendChild(pane);
    return pane;
  }

  // Add a conversation tab without replacing any existing pane or job.
  function createTab(label) {
    if (TABS.length >= MAX_TABS) {
      alert('タブは最大' + MAX_TABS + '本までです。使わないタブを閉じてから開いてください。');
      return;
    }
    pushMirrorToTab();
    const t = makeTabObj(label);
    TABS.push(t);
    makePane(t.id);
    // force: true で idx===activeTab ガードを回避する（最初の1本の時、idxが0＝activeTabと一致し得るため）。
    // activeTab自体は書き換えない — 先に -1 にすると switchTab 内の oldPane=activePane() が
    // activeTabObj()の解決に失敗して #chat-log 全体（親要素）にフォールバックし、そこへ
    // hidden=true を立ててしまう事故があった（2026-09-25 判明・#result [hidden]の!importantで
    // 対話ログ全体が消え、タブ切替後も元のタブに戻っても中身が見えなくなるバグの原因だった）。
    switchTab(t.id, { skipPush: true, force: true });
    return t;
  }

  function newTab() {
    if (createTab('対話')) openChat('対話');
  }

  // ドックを開く既存関数群（openChat/resumeHistory/doExec 等）が呼ばれた時点でタブが
  // 1本も無ければ、最初のタブを黙って作る（ドック初回オープン時）。
  function ensureActiveTab() {
    if (!TABS.length) {
      const t = makeTabObj('対話');
      TABS.push(t);
      const pane = makePane(t.id);
      pane.hidden = false;  // makePane は既定で隠すので、最初の1本はここで表示状態にする
      activeTab = 0;
    }
  }

  function switchTab(tabId, opts) {
    opts = opts || {};
    const idx = TABS.findIndex(t => t.id === tabId);
    if (idx < 0) return;
    if (idx === activeTab && !opts.force) {
      exitWorkTab();
      renderTabBar();
      scrollChatToLatest();
      return;
    }
    if (!opts.skipPush) pushMirrorToTab();
    stopWatch();
    voiceChat.end();
    exitWorkTab();
    byId('voice-bar').hidden = true;
    const oldPane = activePane();
    if (oldPane) oldPane.hidden = true;
    activeTab = idx;
    const t = TABS[activeTab];
    t.unread = false;
    pullMirrorFromTab();
    const pane = paneOf(t.id) || makePane(t.id);
    pane.hidden = false;
    setResultTitle(t.jobId ? 'play' : 'comment', chatLabel || '対話');
    byId('result').classList.remove('err');
    byId('chat-input-row').hidden = false;  // 返答中も打てる（送信分は返答後に届く＝queueFollowup）
    clearAttach();
    setBusy(!!t.pollTimer);
    renderTabBar();
    scrollChatToLatest();
    if (!t.pollTimer && chatSession) startWatch(chatSession);
  }

  function closeTab(tabId, ev) {
    if (ev) ev.stopPropagation();
    const idx = TABS.findIndex(t => t.id === tabId);
    if (idx < 0) return;
    if (TABS.length === 1) { closeResult(); return; }
    const t = TABS[idx];
    if ((tabBusy(t) || t.voiceBusy) && !window.confirm('Close "' + (t.label || 'Chat') + '"?\nThis removes the tab from the panel. Running work will continue.')) return;
    if (t.pollTimer) clearInterval(t.pollTimer);  // 裏で走っていたポーリングだけ止める（サーバー側ジョブは止めない）
    const pane = paneOf(tabId);
    if (pane) pane.remove();
    TABS.splice(idx, 1);
    if (activeTab >= idx) activeTab = Math.max(0, activeTab - 1);
    const newActive = TABS[activeTab];
    switchTab(newActive.id, { skipPush: true, force: true });  // force理由はnewTab()のコメント参照
  }

  function renderTabBar() {
    const bar = byId('chat-tabs');
    if (!bar) return;
    bar.innerHTML = '';
    TABS.forEach(t => {
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'chat-tab' + (t === activeTabObj() ? ' active' : '') + (t.unread ? ' unread' : '');
      btn.onclick = () => switchTab(t.id);
      // タブの状態を一目で示す（ぐるぐる＝AIが思考中／チェック＝回答済み・白紙タブは何も出さない）。
      if (t.pollTimer || t.jobId || t.voiceBusy) {
        const status = document.createElement('span');
        status.className = 'ct-status';
        status.innerHTML = UI_ICONS.loading;
        btn.appendChild(status);
      } else if (t.session) {
        const status = document.createElement('span');
        status.className = 'ct-status';
        status.innerHTML = UI_ICONS.check;
        btn.appendChild(status);
      }
      const label = document.createElement('span');
      label.className = 'ct-label';
      label.textContent = t.label || '対話';
      const text = document.createElement('span');
      text.className = 'ct-text';
      const model = document.createElement('span');
      model.className = 'ct-model';
      model.textContent = MODEL_LABELS[t.model] || t.model || (t.session || t.jobId || t.voiceBusy ? 'Model not reported' : 'No reply yet');
      text.append(label, model);
      btn.appendChild(text);
      btn.title = (t.label || '対話') + ' — ' + tabModelStatus(t);
      const close = document.createElement('span');
      close.className = 'ct-close';
      close.innerHTML = UI_ICONS.cross;
      close.onclick = e => closeTab(t.id, e);
      btn.appendChild(close);
      bar.appendChild(btn);
    });
    if (voiceChat.work) {
      const wbtn = document.createElement('button');
      wbtn.type = 'button';
      wbtn.className = 'chat-tab work-tab' + (workTabActive ? ' active' : '');
      wbtn.title = 'バックグラウンドで進んでいる作業';
      wbtn.onclick = toggleWorkTab;
      const status = document.createElement('span');
      status.className = 'ct-status';
      const w = voiceChat.work;
      status.innerHTML = workTabError ? UI_ICONS.warn : w.status === 'running' ? UI_ICONS.loading : UI_ICONS.check;
      wbtn.appendChild(status);
      const label = document.createElement('span');
      label.className = 'ct-label';
      label.textContent = '作業';
      wbtn.appendChild(label);
      bar.appendChild(wbtn);
    }
    const add = document.createElement('button');
    add.type = 'button';
    add.className = 'chat-tab-add';
    add.title = '新しい会話タブ';
    add.textContent = '＋';
    add.onclick = newTab;
    add.disabled = TABS.length >= MAX_TABS;
    bar.appendChild(add);
    const status = byId('chat-model-status');
    status.hidden = workTabActive;
    status.textContent = tabModelStatus(activeTabObj());
  }

  function escapeHtml(s) {
    return String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;')
      .replace(/>/g, '&gt;').replace(/\"/g, '&quot;').replace(/'/g, '&#39;');
  }

  function setResultTitle(iconKey, label) {
    byId('result-title').innerHTML = (UI_ICONS[iconKey] || '') + ' ' + escapeHtml(label);
  }

  function renderAttach() {  // 添付チップの再描画（未添付なら箱ごと隠す）
    const box = byId('chat-attach');
    updateSendBtn();
    if (!pendingAttachment) { box.hidden = true; box.innerHTML = ''; return; }
    const nm = pendingAttachment.name.replace(/</g, '&lt;').replace(/>/g, '&gt;');
    box.hidden = false;
    if (pendingAttachment.uploading) {
      box.innerHTML = '<span class="attach-chip up">' + UI_ICONS.loading
        + ' <span class="attach-name">' + nm + '</span></span>';
    } else {
      box.innerHTML = '<span class="attach-chip">' + UI_ICONS.attach + ' <span class="attach-name">' + nm + '</span>'
        + ' <span class="ax" onclick="clearAttach()">' + UI_ICONS.cross + '</span></span>';
    }
  }
  function clearAttach() { pendingAttachment = null; renderAttach(); }

  function closeChatAddMenu() {
    byId('chat-add-menu').hidden = true;
    byId('chat-add-btn').setAttribute('aria-expanded', 'false');
  }
  function closeSkillPicker() {
    byId('skill-picker').hidden = true;
    byId('skill-btn').setAttribute('aria-expanded', 'false');
  }
  function closeChatPickers() {
    closeChatHistory();
    closeChatAddMenu();
    closeAttachmentMenu();
    closeSkillPicker();
    closeVaultPicker();
  }
  function toggleChatAddMenu() {
    const open = byId('chat-add-menu').hidden;
    closeChatPickers();
    byId('chat-add-menu').hidden = !open;
    byId('chat-add-btn').setAttribute('aria-expanded', String(open));
    if (open) byId('attach-btn').focus();
  }
  function closeAttachmentMenu() {
    byId('attachment-menu').hidden = true;
    byId('attach-btn').setAttribute('aria-expanded', 'false');
  }
  function toggleAttachmentMenu() {
    const open = byId('attachment-menu').hidden;
    closeChatAddMenu();
    closeVaultPicker();
    closeSkillPicker();
    byId('attachment-menu').hidden = !open;
    byId('attach-btn').setAttribute('aria-expanded', String(open));
    if (open) byId('attachment-menu').querySelector('button').focus();
  }
  document.addEventListener('click', event => {
    if (!event.target.closest('#history-btn, #chat-history, #chat-add-btn, #chat-add-menu, #attachment-menu, #skill-picker, #vault-picker'))
      closeChatPickers();
  });
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape' && ['chat-history', 'chat-add-menu', 'attachment-menu', 'skill-picker', 'vault-picker']
        .some(id => !byId(id).hidden)) {
      const historyOpen = !byId('chat-history').hidden;
      closeChatPickers();
      byId(historyOpen ? 'history-btn' : 'chat-add-btn').focus();
    }
  });

  // 🗂 Vault内ファイルを対話のソースに選ぶ（2026-09-14）。/upload と同じ pendingAttachment に
  // 収束させるので、送信側(sendFollowup)は一切触らない＝ソースが増えるだけ。
  // /files/search はサーバー側で VAULT_INDEX を軽量フィールドだけ検索して返す（/files/data の
  // 全件ロードは持ち込まない）。
  let vpTimer = null;
  function toggleVaultPicker() {
    closeChatAddMenu();
    closeAttachmentMenu();
    const box = byId('vault-picker');
    if (box.hidden) {
      closeSkillPicker();
      box.hidden = false;
      byId('vp-query').value = '';
      byId('vp-results').innerHTML = '<div class="vp-empty">' + UI_ICONS.loading + ' 読み込み中…</div>';
      byId('vp-query').focus();
      vpSearch('');  // 空クエリでも最近作成順の候補を出す（検索専用だと開いた瞬間は空箱だった）
    } else {
      closeVaultPicker();
    }
  }
  function closeVaultPicker() { byId('vault-picker').hidden = true; }
  function vpSearch(q) {
    clearTimeout(vpTimer);
    const query = q.trim();
    vpTimer = setTimeout(() => {
      fetch('/files/search?q=' + encodeURIComponent(query))
        .then(r => r.json())
        .then(d => renderVpResults(d.items || []))
        .catch(() => { byId('vp-results').innerHTML = '<div class="vp-empty">検索に失敗しました</div>'; });
    }, query ? 250 : 0);
  }
  function renderVpResults(items) {
    const box = byId('vp-results');
    if (!items.length) { box.innerHTML = '<div class="vp-empty">該当ファイルなし</div>'; return; }
    box.innerHTML = '';
    items.forEach(it => {
      const btn = document.createElement('button');
      btn.className = 'vp-item';
      btn.innerHTML = escapeHtml(it.title) + '<span class="vp-folder">' + escapeHtml(it.folder) + '</span>';
      btn.onclick = () => selectVaultFile(it);
      box.appendChild(btn);
    });
  }
  function selectVaultFile(it) {
    pendingAttachment = { name: it.title, path: it.path };
    renderAttach();
    closeVaultPicker();
  }

  let skillCategory = 'starter';
  const STARTER_SKILLS = ['next', 'discuss', 'plan', 'weekly-review'];
  function toggleSkillPicker() {
    closeChatAddMenu();
    closeAttachmentMenu();
    const box = byId('skill-picker');
    const btn = byId('skill-btn');
    if (box.hidden) {
      closeVaultPicker();
      renderSkillFilters();
      renderSkillResults();
      box.hidden = false;
      btn.setAttribute('aria-expanded', 'true');
      byId('skill-query').focus();
    } else {
      closeSkillPicker();
    }
  }
  function renderSkillFilters() {
    const filters = byId('skill-filters');
    filters.replaceChildren();
    const categories = [['starter', 'Start here'], ['all', 'All skills'],
      ...[...new Set(SKILL_CATALOG.map(s => s.category))].map(cat => [cat, cat])];
    categories.forEach(([key, label]) => {
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'skill-filter';
      btn.textContent = label;
      btn.setAttribute('aria-pressed', String(key === skillCategory));
      btn.onclick = () => {
        skillCategory = key;
        byId('skill-query').value = '';
        filters.querySelectorAll('button').forEach(b => b.setAttribute('aria-pressed', String(b === btn)));
        renderSkillResults();
      };
      filters.appendChild(btn);
    });
  }
  function renderSkillResults() {
    const query = byId('skill-query').value.trim().toLocaleLowerCase();
    const words = query.split(/\s+/).filter(Boolean);
    const items = SKILL_CATALOG.filter(s => words.length
      ? words.every(word => [s.name, s.label, s.description, s.category, s.search || '']
          .join(' ').toLocaleLowerCase().includes(word))
      : skillCategory === 'all' || (skillCategory === 'starter'
          ? STARTER_SKILLS.includes(s.name) : s.category === skillCategory));
    if (!query && skillCategory === 'starter')
      items.sort((a, b) => STARTER_SKILLS.indexOf(a.name) - STARTER_SKILLS.indexOf(b.name));
    const box = byId('skill-results');
    box.replaceChildren();
    box.scrollTop = 0;
    items.forEach(skill => {
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'skill-item';
      btn.dataset.skill = skill.name;
      const label = document.createElement('strong');
      label.textContent = skill.label;
      const description = document.createElement('small');
      description.textContent = skill.description;
      btn.append(label, description);
      btn.onclick = () => insertSkill(skill.name);
      box.appendChild(btn);
    });
    byId('skill-count').textContent = items.length ? items.length + ' skills' : 'No matching skills. Try another word.';
  }
  function skillSearchKey(event) {
    if (event.key === 'ArrowDown' || event.key === 'Enter') {
      event.preventDefault();
      byId('skill-results').querySelector('button')?.focus();
    }
  }
  function insertSkill(name) {
    if (!SKILL_CATALOG.some(s => s.name === name)) return;
    closeSkillPicker();
    const inp = byId('chat-input');
    const names = new Set(SKILL_CATALOG.map(s => s.name));
    const previous = /^\/([a-z0-9-]+)(?:\s+|$)/.exec(inp.value);
    const details = previous && names.has(previous[1]) ? inp.value.slice(previous[0].length) : inp.value;
    inp.value = '/' + name + ' ' + details;
    inp.focus();
    inp.setSelectionRange(inp.value.length, inp.value.length);
  }

  function onFilePick(input) {  // ファイル選択 → /upload に生バイナリ POST → パス受領
    const file = input.files && input.files[0];
    input.value = '';  // 同じファイルを連続選択できるように毎回クリア
    if (!file) return;
    pendingAttachment = { name: file.name, uploading: true };
    renderAttach();
    fetch('/upload?name=' + encodeURIComponent(file.name),
          { method: 'POST', headers: { 'Content-Type': file.type || 'application/octet-stream' }, body: file })
      .then(r => r.json())
      .then(d => {
        if (d.error) { pendingAttachment = null; renderAttach(); alert('添付に失敗: ' + d.error); return; }
        pendingAttachment = { name: d.name, path: d.path };
        renderAttach();
      })
      .catch(e => { pendingAttachment = null; renderAttach(); alert('添付に失敗: ' + e); });
  }
  const MODEL_LABELS = __MODEL_LABELS__;
  const MODEL_EFFORT = __MODEL_EFFORT__;  // dashboard_model -> effort（/settingsと同じ永続値。ここで変えた分もローカルに反映していく）

  function mdInline(s, workLinks = false) {  // 行内装飾（画像・リンク・強調・code。ブロック要素は mdlite 側で組む）
    // 画像embed（外部URLはそのまま・vault相対パスは /vault-image 経由）。2026-09-26 追加：
    // AIの返答に図・生成画像・参照元リンクを含められるようにする（対話ドックの表現力強化）。
    s = s.replace(/!\[([^\]]*)\]\(([^)\s]+)\)/g, (m, alt, url) => {
      const src = /^https?:\/\//i.test(url) ? url : ('/vault-image?path=' + encodeURIComponent(url));
      return '<img src="' + src.replace(/"/g, '&quot;') + '" alt="' + alt.replace(/"/g, '&quot;') + '" loading="lazy">';
    });
    s = s.replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');
    if (workLinks) s = s.replace(/\[([^\]]+)\]\((\/files\?p=[^\s)"']+)\)/g,
      '<a href="$2" target="_blank" rel="noopener">$1</a>');
    return s.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>').replace(/`([^`]+)`/g, '<code>$1</code>');
  }

  // 結果テキストの軽量 markdown → HTML（エスケープしてから装飾）。
  // GFMテーブル・箇条書き・番号付きリスト・見出し・区切り線・画像・リンクに対応（2026-08-11。
  // 画像/リンク/```コードは2026-09-26追加）。```mermaid は <pre class="mermaid"> として出し、
  // renderMermaidIn() が mermaid.js を必要時だけ遅延読み込みして図に変換する（毎ページ読み込むと
  // 重いため。他言語の```はシンタックスハイライト無しの<pre><code>のみ）。
  // 生成途中（ストリーミング）の不完全なテキストが来ても壊れないよう、行単位で判定する。
  function mdlite(t, workLinks = false) {
    const inline = s => mdInline(s, workLinks);
    t = t.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    const lines = t.split('\n'), out = [];
    const UL = /^\s*[-*]\s+/, OL = /^\s*\d+\.\s+/, H = /^\s*#{1,6}\s+/, FENCE = /^\s*```/;
    const isSep = s => /^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$/.test(s);
    const cells = s => s.replace(/^\s*\|/, '').replace(/\|\s*$/, '').split('|').map(c => inline(c.trim()));
    const isTableHead = (i) => lines[i].indexOf('|') >= 0 && i + 1 < lines.length && isSep(lines[i + 1]);
    let i = 0;
    while (i < lines.length) {
      const l = lines[i];
      if (FENCE.test(l)) {  // ```コードブロック。```mermaid は閉じ```が来てから図として描画する
        const lang = l.replace(FENCE, '').trim().toLowerCase();  // （閉じる前の不完全な構文を
        i++;                                                      // mermaid.run()に渡すと「Syntax error」
        const buf = [];                                           // が一瞬出る＝2026-10-04報告のバグ）。
        while (i < lines.length && !FENCE.test(lines[i])) { buf.push(lines[i]); i++; }
        const closed = i < lines.length;  // 閉じ```がまだ来ていない＝ストリーミング中の未完成断片
        if (closed) i++;
        out.push(lang === 'mermaid' && closed
          ? '<pre class="mermaid">' + buf.join('\n') + '</pre>'
          : '<pre class="cm-code"><code>' + buf.join('\n') + '</code></pre>');
        continue;
      }
      if (isTableHead(i)) {  // GFMテーブル
        const head = cells(l);
        i += 2;
        const rows = [];
        while (i < lines.length && lines[i].trim() && lines[i].indexOf('|') >= 0) { rows.push(cells(lines[i])); i++; }
        out.push('<div class="cm-table-wrap"><table class="cm-table"><thead><tr>'
          + head.map(c => '<th>' + c + '</th>').join('') + '</tr></thead><tbody>'
          + rows.map(r => '<tr>' + r.map(c => '<td>' + c + '</td>').join('') + '</tr>').join('')
          + '</tbody></table></div>');
        continue;
      }
      if (UL.test(l) || OL.test(l)) {  // 箇条書き・番号付き
        const ul = UL.test(l), re = ul ? UL : OL, tag = ul ? 'ul' : 'ol', items = [];
        while (i < lines.length && re.test(lines[i])) { items.push(inline(lines[i].replace(re, ''))); i++; }
        out.push('<' + tag + ' class="cm-list">' + items.map(x => '<li>' + x + '</li>').join('') + '</' + tag + '>');
        continue;
      }
      if (H.test(l)) { out.push('<div class="cm-h">' + inline(l.replace(H, '')) + '</div>'); i++; continue; }
      if (/^\s*(-{3,}|\*{3,})\s*$/.test(l)) { out.push('<hr class="cm-hr">'); i++; continue; }
      if (!l.trim()) { i++; continue; }
      const para = [];  // 連続する通常行は1段落にまとめる
      while (i < lines.length && lines[i].trim() && !UL.test(lines[i]) && !OL.test(lines[i])
             && !H.test(lines[i]) && !isTableHead(i) && !FENCE.test(lines[i])) { para.push(inline(lines[i])); i++; }
      out.push('<p class="cm-p">' + para.join('<br>') + '</p>');
    }
    return out.join('');
  }

  // mermaid.js は3MB超あるため全ページ常時読み込みはしない。実際に ```mermaid が
  // メッセージに現れた時だけ /assets/mermaid.min.js を遅延読み込みする（2026-09-26）。
  // 配色は /review のプレビュー図と同じ流儀（/theme.css のCSS変数をそのまま渡す）。
  let _mermaidLoading = null;
  function loadMermaid(cb) {
    if (window.mermaid) { cb(); return; }
    if (!_mermaidLoading) {
      _mermaidLoading = new Promise(resolve => {
        const s = document.createElement('script');
        s.src = '/assets/mermaid.min.js';
        s.onload = () => {
          const cs = getComputedStyle(document.documentElement);
          const cv = name => cs.getPropertyValue(name).trim();
          mermaid.initialize({
            startOnLoad: false, theme: 'base',
            themeVariables: {
              background: cv('--bg'), primaryColor: cv('--card'), primaryTextColor: cv('--fg'),
              primaryBorderColor: cv('--line'), lineColor: cv('--muted'),
              secondaryColor: cv('--card'), tertiaryColor: cv('--bg'),
              fontFamily: cv('--font-ui')
            }
          });
          resolve();
        };
        document.head.appendChild(s);
      });
    }
    _mermaidLoading.then(cb);
  }

  // メッセージ要素内の未描画 ```mermaid を図に変換する。挿入直後・ストリーミング更新のたびに
  // 呼んでよい（対象が無ければ何もしない＝ロードもしない）。要素の中身は呼び出し時点の
  // 最新DOMから再取得する（読み込み待ちの間にストリーミングで innerHTML が差し替わっても安全）。
  function renderMermaidIn(el) {
    if (!el || !el.querySelectorAll) return;
    if (!el.querySelectorAll('pre.mermaid').length) return;
    loadMermaid(() => {
      const nodes = [...el.querySelectorAll('pre.mermaid')];
      if (!nodes.length) return;
      try {
        mermaid.run({ nodes }).then(() => {
          // mermaid.run()は構文エラー時にreject/catchではなく「Syntax error in text」の
          // エラーSVGをDOMへ直接書き込む（v10.9系の仕様）。.catch()だけでは拾えないため
          // 描画後にerror-iconを検知して静かなフォールバック表示に差し替える（2026-10-04）。
          nodes.forEach(n => {
            if (n.querySelector('.error-icon')) n.innerHTML = '<span style="color:var(--muted)">図を表示できません</span>';
          });
        }).catch(e => console.warn('mermaid:', e));
      }
      catch (e) { console.warn('mermaid:', e); }
    });
  }

  function setBusy(on) {
    document.querySelectorAll('.exec-btn').forEach(b => b.classList.toggle('busy', on));
    updateMiniBar(on);
    if (!on) stopRequestedJob = '';
    updateSendBtn();
    if (byId('voice-btn').getAttribute('aria-pressed') !== 'true') byId('chat-input').placeholder = on ? '返答中… 送信すると返答の後に届きます'
                                                               : '続きを入力…（Enterで送信）';
  }

  // ⏹ 実行中の claude -p を中断する（2026-08-18）。独立ジョブを誤停止しないよう、
  // サーバーから job ID が返るまでは停止ボタンを出さない。今表示中のタブのジョブだけを
  // 止める（他タブのジョブを止めたければ、そのタブに切り替えてから押す）。
  let stopRequestedJob = '';
  function stopJob() {
    const jobId = activeTabObj() ? activeTabObj().jobId : '';
    if (!jobId || stopRequestedJob === jobId) return;
    stopRequestedJob = jobId;
    updateSendBtn();
    fetch('/job-stop?id=' + encodeURIComponent(jobId)).catch(() => {});
  }

  // ■/➤ 1ボタン化（2026-10-04）: 停止ボタンを上部から送信ボタンに統合する。返答中かつ
  // 入力欄が空（＝送るものが無い）の時だけ ■停止 になり、1文字でも打てば ➤送信（返答後に届く
  // 待ち行列へ）に戻る。2つのボタンが隣に並ばないので押し間違えが起きない。送信直後の2度押しや
  // 入力を消した瞬間の誤タップで止めないよう、■ に変わってから STOP_ARM_MS の間は押しても無視する。
  const STOP_ARM_MS = 800;
  let stopArmedAt = 0;
  function voiceChatOn() { return byId('voice-btn').getAttribute('aria-pressed') === 'true'; }
  function sendBtnStopState() {
    const tab = activeTabObj();
    return !!(tab && tab.jobId && !voiceChatOn()
              && !byId('chat-input').value.trim() && !pendingAttachment);
  }
  function updateSendBtn() {
    const btn = byId('chat-send-btn');
    if (!btn) return;
    const stop = sendBtnStopState();
    if (stop !== btn.classList.contains('stop-mode')) {
      btn.classList.toggle('stop-mode', stop);
      btn.innerHTML = stop ? UI_ICONS.stop : UI_ICONS.send;
      btn.title = stop ? '停止（ここまでの生成内容は残ります）' : '送信';
      btn.setAttribute('aria-label', stop ? '停止' : '送信');
      if (stop) stopArmedAt = Date.now();
    }
    const tab = activeTabObj();
    btn.disabled = stop && !!tab && stopRequestedJob === tab.jobId;
  }
  function sendOrStop() {
    const btn = byId('chat-send-btn');
    if (btn.classList.contains('stop-mode') && sendBtnStopState()) {
      if (Date.now() - stopArmedAt >= STOP_ARM_MS) stopJob();
      return false;
    }
    return sendFollowup();
  }

  // ── 最小化ドック（2026-08-07）: 会話（chatSession・ポーリング・ntfy見張り）は生かしたまま
  // 見た目だけ畳む。「閉じる」しか選択肢が無く、戻るには実行履歴から選び直すしかなかった
  // 問題への対処。畳んでいる間に応答が届いたら ✅ に変え、開けば読める。 ──
  let minimized = false;
  let miniUnread = false;

  function updateMiniBar(busy) {
    if (!minimized) return;
    const mini = byId('result-mini');
    if (busy) { byId('rm-status').innerHTML = UI_ICONS.hourglass; miniUnread = false; mini.classList.remove('unread'); }
    else if (miniUnread) { byId('rm-status').innerHTML = UI_ICONS.check; mini.classList.add('unread'); }
    else { byId('rm-status').innerHTML = UI_ICONS.comment; mini.classList.remove('unread'); }
  }

  // ── 最大化（2026-08-13）: 1つのボタンが最大化⇄縮小に入れ替わる（ブラウザと同じ流儀）──
  let maximized = false;

  function applyMaximize() {
    byId('result').classList.toggle('maxi', maximized);
    const b = byId('maxi-btn');
    if (b) {
      b.innerHTML = (maximized ? UI_ICONS.shrink : UI_ICONS.maximize)
        + '<span class="rbtn-label"> ' + (maximized ? '縮小' : '最大化') + '</span>';
      b.title = maximized ? '元のサイズに戻す' : '画面いっぱいに広げて集中して対話する';
    }
  }

  function toggleMaximize() {
    maximized = !maximized;
    applyMaximize();
    scrollChatToLatest();
  }

  // ドックが開いている／畳んでいる間は右下の丸ボタンを隠す（同じ場所を取り合わないように）
  function updateFabVisibility() {
    const fab = byId('chat-fab');
    if (!fab) return;
    fab.hidden = !byId('result').hidden || !byId('result-mini').hidden;
  }

  function minimizeResult() {
    closeChatPickers();
    minimized = true;
    byId('result').classList.add('mini');
    byId('rm-label').textContent = chatLabel || '対話';
    byId('result-mini').hidden = false;
    updateMiniBar(!!(activeTabObj() && activeTabObj().pollTimer));
    updateFabVisibility();
  }

  function restoreResult() {
    minimized = false;
    miniUnread = false;
    byId('result').classList.remove('mini');
    byId('result-mini').hidden = true;
    byId('result-mini').classList.remove('unread');
    scrollChatToLatest();
    updateFabVisibility();
  }

  // ドック全体を閉じる（全タブ）。個別タブだけ畳みたい時は closeTab() を使う。
  function closeResult() {
    const needsConfirmation = TABS.length > 1 || TABS.some(t => tabBusy(t) || t.voiceBusy);
    if (needsConfirmation && !window.confirm('Close the chat panel and all its tabs?\nUse Minimize to keep your conversations available. Running work will continue.')) return;
    closeChatPickers();
    voiceChat.end();
    exitWorkTab();
    TABS.forEach(t => { if (t.pollTimer) clearInterval(t.pollTimer); });
    TABS = [];
    activeTab = 0;
    byId('chat-log').innerHTML = '';
    stopWatch();
    stopSpeak();  // パネルを閉じたら黙る
    byId('result').hidden = true;
    byId('result').classList.remove('mini');
    byId('result-mini').hidden = true;
    minimized = false;
    miniUnread = false;
    chatSession = '';
    clearAttach();
    updateFabVisibility();
  }

  function attachCopy(el, text) {
    if (typeof text === 'string') el.dataset.copyText = text;
    if (!('copyText' in el.dataset)) {
      // Older saved docks have rendered HTML only; assistant source survives in ttsText.
      const content = el.cloneNode(true);
      content.querySelectorAll('.msg-actions, .msg-speak, .chat-acct, .stop-note, .choice-btns, .chat-cursor')
        .forEach(node => node.remove());
      content.querySelectorAll('br').forEach(node => node.replaceWith('\n'));
      content.querySelectorAll('p, .cm-h, li, pre, tr').forEach(node => node.append('\n'));
      el.dataset.copyText = el.dataset.ttsText || content.textContent.trim();
    }
    let actions = el.querySelector('.msg-actions');
    if (!actions) {
      actions = document.createElement('div');
      actions.className = 'msg-actions';
      el.appendChild(actions);
    }
    if (!actions.querySelector('.msg-copy')) {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'msg-copy';
      button.title = button.ariaLabel = el.classList.contains('user') ? 'Copy prompt' : 'Copy reply';
      button.innerHTML = UI_ICONS.copy + '<span aria-live="polite">Copy</span>';
      actions.prepend(button);
    }
    const speaker = el.querySelector('.msg-speak');
    if (speaker && speaker.parentElement !== actions) actions.appendChild(speaker);
    return actions;
  }

  function copyWithSelection(text) {
    const focused = document.activeElement;
    const selection = window.getSelection();
    const ranges = selection ? Array.from({length: selection.rangeCount}, (_, i) => selection.getRangeAt(i).cloneRange()) : [];
    const input = document.createElement('textarea');
    input.value = text;
    input.readOnly = true;
    input.style.cssText = 'position:fixed;top:0;left:0;width:1px;height:1px;opacity:0;font-size:16px;';
    document.body.appendChild(input);
    try {
      input.select();
      input.setSelectionRange(0, text.length);
      if (!document.execCommand('copy')) throw new Error('Copy unavailable');
    } finally {
      input.remove();
      if (focused && focused.isConnected) focused.focus({preventScroll:true});
      if (selection) { selection.removeAllRanges(); ranges.forEach(range => selection.addRange(range)); }
    }
  }

  async function copyMessage(button) {
    const text = button.closest('.chat-msg').dataset.copyText || '';
    const label = button.querySelector('span');
    clearTimeout(button.copyTimer);
    try {
      if (navigator.clipboard && navigator.clipboard.writeText) {
        try { await navigator.clipboard.writeText(text); }
        catch (error) { copyWithSelection(text); }
      } else copyWithSelection(text);
      label.textContent = 'Copied';
      button.dataset.state = 'copied';
    } catch (error) {
      label.textContent = 'Copy failed';
      button.dataset.state = 'error';
    }
    button.copyTimer = setTimeout(() => { label.textContent = 'Copy'; delete button.dataset.state; }, 1800);
  }

  function addMsg(role, innerHtml, text) {
    const d = document.createElement('div');
    d.className = 'chat-msg ' + role;
    d.innerHTML = innerHtml;
    if (typeof text === 'string') attachCopy(d, text);
    activePane().appendChild(d);
    d.scrollIntoView({ behavior: 'smooth', block: 'end' });
    renderMermaidIn(d);
    return d;
  }

  function openChat(label) {  // 自由入力チャット：プレフィルなしでこの場で開始（今アクティブなタブに開く）
    ensureActiveTab();
    voiceChat.end();
    exitWorkTab();
    byId('voice-bar').hidden = true;
    byId('result').hidden = false;
    restoreResult();  // 前の会話を最小化したまま新しい会話を開く事故を防ぐ
    byId('result').classList.remove('err');
    setResultTitle('comment', label);
    activePane().innerHTML = '';
    chatSession = '';
    chatLabel = label;
    pushMirrorToTab();
    activeTabObj().model = '';
    clearAttach();
    byId('chat-input-row').hidden = false;
    byId('result').scrollIntoView({ behavior: 'smooth' });
    // Keep the software keyboard closed so touch users can choose voice first.
    if (!window.matchMedia('(max-width: 700px), (pointer: coarse)').matches) {
      byId('chat-input').focus();
    }
    renderTabBar();
    return false;
  }

  let chatHistoryItems = [];
  let chatHistorySequence = 0;

  function closeChatHistory() {
    byId('chat-history').hidden = true;
    byId('history-btn').setAttribute('aria-expanded', 'false');
    ++chatHistorySequence;
  }

  async function toggleChatHistory() {
    const open = byId('chat-history').hidden;
    closeChatPickers();
    if (!open) return;
    byId('chat-history').hidden = false;
    byId('history-btn').setAttribute('aria-expanded', 'true');
    byId('chat-history-search').value = '';
    byId('chat-history-search').focus();
    chatHistoryItems = [];
    byId('chat-history-results').replaceChildren();
    byId('chat-history-message').textContent = 'Loading sessions…';
    const sequence = ++chatHistorySequence;
    try {
      const response = await fetch('/sessions/data?filter=all');
      if (!response.ok) throw new Error('Sessions could not be loaded. Reopen History to retry.');
      const data = await response.json();
      if (sequence !== chatHistorySequence) return;
      chatHistoryItems = (data.items || []).filter(item => item.session);
      renderChatHistory();
    } catch (_) {
      if (sequence === chatHistorySequence)
        byId('chat-history-message').textContent = 'Sessions could not be loaded. Reopen History to retry.';
    }
  }

  function renderChatHistory() {
    const query = byId('chat-history-search').value.trim().toLocaleLowerCase();
    const items = chatHistoryItems.filter(item => !query || [item.label, item.updated, item.model]
      .join(' ').toLocaleLowerCase().includes(query));
    const results = byId('chat-history-results');
    results.replaceChildren();
    items.forEach(item => {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'chat-history-item';
      button.dataset.resumeSession = item.session;
      button.dataset.resumeLabel = item.label;
      button.dataset.resumeModel = item.model || '';
      button.title = item.label;
      const title = document.createElement('span');
      title.className = 'chat-history-title';
      title.textContent = item.label;
      const detail = document.createElement('small');
      detail.textContent = [item.updated, MODEL_LABELS[item.model] || item.model,
        item.running ? 'Running' : ''].filter(Boolean).join(' · ');
      button.append(title, detail);
      results.appendChild(button);
    });
    byId('chat-history-message').textContent = items.length
      ? 'Choose a session to open in a new tab.' : 'No saved sessions match.';
  }

  function resumeHistory(session, label, model, reload) {
    pushMirrorToTab();
    const existing = TABS.find(t => t.session === session);
    if (existing) {
      if (!existing.pollTimer && model) setTabModel(existing, model);
      switchTab(existing.id);
      byId('result').hidden = false;
      restoreResult();
      if (!reload || existing.pollTimer) {
        byId('result').scrollIntoView({ behavior: 'smooth' });
        if (!existing.pollTimer) byId('chat-input').focus();
        return false;
      }
    }
    if (!existing && !createTab(label)) return false;
    voiceChat.end();
    exitWorkTab();
    byId('voice-bar').hidden = true;
    byId('result').hidden = false;
    restoreResult();  // 前の会話を最小化したまま新しい会話を開く事故を防ぐ
    byId('result').classList.remove('err');
    setResultTitle('clock', label);
    chatSession = session;
    chatLabel = label;
    pushMirrorToTab();
    if (model || !existing) activeTabObj().model = model || '';
    renderTabBar();
    // その会話が生まれたエンジン(model)に、いま画面で選択中のモデルを合わせる。
    // 食い違ったまま送信すると、サーバーが「セッション所有者と違うエンジン」と判定して
    // サイレントに新規会話を始めてしまう（=文脈が消える）ため、再開時に必ず揃える。
    if (model) {
      fetch('/set-model?m=' + encodeURIComponent(model) + '&manual=0')
        .then(() => {
          lastAutoModel = model;
          const sel = byId('model-select');
          if (sel && sel.value !== '__auto__') applyModelUi(model, false);
        })
        .catch(() => {});
    }
    const targetTabId = activeTabObj().id;  // 読み込み中にタブを切り替えられても迷子にならないよう固定
    const addToTarget = (role, html, text) => {  // 対象タブが閉じられていたら何もしない
      const pane = paneOf(targetTabId);
      if (!pane) return null;
      const d = document.createElement('div');
      d.className = 'chat-msg ' + role;
      d.innerHTML = html;
      if (typeof text === 'string') attachCopy(d, text);
      pane.appendChild(d);
      if (targetTabId === activeTabObj().id) d.scrollIntoView({ behavior: 'smooth', block: 'end' });
      renderMermaidIn(d);
      return d;
    };
    activePane().innerHTML = '';
    clearAttach();
    stopSpeak();
    const loading = addMsg('assistant', UI_ICONS.loading + ' 過去の会話を読み込み中…');
    activeTabObj().historyLoad = fetch('/history-log?session=' + encodeURIComponent(session))
      .then(r => r.json())
      .then(list => {
        const pane = paneOf(targetTabId);
        if (!pane) return false;
        pane.innerHTML = '';
        if (!list.length) {
          addToTarget('assistant', '過去の会話を読み込めませんでした。');
        } else {
          list.forEach(m => {
            const el = addToTarget(m.role === 'user' ? 'user' : 'assistant', mdlite(m.text), m.text);
            if (m.role === 'assistant' && el) attachSpeak(el, m.text);
            if (m.role === 'assistant' && el && Array.isArray(m.choices) && m.choices.length)
              renderChoices(el, m.choices);
          });
        }
        if (activeTabObj() && activeTabObj().id === targetTabId) scrollChatToLatest();
        return list.length > 0;
      })
      .catch(() => { loading.textContent = '履歴の読み込みに失敗しました。'; return false; });
    byId('chat-input-row').hidden = false;
    byId('result').scrollIntoView({ behavior: 'smooth' });
    byId('chat-input').focus();
    return false;
  }

  function shukiPrepareSessionTab() {
    const active = activeTabObj();
    if (!active) { ensureActiveTab(); return true; }
    if (!active.session && !active.jobId && !activePane().children.length) return true;
    if (TABS.length >= MAX_TABS) {
      alert('Close an unused chat tab before opening another session.');
      return false;
    }
    newTab();
    return true;
  }

  async function shukiResumeSessionLink(session) {
    try {
      const response = await fetch('/sessions/data?filter=all&session=' + encodeURIComponent(session));
      if (!response.ok) throw new Error('Could not find this saved session.');
      const data = await response.json();
      const item = data.items.find(row => row.session === session);
      if (!item) throw new Error('This session is no longer available in the saved history.');
      if (typeof shukiSidebarClose === 'function') shukiSidebarClose();
      resumeHistory(session, item.label, item.model);
    } catch (error) { alert(error.message); }
  }

  async function applySessionTabRequest(job, sourceTab) {
    const action = job.session_tabs;
    if (!action || !['running', 'done'].includes(job.status) || !tabById(sourceTab.id) || sourceTab.sessionTabsBusy) return;
    if (!Array.isArray(action.sessions) || !action.sessions.length || action.sessions.length > 3) return;
    sourceTab.sessionTabsBusy = true;
    let receipt = sourceTab.sessionTabsReceipt;
    try {
      if (!receipt || receipt.request !== action.id) {
        const needed = action.sessions.filter(item => !TABS.some(t => t.session === item.session));
        const opened = [];
        let message = '';
        if (TABS.length + needed.length > MAX_TABS) {
          message = 'Close unused panel tabs, then ask again. No conversations were replaced.';
        } else {
          for (const item of action.sessions) {
            if (!tabById(sourceTab.id)) { message = 'The requesting panel tab was closed.'; break; }
            resumeHistory(item.session, item.label, item.model);
            const target = TABS.find(t => t.session === item.session);
            if (target && (!target.historyLoad || await target.historyLoad) && tabById(target.id)) {
              opened.push(item.session);
            } else {
              message = 'A saved conversation could not be loaded; inspect its panel tab.';
            }
          }
        }
        const status = opened.length === action.sessions.length ? 'opened' : opened.length ? 'partial' : 'failed';
        receipt = {job: job.id, request: action.id, result: {status, opened, message}};
        sourceTab.sessionTabsReceipt = receipt;
        saveDockState();
        if (message && paneOf(sourceTab.id)) {
          const note = document.createElement('div');
          note.className = 'chat-msg assistant'; note.textContent = message;
          paneOf(sourceTab.id).appendChild(note);
        }
      }
      await fetch('/sessions/open-result', {method: 'POST', headers: {'Content-Type': 'application/json'},
                                          body: JSON.stringify(receipt)});
    } finally { sourceTab.sessionTabsBusy = false; }
  }

  // ── モデル切替（ドック常設の<select>。fetch のみ・画面リロードなし。サーバー側で永続化） ──
  // 2026-09-27: 9モデル分のチップ列を<select>1本に畳んだ（ユーザーのフィードバック：スマホで3行占有し
  // チャットログを圧迫していた）。Auto もこの1本の中の値 '__auto__' として扱う。
  let lastAutoModel = __AUTO_MODEL_INITIAL_MODEL__;
  let autoModelNoticeTimer = null;

  // モデル欄の表示状態をまとめて合わせる（select の選択値・effort欄の表示/値）。
  // サーバーへの反映(/set-model・/set-auto-model)は呼び出し側が既に済ませている前提。
  function applyModelUi(model, auto) {
    const sel = byId('model-select');
    if (sel) sel.value = auto ? '__auto__' : model;
    const eff = byId('effort-select');
    if (eff) {
      eff.hidden = auto;
      if (!auto && model in MODEL_EFFORT) eff.value = MODEL_EFFORT[model];
    }
  }

  function reportAutoModel(model) {
    if (!model) return;
    const sel = byId('model-select');
    if (!sel || sel.value !== '__auto__') { lastAutoModel = model; return; }
    if (lastAutoModel && model !== lastAutoModel) {
      const status = byId('auto-model-status');
      status.textContent = 'Auto → ' + (MODEL_LABELS[model] || model);
      clearTimeout(autoModelNoticeTimer);
      autoModelNoticeTimer = setTimeout(() => { status.textContent = ''; }, 3500);
    }
    lastAutoModel = model;
  }
  window.reportAutoModel = reportAutoModel;

  function setAutoModelMode() {
    fetch('/set-auto-model?enabled=1')
      .then(r => { if (!r.ok) throw 0; applyModelUi(lastAutoModel, true); })
      .catch(() => { const sel = byId('model-select'); sel.classList.add('errflash'); setTimeout(() => sel.classList.remove('errflash'), 1500); });
  }

  function setModel(m) {
    fetch('/set-model?m=' + encodeURIComponent(m) + '&manual=1')
      .then(r => { if (!r.ok) throw 0;
        lastAutoModel = m;
        applyModelUi(m, false);
        byId('auto-model-status').textContent = ''; })
      .catch(() => { const sel = byId('model-select'); sel.classList.add('errflash'); setTimeout(() => sel.classList.remove('errflash'), 1500); });
  }

  // <select id="model-select"> の onchange。Auto を選べば /set-auto-model、具体モデルなら /set-model。
  function onModelSelect(v) {
    if (v === '__auto__') setAutoModelMode();
    else setModel(v);
  }

  // <select id="effort-select"> の onchange。モデルごとの思考量を /settings と同じ場所に永続化する
  // （楽観更新: 失敗したら選択を巻き戻す）。
  function onEffortSelect(level) {
    const sel = byId('model-select');
    const m = sel ? sel.value : '';
    if (!m || m === '__auto__') return;
    const prev = MODEL_EFFORT[m];
    MODEL_EFFORT[m] = level;
    fetch('/set-effort?m=' + encodeURIComponent(m) + '&level=' + encodeURIComponent(level))
      .then(r => { if (!r.ok) throw 0; })
      .catch(() => { MODEL_EFFORT[m] = prev; byId('effort-select').value = prev; });
  }

  // ── モデル選択ポップアップ（2026-08-16）: [data-exec-skill] はクリック即実行なので、
  // ドックが開く前にモデルを選ばせるにはここで一度止めるしかない。選ぶ＝実行（確認は挟まない）。
  let pendingExec = null;

  function exec(skill, textEnc, label) {  // textEnc は URL エンコード済み。data-exec-skill から呼ばれる入口
    pendingExec = { skill, textEnc, label };
    byId('model-pick-title').textContent = (label || skill) + ' を実行 — モデルを選択';
    byId('model-pick-comment').value = '';  // 前回の入力を持ち越さない
    document.querySelectorAll('.mchip-pick').forEach(b => b.classList.toggle('active', b.dataset.model === lastAutoModel));
    byId('model-pick-overlay').hidden = false;
    return false;
  }

  function cancelModelPick() {
    byId('model-pick-overlay').hidden = true;
    pendingExec = null;
  }

  function pickModel(m) {
    byId('model-pick-overlay').hidden = true;
    const p = pendingExec;
    const comment = byId('model-pick-comment').value.trim();
    pendingExec = null;
    if (!p) return;
    fetch('/set-model?m=' + encodeURIComponent(m) + '&manual=1')
      .then(() => {
        lastAutoModel = m;
        applyModelUi(m, false);
        byId('auto-model-status').textContent = '';
      })
      .catch(() => {})  // set-model が失敗しても実行自体は止めない（現在のサーバー側モデルで走る）
      .then(() => { if (p.run) p.run(m); else doExec(p.skill, p.textEnc, p.label, comment); });
  }

  // スキル実行以外（例: /visualize の「作成をリクエスト」）からも同じモデル選択ポップアップを
  // 使うための汎用入口。run(model) は選択確定後・/set-model 完了後に一度だけ呼ばれる。
  // /visualize/exec や /exec はサーバー側の CURRENT_MODEL を読むので、run 内では
  // モデルを渡さず通常どおり実行を投げるだけでよい（set-model は pickModel が済ませている）。
  function pickModelThen(label, run) {
    pendingExec = { run: run, label: label };
    byId('model-pick-title').textContent = (label || '実行') + ' — モデルを選択';
    document.querySelectorAll('.mchip-pick').forEach(b => b.classList.toggle('active', b.dataset.model === lastAutoModel));
    byId('model-pick-overlay').hidden = false;
    return false;
  }

  function doExec(skill, textEnc, label, comment) {  // モデル確定後の実処理（旧 exec() 本体）
    ensureActiveTab();
    voiceChat.end();
    byId('voice-bar').hidden = true;
    unlockAudio();  // exec ボタンタップ＝ジェスチャ
    if (window.SFX) SFX.warm();  // 完了音(chat_done)は非同期ポーリング内で鳴るのでここで起こしておく
    stopSpeak();
    byId('result').hidden = false;
    restoreResult();  // 前の会話を最小化したまま新しい会話を開く事故を防ぐ
    byId('result').classList.remove('err');
    setResultTitle('play', label || '/' + skill);
    activePane().innerHTML = '';
    chatSession = '';
    chatLabel = label || skill;
    pushMirrorToTab();
    activeTabObj().model = '';
    renderTabBar();
    clearAttach();
    activeTabObj().queue = [];
    byId('chat-input-row').hidden = false;  // 実行中も先に次の発言を打てる（返答後に送られる）
    const targetTabId = activeTabObj().id;  // 実行開始～応答到着の間にタブを切り替えられても迷子にならない
    // コメントは吹き出しとしてもログに残す（何を添えて実行したか後から見返せるように）
    if (comment) addMsg('user', mdlite(comment), comment);
    const msg = addMsg('assistant', UI_ICONS.loading + ' 実行中…（30秒〜2分ほど。このまま待たなくてもOK）');
    byId('result').scrollIntoView({ behavior: 'smooth' });
    setBusy(true);
    const startTab = activeTabObj();
    startTab.starting = true;
    fetch('/exec?skill=' + skill + '&text=' + textEnc + '&label=' + encodeURIComponent(chatLabel)
        + (comment ? '&comment=' + encodeURIComponent(comment) : ''))
      .then(r => r.json())
      .then(d => {
        startTab.starting = false;
        if (d.error) {
          if (targetTabId === activeTabObj().id) { byId('result').classList.add('err'); setBusy(false); }
          msg.textContent = d.error === 'busy' ? 'この会話では別の返答を生成中です。終了後にもう一度送信してください。' : d.error;
          returnQueue(startTab);
          return;
        }
        if (targetTabId === activeTabObj().id) setResultTitle('play', (label || '/' + skill) + '（' + (MODEL_LABELS[d.model] || d.model) + '）');
        poll(d.job, msg, targetTabId, d.model || '');
      })
      .catch(e => {
        startTab.starting = false;
        if (targetTabId === activeTabObj().id) { byId('result').classList.add('err'); setBusy(false); }
        msg.textContent = '実行開始に失敗: ' + e;
        returnQueue(startTab);
      });
    return false;
  }

  // ── ⏳ 返答中の先行入力（2026-10-04）: 返答の生成中も入力欄を開けておき、送信された発言は
  // タブごとの queue に積んで「送信待ち」の吹き出しで見せる。claude -p は1ターン1プロセスで
  // 実行中のプロセスへ途中注入はできないため、そのターンが終わった（done/stopped）瞬間に
  // まとめて1発言として送る。割り込みたい時は ⏹（＝吹き出しの「止めて今すぐ送る」）で現在の
  // ターンを止めれば、stopped の時点で待ち行列が送られる。エラーで続きを送れない時は
  // 送信せずに入力欄へ戻す（黙って消さない）。 ──
  function tabBusy(tab) { return !!(tab && (tab.pollTimer || tab.jobId || tab.starting)); }

  function queueFollowup(tab, text, sendText, attHtml) {
    const qid = 'q' + Date.now() + '_' + Math.random().toString(36).slice(2, 6);
    tab.queue = (tab.queue || []).concat([{ id: qid, text: text, sendText: sendText }]);
    const el = addMsg('user', attHtml + mdlite(text || '(添付のみ)'), text || '(添付のみ)');
    el.classList.add('queued');
    el.dataset.qid = qid;
    el.insertAdjacentHTML('beforeend', '<div class="queued-note">' + UI_ICONS.hourglass
      + ' 返答が終わったら送信します'
      + '<button type="button" data-qnow="' + qid + '">止めて今すぐ送る</button>'
      + '<button type="button" data-qcancel="' + qid + '">取り消す</button></div>');
  }

  function unmarkQueued(tab, ids) {
    const pane = paneOf(tab.id);
    if (!pane) return [];
    return ids.map(id => pane.querySelector('.chat-msg.queued[data-qid="' + id + '"]')).filter(Boolean)
      .map(el => {
        el.classList.remove('queued');
        delete el.dataset.qid;
        const note = el.querySelector('.queued-note');
        if (note) note.remove();
        return el;
      });
  }

  // 返答が終わったタブの待ち行列を1発言にまとめて送る（タブが裏に回っていても送る）。
  function flushQueue(tab) {
    if (!tab || !tab.queue || !tab.queue.length || tabBusy(tab)) return;
    const items = tab.queue;
    tab.queue = [];
    if (!tab.session) { tab.queue = items; returnQueue(tab); return; }  // 続ける会話が無い
    unmarkQueued(tab, items.map(q => q.id));
    const pane = paneOf(tab.id);
    if (!pane) return;
    const msg = document.createElement('div');
    msg.className = 'chat-msg assistant';
    msg.innerHTML = UI_ICONS.loading + ' 実行中…';
    pane.appendChild(msg);
    if (activeTabObj() === tab) msg.scrollIntoView({ behavior: 'smooth', block: 'end' });
    startFollowup(tab, items.map(q => q.sendText).join('\n\n'), msg);
  }

  // 送れなかった待ち行列を「送信されなかった」と明示して入力欄へ戻す（アクティブタブの時）。
  function returnQueue(tab) {
    if (!tab || !tab.queue || !tab.queue.length) return;
    const items = tab.queue;
    tab.queue = [];
    unmarkQueued(tab, items.map(q => q.id)).forEach(el => el.insertAdjacentHTML('beforeend',
      '<div class="stop-note">' + UI_ICONS.warn + ' 送信されませんでした</div>'));
    if (activeTabObj() === tab) {
      const inp = byId('chat-input');
      inp.value = [inp.value.trim()].concat(items.map(q => q.text)).filter(Boolean).join('\n');
      updateSendBtn();
    }
  }

  function cancelQueued(qid) {
    const tab = TABS.find(t => (t.queue || []).some(q => q.id === qid));
    if (!tab) return;
    const item = tab.queue.find(q => q.id === qid);
    tab.queue = tab.queue.filter(q => q.id !== qid);
    const pane = paneOf(tab.id);
    const el = pane && pane.querySelector('.chat-msg.queued[data-qid="' + qid + '"]');
    if (el) el.remove();
    const inp = byId('chat-input');
    if (activeTabObj() === tab && !inp.value.trim()) { inp.value = item.text; inp.focus(); }  // 取り消し＝手直しできるよう戻す
    updateSendBtn();
  }

  // /exec に続きの発言を投げて poll に渡す。tab が裏に回っていても動く（共通UIはアクティブ時だけ触る）。
  function startFollowup(tab, sendText, msg) {
    const isActive = () => activeTabObj() === tab;
    const session = isActive() ? chatSession : tab.session;
    const label = isActive() ? chatLabel : tab.label;
    tab.starting = true;
    renderTabBar();
    if (isActive()) setBusy(true);
    const fail = text => {
      tab.starting = false;
      renderTabBar();
      if (isActive()) { byId('result').classList.add('err'); setBusy(false); }
      msg.textContent = text;
      returnQueue(tab);
    };
    fetch('/exec?skill=&text=' + encodeURIComponent(sendText) + '&session=' + encodeURIComponent(session)
        + '&label=' + encodeURIComponent(label))
      .then(r => r.json())
      .then(d => {
        if (d.error) {
          fail(d.error === 'busy' ? 'この会話では別の返答を生成中です。終了後にもう一度送信してください。' : d.error);
          return;
        }
        tab.starting = false;
        if (isActive()) reportAutoModel(d.model);
        poll(d.job, msg, tab.id, d.model || '');
      })
      .catch(e => fail('送信に失敗: ' + e));
  }

  function sendFollowup() {  // チャット欄からの継続発言（session があれば --resume）
    closeAttachmentMenu();
    closeVaultPicker();
    if (voiceChat.active) {
      const input = byId('chat-input');
      voiceChat.sendTyped(input.value); input.value = ''; return false;
    }
    unlockAudio();  // 送信タップ/Enter＝ジェスチャ。完了時の自動読み上げを通すためここでアンロック
    if (window.SFX) SFX.warm();  // 完了音(chat_done)は非同期ポーリング内で鳴るのでここで起こしておく
    stopSpeak();
    const inp = byId('chat-input');
    const text = inp.value.trim();
    if (pendingAttachment && pendingAttachment.uploading) return false;  // アップロード完了まで待つ
    const att = pendingAttachment;
    if (!text && !att) return false;
    inp.value = '';
    // 添付があれば text 先頭にパスを差し込む（claude -p が Read で読む）。ユーザー本文は温存
    const sendText = att ? ('[添付ファイル: ' + att.path + ']\n' + text) : text;
    pendingAttachment = null; renderAttach();
    const attHtml = att ? '<div class="msg-att">' + UI_ICONS.attach + ' '
      + att.name.replace(/</g, '&lt;').replace(/>/g, '&gt;') + '</div>' : '';
    const tab = activeTabObj();
    if (tabBusy(tab)) { queueFollowup(tab, text, sendText, attHtml); updateSendBtn(); return false; }  // 返答後に送る
    addMsg('user', attHtml + mdlite(text || '(添付のみ)'), text || '(添付のみ)');
    const msg = addMsg('assistant', UI_ICONS.loading + ' 実行中…');
    startFollowup(tab, sendText, msg);
    return false;
  }

  // ── 音声読み上げ（通常は /tts → <audio>、Voice conversation は端末の en-US 音声） ──
  // /voicevox-stop（PC スピーカー停止）とは別系統。停止はブラウザ内 stopSpeak() で完結する。
  const TTS_READ_LIMIT = 600;  // 読み上げ上限文字数（文境界でカット。全文読みたければ大きくする）
  const ENGLISH_VOICE_PROFILE = Object.freeze({lang:'en-US', rate:0.98, pitch:1.0, volume:1.0});
  const DASHBOARD_DISPLAY_LANGUAGE = __DISPLAY_LANGUAGE__;
  const SILENT_WAV = 'data:audio/wav;base64,UklGRiQAAABXQVZFZm10IBAAAAABAAEAQB8AAIA+AAACABAAZGF0YQAAAAA=';
  const ttsAudio = new Audio();  // 1個を使い回す（ジェスチャ時のアンロックを保持するため）
  let ttsSeq = 0, audioUnlocked = false, ttsResolve = null;
  let selectedEnglishVoice = null;
  let autoSpeak = localStorage.getItem('autoSpeak') === '1';

  function getEnglishVoice() {
    if (selectedEnglishVoice) return selectedEnglishVoice;
    if (typeof speechSynthesis === 'undefined') return null;
    try {
      selectedEnglishVoice = speechSynthesis.getVoices()
        .find(v => /^en-US(?:-|$)/i.test(v.lang)) || null;
    } catch (_) {}
    return selectedEnglishVoice;
  }
  if (typeof speechSynthesis !== 'undefined' && speechSynthesis.addEventListener) {
    speechSynthesis.addEventListener('voiceschanged', () => { selectedEnglishVoice = null; });
  }

  function unlockAudio() {  // ユーザージェスチャ文脈で呼ぶ。以後ポーリング完了時の自動再生が通る
    if (audioUnlocked) return;
    ttsAudio.src = SILENT_WAV;
    ttsAudio.play().then(() => { audioUnlocked = true; }).catch(() => {});
  }

  function ttsPlain(t) {  // markdown 記号を落として読み上げ用プレーンテキスト化
    return t.replace(/```[\s\S]*?```/g, ' ')
            .replace(/`([^`]*)`/g, '$1')
            .replace(/\*\*?([^*]+)\*\*?/g, '$1')
            .replace(/!?\[([^\]]*)\]\([^)]*\)/g, '$1')
            .replace(/^#+\s*/gm, '')
            .replace(/^[-*>]\s+/gm, '')
            .replace(/https?:\/\/[^\s)]+/g, 'URL')
            .replace(/[|_~#]/g, ' ');
  }

  function ttsChunks(t) {  // 文末（。！？!?・改行）で分割し約60字に結合（voicevox_speak.ps1 と同ロジック）
    const parts = t.split(/(?<=[。！？!?\n])/);
    const chunks = [];
    let cur = '';
    for (const s of parts) {
      if (!s.trim()) continue;
      if (cur.length > 0 && cur.length + s.length > 60) { chunks.push(cur); cur = s; }
      else cur += s;
    }
    if (cur.trim()) chunks.push(cur);
    return chunks.length ? chunks : [t];
  }

  function limitTtsText(text) {
    let plain = ttsPlain(text || '').trim();
    if (plain.length > TTS_READ_LIMIT) {  // 上限内の最後の文末で切る（なければ強制カット）
      const head = plain.slice(0, TTS_READ_LIMIT);
      const m = head.match(/[\s\S]*[。！？!?\n]/);
      plain = m ? m[0] : head;
    }
    return plain;
  }

  function playUrl(url) {
    return new Promise(res => {
      ttsResolve = res;
      ttsAudio.onended = ttsAudio.onerror = () => res();
      ttsAudio.src = url;
      ttsAudio.play().catch(() => res());  // 自動再生ブロック時も止まらず抜ける
    });
  }

  async function speakJapanese(text) {
    stopSpeak();
    const my = ++ttsSeq;
    const plain = limitTtsText(text);
    if (!plain) return;
    const chunks = ttsChunks(plain);
    byId('tts-stop').hidden = false;
    const fetchChunk = c => fetch('/tts?text=' + encodeURIComponent(c))
        .then(r => { if (!r.ok) throw 0; return r.blob(); })
        .then(b => URL.createObjectURL(b));
    let playedAny = false;
    let next = fetchChunk(chunks[0]);
    try {
      for (let i = 0; i < chunks.length; i++) {
        const url = await next;
        if (i + 1 < chunks.length) next = fetchChunk(chunks[i + 1]);  // 再生中に次チャンクを先読み
        if (my !== ttsSeq) { URL.revokeObjectURL(url); return; }    // 停止/新規発話で離脱
        await playUrl(url);
        playedAny = true;
        URL.revokeObjectURL(url);
        if (my !== ttsSeq) return;
      }
    } catch (e) {  // /tts 失敗（VOICEVOX 停止等）→ 端末TTSへ。一部再生済みなら二重読み回避で黙る
      if (my === ttsSeq && !playedAny) { speakFallback(plain); return; }
    }
    if (my === ttsSeq) byId('tts-stop').hidden = true;
  }

  function speakEnglish(text) {
    stopSpeak();
    const my = ++ttsSeq;
    const plain = limitTtsText(text);
    if (!plain) return;
    const chunks = ttsChunks(plain);
    byId('tts-stop').hidden = false;
    const fetchChunk = c => fetch('/tts?voice=en-US&text=' + encodeURIComponent(c))
        .then(r => { if (!r.ok) throw 0; return r.blob(); })
        .then(b => URL.createObjectURL(b));
    let playedAny = false;
    let next = fetchChunk(chunks[0]);
    (async () => {
      try {
        for (let i = 0; i < chunks.length; i++) {
          const url = await next;
          if (i + 1 < chunks.length) next = fetchChunk(chunks[i + 1]);
          if (my !== ttsSeq) { URL.revokeObjectURL(url); return; }
          await playUrl(url);
          playedAny = true;
          URL.revokeObjectURL(url);
          if (my !== ttsSeq) return;
        }
      } catch (_) {
        // Keep the fallback English too; never fall back to Japanese VOICEVOX here.
        if (my === ttsSeq && !playedAny) speakFallback(plain, ENGLISH_VOICE_PROFILE);
        return;
      }
      if (my === ttsSeq) byId('tts-stop').hidden = true;
    })();
  }

  function speakVoice(text, language = 'en') {
    if (language === 'ja') return speakJapanese(text);
    return speakEnglish(text);
  }

  // Normal chat read-aloud (automatic and per-message) follows the saved dashboard language.
  function speak(text) {
    return speakVoice(text, DASHBOARD_DISPLAY_LANGUAGE);
  }

  function speakFallback(t, profile = {lang:'ja-JP', rate:1.0, pitch:1.0, volume:1.0}) {
    try {
      speechSynthesis.cancel();
      const u = new SpeechSynthesisUtterance(t);
      u.lang = profile.lang;
      u.rate = profile.rate;
      u.pitch = profile.pitch;
      u.volume = profile.volume;
      u.onend = u.onerror = () => { byId('tts-stop').hidden = true; };
      speechSynthesis.speak(u);
    } catch (e) { byId('tts-stop').hidden = true; }
  }

  function stopSpeak() {  // ブラウザ内再生の停止（PC スピーカーの /voicevox-stop とは別物）
    ttsSeq++;
    ttsAudio.pause();
    if (ttsResolve) { ttsResolve(); ttsResolve = null; }  // 再生待ちの speak() ループを起こして離脱させる
    try { speechSynthesis.cancel(); } catch (e) {}
    byId('tts-stop').hidden = true;
  }

  function toggleAutoSpeak() {
    autoSpeak = !autoSpeak;
    localStorage.setItem('autoSpeak', autoSpeak ? '1' : '0');
    byId('tts-toggle').classList.toggle('on', autoSpeak);
    if (autoSpeak) unlockAudio(); else stopSpeak();  // ON タップ＝ジェスチャ。ここでアンロック
  }

  function attachSpeak(el, text) {  // アシスタントメッセージに読み上げボタンを付ける
    el.dataset.ttsText = text;
    const actions = attachCopy(el, text);
    if (actions.querySelector('.msg-speak')) return;
    const b = document.createElement('a');
    b.href = '#';
    b.className = 'msg-speak';
    b.innerHTML = UI_ICONS.speaker;
    b.title = 'このメッセージを読み上げ';
    actions.appendChild(b);
  }

  // Recording format for voice conversation.
  function pickMicMime() {
    const cands = ['audio/webm;codecs=opus', 'audio/webm', 'audio/mp4', 'audio/ogg;codecs=opus'];
    for (const c of cands) { if (window.MediaRecorder && MediaRecorder.isTypeSupported(c)) return c; }
    return '';
  }
  const MIC_MIME = pickMicMime();
  const MIC_SUPPORTED = !!(navigator.mediaDevices && navigator.mediaDevices.getUserMedia
                            && window.MediaRecorder && MIC_MIME);

  // forTabId 省略時は「呼び出した瞬間にアクティブだったタブ」に固定する（doExec/sendFollowup等の
  // 呼び出し元が既に targetTabId を捕まえてから渡してくる・restoreDockState は複数タブぶん明示的に渡す）。
  // ここで拾うタブは背後に回っても消えない（tab.pollTimer/tab.jobId で追い続ける）ので、
  // 他タブを操作している間も応答生成は止まらない。入力欄・自動読み上げ・停止ボタンといった
  // 「今画面に出ている1本分」の共有UIだけは、その時点でこのタブがアクティブな場合に限って触る。
  function poll(id, msgEl, forTabId, model) {
    const tid = forTabId || (activeTabObj() && activeTabObj().id);
    const tab = tabById(tid);
    if (!tab) return;  // 対象タブが既に閉じられていた
    const isActive = () => activeTabObj() === tab;
    if (isActive()) stopWatch();  // ntfy監視中に自分でポーリングを引き継ぐ場合、二重ポーリングを避ける
    if (tab.pollTimer) clearInterval(tab.pollTimer);
    tab.watchLastJobId = id;  // このジョブは（このタブでは）既に表示済み扱いにする（監視再開時の誤検知防止・タブ単位）
    tab.jobId = id;
    if (typeof model === 'string') tab.model = model;
    renderTabBar();  // タブのぐるぐるアイコンを即座に反映（背後のタブで開始した場合も気づけるように）
    if (isActive()) setBusy(true);  // ID確定後に対象を限定した停止ボタンを有効化
    tab.pollTimer = setInterval(() => {
      fetch('/job?id=' + id).then(r => r.json()).then(d => {
        if (tabById(tid) !== tab || tab.jobId !== id) return;
        // サーバー再起動でJOB状態が消えると /job は404 {"error":"unknown job"} を返す。
        // d.status が undefined のままだと後続の分岐に落ちて「(結果なし)」に誤表示されて
        // いたので、ここで検知して transcript からの復元を試みる（2026-08-17）。
        if (d.error === 'unknown job') {
          clearInterval(tab.pollTimer); tab.pollTimer = null;
          tab.jobId = '';
          renderTabBar();
          if (isActive()) setBusy(false);
          recoverFromLostJob(msgEl, tab.id);
          return;
        }
        setTabModel(tab, d.model);
        applySessionTabRequest(d, tab).catch(() => {});
        if (d.status === 'running') {
          if (d.partial) {
            msgEl.innerHTML = mdlite(d.partial) + '<span class="chat-cursor">▌</span>';
            attachCopy(msgEl, d.partial);
            renderMermaidIn(msgEl);
          }
          return;
        }
        clearInterval(tab.pollTimer); tab.pollTimer = null;
        tab.jobId = '';
        if (!isActive()) tab.unread = true;
        else if (minimized) miniUnread = true;  // 畳んでいる間に届いた返答は ✅ で知らせる
        if (isActive()) setBusy(false);
        renderTabBar();
        // 実行に使ったアカウント・モデル（空いている方へ自動で切り替わる／モデルは途中で
        // 変えられるので、どの応答がどれで走ったか毎回の吹き出しに出す・2026-08-13）
        const modelLabel = MODEL_LABELS[d.model] || d.model || '';
        const acctParts = [d.account, modelLabel].filter(Boolean);
        const acct = acctParts.length ? '<div class="chat-acct">' + acctParts.join(' ・ ') + '</div>' : '';
        // Claudeが上限/認証切れでCodexへ回った時は、モデルが変わったことを明示する
        // （黙って変わると返答の質の違いの理由が分からない・2026-09-26）。
        const switched = d.model_switched
          ? '<div class="stop-note">' + UI_ICONS.warn + ' Claudeが使えずモデルを切り替えました（'
            + escapeHtml(d.model_switched) + '）</div>'
          : '';
        if (d.status === 'error') {
          msgEl.innerHTML = mdlite(d.result || '(エラー)') + acct + switched;
          attachCopy(msgEl, d.result || '(エラー)');
          renderMermaidIn(msgEl);
          tab.session = d.session || tab.session;
          if (isActive()) { byId('result').classList.add('err'); chatSession = tab.session; byId('chat-input-row').hidden = false; byId('chat-input').focus(); }
          returnQueue(tab);  // エラー後に待ち行列を流すと同じ失敗を重ねるので入力欄へ戻す
          return;
        }
        if (d.status === 'stopped') {
          // partial には停止直前まで実際に生成されていた内容が入っている（結果ではなく
          // 途中経過だが、捨てずに見せる。中断なので session はそのまま残し続きを打てる）。
          msgEl.innerHTML = mdlite(d.partial || '') + '<div class="stop-note">'
            + UI_ICONS.stop + ' 停止しました（ここまでが生成済みの内容です）</div>';
          attachCopy(msgEl, d.partial || '');
          renderMermaidIn(msgEl);
          if (d.session) {
            tab.session = d.session;
            if (isActive()) { chatSession = d.session; byId('chat-input-row').hidden = false; byId('chat-input').focus(); startWatch(d.session); }
          }
          flushQueue(tab);  // ⏹で止めた＝割り込み。待っていた発言をすぐ送る
          return;
        }
        if (isActive() && window.SFX) SFX.chat_done();
        // 思考過程は画面に表示しない。サーバー側で保持していても、利用者には最終回答だけを見せる。
        msgEl.innerHTML = mdlite(d.result || '(結果なし)');
        renderMermaidIn(msgEl);
        attachSpeak(msgEl, d.result || '');
        if (acct) msgEl.insertAdjacentHTML('beforeend', acct);
        if (switched) msgEl.insertAdjacentHTML('beforeend', switched);
        // エンジンをまたいだ引き継ぎはベストエフォート（要約せず原文を渡すだけ）なので、
        // 保証はできないと画面上で明示する（決裁 d-b1438040・2026-09-07 承認）。
        if (d.cross_engine_handoff) msgEl.insertAdjacentHTML('beforeend',
          '<div class="stop-note">' + UI_ICONS.warn
            + ' 引き継ぎは不完全な場合があります（会話がエンジンをまたいでいます）</div>');
        if (d.choices && d.choices.length) renderChoices(msgEl, d.choices);  // 選択肢/承認ボタン
        if (isActive() && autoSpeak && d.result) speak(d.result);  // 🔊 ON なら新しい返答を自動読み上げ（アクティブタブのみ）
        if (d.session) {
          tab.session = d.session;
          if (isActive()) {
            chatSession = d.session;
            byId('chat-input-row').hidden = false;
            byId('chat-input').focus();
            startWatch(d.session);  // ntfyの選択肢ボタンからの返信をタブ側が拾えるように見張り続ける
          }
        }
        flushQueue(tab);  // 返答中に送られていた発言をここで届ける
      }).catch(() => {});  // 一時的な通信失敗は次のポーリングに任せる
    }, 900);  // 途中経過(partial)を見せたいので短め（2026-07-27）
  }

  // サーバー再起動でJOB状態を見失った時のフォールバック（2026-08-17、2026-08-24 リトライ化）。
  // dashboard_server.py の claude -p は素の subprocess.Popen で起動しており（プロセスグループ
  // 指定なし）、Windowsでは親(HTTPサーバー)が Stop-Process 等で落ちても子(claude本体)は道連れに
  // ならず実行を続ける。つまりサーバー再起動の瞬間はまだ応答が書き終わっていないことが多い
  // （特にツール呼び出しを何度も挟む長いターン）。旧実装は /history-log を1回だけ見て末尾が
  // assistant でなければ即諦めていたため、裏で応答が完成しても取りこぼし、
  // 「🔄再読み込み」ボタンを押しても sessionStorage の古いスナップショットを描き直すだけで
  // 新しい内容は出ず（saveDockState の保存タイミングは応答完了前）、結局ホームの対話履歴から
  // 手動で開き直すしかなかった。ここでは「今の吹き出しを含めて表示済みの件数」を基準に、
  // transcript（/history-log）がその件数に追いつく＝応答完了まで数秒おきに待ち続ける。
  function recoverFromLostJob(msgEl, forTabId) {
    const tab = tabById(forTabId) || activeTabObj();
    if (!tab) return;
    const isActive = () => activeTabObj() === tab;
    const session = tab.session;
    const RECOVER_INTERVAL_MS = 3000;
    const RECOVER_MAX_MS = 5 * 60 * 1000;  // 多段ツール呼び出しの長考でも待てるよう5分
    const startTs = Date.now();
    // 今表示中の吹き出し（このmsgEl自身＝まだ埋まっていない応答枠）を含めた件数。
    // /history-log の件数がこれに追いついた時、末尾のassistantが「今回の本物の応答」だと分かる
    // （追いつく前に見えるassistant末尾は、まだ書き終わっていない一つ前のターンの可能性がある）。
    const pane = paneOf(tab.id);
    const knownCount = pane ? pane.querySelectorAll('.chat-msg').length : 0;
    function giveUp() {
      if (isActive()) byId('result').classList.add('err');
      msgEl.innerHTML = 'サーバー再起動から時間が経ちましたが実行結果を確認できませんでした。';
      // location.reload() は sessionStorage の古いスナップショット(saveDockState)を描き直す
      // だけで応答完了後の内容を反映しない。resumeHistory() は /history-log を直接取り直す
      // ので、こちらを直接呼ぶボタンにする（2026-08-24。ホーム→対話履歴から開き直すのと同じ経路）。
      const btns = document.createElement('div');
      btns.className = 'choice-btns';
      const b = document.createElement('button');
      b.type = 'button';
      b.className = 'choice-btn';
      b.innerHTML = UI_ICONS.refresh + ' 会話を読み直す';
      b.onclick = () => { switchTab(tab.id); resumeHistory(session, tab.label, null, true); };
      btns.appendChild(b);
      msgEl.appendChild(btns);
      if (isActive()) byId('chat-input-row').hidden = false;
      returnQueue(tab);
    }
    if (!session) { giveUp(); return; }
    msgEl.innerHTML = UI_ICONS.loading + ' サーバーが再起動されました。実行が裏で続いている'
      + '可能性があるため結果を待っています…';
    function attempt() {
      fetch('/history-log?session=' + encodeURIComponent(session)).then(r => r.json()).then(msgs => {
        const last = msgs && msgs.length ? msgs[msgs.length - 1] : null;
        if (last && last.role === 'assistant' && msgs.length >= knownCount) {
          if (isActive()) byId('result').classList.remove('err');
          msgEl.innerHTML = mdlite(last.text);
          renderMermaidIn(msgEl);
          attachSpeak(msgEl, last.text);
          if (!isActive()) tab.unread = true;
          if (isActive()) {
            byId('chat-input-row').hidden = false;
            byId('chat-input').focus();
            if (minimized) miniUnread = true;
            if (autoSpeak) speak(last.text);  // 🔊 ON なら復旧できた返答も自動読み上げ
            startWatch(session);
          }
          renderTabBar();
          flushQueue(tab);
          return;
        }
        if (Date.now() - startTs > RECOVER_MAX_MS) { giveUp(); return; }
        setTimeout(attempt, RECOVER_INTERVAL_MS);
      }).catch(() => {
        if (Date.now() - startTs > RECOVER_MAX_MS) { giveUp(); return; }
        setTimeout(attempt, RECOVER_INTERVAL_MS);
      });
    }
    attempt();
  }

  // ── 🔄 再取得（2026-08-30 ユーザーの投函メモ）──
  // 通信が切れて応答が吹き出しに出ないまま poll() が静かに止まる経路（モバイルの
  // バックグラウンドで setInterval が凍結／タブ復元時に jobId を持ち越せなかった／
  // 一時的な通信失敗が長引いた）では、これまでページ全体をリロードして対話履歴から
  // 開き直すしか手が無かった（recoverFromLostJob はサーバー再起動を検知できた時だけ）。
  // このボタンは「今ドックで開いている会話」に限定して最新状態を取り直す：
  //   ① まずサーバーにこのセッションの実行中ジョブを問い合わせ、生きていれば poll() を張り直す
  //   ② ジョブが把握されていなければ /history-log からログ全文を取り直して描き直す
  // どちらもページ遷移なし。session が無い＝取り直す対象が無い時は何もしない。
  function refetchDock() {
    const tab = activeTabObj();
    const btn = byId('refetch-btn');
    if (btn && btn.disabled) return;
    const jobId = activeTabObj() ? activeTabObj().jobId : '';
    if (!chatSession && !jobId) return;  // まだ会話が始まっていない（openChat 直後など）
    if (btn) { btn.disabled = true; setTimeout(() => { btn.disabled = false; }, 4000); }
    const q = jobId ? ('id=' + encodeURIComponent(jobId))
                     : ('session=' + encodeURIComponent(chatSession));
    fetch('/job?' + q).then(r => r.ok ? r.json() : null).then(d => {
      if (activeTabObj() !== tab) return;
      if (d && d.id && d.status) {
        // ジョブがまだ生きている（running でも done 直後でも）。末尾の応答枠へ poll を張り直す。
        const last = activePane().lastElementChild;
        const msgEl = (last && last.classList.contains('assistant'))
          ? last : addMsg('assistant', UI_ICONS.loading + ' 最新の状態を取り直しています…');
        byId('result').classList.remove('err');
        setBusy(d.status === 'running');
        poll(d.id, msgEl, tab.id, d.model || '');
        return;
      }
      reloadTranscriptInPlace();  // サーバーはこのジョブを把握していない → transcript を取り直す
    }).catch(() => { if (activeTabObj() === tab) reloadTranscriptInPlace(); });
  }

  function reloadTranscriptInPlace() {
    if (!chatSession) {  // session が無いと /history-log を引けない（取り直せない）
      byId('result').classList.add('err');
      addMsg('assistant', 'この会話は再取得できません（セッションIDがありません）。ホームの対話履歴から開き直してください。');
      byId('chat-input-row').hidden = false;
      return;
    }
    if (activeTabObj() && activeTabObj().pollTimer) { clearInterval(activeTabObj().pollTimer); activeTabObj().pollTimer = null; }
    const log = activePane();
    const prevCount = log.querySelectorAll('.chat-msg').length;
    const marker = addMsg('assistant', UI_ICONS.loading + ' 最新の状態を取り直しています…');
    fetch('/history-log?session=' + encodeURIComponent(chatSession))
      .then(r => r.json())
      .then(list => {
        log.innerHTML = '';
        if (!list || !list.length) {
          addMsg('assistant', '会話ログを取得できませんでした。少し待ってからもう一度試してください。');
          byId('chat-input-row').hidden = false;
          return;
        }
        list.forEach(m => {
          const el = addMsg(m.role === 'user' ? 'user' : 'assistant', mdlite(m.text), m.text);
          if (m.role === 'assistant') attachSpeak(el, m.text);
        });
        setBusy(false);
        byId('result').classList.remove('err');
        byId('chat-input-row').hidden = false;
        byId('chat-input').focus();
        const lastMsg = list[list.length - 1];
        if (log.querySelectorAll('.chat-msg').length > prevCount && lastMsg.role === 'assistant') {
          if (window.SFX) SFX.chat_done();               // 取り直して応答が増えた＝完了通知と同じ扱い
          if (minimized) { miniUnread = true; updateMiniBar(false); }
          if (autoSpeak) speak(lastMsg.text);
        }
        startWatch(chatSession);  // 以後 ntfy 経由の返信も拾えるようにしておく
      })
      .catch(e => {
        marker.textContent = '取り直しに失敗しました: ' + e;
        byId('chat-input-row').hidden = false;
      });
  }

  // ── 選択肢・承認ボタン（2026-08-16）: NTFY_CHOICES を対話パネル内にも表示。ボタンを押す
  // 行為そのものを人間確認とみなし、そのジョブに限り改札フック(CLAUDE_UNMANNED)を外して送信
  // する（confirm=1）。自由入力のテキスト送信（sendFollowup）は対象外のまま。 ──
  function renderChoices(msgEl, choices) {
    const box = document.createElement('div');
    box.className = 'choice-btns';
    choices.forEach(c => {
      const b = document.createElement('button');
      b.type = 'button';
      b.className = 'choice-btn';
      b.textContent = c;
      b.onclick = () => sendChoice(c, box);
      box.appendChild(b);
    });
    msgEl.appendChild(box);
  }

  function sendChoice(text, box) {
    const targetTabId = activeTabObj().id;
    box.querySelectorAll('button').forEach(b => b.disabled = true);  // 連打・二重送信防止
    unlockAudio();
    stopSpeak();
    addMsg('user', mdlite(text), text);
    const msg = addMsg('assistant', UI_ICONS.loading + ' 実行中…');
    setBusy(true);
    fetch('/exec?skill=&text=' + encodeURIComponent(text) + '&session=' + encodeURIComponent(chatSession)
        + '&label=' + encodeURIComponent(chatLabel) + '&confirm=1')
      .then(r => r.json())
      .then(d => {
        if (d.error) {
          byId('result').classList.add('err');
          msg.textContent = d.error === 'busy' ? 'この会話では別の返答を生成中です。終了後にもう一度送信してください。' : d.error;
          setBusy(false);
          byId('chat-input-row').hidden = false;
          return;
        }
        reportAutoModel(d.model);
        poll(d.job, msg, targetTabId, d.model || '');
      })
      .catch(e => { byId('result').classList.add('err'); msg.textContent = '送信に失敗: ' + e; setBusy(false); byId('chat-input-row').hidden = false; });
  }

  // ntfyの選択肢ボタンはスマホ→サーバーへ直接 GET /exec するため、poll() が止まった後の
  // タブは何も知らない。ここで低頻度に見張り、想定外の新規ジョブ（＝ntfy経由の返信）を
  // 検知したら通常の poll() に引き継ぐ。バックグラウンドタブや長時間放置での電池消費を
  // 避けるため、非表示中は止め・10分で自動終了する（2026-07-28 追加）。
  function startWatch(session) {
    // 既に見張り中なら何もしない（多重起動防止）。startWatch() は poll() 完了時と
    // visibilitychange の両方から呼ばれるため、タイミングが重なると複数のタイマーが
    // 並行して動き、同じジョブを二重に検知して poll() を複数回呼ぶ＝メッセージ枠が
    // 複数作られ最初の枠は「実行中…」のまま固まり、autoSpeak も重複発火する
    // （2026-07-29 判明・TTSの同文連呼と「実行中から動かない」の共通原因）。
    if (watchTimer) return;
    const tab = activeTabObj();  // 見張り対象を呼び出し時点のアクティブタブに固定（タブ単位でjob既読を追う）
    if (!tab) return;
    watchStartTs = Date.now();
    watchTimer = setInterval(() => {
      if (document.hidden) return;
      if (Date.now() - watchStartTs > WATCH_MAX_MS) { stopWatch(); return; }
      fetch('/job?session=' + encodeURIComponent(session)).then(r => { if (!r.ok) throw 0; return r.json(); })
        .then(d => {
          if (d.id === tab.watchLastJobId) return;  // このタブでは既知のジョブ＝変化なし
          // タブ切替中にfetchが返ってくることがある。既にこのwatchは止まっているはずだが、
          // 念のため対象タブがまだ存在するか確認してから描き込む（消えたタブへの書き込み事故防止）。
          if (!tabById(tab.id)) return;
          // 新規ジョブを検知。running/done を問わず poll() に渡す（実行が速く、この4秒間隔の
          // 隙間で既に完了していた場合も poll() 側の初回フェッチで正しく結果を拾える。
          // 「done なら無視」にすると、その一回きりの結果を永遠に取りこぼす＝2026-07-29 判明の
          // バグそのものだったので、running 限定のガードは撤去した）。
          tab.watchLastJobId = d.id;
          const isActive = () => activeTabObj() === tab;
          // ntfy経由だとユーザー発言はブラウザを経由しないため、通常のsendFollowup()と違い
          // addMsg('user', …) が一度も呼ばれていない。/job の prompt から復元して表示する
          // （2026-07-29 追加。session継続時の prompt はそのまま次の発言テキスト＝1381行
          // start_job() の prompt = text.strip() と同じ値）。
          const pane = paneOf(tab.id);
          const addToTab = (role, html, text) => {
            if (!pane) return null;
            const d2 = document.createElement('div');
            d2.className = 'chat-msg ' + role;
            d2.innerHTML = html;
            if (typeof text === 'string') attachCopy(d2, text);
            pane.appendChild(d2);
            if (isActive()) d2.scrollIntoView({ behavior: 'smooth', block: 'end' });
            renderMermaidIn(d2);
            return d2;
          };
          if (d.prompt) addToTab('user', mdlite(d.prompt), d.prompt);
          const msg = addToTab('assistant', d.status === 'running'
            ? UI_ICONS.loading + ' 実行中…' : UI_ICONS.loading + ' 確認中…');
          if (!msg) return;  // 対象タブのペインが既に無い
          if (isActive()) setBusy(true);
          poll(d.id, msg, tab.id, d.model || '');  // poll() 側で完了後に startWatch() を再度呼び、見張りを継続する
        }).catch(() => {});
    }, WATCH_INTERVAL_MS);
  }
  function stopWatch() { if (watchTimer) { clearInterval(watchTimer); watchTimer = null; } }
  document.addEventListener('visibilitychange', () => {
    if (document.hidden) stopWatch();
    // 音声会話がアクティブな間は watch() を再開しない（2026-09-26）。voice の各ターンも
    // 同じ chatSession の下で新規ジョブを作るが、voice 側は poll() を使わず
    // tab.watchLastJobId を更新しないため、watch() がそれを「ntfy経由の外部発言」と
    // 誤検知して d.prompt（サーバーがLLM用に合成した内部プロンプト全文。作業状態のJSON
    // 付き）をそのままユーザー発言として吹き出しに二重表示していた（画面ロック→復帰の
    // たびにこの誤検知が起きていた）。
    else if (chatSession && !voiceChat.active && !(activeTabObj() && activeTabObj().pollTimer)) startWatch(chatSession);
  });

  // ── ドックを開く入口（クリック委譲・2026-08-11 にホーム側のリスナから分離） ──
  // どのページからでもスキル実行・チャット開始・履歴再開ができるよう、ドック自身が
  // 自分あてのクリックを拾う。ホーム側のリスナには決裁・メモなどホーム固有の処理だけが残る。
  // 対応する目印:
  //   [data-exec-skill]     モデル選択ポップアップを開く（選択後にスキルを裏実行してドックに出す。data-exec-text / -label 併用）
  //   [data-open-chat]      空のチャットを開く
  //   [data-resume-session] 過去の会話を読み直して再開する
  //   .msg-speak            その発言を読み上げる
  //   .mchip-pick           モデル選択ポップアップ内のチップ（選ぶと即実行）
  document.addEventListener('click', e => {
    const savedLink = e.target.closest('a[href]');
    if (savedLink) {
      const url = new URL(savedLink.href, location.href);
      const session = url.searchParams.get('resume');
      if (url.origin === location.origin && url.pathname === '/' && /^[0-9a-f-]{36}$/i.test(session || '')) {
        e.preventDefault(); shukiResumeSessionLink(session); return;
      }
    }
    const sp = e.target.closest('.msg-speak');
    if (sp) { e.preventDefault(); unlockAudio(); speak(sp.closest('.chat-msg').dataset.ttsText || ''); return; }
    const copy = e.target.closest('.msg-copy');
    if (copy) { e.preventDefault(); copyMessage(copy); return; }
    const qc = e.target.closest('[data-qcancel]');
    if (qc) { e.preventDefault(); cancelQueued(qc.dataset.qcancel); return; }
    const qn = e.target.closest('[data-qnow]');
    if (qn) { e.preventDefault(); stopJob(); return; }  // stopped になった時点で flushQueue が送る
    const ex = e.target.closest('[data-exec-skill]');
    if (ex) { e.preventDefault(); exec(ex.dataset.execSkill, ex.dataset.execText || '', ex.dataset.execLabel || ''); return; }
    const oc = e.target.closest('[data-open-chat]');
    if (oc) { e.preventDefault(); openChat(oc.dataset.openChat); return; }
    const rh = e.target.closest('[data-resume-session]');
    // session が空文字の行は無人便（12:30便・AIレーン実行便）の実行結果で、再開できる
    // 対話が無い（2026-09-05・対話履歴への無人便統合）。クリックしても何もしない。
    if (rh && rh.dataset.resumeSession) {
      e.preventDefault();
      if (typeof shukiSidebarClose === 'function') shukiSidebarClose();
      closeChatHistory();
      resumeHistory(rh.dataset.resumeSession, rh.dataset.resumeLabel, rh.dataset.resumeModel);
      return;
    }
    const mp = e.target.closest('.mchip-pick');
    if (mp) { e.preventDefault(); pickModel(mp.dataset.model); return; }
  });

  // ── ページ遷移をまたいだ引き継ぎ（2026-08-11） ──
  // SHUKI はページごとに完全なHTMLを返すMPAなので、遷移すると当然DOMは破棄される。
  // ドックを「全ページで消えずに残る」ように見せるため、離脱時に会話の見た目と状態を
  // sessionStorage へ退避し、遷移先で描き直す。走っていたジョブはIDを持ち越して
  // ポーリングを再開するので、応答待ちのまま別ページへ移っても結果を取りこぼさない。
  // sessionStorage を使うのはタブ単位で完結させるため（別タブに会話が漏れない・タブを
  // 閉じれば消える）。
  const DOCK_KEY = 'shukiDockState';
  const DOCK_TTL_MS = 6 * 60 * 60 * 1000;   // 6時間以上前の会話は復元しない（放置後の突然の復活を防ぐ）
  const DOCK_LOG_MAX = 300000;              // 保存する会話ログの上限（sessionStorage枠を食い潰さない）

  function saveDockState() {
    try {
      if (byId('result').hidden) { sessionStorage.removeItem(DOCK_KEY); return; }
      pushMirrorToTab();
      const tabs = TABS.map(t => {
        const pane = paneOf(t.id);
        let log = pane ? pane.innerHTML : '';
        while (log.length > DOCK_LOG_MAX && pane && pane.children.length > 1) {
          pane.removeChild(pane.firstElementChild);  // 古い発言から捨てる
          log = pane.innerHTML;
        }
        return { id: t.id, session: t.session, label: t.label, model: t.model, log: log,
                 jobId: t.pollTimer ? t.jobId : '', unread: t.unread,  // 応答待ちのまま離脱したか
                 watchLastJobId: t.watchLastJobId, queue: t.queue || [],
                 sessionTabsReceipt: t.sessionTabsReceipt };  // Do not reopen handled actions after reload.
      });
      sessionStorage.setItem(DOCK_KEY, JSON.stringify({
        ts: Date.now(),
        tabs: tabs,
        activeTab: activeTab,
        minimized: minimized,
        maximized: maximized,
        unread: miniUnread,
        err: byId('result').classList.contains('err'),
        inputHidden: byId('chat-input-row').hidden,
      }));
    } catch (e) {}  // 保存できなくても会話は続けられる（容量超過・プライベートモード等）
  }

  function restoreDockState() {
    let s = null;
    try { s = JSON.parse(sessionStorage.getItem(DOCK_KEY) || 'null'); } catch (e) { return; }
    if (!s) return;
    if (Date.now() - (s.ts || 0) > DOCK_TTL_MS) { sessionStorage.removeItem(DOCK_KEY); return; }
    byId('result').hidden = false;
    byId('result').classList.toggle('err', !!s.err);
    const saved = (s.tabs && s.tabs.length) ? s.tabs : [{
      id: null, session: s.session || '', label: s.label || '対話', log: s.log || '', jobId: s.jobId || '',
    }];  // 旧・単一会話スキーマ（〜2026-09-25）からの後方互換
    TABS = saved.map(st => {
      const t = makeTabObj(st.label);
      if (st.id) t.id = st.id;
      t.session = st.session || '';
      t.model = st.model || '';
      t.unread = !!st.unread;
      // 旧・単一会話スキーマ（〜2026-09-25）は tab.watchLastJobId を持たないので、
      // 代わりにトップレベルの旧 s.watchLastJobId（後方互換のためだけ残る）を1本目に充てる。
      t.watchLastJobId = st.watchLastJobId || (saved.length === 1 ? (s.watchLastJobId || '') : '');
      t.sessionTabsReceipt = st.sessionTabsReceipt;
      t.queue = Array.isArray(st.queue) ? st.queue : [];
      return t;
    });
    activeTab = Math.min(Math.max(s.activeTab || 0, 0), TABS.length - 1);
    byId('chat-log').innerHTML = '';
    TABS.forEach((t, i) => {
      const pane = makePane(t.id);
      pane.innerHTML = saved[i].log || '';
      pane.querySelectorAll('.chat-msg').forEach(el => {
        const actions = attachCopy(el);
        const button = actions.querySelector('.msg-copy');
        button.querySelector('span').textContent = 'Copy';
        delete button.dataset.state;
      });
      pane.hidden = (i !== activeTab);
    });
    renderTabBar();
    pullMirrorFromTab();
    setResultTitle('comment', chatLabel || '対話');
    // ページ遷移で tab.watchLastJobId は消えてしまうため、上の TABS 生成時に保存値から
    // 復元済み（st.watchLastJobId）。これが無いと startWatch() が「直近の完了済みジョブ」を
    // 新規と誤認し、既にペインに描画済みのA→Bを再度追記して二重表示・読み上げ二重発火する
    // （2026-08-24 判明。サーバー再起動の復旧 location.reload() だけでなく通常のページ
    // 遷移全般で再現。2026-09-25 タブ機能新設でグローバル1本→タブごとに変更：グローバル
    // のままだと別タブの既読ジョブIDを引きずって誤検知し、まさに同じ理由で二重表示していた）。
    byId('chat-input-row').hidden = !!s.inputHidden;
    maximized = !!s.maximized;  // 最大化はページ遷移をまたいで保つ（畳んだ状態と独立）
    applyMaximize();
    if (s.minimized) { minimizeResult(); miniUnread = !!s.unread; updateMiniBar(!!saved.some(st => st.jobId)); }
    else scrollChatToLatest();
    // 応答待ちのまま遷移してきたタブがあれば、それぞれ自分のペインでポーリングを再開する
    // （非アクティブなタブぶんも裏で継続。setBusy 等の共通UIは poll() 内で isActive 判定して触る）。
    TABS.forEach((t, i) => {
      if (!saved[i].jobId) return;
      const pane = paneOf(t.id);
      const msgs = pane ? pane.querySelectorAll('.chat-msg.assistant') : [];
      const msgEl = msgs.length ? msgs[msgs.length - 1]
        : (pane ? (() => { const d = document.createElement('div'); d.className = 'chat-msg assistant';
                            d.innerHTML = UI_ICONS.loading + ' 実行中…'; pane.appendChild(d); return d; })() : null);
      if (msgEl) poll(saved[i].jobId, msgEl, t.id, t.model);
    });
    TABS.forEach(t => { if (!tabBusy(t)) flushQueue(t); });  // 遷移中に返答が終わっていた分
    if (!(activeTabObj() && activeTabObj().jobId) && chatSession) {
      startWatch(chatSession);  // ntfy経由の返信を拾えるようにしておく
    }
    updateFabVisibility();
  }

  // pagehide はモバイルSafari等で beforeunload が発火しないケースを拾う。visibilitychange も
  // 併用するのは、アプリ切替やタブ非表示のまま端末がページを破棄する経路への保険。
  window.addEventListener('pagehide', saveDockState);
  document.addEventListener('visibilitychange', () => { if (document.hidden) saveDockState(); });
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', restoreDockState);
  else restoreDockState();
  const savedSessionLink = new URLSearchParams(location.search).get('resume');
  if (/^[0-9a-f-]{36}$/i.test(savedSessionLink || '')) {
    if (document.readyState === 'loading')
      document.addEventListener('DOMContentLoaded', () => shukiResumeSessionLink(savedSessionLink));
    else shukiResumeSessionLink(savedSessionLink);
  }

  // ── モデル推奨エフェクト（2026-09-01）: /usage-accounts の残量+reset時刻を見て、
  // 「推奨しないモデル」だけ赤くする（ホーム画面のアカウントパネルとは独立。ドックは
  // 全ページ共通なので、ここで自前に取得する）。専用の週次枠が無い Haiku/Fable は
  // 近い枠で代用する（Haiku＝全体週次、Fable＝最上位モデルなので Opus週で代用）。
  const RISK_DANGER = 80;  // dashboard_server.py の CC_USAGE_DANGER と揃える（モジュールを跨がないよう値だけ複製）
  const RISK_RESET_FAR_MIN = 180;  // reset まで3時間以上あるのに高使用率＝「まだ遠いのに残量が少ない」
  const MODEL_RISK_WINDOW = __MODEL_RISK_WINDOW__;
  const MODEL_USAGE_EXEMPT = new Set(__MODEL_USAGE_EXEMPT__);

  function windowRisk(w) {  // 高使用率かつresetが遠い時だけ理由文字列を返す。リスク無しは null
    if (!w || w.utilization == null || w.utilization < RISK_DANGER) return null;
    if (!w.resets_at) return '残量僅少（reset時刻不明）';
    const minLeft = (new Date(w.resets_at) - new Date()) / 60000;
    if (!(minLeft > RISK_RESET_FAR_MIN)) return null;  // reset間近なら気にしなくてよい
    const days = Math.floor(minLeft / 1440), hours = Math.floor((minLeft % 1440) / 60);
    return '残量僅少・reset ' + (days ? days + 'd,' : '') + hours + 'h後';
  }

  // モデルが「推奨しない」状態かどうか（両アカウントとも同時に苦しい時だけ、片方に空きがあれば
  // 自動切替が拾うので実害が出ないため）。理由文字列を返す／リスク無しは null。
  function riskReason(usageAccounts, model) {
    if (!model || !usageAccounts.length || MODEL_USAGE_EXEMPT.has(model)) return null;
    const wkey = MODEL_RISK_WINDOW[model] || 'seven_day';
    let reason = null;
    const risky = usageAccounts.every(a => {
      const r = windowRisk(a[wkey]) || windowRisk(a.five_hour);
      if (r) reason = reason || r;
      return !!r;
    });
    return risky ? reason : null;
  }

  function updateModelRisk(usageByAccount) {
    const accounts = Object.values(usageByAccount || {}).filter(a => a && !a.error);
    document.querySelectorAll('.mchip-pick').forEach(btn => {
      const reason = riskReason(accounts, btn.dataset.model);
      btn.classList.toggle('mchip-risk', !!reason);
      if (reason) btn.title = reason; else btn.removeAttribute('title');
    });
    // <select> は個別の option を赤くできないため、危ないモデルは「⚠ 」をラベルに前置きし、
    // 今まさに選択中のモデルが危ない時だけ select 自体の枠を赤くする。
    const sel = byId('model-select');
    if (sel) {
      if (sel.dataset.baseTitle === undefined) sel.dataset.baseTitle = sel.title;
      let selReason = null;
      [...sel.options].forEach(opt => {
        if (opt.dataset.baseLabel === undefined) opt.dataset.baseLabel = opt.textContent;
        const reason = riskReason(accounts, opt.value);
        opt.textContent = (reason ? '⚠ ' : '') + opt.dataset.baseLabel;
        if (opt.value === sel.value && reason) selReason = reason;
      });
      sel.classList.toggle('mchip-risk', !!selReason);
      sel.title = selReason ? (selReason + ' ／ ' + sel.dataset.baseTitle) : sel.dataset.baseTitle;
    }
  }

  fetch('/usage-accounts').then(r => r.json()).then(updateModelRisk).catch(() => {});

'''


def assets_head():
    """<head> に入れるドックのスタイル。"""
    return "<style>" + CSS + dashboard_mascot.CSS + "</style>"


def dock_html():
    """</body> 直前に入れるドック本体（HTML＋スクリプト）。

    HTML/JS は vault のデータを含まない静的テンプレートなので、翻訳は tt() でまとめてかける
    （タスク名などデータが混ざる箇所に tt() を使うと誤置換しうるが、ここは対象外）。
    lang=ja なら tt() は素通しで、文字列は1文字も変わらない。
    """
    # ラベルは tt() の**後**に差し込まれるためテンプレート翻訳から漏れる。ここで t() を通す
    # （「Muse（実験・低速）」だけが lang=en で日本語のまま残っていた・2026-09-07）。
    labels = json.dumps({v: shuki_i18n.t(label, ctx="chat") for v, label in MODELS}, ensure_ascii=False)
    current = _current_model_getter()
    auto_model_mode = bool(_auto_model_mode_getter())
    model_effort = dashboard_settings.load_settings().get("model_effort", model_registry.effort_defaults())
    # モデル選択（2026-09-27）: 9モデル分のチップ列が折り返してユーザーのスマホでチャットログを圧迫していた
    # ため<select>1本に畳んだ。Auto もこの1本の中の選択肢にする（従来は別チップだった）。
    model_select = (
        f'<select id="model-select" class="model-select" aria-label="{shuki_i18n.t("モデル選択", ctx="chat")}"'
        ' onchange="onModelSelect(this.value)"'
        f' title="{shuki_i18n.t("Auto はプロバイダ内でモデル階層を自動選択します。個別モデルを選ぶとAutoは解除されます。", ctx="chat")}">'
        f'<option value="__auto__"{" selected" if auto_model_mode else ""}>{shuki_i18n.t("Auto", ctx="chat")}</option>'
        + "".join(
            f'<option value="{v}"{" selected" if not auto_model_mode and v == current else ""}>{shuki_i18n.t(label, ctx="chat")}</option>'
            for v, label in MODELS
        )
        + "</select>"
    )
    # effortはモデルごとの永続設定（/settings と同じ dashboard_settings.json）。Autoの間は
    # どのモデルの設定を編集しているのか曖昧になるため隠す（具体モデルを選ぶと現れる）。
    effort_select = (
        f'<select id="effort-select" class="effort-select" aria-label="{shuki_i18n.t("思考量(effort)", ctx="chat")}"'
        f'{" hidden" if auto_model_mode else ""} onchange="onEffortSelect(this.value)"'
        f' title="{shuki_i18n.t("思考量（effortが高いほどよく考えるが遅い・モデルごとに保存されます）", ctx="chat")}">'
        + "".join(
            f'<option value="{level}"{" selected" if model_effort.get(current) == level else ""}>{level}</option>'
            for level in dashboard_settings.EFFORT_LEVELS
        )
        + "</select>"
    )
    pick_chips = "".join(
        f'<button type="button" class="mchip-pick{" active" if v == current else ""}"'
        f' data-model="{v}">{shuki_i18n.t(label, ctx="chat")}</button>'
        for v, label in MODELS
    )
    html_out = (shuki_i18n.tt_html(HTML, ctx="chat")
                .replace("__MODEL_SELECT__", model_select)
                .replace("__EFFORT_SELECT__", effort_select)
                .replace("__MODEL_CHIPS_PICK__", pick_chips))
    static_icons = {
        "PLAY": _chat_icon("play"), "STOP": _chat_icon("stop"), "REFRESH": _chat_icon("refresh"),
        "CLOCK": _chat_icon("clock"),
        "SPEAKER": _chat_icon("speaker"), "MAXIMIZE": _chat_icon("maximize"),
        "MINIMIZE": _chat_icon("minimize"), "CROSS": _chat_icon("cross"),
        "ATTACH": _chat_icon("attach"), "FOLDER": _chat_icon("folder"), "LAYERS": _chat_icon("layers"),
        "MIC": _chat_icon("mic"), "SEND": _chat_icon("send"),
        "HOURGLASS": _chat_icon("hourglass"), "PENCIL": _chat_icon("pencil", 22),
        "SETTINGS": _chat_icon("settings"), "PLUS": _chat_icon("plus"),
    }
    for name, icon in static_icons.items():
        html_out = html_out.replace("__ICON_" + name + "__", icon)
    html_out = (html_out.replace("__MASCOT_HEADER__", dashboard_mascot.button_html("header"))
                .replace("__MASCOT_SPRITE__", dashboard_mascot.sprite_html()
                         if dashboard_settings.load_settings().get("mascot_enabled", True)
                         else _chat_icon("pencil", 22)))
    voice_js = Path(__file__).with_name("dashboard_voice.js").read_text(encoding="utf-8")
    return html_out + "\n<script>\n" + shuki_i18n.tt_js_ui(voice_js, ctx="chat") + "\n" + (shuki_i18n.tt_js_ui(JS, ctx="chat")
        .replace("__MODEL_LABELS__", labels)
        .replace("__AUTO_MODEL_INITIAL_MODEL__", json.dumps(current))
        .replace("__MODEL_EFFORT__", json.dumps(model_effort, ensure_ascii=False))
        .replace("__MODEL_RISK_WINDOW__", MODEL_RISK_WINDOW_JSON)
        .replace("__MODEL_USAGE_EXEMPT__", MODEL_USAGE_EXEMPT_JSON)
        .replace("__CHAT_ICONS__", CHAT_ICON_JSON)
        .replace("__DISPLAY_LANGUAGE__", json.dumps(shuki_i18n.current_lang()))
        .replace("__SKILL_CATALOG__", json.dumps(_skill_catalog_getter(), ensure_ascii=False)
                 .replace("<", "\\u003c"))) + "\n" + shuki_i18n.tt_js_ui(VOICE_BINDINGS, ctx="chat") + "\n" + shuki_i18n.tt_js_ui(dashboard_mascot.JS, ctx="chat") + "\n</script>"


VOICE_BINDINGS = r'''
function renderWorkConversation(work) {
  const log = byId('voice-work-messages');
  const states = {queued:'Queued', read:'Read — worker reported', applied:'Applied — worker reported'};
  // Older snapshots contain only the available messages and latest worker update.
  const history = Array.isArray(work.conversation) ? work.conversation : [
    ...(work.scope ? [{id:'scope', role:'user', kind:'scope', text:work.scope}] : []),
    ...(work.messages || []).map(message => ({...message, role:'user', kind:'message'})),
    ...(work.progress?.text ? [{id:'progress', role:'worker', kind:'progress', text:work.progress.text}] : []),
    ...(work.question ? [{...work.question, role:'worker', kind:'question'}] : []),
    ...(work.result ? [{id:'result', role:'worker', kind:'reply', text:work.result}] : [])
  ];
  const signature = JSON.stringify([work.id, history, work.messages]);
  if (log.dataset.signature === signature) return;
  const atBottom = log.dataset.job !== work.id || log.scrollHeight - log.scrollTop - log.clientHeight < 48;
  const scrollTop = log.scrollTop;
  log.dataset.job = work.id;
  log.dataset.signature = signature;
  log.replaceChildren();
  for (const entry of history) {
    const row = document.createElement('div');
    row.className = 'work-message work-message-' + (entry.role === 'user' ? 'user' : 'worker');
    row.dataset.event = entry.id || '';
    const label = document.createElement('div');
    label.className = 'work-message-label';
    const kind = {scope:'Approved scope', progress:'Update', question:'Question', reply:'Reply',
      read:'Message read', applied:'Message applied'}[entry.kind] || '';
    const message = entry.role === 'user' && (work.messages || []).find(message =>
      entry.id === 'message-' + message.id || entry.id === message.id);
    label.textContent = (entry.role === 'user' ? 'You' : 'Worker') + (kind ? ' · ' + kind : '')
      + (entry.created ? ' · ' + new Date(entry.created * 1000).toLocaleTimeString() : '')
      + (message ? ' · ' + (states[message.status] || 'Queued') : '');
    const body = document.createElement('div');
    body.className = 'work-message-body';
    if (entry.role === 'user') { body.textContent = entry.text; body.style.whiteSpace = 'pre-wrap'; }
    else body.innerHTML = mdlite(entry.text || '', true);
    row.append(label, body);
    log.appendChild(row);
  }
  renderMermaidIn(log);
  log.scrollTop = atBottom ? log.scrollHeight : scrollTop;
}
const voiceChat = new VoiceConversation({
  mime: MIC_MIME,
  pause: () => Number(byId('voice-pause').value),
  state: text => {
    byId('voice-status').textContent = text;
    const finish = byId('voice-ielts-finish');
    const answer = byId('voice-ielts-answer');
    if(answer) { answer.hidden=!voiceChat.active || !voiceChat.speakingPractice; answer.disabled=voiceChat.busy; }
    if (finish) finish.disabled = finish.dataset.scoring === '1' || (voiceChat.active &&
      (voiceChat.busy || voiceChat.transcribing > 0 || !!voiceChat.pending || voiceChat.speaking || voiceChat.clipSpeech));
    const tab = activeTabObj();
    const busy = voiceChat.active && voiceChat.busy;
    if (tab && tab.voiceBusy !== busy) { tab.voiceBusy = busy; renderTabBar(); }
  },
  model: model => { setTabModel(activeTabObj(), model); window.reportAutoModel?.(model); },
  active: on => {
    // 音声会話中は watch()（ntfy経由の外部返信検知）を止める（2026-09-26）。voice の各ターンも
    // 同じ chatSession の下で新規ジョブを作るが、tab.watchLastJobId は poll() だけが更新するため、
    // watch() が動いたままだと自分自身の発言を「外部からの新規発言」と誤検知し、サーバーが
    // LLM用に合成した内部プロンプト全文（作業状態のJSON付き）をそのままユーザー発言として
    // 二重表示していた（実機報告：発言のたびに背景作業のJSONが吹き出しに混ざる）。
    if (on) stopWatch();
    byId('voice-bar').hidden = false;
    byId('voice-conversation-hint').hidden = !on;
    byId('chat-input').placeholder = on ? 'Say it or type it here…' : 'Continue the conversation…';
    byId('voice-btn').innerHTML = UI_ICONS.mic;
    byId('voice-btn').setAttribute('aria-pressed', String(on));
    byId('attach-btn').disabled = on;
    byId('chat-add-btn').disabled = on;
    byId('chat-add-btn').hidden = on; byId('voice-btn').hidden = on;
    if (on) closeChatPickers();
    // モデル行は音声中も出したままにする（2026-09-24）。音声の応答モデルも
    // チップの選択に従うようになったので、隠すと切り替え手段が消える。
    if (!on) {
      autoSpeak = localStorage.getItem('autoSpeak') === '1';
      byId('tts-toggle').classList.toggle('on', autoSpeak);
    }
  },
  language: lang => {
    const label = lang === 'ja' ? '日本語' : 'English';
    byId('voice-language').textContent = label;
    byId('voice-language').title = 'Active voice language: ' + label;
    byId('voice-language-select').value = lang;
  },
  sources: (el, sources) => {
    const row = document.createElement('div'); row.className = 'voice-sources';
    row.setAttribute('aria-label', 'Notes checked');
    const buildVaultFileHref = path => '/files?p=' + encodeURIComponent(String(path));
    const sourceFileHref = source => {
      // The server-provided URL is the same canonical link shown in the lookup
      // payload. Keep it when present so top-level source links cannot drift.
      if (typeof source.url === 'string' && source.url.startsWith('/files?p=')) return source.url;
      return buildVaultFileHref(source.path);
    };
    for (const source of sources) {
      if (!source.path) continue;
      const link = document.createElement('a');
      link.href = sourceFileHref(source);
      link.target = '_blank'; link.rel = 'noopener';
      link.textContent = 'Checked: ' + source.title; row.append(link);
    }
    el.append(row);
  },
  // 音声の応答が返すセッションIDを対話パネル側にも渡す。これで音声を終えて
  // そのまま入力欄で続けても（逆に入力欄から音声へ移っても）同じ会話が続く。
  session: id => { if (id) chatSession = id; },
  workReply: () => byId('voice-work-reply').value,
  clearWorkReply: () => { byId('voice-work-reply').value = ''; },
  notice: text => addMsg('assistant', mdlite(text), text),
  draft: text => { byId('voice-status').textContent = voiceChat.speakingPractice && text ? 'Answer captured — continue speaking or press Send answer.' : text || 'Listening'; },
  user: text => { byId('voice-conversation-hint').hidden = true; return addMsg('user', mdlite(text), text); },
  reply: () => addMsg('assistant', '…'),
  render: (el, text) => { el.innerHTML = mdlite(text); attachCopy(el, text); renderMermaidIn(el); },
  proposal: proposal => {
    // 承認前の提案(Go ahead待ち)は会話の一部として会話ビューにそのまま出す（作業タブへは出さない）。
    // 作業タブに切り出すのは承認後の進行状況(work)だけ（2026-09-26）。
    byId('voice-proposal').hidden = !proposal;
    if (proposal) {
      const summary = byId('voice-work-summary');
      if (summary.dataset.summary !== proposal.summary) {
        summary.replaceChildren();
        if (proposal.changes) {
          const changes = document.createElement('div');
          changes.textContent = 'Plan updated — changes only:\n' + proposal.changes;
          changes.style.whiteSpace = 'pre-wrap';
          summary.append(changes);
          const details = document.createElement('details');
          const heading = document.createElement('summary');
          heading.textContent = 'Full current plan'; details.append(heading);
          const full = document.createElement('div'); full.textContent = proposal.summary;
          details.append(full); summary.append(details);
        } else summary.textContent = proposal.summary;
        summary.dataset.summary = proposal.summary;
      }
      byId('voice-work-approval-hint').textContent = voiceChat.language === 'ja'
        ? 'クリックせずに開始するには、表示された開始コマンドをそのまま言ってください。'
        : 'Ready to start. Reply naturally, or keep discussing; this plan stays visible.';
      byId('voice-proposal-error').textContent = proposal.error || '';
      byId('voice-work-start').disabled = !!proposal.starting;
      byId('voice-work-start').textContent = proposal.starting ? 'Starting…' : 'Go ahead';
    }
  },
  work: work => {
    if (!work) {  // ジョブがサーバー台帳から消えて復旧不能（2026-09-14）。カードごと畳んで隠す
      byId('voice-work-progress').hidden = true;
      byId('voice-proposal').hidden = true;
      workTabError = '';
      exitWorkTab();
      renderTabBar();  // 作業タブのボタン自体を消す
      return;
    }
    // 進行状況は「作業」タブ側でだけ表示する。会話ビューは占有しない（2026-09-26）。
    workTabError = work.error || '';
    byId('voice-work-progress').hidden = false;
    byId('voice-proposal').hidden = true;
    byId('voice-work-card').hidden = !workTabActive;
    renderTabBar();  // 実行中/完了/エラーのアイコンを作業タブへ反映
    const running = work.status === 'running';
    byId('voice-work-status').textContent = work.error ? 'Check work status' : running
      ? (work.stop_requested ? 'Stop requested' : 'Working — you can keep talking')
      : (work.status === 'waiting' ? 'Waiting for your answer'
        : work.status === 'done' ? 'Work finished — review the result' : 'Work ' + work.status);
    byId('voice-work-note').textContent = work.error || (running
      ? (work.stop_requested ? 'Waiting for a tool boundary; existing changes are kept.'
        : 'Messages below go to this work thread. Changes beyond its approved scope require approval.') : '');
    byId('voice-work-model').textContent = 'Work model: ' + (work.model || 'Not reported');
    const progress = work.progress || {};
    const activity = work.activity || {};
    const dated = item => item.text ? item.text + (item.updated ? ' · ' + new Date(item.updated * 1000).toLocaleTimeString() : '') : '';
    byId('voice-work-latest').textContent = [dated(progress), dated(activity)].filter(Boolean).join(' / ');
    const question = work.question;
    const extra = byId('voice-work-extra');
    const previousStatus = extra.dataset.status || '';
    const previousQuestion = extra.dataset.question || '';
    if (work.error || (question && (question.id !== previousQuestion || previousStatus !== 'waiting'))
        || (work.status === 'waiting' && previousStatus !== 'waiting')) extra.open = true;
    extra.dataset.status = work.status || '';
    extra.dataset.question = question?.id || '';
    byId('voice-work-question').textContent = question ?
      (question.kind === 'scope' ? 'Revised scope: ' : 'Worker asks: ') + question.text : '';
    byId('voice-work-approve').hidden = work.status !== 'waiting' || question?.kind !== 'scope';
    byId('voice-work-approve').disabled = !work.resume_ready || !!work.sending;
    const canSend = running || (['done', 'waiting'].includes(work.status) && work.resume_ready);
    byId('voice-work-send').disabled = !!work.sending || !canSend || !!question && (running || question.kind === 'scope');
    byId('voice-work-send').textContent = work.sending ? 'Sending…' : 'Send';
    byId('voice-work-reply').disabled = byId('voice-work-send').disabled;
    const sendState = byId('voice-work-send-state');
    sendState.textContent = work.sending ? 'Sending to this work thread…' : work.send_error || '';
    sendState.dataset.error = String(!!work.send_error);
    renderWorkConversation(work);
    byId('voice-work-stop').hidden = !running && work.status !== 'waiting';
    byId('voice-work-stop').disabled = !!work.stop_requested;
    byId('voice-work-detail').innerHTML = mdlite(work.result || work.partial || work.scope || '', true);
    renderMermaidIn(byId('voice-work-detail'));
    byId('voice-result').hidden = !['done', 'stopped', 'error'].includes(work.status);
  },
  rememberWork: (kind, id) => {
    if (id) localStorage.setItem('voiceWork', JSON.stringify({kind, id}));
    else localStorage.removeItem('voiceWork');
  },
  speak: (text, language = 'en', force = false) => { if (autoSpeak || force) speakVoice(text, language); },
  stopSpeak
});
function toggleVoiceConversation() {
  if (voiceChat.active) { voiceChat.end(); return; }
  voiceChat.speakingPractice = '';
  byId('voice-ielts-finish').hidden = true;
  byId('voice-ielts-answer').hidden = true;
  if (activeTabObj() && activeTabObj().pollTimer) {
    byId('voice-bar').hidden = false;
    voiceChat.state('Finish the current recording or job before starting voice.'); return;
  }
  // 進行中の会話があるならそれを引き継いで話し始める（2026-09-24）。従来は
  // openChat() で毎回ログと session を捨てていたため、入力欄→音声の切替で
  // 会話が切れていた。新規に始める時だけ従来どおり新しい会話を開く。
  const continuing = !byId('result').hidden && chatSession;
  if (continuing) {
    byId('voice-bar').hidden = false;
    restoreResult();
    byId('chat-input-row').hidden = false;
  } else {
    openChat('Voice conversation · English voice');
  }
  unlockAudio();
  autoSpeak = true;
  byId('tts-toggle').classList.add('on');
  voiceChat.start(continuing ? chatSession : '');
}
const IELTS_PRACTICE_KEY = 'shuki-ielts-speaking-practice';
const IELTS_SCORE_JOB_KEY = 'shuki-ielts-speaking-score-job';
window.startIELTSSpeaking = async () => {
  if (voiceChat.active || activeTabObj()?.pollTimer)
    throw new Error('Finish the current voice conversation or chat reply before starting IELTS practice.');
  if (sessionStorage.getItem(IELTS_SCORE_JOB_KEY))
    throw new Error('Wait for the current Speaking feedback to be saved before resuming practice.');
  let practice = null;
  const saved = sessionStorage.getItem(IELTS_PRACTICE_KEY);
  if (saved) {
    try { practice = await voiceChat.request('/english/exercise?id=' + encodeURIComponent(saved), {}, 10000, true); }
    catch (_) { sessionStorage.removeItem(IELTS_PRACTICE_KEY); }
    if (practice?.result) { practice=null; sessionStorage.removeItem(IELTS_PRACTICE_KEY); }
  }
  openChat('IELTS Speaking · English voice'); unlockAudio(); autoSpeak=true;
  byId('tts-toggle').classList.add('on');
  await voiceChat.start(practice?.thread || '');
  if (!voiceChat.active || !voiceChat.stream) throw new Error('Microphone access is needed to start Speaking practice.');
  try {
    if (!practice) practice = await voiceChat.request('/english/speaking/start', {
      method:'POST',headers:{'Content-Type':'application/json'},body:'{}'}, 10000, true);
    voiceChat.speakingPractice=practice.id; sessionStorage.setItem(IELTS_PRACTICE_KEY,practice.id);
    byId('voice-ielts-finish').hidden=false;
    byId('voice-ielts-answer').hidden=false;
    voiceChat.clearProposal(); voiceChat.lookupApproval=null;
    voiceChat.sendTyped(practice.turns.length ? 'Please repeat the last examiner question.' : 'Start IELTS Speaking practice.');
  } catch(error) { voiceChat.end(); throw error; }
};
async function pollIELTSScore(id) {
  const button=byId('voice-ielts-finish'); button.disabled=true; button.dataset.scoring='1';
  const reply=addMsg('assistant','Saving Speaking feedback…');
  const deadline=Date.now()+180000;
  try {
    while(Date.now()<deadline) {
      const data=await voiceChat.request('/job?id='+encodeURIComponent(id),{},10000,true);
      if(data.status==='running') { await new Promise(resolve=>setTimeout(resolve,700)); continue; }
      if(data.status!=='done') throw new Error(data.result || 'Speaking feedback was not saved.');
      voiceChat.ui.render(reply,data.result); voiceChat.state('Speaking feedback saved. Open English for your trend.');
      sessionStorage.removeItem(IELTS_SCORE_JOB_KEY); sessionStorage.removeItem(IELTS_PRACTICE_KEY);
      voiceChat.speakingPractice=''; button.hidden=true;
      window.dispatchEvent(new CustomEvent('english-speaking-saved',{detail:data.english_exercise}));
      window.dispatchEvent(new Event('english-updated')); return;
    }
    throw new Error('Scoring is still running. Return to English later to check the saved feedback.');
  } catch(error) {
    voiceChat.ui.render(reply,error.message); voiceChat.state(error.message);
    sessionStorage.removeItem(IELTS_SCORE_JOB_KEY);
  } finally { button.dataset.scoring=''; button.disabled=false; }
}
async function finishIELTSSpeaking() {
  const id=voiceChat.speakingPractice || sessionStorage.getItem(IELTS_PRACTICE_KEY);
  if(!id) return;
  if(voiceChat.active && (voiceChat.busy || voiceChat.transcribing || voiceChat.pending || voiceChat.speaking || voiceChat.clipSpeech)) {
    voiceChat.state('Send your current answer and wait for the examiner reply before finishing.'); return;
  }
  voiceChat.end();
  try {
    const result=await voiceChat.request('/english/speaking/finish',{
      method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id})},10000,true);
    if(result.exercise) {
      sessionStorage.removeItem(IELTS_PRACTICE_KEY); voiceChat.speakingPractice='';
      byId('voice-ielts-finish').hidden=true;
      window.dispatchEvent(new CustomEvent('english-speaking-saved',{detail:result.exercise.id})); return;
    }
    sessionStorage.setItem(IELTS_SCORE_JOB_KEY,result.job); await pollIELTSScore(result.job);
  } catch(error) { voiceChat.state(error.message); }
}
try {
  const saved=sessionStorage.getItem(IELTS_PRACTICE_KEY);
  if(saved) { voiceChat.speakingPractice=saved; byId('voice-ielts-finish').hidden=false; byId('voice-bar').hidden=false; }
  const scoring=sessionStorage.getItem(IELTS_SCORE_JOB_KEY);
  if(scoring) pollIELTSScore(scoring);
} catch (_) {}
window.addEventListener('pagehide', () => voiceChat.end());
try { voiceChat.restoreWork(JSON.parse(localStorage.getItem('voiceWork') || 'null')); } catch (_) {}
'''
