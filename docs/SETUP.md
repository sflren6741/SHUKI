# Setup — reproduce this system / 再現手順

> **TL;DR** — ツールを3つ（Git・Claude Code・Obsidian）入れてこのリポをダウンロードし、ターミナルで `claude` を起動して `/setup` と打つだけ。残りはチャットで全部設定されます。ファイルを直接編集する必要はありません。
>
> **所要時間の目安**：手作業 約10〜15分 ＋ `/setup` の対話 約10〜15分。

このページだけ読めば完結するように、各手順に「これは何をしているのか」の軽い説明を付けています。途中で詰まったら各セクションの 💡 を読んでください。

---

## 0. 前提を3行で

- **Claude Code** … このシステムの“頭脳”。ターミナル（黒い画面）で動くAIで、ファイル作成・整理・自動化を全部やる。**メインの操作窓**。
- **Obsidian** … Markdownファイルを見る“ビューア兼DB”。グラフ表示・表（Bases）・ノート閲覧に使う。編集の主役ではない。
- **Git** … このリポ（ひな形）をダウンロードするためのツール。1回使うだけ。

> つまり「Claude Code で書く・整理する → Obsidian で眺める」という分担です。

---

## 1. 事前準備（人間が手でやること・〜15分）

**ここだけが手作業。** 4つのツールを入れて、リポを置いて、`claude` を起動するところまで。

### ① Git をインストール（リポを取得するため）

リポを `git clone` でダウンロードするのに使います。ダウンロード版ZIPで代用も可（→ ④の代替案）。

| OS | 入れ方 |
|---|---|
| Windows | <https://git-scm.com/download/win> からインストーラを実行（全部「次へ」でOK） |
| Mac | ターミナルで `git --version` を実行すると未導入なら自動で促される。または <https://git-scm.com/download/mac> |
| Linux | `sudo apt install git`（Debian/Ubuntu）など |

💡 **「ターミナル」とは**：コマンドを打つ黒い画面。Windowsは「PowerShell」または「ターミナル」、Macは「ターミナル.app」。スタートメニュー/Spotlightで検索すると出ます。

### ② Claude Code をインストール（AI本体）

公式手順：<https://docs.claude.com/en/docs/claude-code/overview>

- **CLI版**（ターミナルで `claude` と打つ）か **VS Code拡張版** のどちらでもOK。迷ったらまずCLI版。
- 動かすには **Anthropicの有料アカウント** が必要です（無料枠なし）。
  - Claude Pro（$20/月〜）か、API クレジットのどちらか。
  - サインアップ：<https://claude.ai/>（Pro）/ <https://console.anthropic.com/>（API）

💡 インストール後、ターミナルで `claude --version` が表示されれば成功です。

### ③ Obsidian をインストール（ビューア）

公式サイト：**<https://obsidian.md/>** → 画面の「Get Obsidian / Download」から自分のOS版をダウンロードして実行。

- Windows: `.exe` を実行 → 「次へ」で完了
- Mac: `.dmg` を開いて Obsidian を Applications にドラッグ
- 無料で使えます（個人利用）。アカウント登録は不要。

💡 vault（ヴォルト）= Obsidian が管理する「ノートの入った1フォルダ」のこと。次の④で作るフォルダがそのまま vault になります。

### ④ このリポをダウンロード（ひな形を手元に置く）

ターミナルで、ノートを置きたい場所に移動してから：

```bash
git clone https://github.com/sflren6741/SHUKI my-vault
```

これで `my-vault` というフォルダが作られ、中にひな形一式が入ります。`my-vault` の部分は好きな名前でOK。

💡 **Gitを使いたくない場合**：GitHubページの緑の「Code」ボタン → 「Download ZIP」でダウンロードし、好きな場所に解凍 → そのフォルダを `my-vault` として使えばOK（以降の手順は同じ）。

### ⑤ Obsidian で vault として開く

1. Obsidian を起動
2. 「**Open folder as vault**」（フォルダを vault として開く）を選ぶ
   - 初回起動画面、または左下の vault 切替アイコン → 「Open folder as another vault」
3. ④で作った `my-vault` フォルダを選択
4. 「Trust author and enable plugins?」と聞かれたら **Trust** を選ぶ（同梱プラグインを使うため）

💡 開いた直後に「コミュニティプラグインを有効化しますか？」と聞かれることがあります。`/setup` で案内するので、ここでは有効化しておけば後がスムーズです（後でも設定可）。

### ⑥ vault フォルダで `claude` を起動

ターミナルで vault フォルダに移動して Claude Code を立ち上げます：

```bash
cd my-vault
claude
```

