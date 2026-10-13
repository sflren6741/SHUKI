# モバイルアクセス — スマホからダッシュボードに繋ぐ / Mobile access

> **TL;DR (EN)** — The dashboard only listens on `127.0.0.1` on the PC for security reasons (opening it to the whole LAN exposed an admin-level exec route in testing). Reach it from your phone over **Tailscale**: install Tailscale on both devices, enable **Tailscale Serve** on the PC to put an HTTPS front on port 8765, then open that HTTPS URL on your phone and optionally "Add to Home Screen" (PWA) for an app-like icon and push notifications.

vault自体はローカルのMarkdownファイルで、同期やビューアアプリは不要です。スマホから使うのは**ダッシュボード（ブラウザ画面）**で、PC側で動いている `dashboard_server.py` に繋ぎに行く構成です。

---

## なぜ Tailscale か

ダッシュボードは PC の `127.0.0.1:8765` だけで待ち受けています（`0.0.0.0` にすると LAN 上の誰からでも `/exec`（権限チェックなしの Claude 起動）に届いてしまうことが実測で確認済み）。LANを跨いだ安全な接続には Tailscale（または同種の個人用VPNメッシュ）を使い、PC側のファイアウォールで Tailscale のネットワーク帯（`100.64.0.0/10`）以外からの8765番ポートへの接続を遮断します。

---

## 手順

### 1. PCとスマホの両方に Tailscale を入れる

[tailscale.com](https://tailscale.com/) からインストールし、同じアカウントでログインして同じ tailnet に参加させます。

### 2. PCでファイアウォールを絞る（1回だけ・管理者権限）

リポ同梱の `scripts/setup_tailscale_firewall.ps1` を管理者権限の PowerShell で実行します。8765番ポートへの着信を Tailscale のアドレス帯だけに許可するルールが作られます。

### 3. PCで Tailscale Serve を有効化

```
tailscale serve https / http://127.0.0.1:8765
```

これで PC の Tailscale ホスト名に対する HTTPS アクセスが、ローカルの `127.0.0.1:8765`（ダッシュボード）に転送されます。ホスト名は `tailscale status` で確認できます。

### 4. ダッシュボードを起動しておく

PC側でいつも通り：

```powershell
$env:SHUKI_VAULT = (Get-Location).Path
python scripts/dashboard_server.py
```

### 5. スマホのブラウザで開く

`https://<PCのTailscaleホスト名>/` を開きます。タスクボード・カレンダー・ニュース・AIチャット・決裁カードが全部そのまま使えます。

💡 **ホーム画面に追加（PWA）**：ブラウザの共有メニューから「ホーム画面に追加」を選ぶと、アプリのようなアイコンで開けます。対応していれば通知（Web Push）も届きます。

---

## 外出先でのキャプチャ

- 思いついたことはダッシュボードの AI チャットにそのまま打つだけ。`@orchestrator` が行き先を振り分けます。
- 声で残したい時は `/voice-capture` スキルで話した内容をそのままインボックスへ保存できます。
- 共有メニューから URL をチャットに貼ると、`knowledge` エージェントがナレッジ化します。

---

## 代替案

| 方法 | メモ |
|---|---|
| **Tailscale Serve**（本ガイド） | 無料枠で始めやすい。PCの電源が入っている時だけアクセス可 |
| **自前のリバースプロキシ＋証明書** | 自分でTLS終端を管理できるなら可。設定の手間は増える |
| **クラウドVPSに常時起動のダッシュボードを置く** | PCの電源に依存しなくなるが、vaultのデータをVPS側に置く判断が要る（本リポはその前提では作っていない） |
