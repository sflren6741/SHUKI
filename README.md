# 🏯 Obsidian × Claude Code — Personal AI Intranet

> A local-first "AI intranet" built on a single Obsidian vault and driven by [Claude Code](https://claude.com/claude-code).
> Four core agents + an extensible specialist system, a type-driven PARA knowledge base, scheduled automation, and—most importantly—**guardrails that decide what the AI must *not* do.**

*Read this in [日本語](#-日本語) below.*

---

## Why I built this

I wanted one place where my whole life is organized—work, money, language study, sport, relationships, reflection—and an AI layer that actually *helps run it* instead of being a chat box I have to babysit.

Plain ChatGPT-style chat forgets everything between sessions and has no opinion about where information belongs. So I turned a plain Obsidian vault into a small organization: a set of **named agents with clear jobs and clear boundaries**, a **type-driven filing system**, and **scheduled routines** that run on their own. Claude Code is the runtime; Obsidian is the database and the UI.

This repository is the **framework only**—the agents, rules, templates, and structure. None of my personal notes are included.

## What's good about it (my perspective)

- **Local-first & private.** Everything lives in Markdown files on my own machine. No vendor lock-in, fully searchable, diff-able in git, editable in plain Obsidian.
- **Specialized agents beat one generalist.** Instead of one assistant trying to do everything, nine agents each own a domain (triage, finance, planning, review, reflection, knowledge, etc.) and hand off to each other through tasks—not lost chat threads.
- **Type-driven PARA.** Projects / Areas / Resources / Archive are expressed by a `type:` property and wikilinks, *not* by rigid folders. Obsidian Bases + properties make attribute-driven organization far more flexible than folder-driven.
- **Trust comes from constraints.** The most useful design choice is what the AI is *forbidden* to do: it never ghostwrites messages to my partner, never moves money, never makes health calls—those require a human. Several agents are read-only by tool permission, so the boundary is technically enforced, not just requested.
- **Automation that compounds.** A morning standup, a weekly review, nightly QA, and inbox routing run on a schedule. A separate local LLM (Ollama) sweeps the vault at night for typos and broken frontmatter.
- **A knowledge graph that grows itself.** Recurring themes become "concept nodes" that link across notes, so the vault gets *more* connected the longer I use it.

## Architecture at a glance

```
Obsidian Vault (Markdown, local)
├── 00_Intranet/     ← the "constitution": rules every agent must read
├── 03_Projects/     ← time-bound bundles of tasks (type: project)
├── 04_Tasks/        ← one task per file (status / due / agent / area)
├── 05_Areas/        ← ongoing areas of responsibility (single hub note each)
├── 06_Resources/    ← reusable knowledge + concept nodes (the graph hubs)
├── 01_Inbox/        ← unprocessed capture, auto-routed by the orchestrator
├── 07_Logs/         ← dated records (standups, reviews, reflections)
└── .claude/
    ├── agents/      ← agent definitions (4 core + add your own specialist agents)
    └── skills/      ← interactive, confirmation-required workflows
```

> **This repo ships the *system only*** — agents, rules (`00_Intranet/`), the operating manual (`CLAUDE.md`), and templates (`_Templates/`). Each PARA folder above carries a short `README.md` explaining its purpose plus **one skeleton `_example-*.md`** that shows the frontmatter properties in context (e.g. a near-empty *person note* demonstrating that relationships live in Resources too). **No personal notes, logs, or resources are included** — delete the `_example-*` files once you've got the idea.

### The 4 core agents (+ add your own)

| Tier | Agent | Job |
|---|---|---|
| Orchestrator | `orchestrator` | Triage, morning standup, weekly review |
| Core | `reviewer` | Double-checks other agents' output (read-only) |
| Core | `knowledge` | Turns URLs/content into linked knowledge notes; weekly graph upkeep |
| Core | `infrastructure` | Audits the task DB, finds duplicates & silent failures (proposals only) |
| + | `<your-agent>` | Add specialists to fit your life: finance, language learning, planning, reflection, etc. See [AGENTS.md](docs/AGENTS.md) |

**Agents = unattended & routine. Skills = interactive & needs confirmation.** Sensitive work (weekly review, task audit) runs as a *skill* in the foreground so a human stays in the loop.

## 📚 Full reproduction guide

The goal: **read this repo and you can reproduce the whole setup** (then customize). Deep dives live in [`docs/`](docs/):

| Guide | What it covers |
|---|---|
| [SETUP.md](docs/SETUP.md) | End-to-end: vault → this repo → identity → run Claude Code |
| [OBSIDIAN-SETUP.md](docs/OBSIDIAN-SETUP.md) | Plugins & settings (Templater, Linter, Bases, links) |
| [AGENTS.md](docs/AGENTS.md) | How agents work & **how to create your own** |
| [MOBILE-SYNC.md](docs/MOBILE-SYNC.md) | Android + Obsidian + **FolderSync** sync recipe |
| [AUTOMATION.md](docs/AUTOMATION.md) | Scheduled standup / review / nightly QA (+ local Ollama) |
| [TIPS.md](docs/TIPS.md) | Mental models: type-driven PARA, **wikilinks**, concept nodes, boundaries |

## Day-to-day workflow

The primary interface is **Claude Code, not Obsidian**. Obsidian is for browsing and reading; Claude Code is for creating and organizing.

```
# Dump anything into the inbox — Claude routes it
"add a note: I want to read 'Thinking Fast and Slow'"
"inbox: remind me to follow up on the project proposal"

# Organize and retrieve
"show me my in-progress tasks for this week"
"summarize everything I logged last week about running"

# Knowledge
"turn this URL into a knowledge note: https://..."
"what do I know about <topic>?"

# Weekly review (interactive — you stay in the loop)
/weekly-review
```

All of this happens in chat. The vault files are the output, not the input. You only open Obsidian when you want to browse the graph, read a note, or see a filtered view via Bases.

---

## Setup

> Quick start below; the [full guide](docs/SETUP.md) has every step.

1. **Install Claude Code** — see the [official docs](https://docs.claude.com/en/docs/claude-code/overview).
2. **Clone into a new (or existing) Obsidian vault folder:**
   ```bash
   git clone <your-repo-url> my-vault
   cd my-vault
   ```
   Open the folder as a vault in [Obsidian](https://obsidian.md/).
3. **Fill in your identity.** Edit `00_Intranet/AI運用ルール集（イントラ）/🪪 Identity.md` — it's a template with `<...>` placeholders. This is the first file every agent reads.
4. **Review the rules & boundaries.** Skim `CLAUDE.md` (the top-level operating manual) and the rules under `00_Intranet/`. Adjust the "human-confirmation-required" zones to your own life.
5. **Tune the agents.** The files in `.claude/agents/` are the source of truth for behavior. Edit triggers/constraints to taste, and add specialist agents as needed.
6. **(Optional) Schedule routines.** The standup / weekly-review / QA agents are wired to run via Windows Task Scheduler in my setup; `CLAUDE.md` documents the schedule. Replace `<WORKSPACE>` / `<HOME>` placeholders with your own paths.
7. **(Optional) Local nighttime QA.** A separate [Ollama](https://ollama.com/) loop sweeps for typos/frontmatter issues. Not required to use the framework.

> The framework is written largely in Japanese (it's my working language). The structure and agent logic translate directly—feel free to localize the rule files.

## Notes & caveats

- This is a **personal system**, opinionated and shaped around how I think. Treat it as a starting point, not a product.
- The vault language is Japanese; agent prompts assume it. English localization is welcome.
- Money / health / outbound-communication actions are intentionally gated behind human confirmation. Keep those guardrails.

## Contact

Questions, ideas, or want to compare setups? **Open a [GitHub Issue](../../issues).** That's the best place to reach me.

## License

[MIT](LICENSE).

---

## 🇯🇵 日本語

> 単一の Obsidian vault を「AIイントラネット」に仕立て、[Claude Code](https://claude.com/claude-code) で駆動するローカルファースト構成。
> コア4体＋拡張可能な専門エージェント群、type駆動のPARAナレッジベース、スケジュール自動化、そして何より **「AIにやらせないこと」を決めるガードレール** が核です。

### なぜ作ったか

仕事・お金・英語・スポーツ・人間関係・内省――生活まるごとを一箇所に整理し、その上で「ただのチャット窓」ではなく **実際に運用を手伝ってくれるAIレイヤー** が欲しかった。

普通のチャット型AIはセッションをまたぐと全部忘れるし、「この情報をどこに置くべきか」という意見を持たない。そこで素の Obsidian vault を小さな組織にしました：**役割と境界が明確な名前付きエージェント群**、**type駆動のファイリング**、そして勝手に回る **定期ルーティン**。Claude Code が実行環境、Obsidian がDB兼UIです。

このリポジトリは **仕組み（フレームワーク）だけ** ――エージェント・ルール・テンプレート・構造のみ。個人ノートは一切含みません。

### ここが良い（自分の観点）

- **ローカルファースト＆プライベート** — 全部が自分のマシン上の Markdown。ベンダーロックインなし、全文検索可、gitで差分管理、素のObsidianで編集可。
- **「何でも屋1体」より「専門家9体」** — 1つのアシスタントに全部やらせるのではなく、トリアージ・家計・計画・レビュー・内省・ナレッジ…と各エージェントがドメインを持ち、チャットの埋もれではなく **タスク経由でハンドオフ** する。
- **type駆動のPARA** — Projects/Areas/Resources/Archive を硬いフォルダではなく `type:` プロパティと wikilink で表現。Obsidian Bases ＋ プロパティのおかげで、フォルダ駆動より属性駆動の方が圧倒的に柔軟。
- **信頼は制約から生まれる** — 一番効いている設計は「AIに**禁止**していること」。センシティブな相手への文章は代筆しない、お金は動かさない、健康判断はしない――全部人間の領分。複数のエージェントはツール権限で読み取り専用にしてあり、境界が**技術的に強制**されている。
- **積み上がる自動化** — 朝のスタンドアップ・週次レビュー・夜間QA・インボックス振り分けがスケジュールで回る。別のローカルLLM（Ollama）が夜間にvaultを巡回して誤字やfrontmatter不整合を拾う。
- **自分で育つナレッジグラフ** — 繰り返し出るテーマは「概念ノード」になりノート横断でリンクされる。使うほどvaultの結合度が上がる。

### 構成のひと目

```
Obsidian Vault（ローカルMarkdown）
├── 00_Intranet/     ← 「憲法」：全エージェントが必ず読むルール集
├── 03_Projects/     ← 期限つきタスクの束（type: project）
├── 04_Tasks/        ← 1ファイル1タスク（status / 期限 / 担当 / area）
├── 05_Areas/        ← 継続責任領域（各1ハブノート）
├── 06_Resources/    ← 再利用ナレッジ＋概念ノード（グラフのハブ）
├── 01_Inbox/        ← 未処理キャプチャ、orchestrator が自動振り分け
├── 07_Logs/         ← 日付つき記録（スタンドアップ・レビュー・内省）
└── .claude/
    ├── agents/      ← エージェント定義（コア4体＋専門エージェントは自分で追加）
    └── skills/      ← 対話・要確認のワークフロー
```

> **このリポジトリは「仕組みだけ」**を配布します — エージェント・ルール（`00_Intranet/`）・運用マニュアル（`CLAUDE.md`）・テンプレート（`_Templates/`）。上図の各 PARA フォルダには、用途を説明する短い `README.md` と、**プロパティの使い方を示す骨組み例 `_example-*.md` を1つずつ**同梱しています（例：ほぼ空の*人物ノート*で「人間関係も Resources で管理する」と一目で分かる）。**個人のノート・ログ・リソースは一切含みません** — 例ファイルは理解したら削除してください。

### コア4体のエージェント（＋自分でカスタム追加）

| Tier | エージェント | 役割 |
|---|---|---|
| 統括 | `orchestrator` | 振り分け・朝のスタンドアップ・週次レビュー |
| コア | `reviewer` | 他エージェント出力のダブルチェック（読み取り専用） |
| コア | `knowledge` | URL/コンテンツをリンク付きナレッジ化・週次グラフ整備 |
| コア | `infrastructure` | タスクDB点検・重複/静かな故障の検出（提案のみ） |
| ＋ | `<専門エージェント>` | 家計・語学・計画・内省など自分の生活に合わせて追加（[AGENTS.md](docs/AGENTS.md) 参照） |

**エージェント＝無人・定型／スキル＝対話・要確認。** センシティブな作業（週次レビュー・タスク棚卸）は人間が必ず関与できるよう、前面の **スキル** として動かします。

### 📚 詳細な再現ガイド

目標は **「このリポを見れば運用をそのまま再現できる」**（その上でカスタマイズ可）。詳細は [`docs/`](docs/) に：

| ガイド | 内容 |
|---|---|
| [SETUP.md](docs/SETUP.md) | 全体手順：vault作成→このリポ導入→Identity記入→Claude Code起動 |
| [OBSIDIAN-SETUP.md](docs/OBSIDIAN-SETUP.md) | プラグイン・設定（Templater / Linter / Bases / リンク） |
| [AGENTS.md](docs/AGENTS.md) | エージェントの仕組みと **自作の仕方** |
| [MOBILE-SYNC.md](docs/MOBILE-SYNC.md) | Android + Obsidian + **FolderSync** での同期手順 |
| [AUTOMATION.md](docs/AUTOMATION.md) | スタンドアップ/レビュー/夜間QA の定期実行（+ローカルOllama） |
| [TIPS.md](docs/TIPS.md) | 思考モデル：type駆動PARA・**wikilink**・概念ノード・境界 |

### 日常の使い方

メインのインターフェースは **Obsidian ではなく Claude Code**。Obsidian は閲覧・グラフ確認用、Claude Code は作成・整理用。

```
# インボックスに何でも投げる — Claude が振り分ける
「メモ追加：『Think Fast and Slow』を読みたい」
「インボックス：プロジェクト提案のフォローアップを忘れずに」

# 整理・検索
「今週の進行中タスクを見せて」
「先週のランニングに関するログをまとめて」

# ナレッジ化
「このURLをナレッジノートにして: https://...」
「<テーマ>について自分が知っていることは？」

# 週次レビュー（対話型 — 人間が必ずループに入る）
/weekly-review
```

全部チャットで完結する。vault ファイルは入力ではなく出力。Obsidian を開くのは、グラフを見たい・ノートを読みたい・Bases のビューで俯瞰したいときだけ。

---

### セットアップ

> 下はクイックスタート。全ステップは[詳細ガイド](docs/SETUP.md)に。

1. **Claude Code を導入** — [公式ドキュメント](https://docs.claude.com/en/docs/claude-code/overview)参照。
2. **新規（または既存）の Obsidian vault フォルダにクローン**：
   ```bash
   git clone <your-repo-url> my-vault
   cd my-vault
   ```
   フォルダを [Obsidian](https://obsidian.md/) で vault として開く。
3. **Identity を埋める** — `00_Intranet/AI運用ルール集（イントラ）/🪪 Identity.md` を編集。`<...>` プレースホルダーのテンプレートです。全エージェントが最初に読むファイル。
4. **ルールと境界を確認** — `CLAUDE.md`（最上位の運用マニュアル）と `00_Intranet/` 以下のルールに目を通し、「人間確認必須ゾーン」を自分の生活に合わせて調整。
5. **エージェントを調整** — `.claude/agents/` のファイルが挙動の権威ソース。トリガー・制約を好みに編集し、専門エージェントを必要に応じて追加。
6. **（任意）ルーティンをスケジュール** — スタンドアップ／週次レビュー／QA は Windows Task Scheduler で起動する想定。`CLAUDE.md` にスケジュール記載あり。`<WORKSPACE>` / `<HOME>` を自分のパスに置換。
7. **（任意）ローカル夜間QA** — 別途 [Ollama](https://ollama.com/) のループが誤字/frontmatterを巡回。フレームワーク利用には必須ではありません。

> フレームワークは主に日本語で書かれています（自分の作業言語のため）。構造とロジックはそのまま通用するので、ルールファイルは自由にローカライズしてください。

### 注意

- これは **個人システム** で、自分の思考に合わせて尖らせてあります。製品ではなく出発点として扱ってください。
- お金／健康／外部発信は意図的に人間確認の後ろに置いています。このガードレールは残すことを推奨します。

### 問い合わせ

質問・アイデア・構成の比較など、**[GitHub Issue](../../issues) を立ててください。** 連絡先として一番確実です。

### ライセンス

[MIT](LICENSE)。
