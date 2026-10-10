---
name: research
description: 任意のトピックについて論文・文献を検索し、課題・ギャップ・体系化・関係図を含む英語レポートを生成する汎用リサーチスキル。「research <topic>」「調べて」「文献調査して」「先行研究まとめて」等で起動。
---

# 🔍 Research — 汎用リサーチスキル

## 起動方法

```
/research <topic>
```

例：
```
/research optimal defensive behavior prediction in soccer
/research transformer architecture variants
/research urban heat island mitigation strategies
```

- トピックは英語推奨（論文DBの網羅性が高い）
- 日本語入力も可 → ステップ1で英語クエリに変換してから検索

---

## フロー

### ステップ 1：クエリ準備

引数のトピックをそのまま使う。日本語の場合は、まず英語の検索クエリを生成する（Claude 自身が変換。ユーザーに確認不要）。

クエリは **2〜3 種類のバリエーション**を用意しておく（同義語・上位概念・関連手法）。例：
- Primary: `defensive player behavior prediction soccer`
- Variant: `football tactical decision making machine learning`
- Broad: `sports player intent prediction`

---

### ステップ 2：論文取得（2ソース並列）

#### A. OpenAlex API（主軸・分野不問）

```
WebFetch: https://api.openalex.org/works?search=<query>&per_page=20&sort=cited_by_count:desc&filter=language:en
```

取得する項目：タイトル / 著者 / 発表年 / 抄録 / 被引用数 / DOI URL

クエリバリアントを最大2つ実行し、結果をマージ（重複は DOI で除去）。

#### B. arXiv API（最新プレプリント・CS/ML 強化）

```
WebFetch: https://export.arxiv.org/api/query?search_query=all:<query>&max_results=10&sortBy=submittedDate&sortOrder=descending
```

XML（Atom形式）を受け取り、タイトル / 著者 / 日付 / 要約 / arXiv URL を抽出。

---

### ステップ 3：WebSearch 補完

OpenAlex・arXiv で拾えない直近の研究・技術ブログ・サーベイ論文を補う。

```
WebSearch: <topic> survey 2024 OR 2025
WebSearch: <topic> review recent advances
```

各1〜2件を補足として追加。

---

### ステップ 4：Claude による統合分析

取得した文献（合計 20〜30 件）を Claude が読み、以下を生成する：

1. **Related Work Table**：タイトル・著者・年・1行サマリー・リンク
2. **Gaps & Open Problems**：先行研究で未解決の問題・手法の限界・データ不足など
3. **Knowledge Taxonomy**：テーマ別・手法別にカテゴリ分類したツリー
4. **Research Relationship Map**：研究の影響関係を Mermaid diagram で表現

分析の視点：
- 時系列（研究の流れ：基礎→応用→最新）
- 手法の系譜（どの手法が何に発展したか）
- 未到達領域（大半の研究が避けている課題）

---

### ステップ 5：レポート出力

レポートを **チャット内に直接表示**する（ファイル保存はユーザーが任意で行う）。

```markdown
# Research Report: <Topic>
Generated: YYYY-MM-DD | Sources: OpenAlex + arXiv + Web

---

## § 1  Related Work

| # | Authors | Year | Title | Key Contribution | Link |
|---|---------|------|-------|-----------------|------|
| 1 | ... | ... | ... | ... | ... |
...（上位 15〜20 件）

---

## § 2  Research Gaps & Open Problems

**Unsolved problems:**
- Gap 1: ...
- Gap 2: ...

**Limitations of existing work:**
- ...

**Underexplored directions:**
- ...

---

## § 3  Knowledge Taxonomy

- **Category A** (e.g., Data Collection)
  - Subcategory A1: GPS / sensor-based
  - Subcategory A2: Vision-based tracking
- **Category B** (e.g., Modeling Approach)
  - Subcategory B1: Rule-based
  - Subcategory B2: Deep learning
- ...

---

## § 4  Research Relationship Map

\`\`\`mermaid
graph TD
  A[Foundational Paper] --> B[Method X 20XX]
  A --> C[Method Y 20XX]
  B --> D[Application Z 20XX]
  C --> D
  D --> E[Open Problem: ...]
\`\`\`

---

## § 5  Suggested Next Steps

- Key papers to read in depth: ...
- Search queries to go deeper: ...
```

---

### ステップ 6：vault への保存（2026-09-26 追加）

レポートをチャット表示するだけでなく、`00_Intranet/参考資料/` にファイルとしても保存する（チャットが流れても vault に記録を残すため。ダッシュボードの `/research` ページは2026-10-06に廃止）。

- ファイル名：`Research - <topic>（YYYY-MM-DD）.md`（`topic` はファイル名に使えない文字 `: / \ * ? " < > |` を除去したもの。長すぎる場合は100字程度で切る）
- frontmatter：
  ```yaml
  ---
  title: "Research - <topic>（YYYY-MM-DD）"
  type: 📰記事
  area: ""
  date: YYYY-MM-DD
  created: YYYY-MM-DD
  ---
  ```
- 本文はステップ5のレポート全体（§1〜§5）をそのまま書き込む
- ダッシュボードから起動された場合（プロンプト内に「SHUKI research page」等の記載がある場合）は、実行完了メッセージの末尾に保存先ファイルへの相対パスを一言添える

---

## 制約

- 1回の実行で取得する論文数：上限 30 件（速度と品質のバランス）
- API エラー時：該当ソースをスキップし、残りで生成。エラー内容をレポート末尾に記載
- 抄録が取得できない論文はタイトル・著者のみ記載し、サマリー欄を `(abstract unavailable)` とする
- **Relationship Map は上位 8〜10 件に絞る**（多すぎると図が読めなくなる）

---

## 🔄 セルフQAの3行

```
- 事実チェック: <論文タイトル・著者・年は取得データに基づいているか。捏造がないか>
- トーン: <ギャップ・課題を誇張せず、取得文献から導けるものだけ書いたか>
- アンチスロップ: <「画期的」「革命的」等の評価フィラーが混入していないか>
```
