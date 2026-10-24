# Setup — reproduce this system / 再現手順

## Local voice input (public release)

Public voice recognition runs locally with [faster-whisper](https://github.com/SYSTRAN/faster-whisper). No Soniox account, speech-provider key or paid speech API is required. Soniox, offline memo delivery and optional feature plugins are excluded from this release.

Install the tested optional voice dependencies in the **same Python environment that launches the dashboard**. For the Windows `scripts/.venv` layout, run from the repository root:

```powershell
.\scripts\.venv\Scripts\python.exe -m pip install faster-whisper==1.2.1 av==16.1.0
```

Without these optional packages, the dashboard still starts and voice requests return a setup message. With no custom `stt_script`, the bundled `shuki_core/speech.py` uses the multilingual `small` model on CPU with int8 computation. The first voice request downloads public model weights into the external SHUKI data directory (`speech/models`); allow internet access and time for this first download. Later recognition uses the cached model locally. Audio is processed in memory rather than uploaded to a speech service. Recognition quality and speed depend on the clip and computer; test your microphone after setup.

An existing custom local engine can still be selected using private `stt_script` and `stt_venv_python` paths. Empty/null custom paths select the bundled local implementation; never copy another user's paths or credentials. Microphone access needs localhost or HTTPS when accessing SHUKI from another device. A public update does not activate or configure another installation automatically.

> **TL;DR** — ツールを2つ（Git・Claude Code）入れてこのリポをダウンロードし、ターミナルで `claude` を起動して `/setup` と打つだけ。残りはチャットで全部設定されます。ファイルを直接編集する必要はありません。日常の操作は、セットアップ後にブラウザで起動する SHUKI ダッシュボードから行います。
>
> **所要時間の目安**：手作業 約10〜15分 ＋ `/setup` の対話 約10〜15分。

このページだけ読めば完結するように、各手順に「これは何をしているのか」の軽い説明を付けています。途中で詰まったら各セクションの 💡 を読んでください。

---

## 0. 前提を3行で

- **Claude Code** … このシステムの“頭脳”。ターミナル（黒い画面）で動くAIで、ファイル作成・整理・自動化を全部やる。有料アカウントが必要（無料枠なし）。
- **SHUKI ダッシュボード** … ブラウザで動く画面。タスク・予定・ニュース・AIチャットをここから操作する。**日常の操作はここがメイン**。
- **Git** … このリポ（ひな形）をダウンロードするためのツール。1回使うだけ。

> つまり「Claude Code が裏側で書く・整理する → ダッシュボードで操作する」という分担です。

---

## 1. 事前準備（人間が手でやること・〜15分）

**ここだけが手作業。** 2つのツールを入れて、リポを置いて、`claude` を起動するところまで。

### ① Git をインストール（リポを取得するため）

リポを `git clone` でダウンロードするのに使います。ダウンロード版ZIPで代用も可（→ ③の代替案）。

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

### ③ このリポをダウンロード（ひな形を手元に置く）

ターミナルで、ノートを置きたい場所に移動してから：

```bash
git clone https://github.com/sflren6741/SHUKI my-vault
```

これで `my-vault` というフォルダが作られ、中にひな形一式が入ります。`my-vault` の部分は好きな名前でOK。

💡 **Gitを使いたくない場合**：GitHubページの緑の「Code」ボタン → 「Download ZIP」でダウンロードし、好きな場所に解凍 → そのフォルダを `my-vault` として使えばOK（以降の手順は同じ）。

🔒 **まだ非公開（private）のリポジトリに招待された場合**：上の `git clone` はそのままでは通りません（`Repository not found` と出ます）。どちらかで進めてください。

- **ZIPで受け取る（手軽・おすすめ）** — GitHub にログインした状態でリポジトリのページを開き、緑の「Code」→「Download ZIP」。認証設定が要りません。
- **`git clone` したい** — 認証が必要です。[GitHub CLI](https://cli.github.com/) を入れて `gh auth login` を1回済ませるのが一番楽で、以降は上の `git clone` がそのまま通ります。CLI を使わない場合は GitHub の Settings → Developer settings → **Personal access tokens** でトークンを作り、clone 時のパスワード欄にそれを貼ります（アカウントのパスワードでは通りません）。

いずれの場合も、招待メールのリンクから**先に招待を承諾**しておく必要があります。

### ④ vault フォルダで `claude` を起動

ターミナルで vault フォルダに移動して Claude Code を立ち上げます：

```bash
cd my-vault
claude
```

💡 `cd` は「フォルダを移動する」コマンド。`cd my-vault` で先ほどのフォルダに入り、`claude` でAIが起動します。VS Code拡張版を使う場合は、VS Code で `my-vault` フォルダを開いて拡張機能パネルから起動します。

> **既存の vault に組み込む場合**：`.claude/` `00_Intranet/` `CLAUDE.md` `_Templates/` `scripts/` を自分の vault にコピーするだけでOK。

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
| 自動化スクリプト（任意） | 朝/夜の自動実行 `.ps1` を生成 | やるか答えるだけ |
| 専門エージェント（任意） | 家計・語学など独自AIを追加 | 役割を答えるだけ |

💡 全部いきなりやらなくてOK。**自動化（任意）はスキップ**しても普通に使えます。まず Identity・Areas だけ埋めて使い始め、慣れてから広げるのがおすすめ。

---

## 3. セットアップ後にできること

**まずはダッシュボードを起動してみてください。** vault フォルダのルートで：

```powershell
pip install pyyaml   # 初回だけ
$env:SHUKI_VAULT = (Get-Location).Path
python scripts/dashboard_server.py
```

ブラウザで <http://127.0.0.1:8765/> を開くと、タスク・予定・ニュース・AIチャットが1画面にまとまっています。**日常はここから操作**します。裏側では Claude Code が動いていますが、画面はダッシュボードだけで完結します。

Claude Code のターミナルチャットには、思いついたことをそのまま話しかけることもできます。「メモ追加：〇〇」と投げればインボックスに入り、「タスク化して」でタスクになります。迷ったら `/next` で「今やる一手」が1つ出ます。込み入った調査やファイル整理をしたい時は、こちらを直接使うと早いです。

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
| `git` が見つからない | ①が未導入。または③をZIPダウンロードで代替 |
| `git clone` で `Repository not found` | 非公開リポジトリに招待された場合。招待を承諾した上で、③の🔒の手順（ZIP か `gh auth login`）で取得する |
| ダッシュボードにブラウザで繋がらない | `python scripts/dashboard_server.py` を起動したターミナルが生きているか確認。Python 3.11 以降が必要 |
| 文字化け・日本語が読みづらい | フレームワークは日本語ベース。ルールファイルは自由に英訳・ローカライズ可 |

---

## 参考ドキュメント（必要になったら読む）

| ドキュメント | いつ読む |
|---|---|
| [AGENTS.md](AGENTS.md) | エージェントの仕組み・自作の仕方を知りたい時 |
| [AUTOMATION.md](AUTOMATION.md) | 朝/夜の自動実行を組みたい時（Task Scheduler登録など） |
| [TIPS.md](TIPS.md) | type駆動PARA・wikilink・概念ノードの考え方を知りたい時 |
| [MOBILE-SYNC.md](MOBILE-SYNC.md) | 外出先からダッシュボードに繋ぎたい時 |

> このリポは「正解」ではなく**出発点**。自分の思考に合わせて育てるほど効きます。
</content>
</invoke>
