# Setup — reproduce this system / 再現手順

> **TL;DR** — ツールを3つ入れてクローンしたら `claude` を起動、あとは `/setup` を打つだけ。ファイルを直接編集する必要はありません。

---

## 1. 事前準備（人間が手でやること・〜10分）

これだけが手作業。あとは Claude Code とのチャットで完結する。

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

## 2. あとはチャットで完結

`claude` を起動したら、チャットに以下を入力：

```
/setup
```

Claude Code がヒアリングしながら以下を自動で設定する：

- **Identity.md** — あなたのプロフィール・価値観・AIへの境界線
- **Areas** — 管理したい生活領域のハブファイル（`05_Areas/`）
- **CLAUDE.md のパス設定** — `<WORKSPACE>` 等のプレースホルダーを実際のパスに置換
- **専門エージェント**（任意） — 家計・語学・計画など、用途に合わせて追加

**ファイルを直接編集しなくても設定が完了します。**

---

## 3. （任意）Obsidian プラグイン設定

日付の自動挿入・Bases ビューを使うなら設定が必要。基本的な運用には必須ではない。

→ [OBSIDIAN-SETUP.md](OBSIDIAN-SETUP.md)

---

## 4. （任意）自動化

朝スタンドアップ・週次レビュー・夜間QAをスケジュールで回したいなら。`/setup` 完了後に検討でよい。

→ [AUTOMATION.md](AUTOMATION.md)

---

## カスタマイズ

セットアップ後も、変更はチャットで可能：

```
エージェントを追加して。家計を管理したい。
```
```
Areaに「英語学習」を足して。
```
```
Identityの職業の部分を更新して。
```

直接ファイルを編集したい場合：
- エージェント定義 → `.claude/agents/<name>.md`（[AGENTS.md](AGENTS.md) 参照）
- ルール → `00_Intranet/AI運用ルール集（イントラ）/`
- 運用マニュアル → `CLAUDE.md`

> このリポは「正解」ではなく**出発点**。自分の思考に合わせて育てるほど効く。
