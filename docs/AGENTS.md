# Agents — how they work & how to make one / エージェントの仕組みと作り方

> **TL;DR (EN)** — Each agent is a single Markdown file in `.claude/agents/<name>.md` with YAML frontmatter (`name`, `description`, `tools`) and a body that defines its role, triggers, constraints, and escalation rules. **The file is the source of truth** — editing it changes behavior; editing the README does not. Tool permissions are the real guardrail: a read-only agent literally cannot write. Agents = unattended & routine; **Skills** = interactive & confirmation-required.

---

## 1. エージェント定義の構造 / Anatomy of an agent

`.claude/agents/<name>.md`：

```markdown
---
name: relationship
description: いつ起動するか・何をするか・何をしないかを1〜2文で。Claude はこの description を読んで「このタスクをこのエージェントに振るか」を判断する。
tools: Read, Glob, Grep        # 付与するツール。書けないようにするなら Write/Edit を外す
---

# 役割（このエージェントの一文）

## 🧭 必読コンテキスト   ← 動作前に読むルールファイル（Identity / 哲学 など）
## 📖 役割              ← やること/やらないこと
## ⏰ 起動タイミング     ← トリガー表
## 🚫 やってはいけないこと ← 禁止事項（境界を明文化）
## 🛑 エスカレーション    ← 完了条件を満たせない時の「正しい止まり方」
## 🔄 セルフQAの3行      ← 出力末尾の自己チェック（事実/トーン/アンチスロップ）
```

ポイント:
- **`description` が振り分けの肝**。「〜で起動」「〜はしない」を具体的に書くほど誤起動が減る。
- **`tools` が技術的な境界**。「代筆させない」「消させない」は、文章でお願いするのではなく**ツールを与えない**ことで保証する（例: `relationship` は `Read, Glob, Grep` のみ＝物理的に書き込めない）。
- 本文は「憲法（`00_Intranet/`）を読め」と指す形にして、共通ルールを一箇所に集約する。

---

## 2. 唯一の権威ソース / Source of truth

挙動を決めるのは **`.claude/agents/<name>.md` だけ**。
`CLAUDE.md` やREADMEのエージェント一覧は**要約（ナビゲーション）**で、食い違ったら必ず `.claude/agents/` を信じる。ここを書き換えてもエージェント一覧を直さない限り挙動は変わらない——逆に、**挙動を変えたいなら `.claude/agents/` を編集する**。

---

## 3. エージェント vs スキル / Agents vs Skills

| | エージェント | スキル（`.claude/skills/`） |
|---|---|---|
| 性質 | 無人・定型 | 対話・要確認 |
| 起動 | `@name` / スケジュール | `/skill-name` |
| 向く仕事 | 振り分け・QA・定型レポート | 週次レビュー・タスク棚卸・センシティブな振り返り |
| 人間の関与 | 後追い確認 | 実行中ずっと関与 |

センシティブな作業（関係・健康・お金）は**スキルで前面**に出し、人間が必ずループに入るようにする。これは設計思想（[TIPS.md](TIPS.md) の「境界」）の核。

---

## 4. 新しいエージェントを作る / Add a new agent

1. `.claude/agents/<name>.md` を新規作成。既存（`finance.md` など）をひな形にコピーするのが速い。
2. frontmatter を書く：
   - `name`: ファイル名と一致
   - `description`: 起動条件と禁止事項（**ここが一番大事**）
   - `tools`: 必要最小限。読むだけなら `Read, Glob, Grep`
3. 本文に「必読コンテキスト／役割／トリガー／禁止／エスカレーション／セルフQA」を書く。
4. （任意）`CLAUDE.md` と README のエージェント一覧に1行追記（ナビ用）。
5. `orchestrator` に「この種の依頼は新エージェントへ」と1行足すと振り分けが回る。

> モデルを使い分けたい場合は、軽い定型＝軽量モデル／戦略判断＝最上位、と役割に応じて設計する（このリポの `💰 モデル戦略` 参照）。Claude Code 側の機能でエージェントごとにモデルを指定できる（バージョンにより方法が異なるので公式ドキュメントを確認）。

---

## 5. ハンドオフ / Handoffs

エージェントは自分の領分を超えたら、**チャット内で抱え込まず**タスクを作って他エージェントに渡す（`02_Tasks/` にタスク化し担当・コメントを記入）。これで仕事がチャットに埋もれず追跡可能になる。`orchestrator` がその交通整理をする。

---

## 6. 「正しい止まり方」/ Escalation

完了条件が書けない・境界を超える依頼は、**止まることが正解**。`ai_judgment_ok` を OFF にして人間へエスカレートする。エージェントが暴走しない設計の要。
