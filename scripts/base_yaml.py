#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
base_yaml.py — Obsidian `base` codeblock（YAML本体）の抽出・構造化（ビューエンジン Step1・2026-07-28）

`base` codeblock はそのまま妥当なYAMLなので、独自パーサは書かずvault-scripts内で既に依存済みの
PyYAML（vault_lint.py 等が使用）で読む。ここが担当するのは「構造化（filters/viewsの取り出し）」まで。
述語文字列（`month.contains("2025-06")` 等）の中身はYAMLではなくObsidian独自の式構文なので、
その評価は base_expr.py が担当する（ここでは文字列のまま保持する）。

サポート範囲: `filters:`（and/or再帰）・`views:`（type/name/order/sort/groupBy・
cardsの cover/image/cardSize/imageAspectRatio）・`formulas:`（式文字列を名前付きで保持。
評価は base_expr.eval_value_expr が担当。vault内唯一の使用箇所は 04_Tasks/タスク管理.md・
タスク管理.mdステップで対応・2026-07-28）。
"""
import re
from dataclasses import dataclass, field

import yaml

_BASE_FENCE_RE = re.compile(r"```base\r?\n(.*?)```", re.DOTALL)
_HEADING_RE = re.compile(r"^#{1,6}\s+(.*)$", re.MULTILINE)


class BaseParseError(Exception):
    pass


@dataclass
class BaseSpec:
    filters: object          # None | str | {"and":[...]} | {"or":[...]}（要素は再帰的に同じ形）
    views: list = field(default_factory=list)
    formulas: dict = field(default_factory=dict)  # {formula名: 式文字列}（未評価のまま保持）
    raw: dict = field(default_factory=dict)   # 未対応キーも含む生データ


def find_base_blocks(md_text):
    """本文中の ```base ... ``` フェンスをすべて抽出し、中身（YAMLテキスト）のリストで返す。"""
    return [m.group(1) for m in _BASE_FENCE_RE.finditer(md_text)]


def find_base_blocks_with_headings(md_text):
    """`find_base_blocks` に加え、各ブロック直前の直近見出し（`## 📚 ナレッジ...` 等）をラベルとして
    添える。1ノートに複数 base ブロックが並ぶケース（例: 06_Resources/Resources.md のナレッジDB＋
    OCR保管庫）でブロック切替タブの見出しに使う（ログ/Resourcesステップ・2026-07-28）。"""
    headings = [(m.start(), m.group(1).strip()) for m in _HEADING_RE.finditer(md_text)]
    result = []
    hi = 0
    heading = None
    for m in _BASE_FENCE_RE.finditer(md_text):
        pos = m.start()
        while hi < len(headings) and headings[hi][0] < pos:
            heading = headings[hi][1]
            hi += 1
        result.append({"yaml": m.group(1), "heading": heading})
    return result


def parse_base(yaml_text):
    try:
        data = yaml.safe_load(yaml_text)
    except yaml.YAMLError as e:
        raise BaseParseError(f"invalid base YAML: {e}") from e
    if data is None:
        data = {}
    if not isinstance(data, dict):
        raise BaseParseError(f"base block must be a YAML mapping, got {type(data).__name__}")
    views = data.get("views") or []
    if not isinstance(views, list):
        raise BaseParseError("views: must be a list")
    formulas = data.get("formulas") or {}
    if not isinstance(formulas, dict):
        raise BaseParseError("formulas: must be a mapping")
    return BaseSpec(filters=data.get("filters"), views=views, formulas=formulas, raw=data)
