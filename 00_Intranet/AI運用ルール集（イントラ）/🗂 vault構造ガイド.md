---
title: "🗂 vault構造ガイド"
created: 2026-09-26
updated: 2026-09-26
---
# 🗂 vault構造ガイド（ディレクトリ・PARA・DB書式・wikilink）

> **vault のどこに何を置くか・どう書くかの正本**（2026-09-26 に `CLAUDE.md` 廃止＋`AGENTS.md` 集約にともない分離）。`AGENTS.md` には主要パスの1行表と frontmatter 最小仕様だけを残し、詳細はここが持つ。
> ファイルを新規作成・移動・frontmatter を書く作業に入る前にこのページを読む。関連 → `✅ タスク管理ルール.md`（タスクの粒度・自律ピック）／`⚙️ 定期便カタログ.md`（自動で書き込む便）／`🛠 Technical Setup.md`（スクリプト・接続）。
## 🗂 ディレクトリマップ

| パス | 役割 |
|---|---|
| `03_Projects/` | プロジェクトハブ（`プロジェクト.md` がハブ、`プロジェクト/` 配下に各 Project .md） |
| `00_Intranet/` | 憲法・運用ルール集（AIが必ず参照する目次） |
| `00_Intranet/README.md` | AI向け入口ガイド・役割別必読早見表 |
| `00_Intranet/📖 vaultの使い方.md` | **人間（ユーザー）向け**の使い方1枚まとめ。困った時・今日何しようか迷った時に見る入口（スキル早見表・ディレクトリ早見表・自動処理一覧） |
| `00_Intranet/AI運用ルール集（イントラ）/` | 個別ルール（Identity / 哲学・価値観 / デザイン言語 / QAサイクル等） |
| `99_System/` → `<data>/system/` | **機械ゾーン（人間は開かなくてよい・2026-07-05 分離）**。**2026-10-07 に vault の外 `<data>/system/` へ移動**。下の `99_System/…` 行はすべてそこを指す。人が読むレポートは `07_Logs/レポート/` に分けた（`QA/`・`運用/`・`モデル評価/`・`クイズ/`）。Drive の複製は `<drive>/SHUKI-backup/`。AI・スクリプトの作業領域。人間向け情報は standup・/ops-review 経由で届く |
| `99_System/agent-runs/` | エージェント実行ログ。**`.log` 一本化（2026-07-02）**：履歴の実体は日次 `<系統>_YYYY-MM-DD.log`（1日1ファイル・全文）。.md run log は廃止済み（本文つき旧 .md のみ残存）。「履歴を見る」＝その日の `.log` を開く。infrastructure が `.log` をパースして集計 |
| `07_Logs/レポート/運用/`（旧 `99_System/monitoring/` の md） | 稼働サマリー・運用改善提案（session_limit集計は稼働サマリーに統合） |
| `99_System/ui-queue/` | ダッシュボード（dashboard_server.py・127.0.0.1:8765）のボタン操作の書き戻しキュー（2026-07-15 新設）。決裁パネルの押下結果 `decision_results_<日付>.json` 等。**サーバーはvault本体の.mdを書かず、ここに溜めて次回 orchestrator が回収・反映**（正は orchestrator.md §2）。反映済みは `processed/` へ |
| `07_Logs/レポート/QA/`（旧 `99_System/qa/`） | `vault_lint.py` の日次QAレポート置き場（日付別・朝 orchestrator がトリアージ）。旧名 `local-ai-runs/`（Local AI QA廃止に伴い 2026-07-05 改名） |
| `99_System/briefing/` | 🌅 日次ブリーフィングの本体（2026-07-31 新設）。`<date>_materials.json`（素材・決定的収集）／`<date>.json`（**本文＝画面・音声・履歴の共通源**）／`<date>_script.txt`（音声台本）。読み物としての履歴は `07_Logs/ブリーフィング/` |
| `99_System/decisions/` | ⚖️ 決裁・確認カードのストア（2026-07-31 新設・ブリーフィング本文から分離）。`open.json` に**未処理だけ**が入り、承認/却下・選択・回答すると押した時点で `resolved/<YYYY-MM>.jsonl` へ移る＝再掲が構造的に起きない。応答型は `yes_no` / `choice` / `text`。3時間便の提案は `proposed.json` 経由（`decisions.py --merge`）。仕組みの正は `vault-scripts/decisions.py` |
| `99_System/news/` | 📰 ニュースセクション（ダッシュボード `/news`）のデータ置き場（2026-08-04 新設）。`feeds.json`＝購読RSSフィード一覧（AI・技術／暗号資産／海外転職・スキル）。手で編集する設定なのでここに残る。**2026-10-07（v7.0.0）から、データ本体は vault外の `<workspace>/shuki-data/news/news.db`（SQLite）に移った**。テーブルは、号＝`issues`／`issue_items`（旧 `<date>.json`）、既読URL＝`articles`（旧 `seen_urls.json`・重複防止）、評価＝`ratings`（旧 `feedback.json`。ダッシュボードで押した good/bad/skip。直近 good/bad 各8件が選定プロンプトの参考例になる）、ウォッチ＝`watches`（旧 `watches.json`）。ここに残る旧 `*.json` は凍結したロールバック用で、もう誰も書き込まない（消さない）。**アドホック監視**（2026-08-31新設）は、RSSに無い単発情報を検知するワンショット監視。ユーザーが会話で「〇〇を見張って」と言ったら、Claude Code が `python news_store.py watch "<監視内容>" [--expires YYYY-MM-DD]`（既定は作成日＋30日）で追加し、`python news_store.py watches` で一覧できる。JSON の手書きはしない。日次便が WebSearch で確認し、見つかったらその日の号に category=`🔭ウォッチ` として差し込む。見つかったウォッチと期限切れは、削除せず状態（`hit`／`expired`）を付けて閉じる。日次 `Claude-NewsDigest` が号を生成し、サーバーは最新日付の号を読むだけ。仕組みの正は `<scripts>/news_fetch.py`・`news_store.py`（`🛠 Technical Setup.md` §Per-feature SQLite conversion） |
| `99_System/ai_feedback.jsonl` | 📥 **AIの成果への評価**（2026-09-04 新設）。ダッシュボード `/files` の「要確認」更新ビューに出る🤖 AI完了成果で押した 👍/👎 が1行1件で溜まる（`task_path`/`title`/`agent`/`rating`/`comment`）。サーバーが直接追記するので回収便は不要。12:30便の**補充の手順0**がこれを読み、`bad` が付いた型は次から切り出さず `good` の型を優先する＝評価を選定に還す片方向ループ（ニュースの評価＝`news.db` の `ratings`（旧 `feedback.json`）と同じ思想）。仕組みの正は `.claude/agents/orchestrator.md` §📥 成果の受け取り |
| `99_System/crossword/` | 🧩 クロスワード機能（ダッシュボード `/crossword`）のデータ置き場（2026-09-07 新設）。`puzzles/<id>.json`＝生成済みパズル（資産・git管理下）、`log/`＝現状未使用（進捗はlocalStorageのみ）。テーマ・サイズを指定してその場で新規作成でき、作ったものは一覧からいつでも再プレイできる。生成はAIが単語＋ヒントを考え、グリッドへの座標配置は `vault-scripts/crossword/generate_grid.py`（決定的バックトラッキング）が担う＝AIに座標を書かせず幻覚を防ぐ設計。仕組みの正は `.claude/skills/crossword-gen/SKILL.md` と `🛠 Technical Setup.md` §GET /crossword |
| `99_System/quiz/` | 🧩 クイズ機能（ダッシュボード `/quiz`）のデータ置き場（Phase 0・2026-08-24 新設、同日中に Phase 1 SRS 前倒し実装）。`decks/<id>.json`＝問題バンク（資産・不変・git管理下・`<scripts>/plugins/quiz/validate_deck.py` で機械検証済みのみ出荷）、`log/<id>.jsonl`＝解答ログ（学習状態・消耗品・`POST /quiz/answer` が追記）、`IMPLEMENTATION_PLAN.md`＝設計・実装手順・Phase 1以降の計画メモ。初回デッキ `pl900`（PL-900・60問）。**SRS（間隔反復）は状態ファイルを持たず解答ログを毎回再生して算出**（`vault-scripts/quiz_srs.py`・SM-2）、`GET /quiz/stats/<id>` が習熟状態を返しスタート画面に習熟ゲージ・出題モード4種（復習/間違えた問題/未着手/全部から）を表示。仕組みの正は `99_System/quiz/IMPLEMENTATION_PLAN.md`、サーバー側実装は `🛠 Technical Setup.md` §GET /quiz |
| `99_System/visualize/` | 📊 可視化セクション（ダッシュボード `/visualize`）のデータ置き場（2026-08-04 新設）。`gallery.json`＝`/visualize` スキルが生成した可視化の履歴（対象・可視化タイプ・埋め込み先ノート・プレビュー）。`suggestions.jsonl`＝**AIが気づいた可視化の切り口の投函口**（1行1提案・30日で失効。機械スキャンで拾えない切り口専用。フォーカス帯を奪うので `recommendations.jsonl` には入れない）。提案そのものは `vault-scripts/viz_candidates.py` が毎回vaultをスキャンして決定的に生成（まだ図を持たないMOC/Project/Area・溜まったログ・数値CSV）。実行の追跡は vault外 `dashboard_viz_runs.json`。仕組みの正は `.claude/skills/visualize/SKILL.md` |
| `00_Intranet/参考資料/` | 外部記事の要約等の参考資料置き場 |
| `04_Tasks/タスク管理.md` | タスク管理ハブ（inline base DB） |
| `04_Tasks/タスク管理/タスク/` | タスクDB（各.mdが1タスク） |
| `02_Home/` | ホーム・今日のフォーカス |
| `05_Areas/` | 継続責任領域（`Areas.md` がハブ、各Area は `<area>.md` 単一ハブのみ・フォルダなし） |
| `06_Resources/` | ナレッジ（`Resources.md` ハブ＋inline base DB） |
| `06_Resources/Resources/ナレッジ/` | ナレッジDB本体（本・アニメ・ゲーム・記事など、各.mdが1エントリ）。**👤人物ノートもここ**（`type: 👤人物`） |
| `06_Resources/Resources/概念/` | 概念ノード（繰り返し登場するテーマ・原則・洞察。グラフの意味的ハブ） |
| `06_Resources/Resources/OCR保管庫/` | OCRで取り込んだ生データ保管 |
| `06_Resources/Resources/raw/` | 生の資料・原本置き場（PDF・録音等、git除外/Drive同期のみ） |
| `01_Inbox/` | 未処理（`インボックス.md` ハブ＋inline base DB） |
| `08_Archive/` | アーカイブ |
| `08_Archive/朝スタンドアップ_legacy_20260731/` | 旧モーニングスタンドアップ履歴62件（2026-05-25〜07-31）。ブリーフィング移行にともない退避。スクリプトからの参照はゼロ（`radio_gen.py` の後方互換経路も削除済み） |
| `07_Logs/` | 行動ログ（`ログ.md` ハブ＋inline base DB、`ログ/` サブフォルダにエントリ） |
| `07_Logs/AI対話履歴/` | Claude Code 週次使用状況レポート（毎週日曜18:00 `weekly_review.ps1` が `analyze_claude_usage.py` で自動生成・2026-07-02 週次化。transcript 30日自動削除への保全を兼ねる） |
| `07_Logs/ブリーフィング/` | 日次ブリーフィング履歴（毎朝7:00 `briefing_builder.py --render` が `<日付>.md` を作成・2026-07-31〜） |
| `.claude/agents/` | Claude Code サブエージェント定義（**唯一の権威ソース・6体**） |


