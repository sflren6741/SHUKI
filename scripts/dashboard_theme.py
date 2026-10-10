#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
dashboard_theme.py — デザイントークンの単一情報源（GET /theme.css の実体）

これまでパレットが3箇所に分裂していた（dashboard_server.PALETTE / dashboard_ui.PALETTE /
dashboard_settings.THEMES）ため、テーマ設定を変えても /theme.css を配信していないページ・
下部タブバーの配色だけが古いままズレる問題があった（2026-07-28 発見・UI基盤整備で解消）。

単一の正は引き続き dashboard_settings.THEMES（/settings で編集可能）。
このモジュールはそこから CSS custom properties（:root{...}）を組み立てて配信する入口。

画面コードは生の hex を書かず、必ず var(--xxx) 経由で参照する
（🖥 UIデザイン原則（画面編）.md §1・§7 のルール）。
"""
import hashlib

import dashboard_settings
import shuki_profile

# ── 意味トークン（状態・緊急度）。画面コードは色の名前でなくこちらを使う ──
# 現状は基調9キーのエイリアスだが、将来テーマごとに独立した値を持たせる余地を残すため
# 別名として定義しておく（🖥 UIデザイン原則 §1「意味の予約と識別の分離」）。
SEMANTIC = {
    "--danger": "var(--red)",
    "--warn": "var(--accent)",
    "--ok": "var(--teal)",
    "--info": "var(--blue)",
}

# ── Obsidianエイリアス。dataviz skillでvault内に直書きされるSVG（`var(--text-normal)`等、
# Obsidianのテーマ変数名）が、ダッシュボード上でも改変なしにテーマ追従で描画されるようにする
# （2026-07-30・infographic/dataviz運用の一環。vault側のSVGは書き換えない前提のブリッジ）。
OBSIDIAN_ALIAS = {
    "--text-normal": "var(--fg)",
    "--text-muted": "var(--muted)",
    "--text-faint": "var(--muted)",
    "--background-primary": "var(--bg)",
    "--background-secondary": "var(--card)",
    "--background-modifier-border": "var(--line)",
    "--interactive-accent": "var(--accent)",
}

# ── 派生トークン。各ページが個別に書いていた半透明・角丸・フォントの重複を解消 ──
DERIVED = {
    "--space-1": "4px",
    "--space-2": "8px",
    "--space-3": "16px",
    "--space-4": "24px",
    "--space-5": "32px",
    "--surface-control": "color-mix(in srgb, var(--fg) 5%, var(--card))",
    "--surface-highlight": "color-mix(in srgb, var(--accent) 6%, var(--card))",
    "--control-line": "color-mix(in srgb, var(--fg) 55%, var(--card))",
    "--accent-dim": "color-mix(in srgb, var(--accent) 40%, transparent)",
    "--accent-glow": "color-mix(in srgb, var(--accent) 20%, transparent)",
    "--radius": "12px",
    "--font-ui": "'Yu Gothic UI','Segoe UI',sans-serif",
    "--font-serif": "'Yu Mincho','Hiragino Mincho ProN',serif",
}

# ── 濃淡ランプ（sequential・活動ヒートマップ用。/progress のミニマップ・/control の生活タブが使用）─
# 「量」を表す4段。🖥 UIデザイン原則（画面編）§8.3 に従い **1色相の濃淡**（categorical禁止）。
#
# 明度は card→fg の直線上で取り、そこへアクセント色を 55% 混ぜて色相を乗せる。
# card→accent を直接使わないのは、light テーマのアクセント（#c0872a）が白地に対して
# 明度幅 0.335（OKLab L）しか無く、4段はおろか3段も規定のΔLで入らないため
# （暗テーマは 0.53〜0.65 ある）。card→fg なら全テーマ 0.73〜0.76 で安定する。
# fg は定義上その地に対する最大コントラストの色なので、暗地では「明るくなる」・
# 明地では「暗くなる」＝どちらのモードでも "多い＝地から遠い" が自動的に成立する。
#
# 検証（2026-07-28・dataviz skill の validate_palette.js を --ordinal で実行）：
#   **下の式が実際に生む値そのもの**を5テーマ分計算してかけ、全て ALL CHECKS PASS
#   （明度単調・隣接ΔL≥0.06・最淡段が地に対し2:1以上・単一色相）。
#   最淡段コントラスト: warm-dark 4.99 / cool-dark 4.00 / mono-dark 5.23 / forest 4.23 / light 2.11
#   warm-dark の実値 #9a834f,#b59d67,#d1b980,#ecd399 はヘッドレスEdgeの実ピクセルとも完全一致
#   （＝ブラウザの color-mix(in srgb) と検証に使った計算が同一であることを実測で確認済み）。
#   混合率55%は「合格する範囲で最も色が乗る」点として選定。
# ⚠️ /settings でアクセント色を既定5テーマ外の任意色に変更した場合、この検証は再実行していない。
_HEAT_TINT = "55%"
_HEAT_LIFTS = ("15%", "43%", "72%", "100%")
HEAT = {
    # 0件の日。§8.2「0を責めない」＝警告色でなく、地からわずかに浮く余白として置く
    "--heat-0": "color-mix(in srgb, var(--fg) 7%, var(--card))",
}
HEAT.update({
    f"--heat-{i + 1}": (f"color-mix(in srgb, var(--accent) {_HEAT_TINT}, "
                        f"color-mix(in srgb, var(--fg) {lift}, var(--card)))")
    for i, lift in enumerate(_HEAT_LIFTS)
})

# ── Area 10色（識別トークン・nominal専用。**アイコンにだけ使う**） ──
# 2026-08-06 サイバー配色へ刷新。旧値はテラコッタ/マスタード/オリーブ等のアース系で、
# 既定テーマ cool-dark（スレート×インディゴ）と系統が噛み合わず浮いていた（ユーザーのフィードバック）。
# 新パレットは寒色〜電子色を色相順に10等分し、テーマの accent(#7c8cf5) / teal(#4fd1c5) /
# blue(#5aa9e6) と同じ系統に揃えてある。
#
# **使い方の制約（2026-08-06 追加）**: この色はカードの「1辺だけ塗る」用途に使わない。
# 帯（border-top/left だけ色を付ける）は、丸みのある矩形の一辺だけが浮いて安っぽく見える
# ため廃止した。色はアイコン（と小さなバッジ）だけが持つ。→ 🖥 UIデザイン原則 §1.5
#
# **値は profile.json 側にある**（2026-09-27）。Area名そのものが個人の人生設計なので、
# 名前・色・英字キーは shuki_profile が読む個人データ層に移した。ここに残っているのは
# 「Areaごとに色を1つ持ち、ライトテーマでは暗色版に差し替える」という**仕組み**だけ。
AREA_C = shuki_profile.area_color_map()
# ライトテーマ用の暗色版。上のネオン系は白地に載せるとコントラストが 1.5〜3.0 しか出ず
# アイコンが読めない（実測）。白地 #f5f6fa に対して 3.5 以上になるまで暗くした同色相。
AREA_C_LIGHT = shuki_profile.area_color_map(light=True)
AREA_KEY = shuki_profile.area_key_map()  # CSS変数名は日本語不可なので英字キーへ変換

# ── レアリティ4色（収集品レイヤー限定・/game /achievements のみで使う） ──
# 元は concept_tree.py の RARITY。
RARITY_C = {"legendary": "#b45309", "hero": "#ec4899", "elite": "#0284c7", "novice": "#059669"}

# ── メダル3色（「突出した日」加点レイヤー限定） ──
# RARITY_C と同じ収集品レイヤー扱い（テーマ分割しない固定hex）。11pxセルの1.5pxリム＋淡い
# グローにだけ使う装飾で本文コントラストの対象外。金属感が明地・暗地どちらでも成立する中明度で選定。
# 2026-09-02: 旧・独立ページ /activity 廃止にともない、当時の唯一の消費先だった草グリッドの
# 突出日リムは /progress ミニマップへは移植していない（ミニマップは日付索引に絞った・下記参照）。
# 現在は未使用だが、ヒートマップ系UIを今後拡張する時のため定義だけ残す。
MEDAL_C = {"gold": "#c8a020", "silver": "#9aa0a6", "bronze": "#b5713b"}

# ── スタイルプリセット（配色テーマとは別軸の「見た目の性格」・2026-08-24 Phase2試作） ──
# style=="matrix" の時、選択中の配色テーマ（light/cool-dark等）を問わず黒×緑のレトロPC風に
# 上書きする（ユーザーの「Matrix風スタイルも欲しい」要望への試作第一弾）。9キーの基調パレットと
# フォント・角丸だけを上書きし、レアリティ色・Area色など収集品レイヤーの識別色はそのまま
# （プリセットが変わっても「何のバッジか」の意味は壊さない）。
MATRIX_PALETTE = {
    "bg": "#030803", "fg": "#39ff6a", "muted": "#1f8c3f",
    "accent": "#5dff8f", "card": "#050c05", "line": "#155225",
    "red": "#ff5d5d", "teal": "#39ff6a", "blue": "#5dff8f",
}
MATRIX_DERIVED = {
    "--font-ui": "'Consolas','Courier New',monospace",
    "--font-serif": "'Consolas','Courier New',monospace",
    "--radius": "2px",
}
# body::after の走査線オーバーレイ。position:fixed + pointer-events:none で操作を一切妨げない。
# 走査線の色は var(--fg) 由来にしてある（生hexで緑を焼き込むと、アクセント色を
# 変えたときに走査線だけ緑のまま残るため・2026-09-07）。
MATRIX_EXTRA_CSS = """
body { letter-spacing: .01em; }
body::after {
  content: ""; position: fixed; inset: 0; z-index: 9998; pointer-events: none;
  background: repeating-linear-gradient(
    0deg, color-mix(in srgb, var(--fg) 5%, transparent) 0px,
    color-mix(in srgb, var(--fg) 5%, transparent) 1px,
    transparent 1px, transparent 3px);
  mix-blend-mode: screen;
}
"""

# ── Matrix・くっきり表示（視認性重視版・2026-08-24）──
# ユーザーから「かっこいいMatrix風は気に入ったが見やすさも欲しい」とのフィードバックを受けて追加。
# 通常版を置き換えず別プリセットとして併存させる。muted/lineのコントラスト比が低かった実測
# （bg比 muted 4.5:1 / line 2.1:1）を受け、両方を明るくしてAA基準（本文4.5:1・UI部品3:1）を
# 満たす値に調整。fgのネオン緑はそのまま維持し「Matrixらしさ」は崩さない。走査線は無効化。
MATRIX_HC_PALETTE = {
    "bg": "#050a05", "fg": "#4dff85", "muted": "#5fd98c",
    "accent": "#7dffaa", "card": "#0a140a", "line": "#3a9e5c",
    "red": "#ff7a7a", "teal": "#4dff85", "blue": "#7dffaa",
}
MATRIX_HC_DERIVED = dict(MATRIX_DERIVED)
MATRIX_HC_EXTRA_CSS = "body { letter-spacing: .01em; }\n"

MATRIX_STYLE_KEYS = ("matrix", "matrix-hc")

# ── やわらかスタイル（2026-09-04 追加）──────────────────────────────
# 経緯: 本人以外に使ってもらう前提で見せたところ「もう少しかわいいUIじゃないと使いたくない」。
# ユーザーの指示は「シンプル・白ベース・少しデコレートも・**色はカスタマイズできるところは変えない**」。
#
# よって matrix と違い **配色を一切上書きしない**（palette override = None）。
# 白ベースは配色テーマ側の新パレット `milky` が担当し、accent は従来どおり /settings で
# 自由に変えられる＝「色のカスタマイズ層」に手を触れない。このスタイルが動かすのは
# **形（角丸）・余白・影・線の弱さ・フォント**だけ。
#
# 既定の「サイバー＝角丸2px・直線」（🖥 UIデザイン原則 §1.5）は standard スタイルの規定であり、
# ここはそれを**選んだ人にだけ**丸める上書きレイヤーとして分離してある（§11）。
_SOFT_R = "16px"
SOFT_DERIVED = {
    "--radius": _SOFT_R,
    # 丸ゴシックは Windows に既定で無い（実測: comic/Inkfree/Segoe Print のみ）。
    # 入っている端末（iOS の Hiragino Maru Gothic 等）だけ拾い、無ければ通常の sans に落ちる。
    "--font-ui": ("'M PLUS Rounded 1c','Hiragino Maru Gothic ProN','Quicksand',"
                  "'Yu Gothic UI','Segoe UI',sans-serif"),
}
# 角丸は「全部まとめて丸める」方式を取る。SHUKI の border-radius は各ページの CSS に
# 直書きが約1,000箇所あり（2px/8px/12px…）、トークン var(--radius) 経由は5箇所しかないため、
# トークンを変えるだけでは画面はほとんど丸くならない（2026-09-04 実測）。
# そこで要素セレクタ列 + !important で一括して丸め、**形に意味がある**ピル・円・
# 上辺だけ丸いドロワーは後段で戻す。border-radius は箱より大きい値を自動で縮めるので、
# 細いバーやドットは自然にピル・円になる（＝小さい要素ほど丸くなる）。
SOFT_EXTRA_CSS = """
html body :is(div,section,article,aside,main,nav,header,footer,form,fieldset,label,
  ul,ol,li,dl,dt,dd,table,td,th,p,span,a,button,input,select,textarea,img,pre,code,
  details,summary,dialog,figure,canvas,video,iframe) {
  border-radius: 16px !important;
}
/* 形が意味を持つものは戻す（ピル＝タグ/バッジ、円＝ドット・アイコン枠、上辺のみ＝ドロワー） */
html body :is([class*="pill"],[class*="chip"],[class*="badge"],[class*="tag"],[class*="dot"],
  [class*="avatar"],[class*="round"],.bn-item,.navlink,.hbtn) { border-radius: 999px !important; }
