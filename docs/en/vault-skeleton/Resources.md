---
title: "Resources"
created: 2026-06-06
date: 2026-06-06
---

# 📚 Resources — knowledge & concept nodes

> Reusable knowledge (`ナレッジ/`) and cross-cutting concept nodes (`概念/`).
> **People are kept as knowledge notes too** (`type: 👤人物`). Write `person: "[[Name]]"` in a log and the backlinks collect themselves.
> Once the same theme shows up in three or more files, make it a concept node.

```base
filters:
  and:
    - file.inFolder("06_Resources/Resources")
    - status != "archived"
views:
  - type: table
    name: 📖 Knowledge
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
    name: 👤 People
    filters:
      or:
        - type == "👤人物"
        - type == "👤Person"
    order:
      - file.name
      - area
    sort:
      - property: file.name
        direction: ASC
  - type: table
    name: 💡 Concept nodes
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
    name: 📋 Everything
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

**Quick links**: [[タスク管理|Tasks]] · [[ログ|Logs]] · [[Areas]]  
To capture a URL: drop a note in `01_Inbox/インボックス/` with `type: "🔗URL"` + `url:` → `@knowledge` handles it
