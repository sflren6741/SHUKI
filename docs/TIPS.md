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

同じテーマが**3ファイル以上**に出てきたら、`05_Resources/Resources/概念/` に小さなノートを作る。

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

- **代筆禁止ゾーン**：大切な人へのメッセージ・手紙はAIに書かせない（`relationship` はツール権限で読み取り専用＝技術的に書けない）。
- **人間確認必須ゾーン**：お金・健康・外部送信はAI判断で進めない。
- **完了条件が書けないタスク**：`ai_judgment_ok` を OFF にして人間へエスカレート。

制約があるから安心して任せられる。これは思想であり、各エージェント定義とルールに埋め込まれている。

---

## 7. 迷ったら / Quick decision rules

- **Log か Resource か？** → 「日付の固有性で意味が決まるか？」Yes=Log、No=Resource。
- **タスクか？** → 「完了条件が書けるか？」書けないなら Area か Project の検討事項。
- **概念ノードを作る？** → 同テーマが3ファイル以上に出たら作る。
- **wikilink を貼る？** → frontmatter の構造リンクは必ず、本文リンクは「明示的に関連がある時だけ」。
