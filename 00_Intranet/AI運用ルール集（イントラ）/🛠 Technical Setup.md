# 🛠 Technical Setup

> [!note] 🛠
>
> **AI運用環境の前提を一覧する場所。** どの端末・どのコネクタが繋がっていて、AIから何が触れるかをここで把握する。
>
> ⚠️ **これはテンプレートです。** `<...>` を自分の環境に置き換えて使ってください。

## OS・主要環境 / Environment

- **メインPC**：`<例: Windows / macOS / Linux>`
- **モバイル**：`<例: Android / iPhone>`（同期方法は docs/MOBILE-SYNC.md）
- **エディタ**：Obsidian（vault の編集・閲覧・グラフ）
- **AI実行環境**：Claude Code（CLI / VS Code 拡張）

## 接続コネクタ / Connectors

AI／自動化から触れる外部サービスをここに列挙する（触れる範囲も明記）。

| 種別 | 接続先 | 用途 | AIが触れる範囲 |
|---|---|---|---|
| Calendar | `<例: Google Calendar>` | 予定取得・スタンドアップ | 読み取り |
| Storage | `<例: Google Drive>` | vault の端末間同期 | — |
| （任意）家計 | `<家計管理ツール>` | 月次マネー管理 | 提示のみ・実行なし |

## モデル戦略（要約）/ Model strategy

詳細は [[💰 モデル戦略]]。原則：**定型は軽量モデル／実務は標準／戦略判断は最上位＋セカンドオピニオン**。

## モバイル運用 / Mobile

- キャプチャ手順：思いついたら `01_Inbox/インボックス/` に直投げ → PCで `@orchestrator` が振り分け。
- 同期の具体手順は [docs/MOBILE-SYNC.md](../../docs/MOBILE-SYNC.md)。