html body :is([class*="circle"],[class*="ring"]) { border-radius: 50% !important; }
html body :is([class*="drawer"],[class*="sheet"]) { border-radius: 18px 18px 0 0 !important; }
html body header { border-radius: 0 0 20px 20px !important; }
/* 余白と行間。文字を大きくせず「詰まっていない」印象だけを作る */
html body { line-height: 1.72; }
/* 面は硬い枠線でなく淡い影で浮かせる（枠線は消さずに弱める＝ダークテーマでも輪郭が残る） */
html body :is([class*="card"],[class*="panel"],[class*="tile"],[class*="box"],[class*="cell"]) {
  border-color: color-mix(in srgb, var(--line) 65%, transparent);
  box-shadow: 0 2px 10px color-mix(in srgb, var(--accent) 8%, transparent);
}
"""

# 角ばらせるスキン（2026-09-15）。soft の逆向きで、全要素を 2px に揃え、形に意味がある
# ものだけ後段で戻す。**既定ではない**——2026-09-15 に standard へ適用してユーザーが実機で見比べた
# 結果「丸い方が良い」と判断されたため、任意スキンとして残す扱いにした。
# 経緯：§1.5 は 2026-08-06 に「角丸は2pxに統一」と決めていたが、実装は 8px/12px/20px のまま
# 140箇所が非準拠で、1年近く誰も困っていなかった。原則の方を実態に合わせて改訂し
# （🖥 UIデザイン原則（画面編）§1.5 参照）、2px はこのスキンを選んだ時だけの見た目とする。
SHARP_EXTRA_CSS = """
html body :is(div,section,article,aside,main,nav,header,footer,form,fieldset,label,
  ul,ol,li,dl,dt,dd,table,td,th,p,span,a,button,input,select,textarea,img,pre,code,
  details,summary,dialog,figure,canvas,video,iframe) {
  border-radius: 2px !important;
}
/* 形が意味を持つものは戻す（§1.5 が明示的に認めた例外だけ） */
html body :is([class*="pill"],[class*="chip"],[class*="badge"],[class*="tag"],[class*="dot"],
  [class*="avatar"],[class*="round"],.bn-item,.navlink,.hbtn):not([class*="chips"]):not([class*="tags"]):not([class*="badges"]):not([class*="-title"]):not([class*="-br"]):not([class*="-label"]) {
  border-radius: 999px !important;
}
html body :is([class*="circle"],[class*="ring"],.hd-logo) { border-radius: 50% !important; }
html body :is([class*="drawer"],[class*="sheet"]) { border-radius: 16px 16px 0 0 !important; }
"""

# Digital Agency dashboard guide, sections 3.4 and 4.4: hierarchy through
# alignment, whitespace and typography; reserve color for meaningful emphasis.
# Scoped to standard so deliberately expressive skins remain selectable.
STANDARD_EXTRA_CSS = """
html body { background-image:none; line-height:1.6; }
html body :is(h1,h2,h3,.focus-title,.card-title) {
  font-family:var(--font-ui); letter-spacing:normal; }
