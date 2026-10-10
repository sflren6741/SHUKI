#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""モデル定義の単一情報源。

モデルの論理キー・各CLIで使う名前・ダッシュボード表示名・定期便の役割を
model_registry.jsonに集約する。呼び出し側は生のモデル名ではなく役割を参照する。
"""
import json
import os
import uuid
from functools import lru_cache
from pathlib import Path

import shuki_paths

# Shipped defaults (tracked and published). Automatic updates from codex_maintenance are
# runtime data, so only the values that differ are kept outside the code tree and merged
# over the defaults when loading (2026-10-07).
REGISTRY_FILE = Path(__file__).resolve().parent / "model_registry.json"
_ENGINES = {"claude", "codex", "local"}


class ModelRegistryError(ValueError):
    """レジストリが存在しない、または構造が不正な場合。"""


def overrides_file():
    return shuki_paths.data_dir("operations") / "model_registry.overrides.json"


def _merge(base, extra):
    merged = dict(base)
    for key, value in extra.items():
        merged[key] = _merge(base[key], value) if isinstance(value, dict) and isinstance(base.get(key), dict) else value
    return merged


def _diff(base, new):
    out = {}
    for key, value in new.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            nested = _diff(base[key], value)
            if nested:
                out[key] = nested
        elif base.get(key) != value or key not in base:
            out[key] = value
    return out


def _read(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ModelRegistryError(f"モデルレジストリを読めません: {path}: {exc}") from exc


def _mtime(path):
    try:
        return path.stat().st_mtime_ns
    except OSError:
        return 0


@lru_cache(maxsize=1)
def _load_registry(stamp):
    data = _read(REGISTRY_FILE)
    overrides = overrides_file()
    if overrides.is_file():
        extra = _read(overrides)
        if not isinstance(extra, dict):
            raise ModelRegistryError(f"モデルレジストリの上書きが不正です: {overrides}")
        data = _merge(data, extra)
    _validate(data)
    return data


def load_registry():
    """Reload verified model updates without restarting active conversations."""
    overrides = overrides_file()
    return _load_registry((str(REGISTRY_FILE), _mtime(REGISTRY_FILE), str(overrides), _mtime(overrides)))


def save_overrides(updated):
    """Persist a verified full registry as the difference from the shipped defaults."""
    _validate(updated)
    path = overrides_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + f".{uuid.uuid4().hex}.tmp")
    temp.write_text(json.dumps(_diff(_read(REGISTRY_FILE), updated), ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8")
    os.replace(temp, path)
    return path


def _validate(data):
    if not isinstance(data, dict):
        raise ModelRegistryError("モデルレジストリのルートはオブジェクトである必要があります")
    models = data.get("models")
    roles = data.get("roles")
    order = data.get("dashboard_order")
    if not isinstance(models, dict) or not models:
        raise ModelRegistryError("models が空または不正です")
    if not isinstance(roles, dict) or not roles:
        raise ModelRegistryError("roles が空または不正です")
    if not isinstance(order, list) or len(order) != len(set(order)):
        raise ModelRegistryError("dashboard_order が不正です")
    required = {"engine", "cli_model", "dashboard_model", "label"}
    for key, spec in models.items():
        if not isinstance(spec, dict) or not required.issubset(spec):
            raise ModelRegistryError(f"models.{key} の必須項目が不足しています")
        if spec["engine"] not in _ENGINES:
            raise ModelRegistryError(f"models.{key}.engine が不正です: {spec['engine']}")
        for field in required - {"engine"}:
            if not isinstance(spec[field], str) or not spec[field].strip():
                raise ModelRegistryError(f"models.{key}.{field} が空です")
    if set(order) != set(models):
        raise ModelRegistryError("dashboard_order と models のキーが一致していません")
    for role, key in roles.items():
        if key not in models:
            raise ModelRegistryError(f"roles.{role} が存在しないモデルを参照しています: {key}")


def _resolve_key(ref):
    token = str(ref or "").strip()
    if not token:
        raise ModelRegistryError("モデル参照が空です")
    data = load_registry()
    models = data["models"]
    key = data["roles"].get(token, token)
    if key in models:
        return key
    for candidate, spec in models.items():
        aliases = {
            spec["cli_model"],
            spec["dashboard_model"],
            f"{spec['engine']}/{spec['cli_model']}",
        }
        if token in aliases:
            return candidate
    raise ModelRegistryError(f"未知のモデル参照です: {ref}")


def resolve_model(ref):
    """論理キー・役割・CLI名・ダッシュボードIDを正規化した仕様を返す。"""
    key = _resolve_key(ref)
    spec = dict(load_registry()["models"][key])
    spec["key"] = key
    return spec


def model_for_role(role):
    return resolve_model(role)


def dashboard_model(ref):
    return resolve_model(ref)["dashboard_model"]


def cli_model(ref):
    return resolve_model(ref)["cli_model"]


def engine(ref):
    return resolve_model(ref)["engine"]


def label(ref):
    return resolve_model(ref)["label"]


def dashboard_models():
    """ダッシュボードの表示順に (dashboard_id, label) を返す。"""
    data = load_registry()
    return [
        (data["models"][key]["dashboard_model"], data["models"][key]["label"])
        for key in data["dashboard_order"]
        if data["models"][key].get("selectable", True)
    ]


def dashboard_effort_models():
    """Return (stable settings key, label, current engine/model target) for effort settings."""
    data = load_registry()
    return [
        (
            data["models"][key]["dashboard_model"],
            data["models"][key]["label"],
            f"{data['models'][key]['engine']}/{data['models'][key]['cli_model']}",
        )
        for key in data["dashboard_order"]
        if data["models"][key].get("selectable", True)
    ]


def dashboard_values():
    return {model_id for model_id, _ in dashboard_models()}


def effort_defaults(default="medium"):
    return {model_id: default for model_id, _ in dashboard_models()}


def risk_windows():
    """ClaudeモデルのダッシュボードID→使用量ウィンドウ。"""
    data = load_registry()
    return {
        spec["dashboard_model"]: spec["usage_window"]
        for spec in data["models"].values()
        if spec.get("usage_window")
    }


def usage_exempt_dashboard_models():
    """Claudeクレジット表示の対象外（Codex/ローカル）のダッシュボードID。"""
    return [
        spec["dashboard_model"]
        for spec in load_registry()["models"].values()
        if spec["engine"] != "claude"
    ]


def _check():
    data = load_registry()
    print(f"OK: {REGISTRY_FILE}")
    print(f"models={len(data['models'])} roles={len(data['roles'])}")
    for role in ("dashboard_default", "scheduler_default", "scheduler_fallback"):
        spec = resolve_model(role)
        print(f"{role}: {spec['key']} ({spec['engine']}:{spec['cli_model']})")


if __name__ == "__main__":
    _check()
