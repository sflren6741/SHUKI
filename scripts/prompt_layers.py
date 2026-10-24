"""Shared SHUKI instructions, runtime capabilities, and optional model adjustments.

Keep task content with the caller. Model adjustments are keyed by the resolved
runtime and CLI model, never the UI selection or a role. Add an adjustment only
with repeatable task evidence; an empty map is the default.
"""

SHARED_CORE = (
    "Preserve SHUKI's existing privacy, specialist boundaries, human approval and "
    "stop rules. Existing authorization remains valid for routine steps within "
    "the agreed scope. Carry an authorized task through its completion checks; "
    "keep working after a progress update when no user decision is needed. "
    "Incorporate follow-up instructions into the active task, preserving its "
    "objective unless the user cancels or replaces it. Use concrete completion "
    "criteria and verify results before claiming success. Distinguish verified "
    "results, pending activation and anything you could not confirm. Give brief "
    "reasons and evidence when useful, without exposing internal deliberation. "
    "Honor the task's output contract, including JSON-only output; do not add "
    "reports or commentary to a structured response."
)

RUNTIME_PROMPTS = {
    "claude": (
        "This request runs through Claude Code. Use only tools and native "
        "commands actually available in this session; do not assume another "
        "runtime's capabilities."
    ),
    "codex": (
        "This request runs through Codex CLI. Claude slash commands are not "
        "native Codex commands; use an explicit skill-file instruction when "
        "the caller supplies one. Do not invent Claude-specific agents, hooks "
        "or MCP capabilities that this runtime does not provide."
    ),
}

# Key: (runtime, resolved CLI model). Do not add speculative model stereotypes.
# A version-specific adjustment must use a pinned CLI ID, not a floating alias.
MODEL_PROMPTS: dict[tuple[str, str], str] = {}


def instructions(*, runtime, cli_model="", shared="", runtime_extra="",
                 policy="", runtime_instructions=None):
    """Compose provider-independent rules and an explicit execution adapter.

    Adapters own policy delivery: use the canonical AGENTS.md and its references,
    either through a verified native loader or the policy argument. An unknown
    runtime must supply both policy and its actual capability instructions.
    This composes text; it does not enable a provider or grant tools.
    """
    core = SHARED_CORE + ("\n" + shared if shared else "")
    if runtime_instructions is None:
        adapter = RUNTIME_PROMPTS[runtime]
    else:
        if not isinstance(runtime_instructions, str) or not runtime_instructions.strip():
            raise ValueError("An adapter must describe its actual runtime capabilities")
        if runtime not in RUNTIME_PROMPTS and not policy.strip():
            raise ValueError("A new runtime must explicitly receive the canonical SHUKI policy")
        adapter = runtime_instructions
    if runtime_extra:
        adapter += "\n" + runtime_extra
    parts = (["[SHUKI policy]\n" + policy] if policy else [])
    parts += ["[SHUKI shared core]\n" + core,
              f"[SHUKI runtime: {runtime}]\n" + adapter]
    adjustment = MODEL_PROMPTS.get((runtime, cli_model), "")
    if adjustment:
        parts.append(f"[SHUKI model: {cli_model}]\n" + adjustment)
    return "\n\n".join(parts)


def compose(task, *, runtime, cli_model="", shared="", runtime_extra="",
            policy="", runtime_instructions=None):
    """Keep the user's task first, followed by the reusable instruction layers."""
    return task + "\n\n---\n" + instructions(
        runtime=runtime, cli_model=cli_model, shared=shared,
        runtime_extra=runtime_extra, policy=policy,
        runtime_instructions=runtime_instructions)
