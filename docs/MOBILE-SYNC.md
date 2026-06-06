# Mobile sync — Android + Obsidian + FolderSync / スマホ同期

> **TL;DR (EN)** — Your vault lives in a cloud folder (e.g. Google Drive) on desktop. On Android, **FolderSync** mirrors that cloud folder to a *local* folder, and the Obsidian Android app opens the local folder as a vault. Use two-way sync, sync before and after you edit, and you can capture/read anywhere. This is one known-good recipe — swap the cloud backend or sync tool to taste.

PC側は vault をクラウドフォルダ（例: Google Drive）に置く。Android では **FolderSync** がそのクラウドフォルダを**ローカルフォルダにミラー**し、Obsidian Android がそのローカルフォルダを vault として開く。これで外出先でもキャプチャ・閲覧できる。

> ⚠️ これは「動く一例」。クラウド（Google Drive / Dropbox / OneDrive…）や同期ツール（FolderSync / Syncthing / Obsidian Sync / git）は好みで差し替え可。Obsidian Android は**ローカルフォルダしか vault にできない**ため、クラウド↔ローカルのミラーが要る、という点だけ共通。

---

## 構成 / The shape

```
[PC]  vault = クラウド同期フォルダ（Google Drive for Desktop 配下）
                     ⇅ クラウド（Google Drive）
[Android]  FolderSync: クラウドフォルダ ⇄ 端末ローカルフォルダ
                     ↓
           Obsidian Android: ローカルフォルダを vault として開く
```

---

## 手順 / Steps

### 1. PC側
- vault をクラウド同期フォルダ内に置く（例: Google Drive for Desktop のマイドライブ配下）。
- クラウド側に vault フォルダが上がっていることを確認。

### 2. Android — FolderSync
1. Play ストアから **FolderSync**（無料）or FolderSync Pro を入れる。
2. **Accounts** → クラウド（Google Drive 等）を追加・認証。
3. **Folderpairs** → 新規作成：
   - **Sync type**: Two-way（双方向）
   - **Remote folder**: クラウド上の vault フォルダ
   - **Local folder**: 端末内の任意フォルダ（例: `/storage/emulated/0/Obsidian/MyVault`）
   - **Sync options**: 「Sync on schedule」（例: 15〜30分毎）＋「Sync when files change」を有効化
   - **Conflict rule**: 「Use most recent file」など、好みで（後述の注意も参照）
4. 一度手動同期して、ローカルに vault が落ちてくるのを確認。

### 3. Android — Obsidian
1. Obsidian Android を入れる。
2. **Open folder as vault** → FolderSync の **Local folder** を選択。
3. プラグイン（Templater 等）は端末ごとに設定（`.obsidian/` は同期対象から外すのが無難。下記）。

---

## 競合（コンフリクト）を避ける / Avoiding conflicts

二方向同期の最大の敵は**同時編集による衝突**。実用上のコツ：

- **編集の前に1回・後に1回**手動同期する癖をつける（特にPCとスマホを行き来する時）。
- 片方で開きっぱなしにしてもう片方で編集しない。
- FolderSync の **instant sync（変更検知同期）** を入れておくと衝突が減る。
- `.obsidian/`（Obsidian設定・キャッシュ）と `.git/` は**同期対象から除外**するのが安全。FolderSync の Folderpair → Filters で `.obsidian` / `.git` / `.trash` を除外する。設定は端末ごとに持つ前提（このリポでも `.obsidian/` は gitignore 済み）。
- 大事な変更の前に git でコミットしておくと、最悪戻せる。

---

## 外出先キャプチャ / Capture on the go

- 思いついたら `01_Inbox/インボックス/` に新規ノートを放り込むだけ。PCに戻って `@orchestrator` が振り分ける。
- Android のホームに Obsidian の「新規ノート」ウィジェット／ショートカットを置くと一瞬で書ける。
- 共有メニューから URL を `01_Inbox` に送る運用も便利（`type: 🔗URL` を付けると knowledge エージェントがナレッジ化）。

---

## 代替案 / Alternatives

| 方法 | メモ |
|---|---|
| **Obsidian Sync**（公式・有料） | 競合解決が最も賢い。設定も同期される。手間を金で買う選択 |
| **Syncthing** | クラウドを介さずP2P。プライバシー重視 |
| **git**（手動 push/pull） | 履歴が残るが、モバイルでの操作は面倒 |
| **FolderSync**（本ガイド） | クラウド前提・無料で始めやすい・端末ローカルに実体が残る |