💡 `cd` は「フォルダを移動する」コマンド。`cd my-vault` で先ほどのフォルダに入り、`claude` でAIが起動します。VS Code拡張版を使う場合は、VS Code で `my-vault` フォルダを開いて拡張機能パネルから起動します。

> **既存の vault に組み込む場合**：`.claude/` `00_Intranet/` `CLAUDE.md` `_Templates/` の4つを自分の vault にコピーするだけでOK。

---

## 2. `/setup` で残りを全部終わらせる

`claude` が起動したら、チャット欄に次の1行を打つだけ：

```
/setup
```

あとは Claude Code が**質問しながら**（1〜2問ずつ）、以下を全部設定します。**ファイルを手で編集する必要はありません。**

| 設定されるもの | 何をするか | あなたの作業 |
|---|---|---|
| Identity.md（プロフィール・境界線） | 名前・職業・AIに任せない領域などを記入 | 質問に答えるだけ |
| 哲学・価値観.md（価値観・行動原則） | 大事にしている価値観を定義 | 質問に答えるだけ |
| Areas（生活領域のハブ） | 「仕事」「健康」等の領域ファイルを自動作成 | 領域名を答えるだけ |
| CLAUDE.md のパス設定 | `<WORKSPACE>` 等を実際のパスに自動置換 | パスを答えるだけ |
| Obsidian プラグイン設定 | Templater/Linter等を1ステップずつ案内 | 画面のGUI操作（後述） |
| 自動化スクリプト（任意） | 朝/夜の自動実行 `.ps1` を生成 | やるか答えるだけ |
| 専門エージェント（任意） | 家計・語学など独自AIを追加 | 役割を答えるだけ |

> ⚠️ **Obsidianのプラグイン設定だけはGUI操作が必要**（Claudeが画面を直接触れないため）。でも「設定 → ◯◯ → △△をON」のように1ステップずつ案内するので、検索は不要です。詳しく知りたい時だけ [OBSIDIAN-SETUP.md](OBSIDIAN-SETUP.md) を見てください。

💡 全部いきなりやらなくてOK。**自動化（任意）はスキップ**しても普通に使えます。まず Identity・Areas だけ埋めて使い始め、慣れてから広げるのがおすすめ。

---

## 3. セットアップ後にできること

メインの操作はずっと **Claude Code（チャット）**。Obsidian は見る専用と思ってOKです。

```
# インボックスに何でも投げる（Claudeが行き先を振り分ける）
「タスクを作って：〇〇を調べる」
「メモ：△△を読みたい」

# ナレッジ化（URLを渡すとノートにして既存ノートとリンク）
「このURLをナレッジノートにして: https://...」

# 状況確認
「今週の進行中タスクを見せて」

# 週次レビュー（対話型・人間が必ずループに入る）
/weekly-review
```

💡 困ったら `/setup` をもう一度打てば「何を更新する？」とメニューが出ます（再実行＝アップデートモード）。

---

## 4. うまくいかない時（よくあるつまずき）

| 症状 | 対処 |
|---|---|
| `claude` と打っても「コマンドが見つかりません」 | ②のインストールが未完了。ターミナルを再起動して `claude --version` を確認 |
| `git` が見つからない | ①が未導入。または④をZIPダウンロードで代替 |
| Obsidianでノートの日付が自動で入らない | プラグイン未設定。`/setup` のプラグイン案内、または [OBSIDIAN-SETUP.md](OBSIDIAN-SETUP.md) を実行 |
| プラグインを有効化していいか不安 | このリポは仕組みのみで個人情報なし。Trust して問題なし |
| 文字化け・日本語が読みづらい | フレームワークは日本語ベース。ルールファイルは自由に英訳・ローカライズ可 |

---

## 参考ドキュメント（必要になったら読む）

| ドキュメント | いつ読む |
|---|---|
| [OBSIDIAN-SETUP.md](OBSIDIAN-SETUP.md) | プラグイン設定を手動で詳しくやりたい時 |
| [AGENTS.md](AGENTS.md) | エージェントの仕組み・自作の仕方を知りたい時 |
| [AUTOMATION.md](AUTOMATION.md) | 朝/夜の自動実行を組みたい時（Task Scheduler登録など） |
| [TIPS.md](TIPS.md) | type駆動PARA・wikilink・概念ノードの考え方を知りたい時 |
| [MOBILE-SYNC.md](MOBILE-SYNC.md) | スマホ（Android）と同期したい時 |

> このリポは「正解」ではなく**出発点**。自分の思考に合わせて育てるほど効きます。
</content>
</invoke>
