# Claude work space — AI Intranet

> 📖 **新しく見に来た方へ / New here?** まず [README](README.md) を読んでください（概要・思想・セットアップ）。
> このファイルは Claude Code が毎セッション読み込む**運用マニュアル本体**で、オーナー個人の vault に合わせて書かれています。`<...>` や `<WORKSPACE>` 等のプレースホルダーは自分の環境に置き換えて使ってください。
> This file is the operating manual Claude Code loads every session; it is written for one person's vault. Adapt the placeholders to your own setup.

ここはオーナーのAIエージェント運用イントラネット。Notionから移行したPARA構造のローカル vault。Obsidianでも編集できる構成。

## 🗂 ディレクトリマップ

| パス | 役割 |
|---|---|
| `03_Projects/` | プロジェクトハブ（`プロジェクト.md` がハブ、`プロジェクト/` 配下に各 Project .md） |
| `00_Intranet/` | 憲法・運用ルール集（AIが必ず参照する目次） |
| `00_Intranet/README.md` | AI向け入口ガイド・役割別必読早見表 |
| `00_Intranet/AI運用ルール集（イントラ）/` | 個別ルール（Identity / 哲学・価値観 / デザイン言語 / QAサイクル等） |
| `00_Intranet/agent-runs/` | エージェント実行ログ（infrastructure が集計） |
| `00_Intranet/monitoring/` | 稼働サマリー・セッション制限履歴 |
| `00_Intranet/local-ai-runs/` | Local AI（Ollama）夜間処理の出力先 |
| `00_Intranet/local-ai-runs/qa/` | Local AI が検出した誤字脱字・frontmatter QA レポート（日付別） |
| `04_Tasks/タスク管理.md` | タスク管理ハブ（inline base DB） |
| `04_Tasks/タスク管理/タスク/` | タスクDB（各.mdが1タスク） |
| `02_Home/` | ホーム・今日のフォーカス |
| `05_Areas/` | 継続責任領域（`Areas.md` がハブ、各Area は `<area>.md` 単一ハブのみ・フォルダなし） |
| `06_Resources/` | ナレッジ（`Resources.md` ハブ＋inline base DB） |
| `06_Resources/Resources/ナレッジ/` | ナレッジDB本体（本・アニメ・ゲーム・記事など、各.mdが1エントリ）。**👤人物ノートもここ**（`type: 👤人物`） |
| `06_Resources/Resources/概念/` | 概念ノード（繰り返し登場するテーマ・原則・洞察。グラフの意味的ハブ） |
| `06_Resources/Resources/OCR保管庫/` | OCRで取り込んだ生データ保管 |
| `01_Inbox/` | 未処理（`インボックス.md` ハブ＋inline base DB） |
| `08_Archive/` | アーカイブ |
| `07_Logs/` | 行動ログ（`ログ.md` ハブ＋inline base DB、`ログ/` サブフォルダにエントリ） |
| `07_Logs/AI対話履歴/` | Claude Code 週次使用状況レポート |
| `07_Logs/朝スタンドアップ/` | モーニングスタンドアップ履歴（毎朝7:00 orchestrator が `<日付>.md` を作成） |
| `.claude/agents/` | Claude Code サブエージェント定義（**唯一の権威ソース**。コア4体＋専門エージェントは任意追加） |

## 🤖 利用可能なエージェント

`@<agent-name>` または Agent ツールで起動：

> ⚠️ **この一覧は要約（ナビゲーション）。** 各エージェントの正式な仕様・トリガー・制約は **`.claude/agents/<agent-name>.md` が唯一の正**。この一覧・組織図・README と食い違う場合は必ず `.claude/agents/` を信じること。ここを書き換えてもエージェントの挙動は変わらない（挙動を変えるなら `.claude/agents/` を編集する）。