html body :is(h2,h3) { font-weight:650; line-height:1.35; }
html body .hd-top h1 { font-size:1.375rem; font-weight:650; }
html body :is(.card,.panel,.area-card,.acc-card,.method-card) {
  border-radius:var(--radius); box-shadow:none; }
html body :is(.panel,.area-card,.acc-card) { padding:var(--space-4); }
html body :is(.life-grid,.accounts-band,.sum-grid) { gap:var(--space-3); }
html body :is(.panel h2,.card h2,.acc-head) { font-size:1rem; }
html body :is(.panel .sub,.card .hint,.sum-label,.sum-sub,.acc-reset) {
  font-size:.8125rem; line-height:1.6; }
html body :is(.filter-bar,.toolbar) { background:var(--card); padding:12px 16px; }
html body :is(.filter-bar input,.filter-bar select,.mode-btn) {
  border-radius:8px; min-height:40px; }
html body :is(input[type=text],input[type=search],textarea,select) {
  background:var(--surface-control); border-color:var(--control-line); }
html body #chat-fab { color:var(--bg); box-shadow:none; }
html body .choice-btn:hover:not(:disabled) { color:var(--bg); }
html body :is(.focus-band,.ach-band) {
  background:var(--card); box-shadow:none; animation:none; }
html body .focus-band { padding:var(--space-4); gap:var(--space-4); margin-bottom:var(--space-4); }
html body .focus-title { font-size:1.5rem; font-weight:650; line-height:1.35; }
html body :is(.focus-cta,.focus-cta:hover) {
  border-radius:8px; box-shadow:none; transform:none; min-height:44px; font-weight:650; }
