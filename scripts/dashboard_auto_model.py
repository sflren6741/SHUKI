#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Deterministic model selection for interactive chat and voice turns.

Auto stays within the currently selected provider so an existing Claude or
Codex conversation keeps its session engine when the model tier changes.
"""
import re

import model_registry


HIGH_LOAD = re.compile(
    r"実装|開発|コード|プログラム|デバッグ|バグ修正|原因調査|設計|アーキテクチャ|添付ファイル|"
    r"比較|調査|分析|戦略|計画|レビュー|検証|テスト|移行|リファクタ|仕様|"
    r"\b(?:implement|debug|refactor|architect(?:ure)?|design|analy[sz]e|compare|"
    r"research|investigate|plan|review|test|migrate|diagnos(?:e|is)|trade[ -]?offs?|"
    r"write code|build (?:an? )?(?:app|service|script|tool)|code review|attachment)\b",
    re.IGNORECASE,
)
LOW_LOAD = re.compile(
    r"簡単に|一言で|短く|翻訳|訳して|要約|誤字|文法チェック|スペル|計算して|"
    r"\b(?:translate|translation|summari[sz]e|spellcheck|grammar|convert|calculate|"
    r"define|what is|quick answer|briefly)\b",
    re.IGNORECASE,
)
CODE_OR_TRACE = re.compile(r"```|Traceback \(most recent call last\)|\b(?:stack trace|exception)\b", re.I)
LIST_ITEM = re.compile(r"^\s*(?:[-*+] |\d+[.)] )", re.M)

MODEL_ROLES = {
    "claude": {
        "low": "simple_classify",
        "medium": "dashboard_default",
        "high": "strategic",
    },
    "codex": {
        "low": "codex_luna",
        "medium": "codex_sol",
        "high": "codex_astra",
    },
}


def classify_load(text):
    """Classify one incoming turn using explicit, local-only rules."""
    value = str(text or "").strip()
    if not value:
        return "medium"
    if (len(value) >= 1200 or CODE_OR_TRACE.search(value)
            or len(LIST_ITEM.findall(value)) >= 4 or HIGH_LOAD.search(value)):
        return "high"
    if LOW_LOAD.search(value) or len(value) <= 80:
        return "low"
    return "medium"


def select_model(text, preferred_model, force_high=False):
    """Select a tier within preferred_model's engine; return its dashboard ID."""
    load = "high" if force_high else classify_load(text)
    engine = model_registry.engine(preferred_model)
    roles = MODEL_ROLES.get(engine)
    if not roles:
        # Muse is the only selectable local model, so changing tiers would not
        # change the backend or improve latency.
        return preferred_model
    return model_registry.dashboard_model(roles[load])