### コア（必須）
- **`@orchestrator`** — タスク振り分け・モーニングスタンドアップ・週次レビュー
- **`@reviewer`** — 他エージェント出力・重要判断のダブルチェック（Read専用）
- **`@knowledge`** — URLや外部コンテンツをナレッジノートに変換・wikilink構築・週次メンテナンス
- **`@infrastructure`** — タスクDB棚卸し（**7日以上停滞**を検出）・重複検出・静かな故障監視（提案のみ、Read専用）

### 専門エージェント（任意追加）

自分の用途に合わせて `.claude/agents/` に追加する。フォーマットは `📋 エージェント共通テンプレート.md` を参照。

追加例：
- 家計管理エージェント（支出ログ整理・月次レポート）
- 語学学習エージェント（添削・語彙ノート）
- 計画エージェント（旅行・大型購入の調査・比較）
- 関係性サポートエージェント（記憶整理・事実確認。代筆禁止）
- 内省エージェント（ログ横断でパターン抽出・問いの提示）

各エージェントの完全仕様は `.claude/agents/<agent-name>.md` を参照。

## 🧠 Local AI（Ollama）— 夜間処理担当

vault本体を補助する別レイヤー。`<LOCAL_AI_DIR>\` で管理。

| スクリプト | 用途 | モデル | 起動 |
|---|---|---|---|
| `local_qa_loop.py` | 00:01-18:00 連続ループで vault 全体を巡回、誤字脱字・frontmatter不整合を検出（18:00-24:00 はゴールデンタイム停止） | qwen3.5:9B | Task Scheduler `Claude-LocalAIQA`（00:01） |
| `ocr_intake.py` | OCR保管庫の新規画像を OCR し `_ocr_out/` に下書き .md を出力（夜間バッチ、手動起動） | qwen2.5vl:7b | 手動（将来的に Task Scheduler 追加予定） |
| `ghost.py` | Downloads フォルダの自動分類（vault関係なし、別役） | qwen3.5:9B / deepseek-r1:14b | 手動 |

**Local AI の境界線**：
- ✅ QAレポートを `00_Intranet/local-ai-runs/qa/YYYY-MM-DD.md` に追記するだけ
- ✅ OCR下書きを `06_Resources/Resources/OCR保管庫/_ocr_out/` に出力するだけ（最小拡張）
- ❌ `_ocr_out/` 以外の vault本体ファイルの編集・削除は一切しない
- ❌ センシティブなコミュニケーションの代筆（代筆禁止ゾーン §3.3 継承）
- ❌ 外部API呼び出し（Ollama除く）

**OCR 運用フロー**：
1. 新規画像を `OCR保管庫/` に置く（対応ノートなし or `status: 未処理` のみ処理対象）
2. `ocr_intake.py` が `qwen2.5vl:7b` でテキスト化 → `_ocr_out/<stem>.md` に下書き出力
3. 朝 orchestrator §0.2 が `_ocr_out/` を拾い → `01_Inbox/インボックス/` へ正式投稿 → 通常振り分けへ
4. 既存 180件（`status: archived`）は再処理しない（archived ＝ 完了印）

朝の Claude Code orchestrator が QA レポートを読み、人間（オーナー）に提示する設計。

## 📜 共通ルール（全エージェント＋Claude Code 本体）

すべて `00_Intranet/AI運用ルール集（イントラ）/` 配下に詳細あり。

1. **🪪 オーナーの Identity と哲学** — 必ず確認してから動く
2. **代筆禁止ゾーン** — センシティブな相手への文章はAIが一切代筆しない（→ タスク管理ルール §3.3 に明記。各エージェントにも引き継ぐ）
3. **お金・健康・外部送信** — 人間確認必須。AI判断で進めない
4. **担当境界** — 自分の領分外なら他エージェントへハンドオフ（チャット内で済ませず、`04_Tasks/タスク管理/タスク/` にタスクを作成し担当・コメントを記入）
5. **完了条件が書けないタスク** — `AI判断OK` を OFF にして人間へエスカレート
6. **セルフQA** — 出力末尾に 事実チェック / トーン / アンチスロップ の3行を付ける（QAサイクル §10.4）
7. **ログの日付必須** — ログ・ナレッジ・タスク等を新規作成する際、frontmatter に以下を必ず記入する：
   - `date` — コンテンツが対象とする日付（Notionインポートや他所からの転記の場合は**元の日付**）
   - `created` — ファイルを実際に作成した日付（AIが生成した場合は生成日）
   - 両者が同日でも省略しない。`date` が特定日ではなく期間の場合は範囲（例: `2026-04-29 〜 2026-05-06`）を記入する
8. **YAML出力ルール** — frontmatter を書くときは「独立メタデータ（`担当`/`AI判断OK`/`status` 等）は1項目1行に改行」「値に `:`・`false/true`・絵文字を含むなら値全体を `"` で囲む」を必ず守る。`memo:` に複数メタデータを詰め込まない。詳細 → `00_Intranet/AI運用ルール集（イントラ）/📋 エージェント共通テンプレート.md` §YAML（frontmatter）出力ルール
9. **インボックス情報移行ルール** — インボックスファイルは `status: done` なら削除不要。ただし**ファイルが持つ情報は必ず正式な場所（ナレッジ・ログ・Project hub・タスク等）に移行してから done にする**。インボックス整理では「削除するか」ではなく「内容が正式ファイルに転記されているか」を先に確認する。詳細 → タスク管理ルール §3.8

