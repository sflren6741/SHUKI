# Setup — reproduce this system / 再現手順

> **TL;DR (EN)** — Install Claude Code → make an Obsidian vault → drop this repo into it → fill in `Identity.md` → set up the Obsidian plugins → run Claude Code from the vault folder. Optional: mobile sync, scheduled routines, a local nighttime QA model. Everything is plain Markdown, so it's all customizable.

このページだけで運用を再現できることを目指す。前提は **Claude Code** と **Obsidian**。所要時間 ~30分（自動化・モバイルは任意）。

---

## 0. 前提 / Prerequisites

| 必要 | 用途 |
|---|---|
| [Claude Code](https://docs.claude.com/en/docs/claude-code/overview) | エージェントの実行環境（CLI / VS Code拡張） |
| Anthropic アカウント（有料） | Claude Pro（$20/月〜）または API クレジット — 無料枠なし |
| [Obsidian](https://obsidian.md/) | vault の編集・閲覧・グラフ表示 |
| git | このリポの取得・バージョン管理 |
| （任意）クラウドストレージ | 端末間同期（Google Drive 等） |
| （任意）[Ollama](https://ollama.com/) | ローカルLLMで夜間QA |

> Claude Code は CLI / デスクトップ / VS Code・JetBrains 拡張で使える。本ガイドは vault フォルダ直下で `claude` を起動する前提。

---

## 1. Vault を作ってこのリポを入れる / Create the vault

```bash
# クラウド同期したいなら、同期フォルダの中にクローンする（例: Google Drive 配下）
git clone <your-repo-url> MyVault
cd MyVault
```

Obsidian を開き **「Open folder as vault」** で `MyVault` を選択。
> 既存 vault に組み込む場合は、`.claude/` `00_Intranet/` `CLAUDE.md` `_Templates/` を既存 vault にコピーする。

---

## 2. 自分の情報を入れる / Fill in your identity

`00_Intranet/AI運用ルール集（イントラ）/🪪 Identity.md` を開き、`<...>` を自分の情報に置換する。
**これは全エージェントが毎回最初に読むファイル。** 名前・職種・価値観・「AIにやらせない領域」を書く。書きすぎず、AIに渡したい事実だけ。

次に `CLAUDE.md`（最上位の運用マニュアル）に目を通す。ディレクトリマップ・エージェント一覧・共通ルール・スケジュールが書いてある。`<HOME>` `<WORKSPACE>` などのプレースホルダーは自分のパスに置換する。

---

## 3. Obsidian を設定する / Configure Obsidian

→ [OBSIDIAN-SETUP.md](OBSIDIAN-SETUP.md) の通りに Templater / Linter / Files&Links を設定。
これで新規ノートに日付が自動で入り、リンクが壊れなくなる。

---

## 4. Claude Code を動かす / Run Claude Code

vault フォルダ直下で：

```bash
claude
```

最初の起動で `CLAUDE.md` と `.claude/agents/` が読み込まれる。試しに：

```
@orchestrator 今日のフォーカスは？
```
```
このURLをナレッジ化して: https://example.com/...
```

エージェントは `@<agent-name>` で名指し起動。`orchestrator` が振り分けの中心。
→ エージェントの仕組みと作り方は [AGENTS.md](AGENTS.md)。

---

## 5. （任意）スマホと同期 / Mobile sync

Android + Obsidian + FolderSync でどこでもキャプチャ・閲覧。
→ [MOBILE-SYNC.md](MOBILE-SYNC.md)

## 6. （任意）定期実行を組む / Schedule routines

朝のスタンドアップ・週次レビュー・夜間QA を自動化。
→ [AUTOMATION.md](AUTOMATION.md)

## 7. 使いこなす / Tips & mental models

type駆動PARA・wikilink2層戦略・概念ノード・境界の哲学。
→ [TIPS.md](TIPS.md)

---

## カスタマイズ方針 / Customizing

全部 Markdown とプロパティなので、好きに変えてよい：
- **エージェントを足す/減らす** → `.claude/agents/<name>.md` を追加/削除（[AGENTS.md](AGENTS.md)）
- **Area を自分の人生に合わせる** → `CLAUDE.md` の Area 一覧と `05_Areas/` を編集
- **ルールを変える** → `00_Intranet/` 配下を編集（食い違ったら `.claude/agents/` と `CLAUDE.md` が正）
- **言語** → ルール・テンプレは日本語ベース。英語化も自由

> このリポは「正解」ではなく**出発点**。自分の思考に合わせて尖らせるほど効く。
