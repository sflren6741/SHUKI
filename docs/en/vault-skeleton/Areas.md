---
title: "Areas"
created: 2026-06-06
date: 2026-06-06
---

# 🗺 Areas — ongoing responsibilities

> The areas of life and work you stay responsible for. Each Area is **a single hub `.md` in this folder**. Don't create subfolders.
> Everything derived from an Area (tasks, logs, knowledge) lives in its own DB and links back through the `area:` property.

```base
filters:
  and:
    - file.inFolder("05_Areas")
    - file.name != "Areas"
    - file.name != "_example-area"
views:
  - type: table
    name: 📋 All areas
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
    name: 📋 Everything
    order:
      - file.name
      - status
      - created
    sort:
      - property: file.name
        direction: ASC
```

---

**To add an Area**: create `05_Areas/<area name>.md` and put `area: <area name>` + `created:` in the frontmatter  
**Quick links**: [[タスク管理|Tasks]] · [[プロジェクト|Projects]] · [[ログ|Logs]] · [[Resources]]