## 🧭 Type-Driven PARA 運用

PARA フレームワークを **物理フォルダで厳密に切らず、type プロパティで表現** する。Obsidian の Base ＋ wikilink ＋ プロパティが強力なので、属性駆動の方がフォルダ駆動より柔軟。

### PARA と物理フォルダの対応

| 物理 | 役割 | type 値 / 識別 |
|---|---|---|
| `03_Projects/プロジェクト/` | **P**: 期限つき複数タスクの束（例: 海外旅行2026） | `type: project` |
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

新規にアーカイブしたいものは **元の場所に置いたまま** `status: archived` を立てる。物理移動しない。
- リンク切れない、検索可能、元のコンテキストで保管される
- 各 base view は `status != "archived"` で自動的に隠す
- `08_Archive/アーカイブ.md` は「08_Archiveフォルダ配下」と「status==archived」を OR で集約
- `08_Archive/` フォルダは遺跡レベル 146件の保管のみ、新規移動には使わない

### Log と Resource の境界判断

迷ったら **「日付の固有性で意味が決まるか？」** で判断。
- Yes → Log（その日のスナップショット、再現性なし）
- No → Resource（再利用可能なナレッジ、日付は付随情報）

例: 「2025-08-26 振り返り」→ Log、「Atomic Habits」→ Resource、「ランニングまとめ」→ Resource、「1on1 meet 6月」→ Log。

### Project の扱い

複数タスク・ログ・ナレッジが束になって意味を持つ取り組みは Project として `03_Projects/プロジェクト/<name>.md` に作る。中身は目標・スコープ・関連リンク・base codeblock（`parent.contains("Project名")` で集約）。

完了時は `status: done` → 一定期間後 `status: archived`。物理移動不要。

## 📂 タスクDBの扱い方

- 各タスクは `04_Tasks/タスク管理/タスク/<タイトル> <hash>.md` の1ファイル
- 「ステータス・優先度・期限・担当エージェント・Area」は本文先頭の **frontmatter または見出し直下** に記載されていることが多い
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
- 👤人物ノートの命名: `<名前>.md`（例: `山田太郎.md`）。1ファイル1人物。`area: 人間関係`（特定の関係に紐づく場合はその Area 名）

## 🌐 URLインボックスの使い方

ウェブページをナレッジノートに取り込む手順：

