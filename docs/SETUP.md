# Setup — reproduce this system / 再現手順

> **TL;DR** — ツールを3つ入れてクローンしたら `claude` を起動、あとは `/setup` を打つだけ。ファイルを直接編集する必要はありません。

---

## 1. 事前準備（人間が手でやること・〜10分）

**これだけが手作業。あとはすべて Claude Code とのチャットで完結する。**

| ステップ | 内容 |
|---|---|
| ① [Claude Code](https://docs.claude.com/en/docs/claude-code/overview) をインストール | CLI / VS Code 拡張どちらでも可 |
| ② Anthropic アカウント（有料）を作成 | Claude Pro（$20/月〜）または API クレジット — 無料枠なし |
| ③ [Obsidian](https://obsidian.md/) をインストール | vault の閲覧・グラフ表示に使う |
| ④ このリポをクローン | `git clone https://github.com/sflren6741/SHUKI my-vault` |
| ⑤ Obsidian で vault として開く | **Open folder as vault** で `my-vault` を選択 |
| ⑥ vault フォルダで `claude` を起動 | ターミナルで `cd my-vault && claude` |

> 既存の vault に組み込む場合は `.claude/` `00_Intranet/` `CLAUDE.md` `_Templates/` をコピーするだけでよい。

---

## 2. `/setup` で残りを完結させる

`claude` を起動したら、チャットに以下を入力するだけ：

```
/setup
```

Claude Code が対話しながら以下を**すべて**設定する：

| 設定内容 | 方法 |
|---|---|
| Identity.md（プロフィール・境界線） | ヒアリング → 自動書き込み |
| 哲学・価値観.md（価値観定義・行動原則） | ヒアリング → 自動書き込み |
| Areas（生活領域のハブファイル） | 領域名を聞いて `05_Areas/` に自動作成 |
| CLAUDE.md のパス設定 | パスを聞いて `<WORKSPACE>` 等を自動置換 |
| Obsidian プラグイン設定 | 手順を1ステップずつ案内（GUI操作はあなたが行う） |
| 自動化スクリプト（任意） | `.ps1` を生成・Task Scheduler 登録手順を案内 |
| 専門エージェント（任意） | 役割を聞いて `.claude/agents/` に自動生成 |

**ファイルを直接編集しなくても設定が完了します。**

> Obsidianプラグインの設定（Templater・Linter等）はGUIを使うためClaudeが直接操作することはできませんが、`/setup`がObsidianの画面で何をどこに設定するか1ステップずつ案内します。

---

## セットアップ後にできること

```
# インボックスに何でも投げる
「タスクを作って：〇〇を調べる」
「メモ：△△を読みたい」

# ナレッジ化
「このURLをナレッジノートにして: https://...」

# 状況確認
「今週の進行中タスクを見せて」

# 週次レビュー（対話型）
/weekly-review
```

---

## 参考ドキュメント

| ドキュメント | 用途 |
|---|---|
| [OBSIDIAN-SETUP.md](OBSIDIAN-SETUP.md) | Obsidianプラグイン設定の詳細リファレンス（`/setup`が案内するが、詳しく知りたい場合） |
| [AGENTS.md](AGENTS.md) | エージェントの仕組みと自作の仕方 |
| [AUTOMATION.md](AUTOMATION.md) | 自動化の詳細（`/setup`でスクリプト生成後、Task Schedulerへの登録方法など） |
| [TIPS.md](TIPS.md) | type駆動PARA・wikilink・概念ノード等の思考モデル |
| [MOBILE-SYNC.md](MOBILE-SYNC.md) | Android + Obsidian + FolderSync での同期手順 |

> このリポは「正解」ではなく**出発点**。自分の思考に合わせて育てるほど効く。
