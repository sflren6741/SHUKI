---
name: weekly-review
description: オーナーの1週間を、デジタル活動データ（Chrome検索・Google Maps・Gemini）とvaultのログ・タスクから振り返り、対話しながら週次レビューを作成する。センシティブなログ（関係・健康）を含む場合は機械的に断定せずオーナーと確認しながら書く。「週次レビュー」「今週の振り返り」で起動。
---

# 📅 週次レビュー（対話型）

オーナーの1週間を振り返り、`07_Logs/ログ/週次レビュー/<YYYY-MM-DD>.md` にレポートを作る。
**前面セッションで対話しながら**作るのが従来の無人生成との違い。直近ログに関係・健康などセンシティブな内容が含まれることがあるため、断定せずオーナーに確認しながら進める。

## 🧭 必読コンテキスト

- `00_Intranet/AI運用ルール集（イントラ）/🪪 Identity.md`
- `00_Intranet/AI運用ルール集（イントラ）/哲学・価値観.md`
- `00_Intranet/AI運用ルール集（イントラ）/デザイン言語.md`
- `.claude/agents/orchestrator.md` §週次レビュー（§2〜§9 の構成・デジタル活動分析方針を踏襲）

## 🔄 フロー

### Step 1: データ前処理
**データソースは2系統に分かれる**：

| データ | 取得方法 | 自動/手動 |
|---|---|---|
| Chrome 検索・閲覧履歴 | `sync_weekly_history.py` | **自動**（毎週日曜18:00 `Claude-WeeklyReview` が実行済み） |
| Google Maps 訪問・Gemini 利用 | Google Takeout の**手動エクスポートが必要** | **手動**（オーナーがエクスポートした時のみ） |
| Claude 使用状況 | `analyze_claude_usage.py` | このスキルで実行可 |

手順：
1. Chrome は前処理済みの前提（`weekly_summary.md` に反映される）
2. **Maps/Gemini を含めたい場合のみ**、オーナーが Takeout をエクスポート済みであることを確認し、以下を実行：
```
python <WORKSPACE>\vault-scripts\sync_google_takeout.py    # Gemini/Maps/News（手動エクスポート前提）
python <WORKSPACE>\vault-scripts\resolve_places.py         # 場所解決
python <WORKSPACE>\vault-scripts\generate_summaries.py     # 活動サマリー
python <WORKSPACE>\vault-scripts\analyze_claude_usage.py   # Claude使用状況
```
3. Takeout が無ければ Maps/Gemini セクションは「データなし（手動エクスポート未実施）」と明記してスキップ

> 将来: Takeout エクスポートを OpenClaw 等で自動化したい（時間ができたら。現状は手動）。

### Step 2: 入力を読む
| ソース | パス |
|---|---|
| デジタル活動サマリー | `<WORKSPACE>\weekly_summary.md`（Chromeは自動反映。Maps/GeminiはStep1の手動分が入った時のみ） |
| Claude使用状況 | `07_Logs/AI対話履歴/<期間終了日>.md` |
| タスクDB | `04_Tasks/タスク管理/タスク/*.md`（今週完了・作業中・保留） |
| ログ | `07_Logs/ログ/` 直近7日 |

> `weekly_summary.md` が無い／古い場合は該当セクションを「データなし」でスキップ。ChromeはあるがMaps/Geminiが無い、という部分欠損も明記する。

### Step 3: 対話で組み立てる（このスキルの核心）
- ログにセンシティブな内容（関係の危機・健康・センシティブな話題等）があれば、**機械的に要約せずオーナーに「これ、どう扱う？」と確認**してから書く
- 数字を並べるのではなく「データの裏の行動・関心・変化」を読む（orchestrator §デジタル活動の分析方針に従う）
- 不明・両義的な点はオーナーに質問する（1ターン3問以内）
- タスク棚卸が必要そうなら `/タスク棚卸` を案内（このスキルでは深追いしない）

### Step 4: レポート作成
`07_Logs/ログ/週次レビュー/<YYYY-MM-DD>.md` に Write。構成は orchestrator §週次レビューの §2〜§9 に準拠（数字サマリ／今週最重要3つ／各Area／お金／来週判断ポイント／デジタル活動の散文分析／Claude使用状況）。frontmatter に `date`（期間開始日）/ `created` を付ける。

## 🚫 やってはいけないこと
- ❌ センシティブなログ（個人間コミュニケーション等）をオーナーの確認なく断定的に解釈・要約する
- ❌ センシティブな相手への文章を代筆する（代筆禁止）
- ❌ 数字の羅列で終える（行動の解釈を伴わせる。ただし推測は「かもしれない」）
- ❌ お金・健康の「アクション」を実行する（記述・提案のみ）

## 🔗 wikilink
- 重要な出来事は該当ログ・タスク・概念ノードへ wikilink
- 関係の話題が出たら該当する人物ノートへ

## 🔄 セルフQAの3行
```
- 事実チェック: <数値・日付・出来事はソースに実在するか。推測は仮説と明示したか>
- トーン: <散文分析・断定回避・オーナーの文体に沿うか>
- アンチスロップ: <数字羅列・励まし・心理ラベルがないか>
```