html body :is(.card.top-pick,.fchip.alert) { animation:none; box-shadow:none; }
html body .card.top-pick { background:var(--surface-highlight); }
html body :is(.ach-band:hover,.sum-card:hover,.fchip.link:hover) { box-shadow:none; transform:none; }
html body .ach-bar-fill { background:var(--accent); box-shadow:none; }
html body :is(.focus-memo input,.memo-send,.memo-journal-link) { border-radius:8px; min-height:44px; }
html body :is(.sum-val,.streak-num) { font-weight:650; font-variant-numeric:tabular-nums; }
@media(max-width:700px) {
  html body :is(.panel,.area-card,.acc-card,.focus-band) { padding:var(--space-3); }
  html body .focus-title { font-size:1.25rem; }
  html body .focus-memo { flex-wrap:wrap; }
  html body .focus-memo input { flex-basis:100%; }
  html body :is(.filter-bar input,.filter-bar select,.mode-btn) { min-height:44px; }
}
"""

_STYLE_VARIANTS = {
    "standard": (None, {}, STANDARD_EXTRA_CSS),
    # key: (palette上書き or None, --変数の上書き, 追加CSS)
    "matrix": (MATRIX_PALETTE, MATRIX_DERIVED, MATRIX_EXTRA_CSS),
    "matrix-hc": (MATRIX_HC_PALETTE, MATRIX_HC_DERIVED, MATRIX_HC_EXTRA_CSS),
    "soft": (None, SOFT_DERIVED, SOFT_EXTRA_CSS),
    "sharp": (None, {}, SHARP_EXTRA_CSS),
}

# ── 飾り（decor・2026-09-04）───────────────────────────────────
# style（形）とも theme（色）とも独立した第3の軸。色は accent を薄めて使うだけで新しい色を
# 導入しない（§1「アクセントは1色」を壊さない）。背景の柄は body の background-image に
# 重ねる＝擬似要素を使わないので、既存ページの z-index・スタッキングに一切干渉しない。
# 図鑑・称号のようにページ側で body 背景を持つページでは、ページ側の指定が後から効いて
# 柄は出ない（意図どおり。世界観バンドを潰さない）。
_DECOR_DOTS = ("radial-gradient(circle at center,"
               " color-mix(in srgb, var(--accent) 13%, transparent) 1.5px, transparent 1.6px)")
DECOR_CSS = {
    "off": "",
    "soft": """
