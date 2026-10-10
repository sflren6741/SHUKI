#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""論理モデルを実行エンジンへ橋渡しする共通アダプタ。

モデル名は model_registry.py/json に集約し、呼び出し側は役割名だけを渡す。
Claude は既存の one-shot 呼び出し、Codex は無人ジョブ用の JSONL 呼び出しに
そろえる。外部送信やカレンダー操作を許可するための機能は持たせない。
"""

import json
import os
import shutil
import subprocess
from pathlib import Path

import dashboard_settings
import model_registry
import prompt_layers
import shuki_paths


def _claude_executable():
    return shutil.which("claude") or "claude"


def _codex_executable():
    configured = os.environ.get("CODEX_EXE")
    if configured:
        return configured
    return "codex.cmd" if os.name == "nt" else "codex"


def _codex_error_message(output):
    """JSONLの失敗イベントから短いエラーを取り出す。通常の本文は無視する。"""
    messages = []
    for line in (output or "").splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        event_type = event.get("type")
        item = event.get("item") if isinstance(event.get("item"), dict) else {}
        item_type = item.get("type")
        if event_type in {"error", "turn.failed", "turn.cancelled"} or item_type == "error":
            for obj in (event, item):
                for key in ("message", "error", "detail"):
                    value = obj.get(key) if isinstance(obj, dict) else None
                    if isinstance(value, str) and value.strip():
                        messages.append(value.strip())
                    elif isinstance(value, dict):
                        nested = value.get("message") or value.get("detail")
                        if isinstance(nested, str) and nested.strip():
                            messages.append(nested.strip())
    return messages[-1][:500] if messages else "Codex実行失敗"


def _run_claude(prompt, spec, *, cwd, timeout):
    env = dict(os.environ, CLAUDE_UNMANNED="1", PYTHONUTF8="1")
    cmd = [
        _claude_executable(), "-p", prompt, "--output-format", "json",
        "--model", spec["cli_model"], "--dangerously-skip-permissions",
        "--append-system-prompt", prompt_layers.instructions(
            runtime="claude", cli_model=spec["cli_model"]),
    ]
    try:
        proc = subprocess.run(
            cmd, cwd=str(cwd), capture_output=True, timeout=timeout,
            stdin=subprocess.DEVNULL, encoding="utf-8", errors="replace", env=env,
        )
    except subprocess.TimeoutExpired:
        return False, f"タイムアウト（{timeout}秒）"
    if proc.returncode != 0:
        return False, (proc.stderr or proc.stdout or "").strip()[:500] or f"exit code {proc.returncode}"
    try:
        data = json.loads(proc.stdout.strip())
    except json.JSONDecodeError:
        return False, "Claude出力のJSONパース失敗: " + proc.stdout.strip()[:300]
    if data.get("is_error"):
        return False, (data.get("result") or "（エラー内容不明）")[:500]
    return True, (data.get("result") or "（結果なし）")[:300]


def _run_codex(prompt, spec, *, cwd, vault, scripts_dir, allow_scripts, timeout):
    cwd = Path(cwd).resolve()
    vault = Path(vault).resolve()
    scripts_dir = Path(scripts_dir).resolve()
    # ジョブの出力先（News の作業ファイル・board_quests.json 等）は 2026-10-07 から vault 外の
    # データフォルダにある。範囲指示が vault だけだと Codex は書かずに「成功」で終わる
    # （2026-10-08 実測: News 選定0件・BoardQuests 未生成）。
    data_dir = Path(shuki_paths.data_dir()).resolve()
    effort_key = spec["dashboard_model"]
    settings = dashboard_settings.load_settings()
    effort = settings.get("model_effort", {}).get(
        effort_key, dashboard_settings.model_effort_defaults().get(effort_key, "medium"))
    cmd = [
        _codex_executable(), "exec", "--json", "--ephemeral", "--ignore-user-config",
        "--dangerously-bypass-approvals-and-sandbox", "--model", spec["cli_model"],
        "--cd", str(cwd), "--add-dir", str(vault), "--add-dir", str(data_dir), "--skip-git-repo-check",
        "-c", f"model_reasoning_effort={effort!r}", "-",
    ]
    if allow_scripts and scripts_dir != vault:
        cmd[cmd.index("--skip-git-repo-check"):cmd.index("--skip-git-repo-check")] = [
            "--add-dir", str(scripts_dir),
        ]
    scope = (
        f"The SHUKI vault is {vault}. Treat relative paths as relative to that vault. "
        f"Only read or modify files inside that vault and the SHUKI data directory {data_dir}, "
        f"where job output files live."
    )
    if allow_scripts:
        scope += f" This job explicitly permits the local scripts directory {scripts_dir}."
    scope += " Do not use network, MCP, email, calendar, or other external services.\n\n"
    env = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
    try:
        proc = subprocess.run(
            cmd, cwd=str(cwd), env=env, capture_output=True, text=True,
            encoding="utf-8", errors="replace", input=prompt_layers.compose(
                prompt, runtime="codex", cli_model=spec["cli_model"],
                runtime_extra=scope), timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        out = (exc.stdout or "") if isinstance(exc.stdout, str) else ""
        return False, f"タイムアウト（{timeout}秒）\n{out[-300:]}"
    out = (proc.stdout or "") + (proc.stderr or "")
    if proc.returncode != 0:
        return False, _codex_error_message(out) + f" (exit {proc.returncode})"
    if any(_json_event_type(line) in {"turn.failed", "turn.cancelled"}
           for line in out.splitlines() if _is_json(line)):
        return False, _codex_error_message(out)
    return True, "Codex実行完了"


def _is_json(line):
    try:
        json.loads(line)
        return True
    except json.JSONDecodeError:
        return False


def _json_event_type(line):
    try:
        value = json.loads(line)
    except json.JSONDecodeError:
        return None
    return value.get("type") if isinstance(value, dict) else None


def run_prompt(prompt, model_ref, *, cwd, vault, scripts_dir, allow_scripts=False, timeout=900):
    """役割名/モデルIDを解決して one-shot 実行する。戻り値は (成功, 要約)。"""
    spec = model_registry.resolve_model(model_ref)
    if spec["engine"] == "claude":
        return _run_claude(prompt, spec, cwd=cwd, timeout=timeout)
    if spec["engine"] == "codex":
        return _run_codex(
            prompt, spec, cwd=cwd, vault=vault, scripts_dir=scripts_dir,
            allow_scripts=allow_scripts, timeout=timeout,
        )
    raise ValueError(f"one-shot実行に対応していないエンジンです: {spec['engine']}")