## 🧠 Local AI（Ollama）— 夜間処理担当

vault本体を補助する別レイヤー。`<localai>\` で管理。

| スクリプト | 用途 | モデル | 起動 |
|---|---|---|---|
| `ghost.py` | Downloads フォルダの自動分類（vault関係なし、別役） | qwen3.5:9B / deepseek-r1:14b | 手動 |

> ⚰️ **`local_qa_loop.py`（qwen3.5 夜間QAループ）は 2026-07-02 廃止**。30日で69,063行のレポートがほぼ全て誤検出（正しいデータをルール違反に"修正"提案する事例多数）だったため。ルールが明文化されたチェックは LLM でなく **`vault-scripts/vault_lint.py`（Python・決定的・誤検出0%）** が毎日 00:05 に実行し、同じ `qa/` に出力する（朝トリアージ互換）。
> 🧭 **embedding・関連ノート発見系は Smart Connections（`.smart-env/`）の領分** — Local AI では重複開発しない（2026-07-02 決定）。
> 🖼 **OCRパイプライン（`ocr_intake.py`）は 2026-07-26 廃止**。180件全て `status: archived` で取り込み済み・`_ocr_out/` は空のまま運用需要がなかったため。スクリプト本体は残置（必要時は手動実行可）。
> 🎙️ **`voice_intake.py`（音声メモ入力チャネル）は 2026-07-26 停止**。`VoiceMemos/` ディレクトリが一度も使われず空回りしていたため（提案B・/ops-review で決着）。スクリプト本体は残置（使いたくなれば `VoiceMemos/` を作って Task Scheduler に再登録すればよい）。

**Local AI の境界線**：
- ✅ QAレポートを `99_System/qa/YYYY-MM-DD.md` に追記するだけ
- ❌ 代筆禁止ゾーンの代筆（代筆禁止ゾーン §3.3 継承）
- ❌ 外部API呼び出し（Ollama除く）

朝の Claude Code orchestrator が QA レポートを読み、人間（ユーザー）に提示する設計。


## 🧭 Type-Driven PARA 運用

PARA フレームワークを **物理フォルダで厳密に切らず、type プロパティで表現** する。Obsidian の Base ＋ wikilink ＋ プロパティが強力なので、属性駆動の方がフォルダ駆動より柔軟。

### PARA と物理フォルダの対応

| 物理 | 役割 | type 値 / 識別 |
|---|---|---|
| `03_Projects/プロジェクト/` | **P**: 期限つき複数タスクの束（例: インド旅行2026） | `type: project` |
| `04_Tasks/タスク管理/タスク/` | 単発行動 | （タスク） |
| `05_Areas/<area>.md` | **A**: 領域ハブ＋ビュー | （Area hub） |
| `06_Resources/Resources/ナレッジ/` | **R**: 再利用可能ナレッジ | `type: 📕本/📰記事/📜原則・ルール/📺アニメ・ドラマ/📖漫画/🎮ゲーム/🎵音楽/📺映画` |
| `07_Logs/ログ/` | 時系列記録 | （ログ） |
| `08_Archive/` | **物理アーカイブは遺跡レベルのみ**（新規は使わない） | （古い物理保管） |

### 横串プロパティ

- `status:` — **英語・ハイフン区切りで統一**。DB別の値セット：
  - タスクDB: `todo` / `in-progress` / `done` / `on-hold` / `cancelled`
  - インボックス: `new` / `routing` / `done` / `pending` / `on-hold` / `rejected`
  - ナレッジDB: `inbox` / `in-progress` / `done` / `archived`
  - **`status: archived` は全DB共通の神聖不変値** — 立てれば各 base view から自動的に隠れる
- `area:` — `"[[Area名]]"` で Area に紐付け（複数なら list 形式）
- `parent:` — `"[[Project名]]"` で Project に紐付け
- `date:` — コンテンツが対象とする日付
- `created:` — ファイル作成日

### アーカイブ運用

**判断基準（2026-07-05 明確化）：そのファイルを base view（inline database）経由で見るか、フォルダを直接開いて見るか。**

- **base view 経由（タスクDB・ナレッジDB・ログDB・インボックスDB・OCR保管庫DB等、03/04/06/07配下の各DB）**: 元の場所に置いたまま `status: archived` を立てる。物理移動しない
  - リンク切れない、検索可能、元のコンテキストで保管される
  - 各 base view は `status != "archived"` で自動的に隠す
  - `08_Archive/アーカイブ.md` は「08_Archiveフォルダ配下」と「status==archived」を OR で集約
- **base view を持たない直接参照ファイル・フォルダ（`00_Intranet/` 配下のルール集・ガイド・議論メモ等）**: 使われなくなったら **物理的に `08_Archive/` へ移動**する。base view のフィルタで隠れないため、`status: archived` を立てるだけだとフォルダを直接開いた時に陳腐化ファイルが見え続けて見栄えが悪い（例: `Obsidian設定ガイド.md`・`週次戦略ブリーフ・テンプレ.md`）
- `08_Archive/` フォルダは遺跡レベルの物理保管＋上記の直接参照系アーカイブ

### Log と Resource の境界判断

迷ったら **「日付の固有性で意味が決まるか？」** で判断。
- Yes → Log（その日のスナップショット、再現性なし）
- No → Resource（再利用可能なナレッジ、日付は付随情報）

例: 「2025-08-26 全部話した」→ Log、「Atomic Habits」→ Resource、「ハンドボールまとめ」→ Resource、「1on1 meet 6月」→ Log。

### Project の扱い

複数タスク・ログ・ナレッジが束になって意味を持つ取り組みは Project として `03_Projects/プロジェクト/<name>.md` に作る。中身は目標・スコープ・関連リンク・base codeblock（`parent.contains("Project名")` で集約）。

完了時は `status: done` → 一定期間後 `status: archived`。物理移動不要。

## 📂 タスクDBの扱い方

- 各タスクは `04_Tasks/タスク管理/タスク/<タイトル> <hash>.md` の1ファイル
- 「ステータス・優先度・期限・担当エージェント・Area」は本文先頭の **frontmatter または見出し直下** に記載されていることが多い
- 🤖 **AIレーン（2026-09-04 導入・旧 `ai_judgment_ok` を置き換え）** — 「どれをAIに任せられるか」は **フラグではなく `vault-scripts/ai_lane.py` が毎回導出**する（`ai`🤖 完遂可 / `prep`🤝 下ごしらえまで / `human`🧠 ユーザーのみ）。保存する値はユーザーが「これは自分でやる」と決めた時の **`human_only: true` の1個だけで、未記入がデフォルト＝AIが進めてよい**（オプトアウト方式）。代筆禁止ゾーン・内省・学習・対面・お金／外部送信／健康の最終アクションは、フラグの有無に関係なく**自動ガードが機械的に止める**ので、起票時に判定する工程はない。画面は `/board?mode=ai`（複数選択して「🚚 AIに任せる」「🧠 自分でやる」を一括指示）、CLI は `python ai_lane.py --report` / `--list ai`。仕組みの正は `.claude/agents/orchestrator.md` §✅ AIレーン
- `start:`（予定開始日・2026-07-12導入）＝「この日まで手を付けない」と決めた日＝**意図的な先延ばし**の正式表現（フォーカス・ファネル原則）。start が未来のタスクは /next・/schedule の候補から除外され、🎯今取り組むビューにも出ない。実績用 `start_actual` とは別物
- **ステータス変更時は時刻も記録する（2026-08-18 追加）**：対話（対話ドック含む）でタスクの `status` を `done`/`in-progress` に変更する時、`end_actual`/`start_actual`（日付）に加えて `end_actual_time`/`start_actual_time`（HH:MM・変更した今の時刻）も書く。既存値がある場合は上書きしない。先延ばし実験（[[タスクの着手・完了をSHUKIでトラッキングして先延ばしを実験する]]）の集中密度指標のためのデータで、`/board` の完了ボタン経由の反映ルールと揃える（`.claude/agents/orchestrator.md` §✅ タスクのステータス変更の回収 が正）
- 抽出ロジック例：
  - Glob `04_Tasks/タスク管理/タスク/*.md`
  - Grep でステータス・期限・優先度を抽出
  - 「期限切れ→今日期限→今週期限→優先度高」順でソート
- 書き込み：新規タスクは `04_Tasks/タスク管理/タスク/<新タイトル>.md` を Write で作成
- 既存タスクの更新は Edit で該当行を書き換え

## 📂 Area の扱い方

Area は **単一ハブ .md のみ** で運用する。例外なし。

- `05_Areas/<area>.md` 1ファイルが Area の全てを表す（散文＋base codeblock）
- **Area配下にフォルダを作らない**。サブページが必要になった時点で必ず3DBのいずれかに振り分ける
- 派生コンテンツの振り分け先：
  - **完了がある行動** → `04_Tasks/タスク管理/タスク/`
  - **日付付きの記録・出来事・対話・気づき・MTGメモ・分析レポート** → `07_Logs/ログ/`
  - **学んだこと・本・アニメ・原則・ルール集** → `06_Resources/Resources/ナレッジ/`
- 各エントリの `area` プロパティで Area hub の base 表に自動的に紐づく
- Resources の `type` 一覧: 📕本 / 📰記事 / 📺アニメ・ドラマ / 📖漫画 / 🎮ゲーム / 🎵音楽 / 📺映画 / **📜原則・ルール**（行動指針・運用ルール・なりたい人間像など）/ **👤人物**（人物ノード・連絡先facts）
- 👤人物ノートの命名: `<名前>.md`（例: `<恋人>.md`, `母.md`）。1ファイル1人物。`area: 人間関係`（非公開扱いの人物だけ profile.json の非公開Areaを入れる）

## 🌐 URLインボックスの使い方

ウェブページをナレッジノートに取り込む手順：

1. `01_Inbox/インボックス/<タイトル>.md` を新規作成
2. frontmatterに以下を記入して保存：
   ```yaml
   ---
   title: "<タイトル>"
   type: 🔗URL
   url: https://...
   area: 仕事        # 省略可（@knowledgeが推定）
   status: new
   date: YYYY-MM-DD
   created: YYYY-MM-DD
   ---
   ```
3. `ObsidianInboxMonitor`（3時間おき）が自動検出 → `@orchestrator` → `@knowledge` へ委譲
4. `@knowledge` が `06_Resources/Resources/ナレッジ/` にノートを作成し、既存ノートとwikilink接続

即時処理したい場合は `@knowledge <URL>` で直接起動可。

`@knowledge` の週次メンテナンス（毎週日曜20:00）は既存ナレッジのwikilink整備と陳腐化検出も自動実行する。

## 🗣 対話キュレーション（会話で vault を精緻化する）

非同期の一発処理では届かない「曖昧さの確認・人物や関係の深い理解・ファイル間の関連付け」を、**前面チャットでの会話**で進める仕組み。スキル `/scan` で起動する。

- **対象**: 概念ノード / 人物ノート / ナレッジノート / ログ / Area / タスク（タスクの status 変更はユーザー確認、Area 方針更新もユーザー承認＝それぞれ会話で確認してから反映）。**非公開Areaに関するファイルは対象外**（2026-09-06〜、settings.json の deny ルールでそもそもアクセス不可）
- **2フェーズ**: ①会話（質問で曖昧さを埋める。**ファイルは編集しない**、保留変更を `01_Inbox/編集キュー/<トピック>-<日付>.md` に溜める）→ ②ユーザーが「適用して」と言ったら `@knowledge` 反映モードが編集キューを一括反映
- **起点**: ユーザーがトピック指定／ AIが薄い・曖昧なファイルを検出して提案（`/scan` 引数なし）
- **wikilink 接続もセット**: 情報追記だけでなく、関連ファイル・概念・人物・Project・Area への wikilink も同時にキューへ入れる（双方向・構造リンク含む。第2層の選択的方針に従い張りすぎない）
- 詳細手順 → `.claude/skills/scan/SKILL.md`、反映の仕様 → `.claude/agents/knowledge.md` §🔁 反映モード


## 🔗 wikilink 運用方針（v2、2026-05-27 導入）

vault は **「2層リンク戦略」** で運用：

### 第1層：構造的接続（frontmatter wikilink）

新規ファイル作成・編集時、以下のプロパティは必ず `[[]]` wikilink 形式で書く：

| プロパティ | 役割 | 例 |
|---|---|---|
| `children:` | 親→子（タスクの分解先） | `children:\n  - "[[AWS SAA-C03 取得]]"` |
| `parent:` | 子→親（タスクの統合元） | `parent: "[[インド旅行 2026]]"` |

**area の値は必ず以下の11 Area からプレーンテキストで書く**（wikilink 不要）：
非公開Area / 人間関係 / 自己理解 / 仕事 / 英語 / ハンドボール / 健康 / 娯楽 / お金 / 時間管理 / AI運用

> 🆕 **AI運用**（2026-09-09 追加・決裁 d-3825d9a6 承認）：SHUKI自体の設定・モデル構成・運用改善など、AIエージェント運用そのものに関するタスク・ログ・ナレッジを表すArea。ハブは `05_Areas/AI運用.md`。

- Area に該当しない場合は `area:` を空にする（「その他」「全体」「ナレッジ」等は使わない）
- 複数 Area 跨ぐ場合はリスト形式：
  ```yaml
  area:
    - 非公開Area
    - 時間管理
  ```

**`area:` / `category:` / `agent:` / `status:` などはプレーンのまま**（列挙型値、リンク不要）。

### 第1.5層：概念ノード（Concept layer、2026-05-29 導入）

`06_Resources/Resources/概念/` に繰り返し登場するテーマ・原則・洞察を小さなノートとして置く。
これがグラフの**意味的ハブ**になる。フォルダを横断して多数のログ・タスクから参照される。

概念ノードの書き方：
- frontmatter: `type: 📜原則・ルール` / `area:` / `created:`
- 本文: 1〜2行の定義
- `## 登場した場面`: 実際に登場したログ・タスクへのリンク（3〜5件が目安）
- `## 生まれたアクション`: この概念から生まれたタスクへのリンク（任意）
- `## 関連概念`: 他の概念ノードへのリンク

重要なログには `## 気づき` セクションを追加し、概念ノードへリンクする：
```markdown
## 気づき
- [[将来を先読みする習慣]] — なぜこの概念に繋がるか（1行）
- [[言ったことをやる・一貫性]] — 同上
```

**概念ノードを作るタイミング**：同じテーマが3件以上のファイルに登場したとき。
AIは確認なく概念ノードを新規作成してよい（ログ更新時に自然発生的に追加する）。

**概念ノード新規作成時は「深掘りタスク」を自動起票しない**（2026-09-10 方針変更）：概念ノードを作成しても、`04_Tasks/タスク管理/タスク/<概念名>を深掘りする.md` は自動作成しない。重要な概念の深掘りが必要な場合だけ、ユーザーまたは orchestrator が手動で通常タスクとして起票する。既存の深掘りタスクはそのまま運用し、週1の深掘り枠も既存対象の消化に使う。



### 第2層：本文内 wikilink（手動・選択的）

本文中の `[[...]]` は**明示的に関連がある時だけ**貼る。機械的に貼らない。

> ⛔ **例外（ログ）**: エージェントの実行ログ・作業報告の本文には wikilink を作らない。`99_System/agent-runs/` のログや、チャットへの報告本文でファイル名・タスク名を書くときは `[[]]` を使わずプレーンテキストにする（ログの `[[]]` が実ノートのバックリンク／グラフをログ参照で汚すため）。frontmatter の構造プロパティ（`area:`/`parent:`/`children:`）は従来どおり wikilink 可。既存ログは遡って直さない。
例：タスク本文で `関連ログ: [[2025-08-26 全部話した]]` のように、その文脈で参照したい時のみ。

### 第3層：MOC（Map of Content）

テーマ別のキュレーションは `00_Intranet/MOC/<テーマ>.md` に作る。
AI は勝手に MOC を作らない（手動キュレーション領域）。

現在の MOC（10件）：
- `00_Intranet/MOC/アニメ・ドラマ図書館.md` — ジャンル別アニメ・ドラマ100件＋つながり相関図（作者・スタジオ・シリーズ）
- `00_Intranet/MOC/本図書館.md` — ジャンル別読書ノート8件のキュレーション
- `00_Intranet/MOC/漫画図書館.md` — ジャンル別漫画43件＋つながり相関図（作者・掲載誌・アニメ化）
- `00_Intranet/MOC/ゲーム図書館.md` — ジャンル別ゲーム75件＋つながり相関図（開発元・シリーズ・技術系譜）
- `00_Intranet/MOC/音楽図書館.md` — 楽曲ノート＋ジャンル概論4軸＋つながり相関図（主題歌・挿入歌リンク）
- `00_Intranet/MOC/自己理解マップ.md` — 概念ノード15件＋行動原則
- `00_Intranet/MOC/人物関係図.md` — 人物ノート17件（カテゴリ別）
- `00_Intranet/MOC/資格ロードマップ.md` — 取得予定資格3件（PL-900・ITIL・AWS SAA）の全体俯瞰・つながり
- `00_Intranet/MOC/概念の系統図.md` — 概念35体の合成ツリーSVG（素材ログ⇒概念の家系図＋🔮未合成予告）。`vault-scripts/concept_tree.py` で再生成（手動更新制・ユーザー承認・2026-07-20新規作成）

※「インド旅行 2026」MOC は `03_Projects/プロジェクト/インド旅行 2026.md` に昇格済み（2026-05-27）。

### 内部リンクは相対パス

- `.md` 内のリンクは ローカル相対パスで完結（Notion URL は撤去済）
- 削除済みの旧 `[[Orchestrator|...]]` 系 wikilink はテキスト表記（`🎯 オーケストレーター`）に置換済み


## 💬 メッセージ履歴の管理方針（LINE / FB / IG）

### rawデータ格納場所（すべて vault 外）
| プラットフォーム | raw 投入先（振り返りたい時に置く） | アーカイブ |
|---|---|---|
| Facebook | `<workspace>\facebook_messages\data\raw\*.json` | `…\data\archive\<YYYYMMDD>\` |
| Instagram | `<workspace>\instagram_messages\data\raw\*.json` | `…\data\archive\<YYYYMMDD>\` |
| LINE | エクスポート .txt（Google Drive。ローカル週次取込は未接続） | — |

**rawデータは vault に入れない**。vault には分析・振り返りログのみ置く。

### メッセージ振り返りフロー（非公開Areaの相手は対象外・2026-09-06〜）

`/message-review` スキルと `@relationship` エージェントは 2026-09-06 に廃止した。非公開Areaに関する情報にAIが一切触れない方針への転換（詳細は「📅 現在の運用フェーズ」Phase 4）にともない、相手とのメッセージ振り返り（機械分析・レポート生成）は行わない。振り返りたい場合はユーザーが自分の頭で行う。

母など他の人物とのメッセージ分析が必要な場合は、上表の raw にエクスポートを置いた上でユーザーが対話的に依頼する（専用スキルは無い）。

### vaultへの格納ルール（07_Logs/ログ/）

| ログ種別 | ファイル名パターン | 例 |
|---|---|---|
| 週次レビュー | `週次レビュー（<YYYY-MM-DD>〜<YYYY-MM-DD>）.md` | `週次レビュー（2026-05-25〜2026-05-31）.md` |
| 期間・全体分析 | `<名前>との<媒体>メッセージ分析(<期間>).md` | `母とのLINEメッセージ分析(2024-01〜2026-05).md` |
| frontmatter必須項目 | `area` / `date`（期間の場合は**最終日**・2026-07-05 変更）/ `created` / `person: "[[<名前>]]"` | |

### 人物ノート（👤人物）

`06_Resources/Resources/ナレッジ/` に `type: 👤人物` で配置。ログのfrontmatterで `person: "[[名前]]"` としてwikilink接続。Obsidianのbacklinksパネルで自動集約。