html body {
  background-image: """ + _DECOR_DOTS + """;
  background-size: 22px 22px;
  background-attachment: fixed;
}
""",
    "full": """
html body {
  background-image: """ + _DECOR_DOTS + """,
    linear-gradient(180deg, color-mix(in srgb, var(--accent) 9%, transparent), transparent 340px);
  background-size: 22px 22px, auto;
  background-repeat: repeat, no-repeat;
  background-attachment: fixed, scroll;
}
/* 見出しの小さなモチーフ。意味を運ばない純粋な飾りなので文字（❀）で置く（§9 の
   「意味的アイコンは線SVG」の対象外＝意味を持たないため）。 */
html body h2::before {
  content: "\\2740\\00a0";
  color: color-mix(in srgb, var(--accent) 60%, transparent);
  font-weight: 400;
}
/* 押せるものだけがふわっと浮く（変化の説明・§5）。動きを嫌う設定は尊重する */
@media (prefers-reduced-motion: no-preference) {
  html body :is(button,a[class*="btn"]) { transition: transform .15s ease; }
  html body :is(button,a[class*="btn"]):hover { transform: translateY(-1px); }
}
""",
}


# ── Matrix のアクセント色替え（2026-09-07）─────────────────────────
# ユーザーの要望「Matrix風も緑以外を選べるように（ただしコントラスト比は注意）」への実装。
#
# 設計: **新しい設定項目もUIも増やさない**。既に /settings にある「アクセント色を上書き」の
# ピッカーを matrix でも効かせる（これまで matrix は palette を丸ごと上書きしていたため、
# アクセントを変えても何も起きない死んだ設定になっていた）。
#
# 効かせ方は「色相だけを借りて、明るさは元の緑と同じ見え方に合わせ直す」。
# 単純に色相を回すだけでは駄目で、同じ HSL の明度でも青や赤は緑よりずっと暗く見えるため、
# 回した先で **bg に対するコントラスト比が元（緑）の値を下回らなくなるまで明度を上げ直す**。
# これで「コントラスト比を保った選択肢に限定する」という完了条件を、色の一覧を絞る形ではなく
# **どの色を選んでも比を割らない**形で満たす（AA: 本文4.5:1・UI部品3:1 は元の緑が既に満たす）。
#
# 意味を持つ色は回さない: red（危険）は赤のまま。Area色・レアリティ色・メダル色も従来どおり
# style の影響を受けない（収集品レイヤーは「何のバッジか」の意味を壊さない・§MATRIX_PALETTE）。
_MATRIX_HUE_KEYS = ("bg", "fg", "muted", "accent", "card", "line", "teal", "blue")
_RATIO_CAP = 7.0   # 目標コントラスト比の上限（本文AAA基準）。上の recolor_matrix 参照


def _hex_to_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


def _rgb_to_hex(rgb):
    return "#" + "".join(f"{max(0, min(255, round(c * 255))):02x}" for c in rgb)


def _rgb_to_hsl(rgb):
    r, g, b = rgb
    mx, mn = max(rgb), min(rgb)
    l = (mx + mn) / 2
    if mx == mn:
        return 0.0, 0.0, l
    d = mx - mn
    sat = d / (2 - mx - mn) if l > 0.5 else d / (mx + mn)
    if mx == r:
        hue = ((g - b) / d) % 6
    elif mx == g:
        hue = (b - r) / d + 2
    else:
        hue = (r - g) / d + 4
    return hue * 60, sat, l


def _hsl_to_rgb(hue, sat, l):
    c = (1 - abs(2 * l - 1)) * sat
    x = c * (1 - abs((hue / 60) % 2 - 1))
    m = l - c / 2
    seg = int(hue // 60) % 6
    r, g, b = [(c, x, 0), (x, c, 0), (0, c, x), (0, x, c), (x, 0, c), (c, 0, x)][seg]
    return r + m, g + m, b + m


def _lum(rgb):
    def ch(v):
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = (ch(v) for v in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(hex_a, hex_b):
    """WCAG のコントラスト比（1〜21）。検証・テストからも使う。"""
    a, b = _lum(_hex_to_rgb(hex_a)), _lum(_hex_to_rgb(hex_b))
    hi, lo = max(a, b), min(a, b)
    return (hi + 0.05) / (lo + 0.05)


def recolor_matrix(pal, accent_hex):
    """matrix パレットを accent の色相へ回す。bg に対する各色のコントラスト比は元の値以上を保つ。

    pal: 元の matrix パレット（緑）。accent_hex: /settings で選ばれた #RRGGBB。
    戻り値は新しい9キーの dict（red は意味色なので据え置き）。
    """
    a_h, a_s, _ = _rgb_to_hsl(_hex_to_rgb(accent_hex))
    if a_s < 0.05:      # 無彩色（白・黒・グレー）を選んだ時は色相が無い＝元のまま返す
        return dict(pal)
    old_bg = pal["bg"]
    # bg は「ほぼ黒に色味がわずかに乗っている」だけなので、彩度・明度はそのままに色相だけ回す
    b_h, b_s, b_l = _rgb_to_hsl(_hex_to_rgb(old_bg))
    new_bg = _rgb_to_hex(_hsl_to_rgb(a_h, b_s, b_l))
    out = dict(pal)
    out["bg"] = new_bg
    for k in _MATRIX_HUE_KEYS:
        if k == "bg":
            continue
        # 元の緑が持っていた比を下回らせない。ただし **上限 _RATIO_CAP で頭打ちにする**：
        # 緑は色として飛び抜けて明るく fg で 15:1 もあるため、その比をそのまま他の色相に
        # 課すと青やマゼンタが明度を上げきって「ほぼ白」になり、ネオンらしさが消える
        # （2026-09-07 実測: 青 #d2e0ff・マゼンタ #ffd2e2 まで飛んだ）。7:1 は本文の AAA 基準で
        # AA(4.5:1) より厳しく、この上限でも可読性は担保される。緑（＝上限超え）は
        # 下げる方向には触らないので、既定の見た目は1ピクセルも変わらない。
        want = min(contrast_ratio(pal[k], old_bg), _RATIO_CAP)
        _, sat, l = _rgb_to_hsl(_hex_to_rgb(pal[k]))
        # card/line は bg より暗い（比が低い）面の色。明度を上げると面が浮くので、
        # 比を満たしていればそのまま使い、足りない時だけ上げる。
        for _ in range(101):
            cand = _rgb_to_hex(_hsl_to_rgb(a_h, sat, l))
            if contrast_ratio(cand, new_bg) >= want - 1e-9 or l >= 1.0:
                break
            l = min(1.0, l + 0.01)
        out[k] = cand
    return out


def _is_light(hex_color: str) -> bool:
    """背景色が明るいか（相対輝度 0.5 超）。Area色の明暗版の出し分けに使う。"""
    h = hex_color.lstrip("#")
    if len(h) != 6:
        return False
    def _ch(v):
        c = int(v, 16) / 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    lum = 0.2126 * _ch(h[0:2]) + 0.7152 * _ch(h[2:4]) + 0.0722 * _ch(h[4:6])
    return lum > 0.5


def theme_css(settings=None) -> str:
    """GET /theme.css の本体。:root{ --bg:...; --danger:...; --area-仕事:...; } を返す。

    settings（dashboard_settings.load_settings() の戻り値）を渡さなければ現在の保存値を読む。
    """
    if settings is None:
        settings = dashboard_settings.load_settings()
    pal = dashboard_settings.effective_palette(settings)
    style = settings.get("style")
    variant = _STYLE_VARIANTS.get(style)
    s_pal, s_derived, s_css = variant if variant else (None, {}, "")
    if s_pal:  # matrix 系だけが配色を上書きする。soft は None＝テーマの色をそのまま使う
        pal = dict(pal)
        pal.update(s_pal)
        # アクセント上書きが入っていれば matrix の緑をその色相へ回す（2026-09-07）。
        # これが無いと matrix 選択中はアクセントピッカーが何も効かない死んだ設定になる。
        acc = settings.get("accent", "")
        if acc and dashboard_settings.HEX_RE.match(acc):
            pal = recolor_matrix(pal, acc)
    rows = [f"  --{k}: {v};" for k, v in pal.items()]
    mascot_color = dashboard_settings.sanitize(settings)["mascot_color"]
    rows.append(f"  --mascot-color: {mascot_color};")
    # Selected data-visualization ramp; keep chart ink distinct from status colours.
    chart_blue = '#2a78d6' if _is_light(pal['card']) else '#3987e5'
    rows.append(f'  --chart-blue: {chart_blue};')
    rows += [f"  {k}: {v};" for k, v in SEMANTIC.items()]
    colorblind = settings.get("theme") == "colorblind" and style not in MATRIX_STYLE_KEYS
    if colorblind:
        # Orange danger and blue success avoid a red/green status pair.
        # Warning ink is independent of a user-selected accent.
        rows.append("  --warn: #855b00;")
    rows += [f"  {k}: {v};" for k, v in OBSIDIAN_ALIAS.items()]
    rows += [f"  {k}: {v};" for k, v in DERIVED.items()]
    rows += [f"  {k}: {v};" for k, v in s_derived.items()]
    rows += [f"  {k}: {v};" for k, v in HEAT.items()]
    # Area色は「地が明るいか」で暗色版に切り替える（旧: theme=="light" 決め打ち。白ベースの
    # milky テーマ追加でネオン系が白地に載り読めなくなるため、輝度で判定する方式へ・2026-09-04）
    area_c = AREA_C_LIGHT if _is_light(pal["bg"]) else AREA_C
    if colorblind:
        # Area names carry identity; icons need no difficult hue distinctions.
        area_c = {name: pal["fg"] for name in area_c}
    rows += [f"  --area-{AREA_KEY[name]}: {hexv};" for name, hexv in area_c.items()]
    rows += [f"  --rarity-{name}: {hexv};" for name, hexv in RARITY_C.items()]
    rows += [f"  --medal-{name}: {hexv};" for name, hexv in MEDAL_C.items()]
    css = ":root {\n" + "\n".join(rows) + "\n}\n"
    css += s_css
    # 飾りは matrix（走査線という別の飾りを既に持つ）とは併用しない
    if style not in MATRIX_STYLE_KEYS:
        css += DECOR_CSS.get(settings.get("decor", dashboard_settings.DEFAULT_DECOR), "")
    return css


def effective_bg(settings=None) -> str:
    """テーマ+スタイル適用後の背景色（PWA theme-color/manifest 用）。
    matrix スタイルなら配色テーマに関係なく黒背景を返す（アドレスバー色等をテーマ.css と一致させる）。
    """
    if settings is None:
        settings = dashboard_settings.load_settings()
    style = settings.get("style")
    if style in MATRIX_STYLE_KEYS:
        m_pal = _STYLE_VARIANTS[style][0]
        acc = settings.get("accent", "")
        if acc and dashboard_settings.HEX_RE.match(acc):
            return recolor_matrix(m_pal, acc)["bg"]   # アドレスバー色も同じ色相に揃える
        return m_pal["bg"]
    return dashboard_settings.effective_palette(settings)["bg"]


def etag(settings=None) -> str:
    """テーマ+アクセント色+スタイル+飾りだけのハッシュ。ブラウザキャッシュの検証用（GET /theme.css の ETag）。"""
    if settings is None:
        settings = dashboard_settings.load_settings()
    # Include actual output: code-only design updates must invalidate cached CSS.
    return hashlib.sha1(theme_css(settings).encode("utf-8")).hexdigest()[:12]


if __name__ == "__main__":
    print(theme_css())
