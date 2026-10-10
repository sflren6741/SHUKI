# Tips & mental models / 使いこなしと思考モデル

> **TL;DR (EN)** — A few ideas do most of the work: organize by a `type:` property (not rigid folders); link files with wikilinks in two layers (structural in frontmatter, selective in body); promote recurring themes into "concept nodes" that become graph hubs; render dynamic views with Obsidian Bases; and keep hard boundaries (money/health/relationship messages need a human). Master these and the vault compounds in value.

少数の考え方が効果の大半を生む。順に。

---

## 1. wikilink でファイルを関連付ける / Relate files with wikilinks

`[[ファイル名]]` でノート同士をつなぐ。Obsidian はこれを双方向リンク（backlinks）として扱うので、**片方を書けば逆側にも自動で現れる**。情報が「フォルダの位置」ではなく「関係性」で取り出せるようになる。

**2層リンク戦略**で運用するのがコツ：

- **第1層：構造リンク（frontmatter）** — `parent:` / `children:` などは必ず `[[]]` で書く。タスクの親子・Projectとの紐付けなど、構造を機械的につなぐ。
  ```yaml
  parent: "[[海外旅行 2026]]"
  ```
- **第2層：本文リンク（手動・選択的）** — 本文中の `[[...]]` は**明示的に関連がある時だけ**貼る。機械的に貼らない（貼りすぎるとグラフがノイズになる）。
  ```markdown
  関連ログ: [[2026-01-15 あの日の出来事]]
  ```
- **person リンク** — ログに `person: "[[相手の名前]]"` と書くと、その人物ノート（`type: 👤人物`）に登場箇所が集まる。人間関係が自動で台帳になる。

---

## 2. type駆動 PARA / Type-driven PARA

PARA（Projects / Areas / Resources / Archive）を**硬いフォルダで切らず、`type:` プロパティで表現**する。

- フォルダ移動ではなく**プロパティ1個**で分類が変わる → 再分類が一瞬、リンクも切れない。
- `type:` 例: `project` / `📕本` / `📰記事` / `📜原則・ルール` / `👤人物` …
- **アーカイブも移動しない**：`status: archived` を立てるだけ。元の場所・コンテキストに残り、検索可能、各ビューからは自動で隠れる。

`status` はDB別に統一（英語・ハイフン区切り）：タスク＝`todo/in-progress/done/on-hold/cancelled`、インボックス＝`new/routing/done/...`、ナレッジ＝`inbox/in-progress/done/archived`。`archived` は全DB共通の「神聖不変値」。

---

## 3. 概念ノード / Concept nodes — グラフの意味的ハブ

同じテーマが**3ファイル以上**に出てきたら、`06_Resources/Resources/概念/` に小さなノートを作る。

- 1〜2行で定義 ＋「登場した場面」「生まれたアクション」「関連概念」をリンク。
- これがフォルダを横断する**意味的ハブ**になり、グラフ図で中心に育つ。
- 重要なログに `## 気づき` を足して概念ノードへリンクすると、日々の記録が自動的に概念へ接続される。

→ 使うほど vault の結合度が上がり、「自分が何を繰り返し考えているか」が可視化される。

---

## 4. Obsidian Bases で動的ビュー / Dynamic views with Bases

`area` / `parent` / `status` などのプロパティで**動的な表**を作る。Area ハブや Project ハブに Bases コードブロックを置けば、該当ノートが自動で集まる（`_example-area.md` 参照）。フォルダを開かなくても「この領域の全ノート」が一覧できる。

---

## 5. MOC（Map of Content）/ 手動キュレーション

テーマ別の入口は `00_Intranet/MOC/<テーマ>.md` に**手で**作る（AIには自動生成させない領域）。例：「アニメ図書館」「人物関係図」「自己理解マップ」。Bases が「自動の集約」なら、MOC は「人間の編集した地図」。

---

## 6. 境界＝信頼の源 / Boundaries are the point

このシステムで一番効くのは「AIに**やらせないこと**」を決めていること。

- **代筆禁止ゾーン**：大切な人へのメッセージ・手紙はAIに書かせない（そういう相手を扱うエージェントを作るなら、`tools:` を `Read, Glob, Grep` だけにして**技術的に書けない**状態にするのが確実）。
- **人間確認必須ゾーン**：お金・健康・外部送信はAI判断で進めない。
- **完了条件が書けないタスク**：`ai_judgment_ok` を OFF にして人間へエスカレート。

制約があるから安心して任せられる。これは思想であり、各エージェント定義とルールに埋め込まれている。

---

## 7. 迷ったら / Quick decision rules

- **Log か Resource か？** → 「日付の固有性で意味が決まるか？」Yes=Log、No=Resource。
- **タスクか？** → 「完了条件が書けるか？」書けないなら Area か Project の検討事項。
- **概念ノードを作る？** → 同テーマが3ファイル以上に出たら作る。
- **wikilink を貼る？** → frontmatter の構造リンクは必ず、本文リンクは「明示的に関連がある時だけ」。

---

## 8. 拡張の余白 / Extend it

このテンプレは**汎用的な骨組みだけ**を積んでいる。個人のデータや外部連携に依存する部分は、あなたの vault が育ってから足せばいい。よくある拡張の方向：

| 足せるもの | 中身 | 作り方の起点 |
|---|---|---|
| 💰 家計レビュー | 各社CSV・給与明細から月次で収支・純資産を振り返る対話スキル | `/plan`・既存スキルを雛形に、家計エージェントを `docs/AGENTS.md` の手順で追加 |
| 💬 メッセージ振り返り | エクスポートした会話ログ（特定の相手のみ）を事実ベースで振り返る手動スキル | センシティブなので**無人にしない**。生成物は必ず本人確認 |
| 📥 メール取り込み | Gmail 等の新着をインボックスに投げるスクリプト＋スキル | 認証情報は vault 外・`.gitignore`。取り込み後にラベルを外して再取得防止 |
| 📊 活動レポート | Google Takeout 等の月次エクスポートを解析して活動を可視化 | `process_takeout.py` 相当を vault 外に置き、`/activity-review` 相当のスキルで深掘り |
| 🔧 技術メンテ | スケジューラ・スクリプト・ログの整合を診断・修復するスキル | 「壊れてない？」の機械チェック用。運用の見直しは `/ops-review` |
| 🖼 OCR / 音声インテイク | ローカルLLMで画像OCR・音声文字起こし→インボックス投入 | 「決定的にできない前処理」だけローカルLLMに任せる（下の教訓参照） |

**共通の作り方**: エージェントは `.claude/agents/<name>.md`（`docs/AGENTS.md`）、スキルは `.claude/skills/<name>/SKILL.md`。個人データのパス・認証は**必ず vault 外**に置き、`.gitignore` で公開リポに混ぜない。

### 運用の教訓（先人の失敗から）

- **明文ルールのQAは LLM でなく決定的コードで。** frontmatter・status・date のチェックを LLM 夜間QAに任せると、正しいデータを「違反」と誤検出して直そうとする事故が起きる。だから `scripts/vault_lint.py`（決定的）に寄せている。ローカルLLMは OCR・文字起こしなど「決定的にできない前処理」にだけ使う。
- **監視は放っておくと自己肥大する。** 稼働サマリー・QAレポートを毎日フルで回すと、レポート自体が読まれない量に膨らむ。頻度を絞る（例: 夜間QAは週2回）・要対応0件を常態にする設計にする。
- **カスタムの持ち込みすぎに注意。** 自分の環境に最適化した仕組みを他人へ配る時は、汎用的な骨組みだけ移して、個人設定は「余白」として残す（このリポ自体がその方針で作られている）。
