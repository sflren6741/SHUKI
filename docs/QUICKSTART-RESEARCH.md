# 🔬 研究者向けクイックスタート

**論文を追いかけながら、やることを見失わない** — この2つだけに絞った最短の導入手順です。

SHUKI はフル構成だと「定期便が無人で回る」システムですが、**そこまで要りません**。このページは以下だけを立ち上げます:

- 📋 **タスクボード** — やることをカンバンで見る
- 📰 **論文フィード** — 自分のテーマの新着を毎回まとめて拾う
- 🔍 **`/research`** — 1つのテーマを深く掘って先行研究マップを作る

定期実行（Task Scheduler / cron）は**設定しません**。使いたい時にコマンドを叩くだけです。PCを常時起動しておく必要もありません。

> 全体像は [README](../README.md) の「🎚 どこまで使うか」の節を参照。このページは **A → B** の道順です。

---

## 1. 入れる（〜15分）

| # | やること |
|---|---|
| 1 | [Claude Code](https://docs.claude.com/en/docs/claude-code/overview) をインストール（**有料プランが必要**。操作の主役） |
| 2 | [Obsidian](https://obsidian.md/) をインストール（ノートを読む・グラフを見るビューア） |
| 3 | [Python 3](https://www.python.org/downloads/) を確認（`python --version`。タスクボードと論文フィードに使う。追加ライブラリは不要） |
| 4 | このリポジトリを取得 |

**リポジトリの取得** — 公開されていれば:

```bash
git clone https://github.com/sflren6741/SHUKI my-vault
```

privateリポジトリに招待された場合は、GitHub にログインした状態で **Code → Download ZIP** が一番手軽です（`git clone` だと認証設定が要る）。展開したフォルダが vault になります。

**開く**: Obsidian で「Open folder as vault」→ そのフォルダを選ぶ。

## 2. 自分用に設定する（対話で終わる）

vault フォルダで Claude Code を起動して、`/setup` と打つだけです。

```bash
cd my-vault
claude
```

```
/setup
```

名前・関心領域・Area（＝継続的に気にしている領域）を聞かれるので答えてください。ファイルを直接編集する必要はありません。**研究者なら Area は「研究」「講義」「健康」「生活」あたりから始めるとちょうどよい**です（あとから増やせます）。

同梱の `_example-*.md` はプロパティの書き方を示す見本なので、読んで分かったら消して構いません。

## 3. タスクボードを出す

パス設定を1つだけ。`scripts/shuki_paths.example.json` をコピーして `scripts/shuki_paths.json` を作り、`vault` に自分のフォルダのパスを書きます。

```bash
cd scripts
cp shuki_paths.example.json shuki_paths.json   # Windows なら copy
```

```json
{
  "vault": "C:\\Users\\you\\my-vault"
}
```

起動:

```bash
python scripts/dashboard_server.py
```

ブラウザで <http://127.0.0.1:8765/board> を開くとタスクのカンバンが出ます。**使い終わったら Ctrl+C で止めて構いません** — 常駐させる必要はなく、止めてもデータは Markdown として vault に残ります。

タスクを増やすのは Claude Code 側が速いです:

```
「タスク追加：査読コメントへの返信を金曜までに」
```

## 4. 論文フィードを作る

自分のテーマを arXiv の検索クエリとして登録します。

```bash
python scripts/news_fetch.py --init-feeds research --topic "graph neural network"
```

これで `99_System/news/feeds.json` ができます。**テーマは複数登録するのが本命**です。ファイルを開いて `feeds` に足してください（`url` は上のコマンドが作った形をコピーして、検索語の部分だけ変える）:

```json
{
 "interests": "自分の研究テーマに近い新着論文。手法の新規性・再現性・自分の実験に取り込めるかを重視",
 "feeds": [
  {"name": "arXiv: graph neural network", "url": "http://export.arxiv.org/api/query?search_query=all%3A%22graph+neural+network%22&sortBy=submittedDate&sortOrder=descending&max_results=15", "category": "論文"},
  {"name": "arXiv: cs.LG 新着", "url": "https://rss.arxiv.org/rss/cs.LG", "category": "論文"}
 ]
}
```

`interests` は「何を重要とみなすか」の指示です。ここを具体的に書くほど選定の精度が上がります（例:「因果推論の識別条件に関する理論研究。応用事例より手法そのものを優先」）。

**取得する:**

```bash
python scripts/news_fetch.py
```

新着を集め、その中から重要なものだけを Claude が選びます。結果はダッシュボードの <http://127.0.0.1:8765/news> に出ます。

### 毎日動かさなくていい理由

既読URLを記録しているので、**3日ぶりに実行すれば3日分の新着がまとめて出ます**。取りこぼしません。「気が向いた時に叩く」で成立する設計なので、定期実行の設定は後回しで構いません。

> ⚠️ 分野カテゴリの新着フィード（`cs.LG` など）は1日に数百件流れ、そのうち先頭5件しか読みません。**分野全体の流し見**にはなりますが、狙って追うなら検索クエリのほうを増やしてください。

## 5. 深く掘る

新着の追跡（4節）が「近い研究を見落とさない」ための道具なのに対し、`/research` は**まだ知らない領域の地図を作る**ための道具です。

```
/research contrastive learning for graph representation
```

OpenAlex・arXiv・Web検索から文献を集めて、関連研究の一覧・**まだ埋まっていない課題**・体系化ツリー・研究の関係図（Mermaid）を英語レポートで返します。新しいテーマに入る時や、研究計画・イントロを書く前に使うと効きます。

---

## この先（要らなければ読まなくていい）

| やりたくなったら | 見るところ |
|---|---|
| 論文を読んだメモを構造化して残す | Claude Code に「このURLをナレッジノートにして」と投げる |
| 毎朝自動で新着を取ってきてほしい | [AUTOMATION.md](AUTOMATION.md)（C段。PCを開いた時に追いつく設定も可） |
| スマホから vault を見る | [MOBILE-SYNC.md](MOBILE-SYNC.md) |
| Obsidian の表示を整える | [OBSIDIAN-SETUP.md](OBSIDIAN-SETUP.md) |
| 使えるコマンドを一覧したい | `.claude/skills/` のフォルダ名がそのまま `/` コマンド名。迷ったら普通に話しかければよい |

## つまずいたら

| 症状 | 対処 |
|---|---|
| `python` が見つからない | Windows は `py` で試す。それも無ければ Python を入れ直す（インストール時に「Add to PATH」にチェック） |
| ダッシュボードが空 | タスクがまだ無いだけ。Claude Code に「タスク追加：〜」と投げてから再読み込み |
| `/news` が空 | `python scripts/news_fetch.py` をまだ実行していないか、新着が0件。`99_System/agent-runs/news_fetch_<日付>.log` に理由が出る |
| フィードが取れない | `feeds.json` の `url` をブラウザで開いて中身が返るか確認。arXiv の検索語に記号が入ると壊れることがある |