1. `01_Inbox/インボックス/<タイトル>.md` を新規作成
2. frontmatterに以下を記入して保存：
   ```yaml
   ---
   type: 🔗URL
   url: https://...
   area: "<Area名>"  # 省略可（@knowledgeが推定）
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

- **対象**: 概念ノード / 人物ノート / ナレッジノート / ログ / Area / タスク（タスクの status 変更はオーナー確認、Area 方針更新は reviewer 経由＝それぞれ会話で確認してから反映）
- **2フェーズ**: ①会話（質問で曖昧さを埋める。**ファイルは編集しない**、保留変更を `01_Inbox/編集キュー/<トピック>-<日付>.md` に溜める）→ ②オーナーが「適用して」と言ったら `@knowledge` 反映モードが編集キューを一括反映
- **起点**: オーナーがトピック指定（`/scan <トピック>`）／ AIが薄い・曖昧なファイルを検出して提案（`/scan` 引数なし）
- **代筆禁止の継承**: センシティブな相手への文章の代筆はしない（代筆禁止ゾーン §3.3 を継承）
- **wikilink 接続もセット**: 情報追記だけでなく、関連ファイル・概念・人物・Project・Area への wikilink も同時にキューへ入れる（双方向・構造リンク含む。第2層の選択的方針に従い張りすぎない）
- 詳細手順 → `.claude/skills/scan/SKILL.md`、反映の仕様 → `.claude/agents/knowledge.md` §🔁 反映モード

## 🔗 wikilink 運用方針（v2、2026-05-27 導入）

vault は **「2層リンク戦略」** で運用：

### 第1層：構造的接続（frontmatter wikilink）

新規ファイル作成・編集時、以下のプロパティは必ず `[[]]` wikilink 形式で書く：

| プロパティ | 役割 | 例 |
|---|---|---|
| `children:` | 親→子（タスクの分解先） | `children:\n  - "[[フィギュアスケートをやる]]"` |
| `parent:` | 子→親（タスクの統合元） | `parent: "[[<プロジェクト名>]]"` |

**area の値は自分で定義した Area 名からプレーンテキストで書く**（wikilink 不要）：
`<Area 1>` / `<Area 2>` / ... （`05_Areas/` 配下の .md ファイル名と一致させる）

- Area に該当しない場合は `area:` を空にする（「その他」「全体」「ナレッジ」等は使わない）
- 複数 Area 跨ぐ場合はリスト形式：
  ```yaml
  area:
    - <Area 1>
    - <Area 2>
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

### 第2層：本文内 wikilink（手動・選択的）

本文中の `[[...]]` は**明示的に関連がある時だけ**貼る。機械的に貼らない。
例：タスク本文で `関連ログ: [[2025-08-26 全部話した]]` のように、その文脈で参照したい時のみ。

### 第3層：MOC（Map of Content）

テーマ別のキュレーションは `00_Intranet/MOC/<テーマ>.md` に作る。
AI は勝手に MOC を作らない（手動キュレーション領域）。

MOC の例：
- `00_Intranet/MOC/<テーマ>.md` — ジャンル別ナレッジ一覧
- `00_Intranet/MOC/<テーマ>.md` — 概念ノード＋行動原則のまとめ
- `00_Intranet/MOC/<テーマ>.md` — 人物ノート（カテゴリ別）

大きくなった MOC は `03_Projects/` に Project として昇格させることができる。

### 内部リンクは相対パス

- `.md` 内のリンクは ローカル相対パスで完結（Notion URL は撤去済）
- 削除済みの旧 `[[Orchestrator|...]]` 系 wikilink はテキスト表記（`🎯 オーケストレーター`）に置換済み

## 🛠 Claude Code としての動作原則

