---
created: 2026-06-06
date: 2026-06-06
---

# 📚 Resources — ナレッジ＆概念ノード

> 再利用可能なナレッジ（`ナレッジ/`）と vault 横断テーマの概念ノード（`概念/`）。  
> **人物も「ナレッジ」として管理**（`type: 👤人物`）。`person: "[[名前]]"` でログから逆リンクが自動集約。  
> 同テーマが3ファイル以上に登場したら概念ノードを作る。

```base
filters:
  and:
    - file.inFolder("06_Resources/Resources")
    - status != "archived"
views:
  - type: table
    name: 📖 ナレッジ
    filters:
      and:
        - file.inFolder("06_Resources/Resources/ナレッジ")
    groupBy:
      property: type
      direction: ASC
    order:
      - file.name
      - type
      - area
      - created
    sort:
      - property: created
        direction: DESC
  - type: table
    name: 👤 人物
    filters:
      and:
        - type == "👤人物"
    order:
      - file.name
      - area
    sort:
      - property: file.name
        direction: ASC
  - type: table
    name: 💡 概念ノード
    filters:
      and:
        - file.inFolder("06_Resources/Resources/概念")
    order:
      - file.name
      - area
      - created
    sort:
      - property: created
        direction: DESC
  - type: table
    name: 📋 全件
    groupBy:
      property: type
      direction: ASC
    order:
      - file.name
      - type
      - area
      - created
    sort:
      - property: created
        direction: DESC
```

---

**クイックリンク**: [[タスク管理]] ・ [[ログ]] ・ [[Areas]]  
URL 取り込み: `01_Inbox/インボックス/` に `type: "🔗URL"` + `url:` で投入 → `@knowledge` が処理
