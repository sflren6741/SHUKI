---
created: 2026-06-06
date: 2026-06-06
---

# 🗺 Areas — 継続責任領域

> 継続的に責任を持つライフ・仕事の領域。各 Area は **このフォルダ内の単一ハブ .md** で表す。サブフォルダは作らない。  
> 派生コンテンツ（タスク・ログ・ナレッジ）は各DBに置き、`area:` プロパティで紐づける。

```base
filters:
  and:
    - file.inFolder("05_Areas")
    - file.name != "Areas"
    - file.name != "_example-area"
views:
  - type: table
    name: 📋 全エリア
    filters:
      and:
        - status != "archived"
    order:
      - file.name
      - created
    sort:
      - property: file.name
        direction: ASC
  - type: table
    name: 📋 全件
    order:
      - file.name
      - status
      - created
    sort:
      - property: file.name
        direction: ASC
```

---

**Area を追加するには**: `05_Areas/<area名>.md` を新規作成 → frontmatter に `area: <area名>` + `created:` を記入  
**クイックリンク**: [[タスク管理]] ・ [[プロジェクト]] ・ [[ログ]] ・ [[Resources]]