- ユーザー（オーナー）からの指示が **特定エージェントの役割に当てはまる**なら `@<agent>` で呼び出す
- 「メモを整理して」「タスク化して」「振り分けて」系は **`@orchestrator`** に渡す
- 直接実行する場合も、各エージェントの定義（`.claude/agents/`）と憲法（`00_Intranet/`）を尊重する
- ファイル操作は `\\?\` プレフィックス不要（パスが長い場合は注意）

## ⚙️ スケジュール起動

Windows Task Scheduler `\Claude\` フォルダで稼働中：

| タスク名 | スケジュール | プロンプト・処理 |
|---|---|---|
| `Claude-MorningStandup` | 毎朝 7:00 | `@orchestrator 朝のスタンドアップを生成` |
| `Claude-NightQA` | 毎日 2:00 | `@infrastructure エージェント稼働ログを確認してサマリーを更新` |
| `Claude-WeeklyReview` | 毎週日曜 18:00 | `weekly_review.ps1`：Chrome履歴同期 → オーナーが `/週次レビュー` スキルで対話的に作成 |
| `ObsidianInboxMonitor` | 3時間おき（9:00起点） | `@orchestrator 01_Inbox/ の未処理ファイルを振り分け・プロパティ補完` |
| `Claude-LocalAIQA` | 毎日 00:01 | Local AI: `local_qa_loop.py` を起動、18:00 まで継続ループで誤字脱字・frontmatter QA（18:00-24:00 は停止） |
| `Claude-KnowledgeEnrich` | 毎週日曜 20:00 | `@knowledge メンテナンスモードで実行`（ナレッジwikilink整備・陳腐化検出） |

> **専門エージェントを追加した場合のスケジュール例**：
> - 家計エージェント → `毎日 8:30（スクリプト側で1日のみ）` で月次レポート生成
> - 計画エージェント → `毎朝 6:30` で期限リマインド

**セッション制限リトライ**：全 `\Claude\` 配下タスクに「失敗時30分後に最大3回リトライ」を Task Scheduler ネイティブ機能で設定。設定は `vault-scripts/setup_retry_policy.ps1` を管理者権限で1回実行する。

スケジューラが呼び出す PS1 と Python スクリプトは vault 外で管理：
- Claude Code 用 PowerShell / Python: `<WORKSPACE>\vault-scripts\`
- Local AI 用 Python: `<LOCAL_AI_DIR>\`
- 週次データ出力（weekly_summary.md 等）: `<WORKSPACE>\`

## 💬 コミュニケーション履歴の管理方針（任意）

外部サービス（メッセージアプリ等）のエクスポートデータを vault に取り込む場合：

- **raw データは vault に入れない**。vault 外のディレクトリに格納し、分析・振り返りログのみ vault に置く
- センシティブな会話の自動処理は避ける。手動起動を原則とする
- 生成物は必ずオーナーが確認する（AIの誤読・捏造を防ぐ）

### vaultへの格納ルール（07_Logs/ログ/）

| ログ種別 | ファイル名パターン |
|---|---|
| 期間振り返り | `<YYYY-MM-DD>〜<YYYY-MM-DD> <名前>との振り返り.md` |
| 期間・全体分析 | `<名前>とのメッセージ分析(<期間>).md` |
| frontmatter必須項目 | `area` / `date`（期間の場合は開始日）/ `created` / `person: "[[<名前>]]"` |

### 人物ノート（👤人物）

`06_Resources/Resources/ナレッジ/` に `type: 👤人物` で配置。ログのfrontmatterで `person: "[[名前]]"` としてwikilink接続。Obsidianのbacklinksパネルで自動集約。

## 📅 運用フェーズ（自分の変更履歴を記録する）

> ⚠️ **ここはテンプレートです。** 自分の vault の変更を Phase として記録してください。

**Phase 1（初期構成）** — YYYY-MM-DD 着手

- コア4体エージェント構成でスタート
- PARA 構造・タスクDB・インボックス・ログDBを定義

**Phase 2（拡張）** — YYYY-MM-DD 着手（任意）

- 専門エージェントを追加した場合はここに記録
- Area の追加・廃止もここに記録
