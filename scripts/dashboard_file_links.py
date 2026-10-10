"""Shared builders for links into the dashboard's vault-file route."""

from urllib.parse import quote


FILES_ROUTE = "/files"


def normalise_vault_relative_path(value):
    """Return a canonical vault-relative path or raise for malformed input.

    Links are built from paths that have already been resolved inside the vault,
    but keeping this boundary strict prevents accidental absolute/traversal
    URLs when a caller receives a path from a query or model output.
    """
    if not isinstance(value, str):
        raise ValueError("vault path must be a string")
    relative = value.replace("\\", "/")
    if not relative or "\x00" in relative:
        raise ValueError("vault path is empty or contains a NUL byte")
    if relative.startswith("/") or (len(relative) >= 2 and relative[1] == ":"):
        raise ValueError("vault path must be relative")
    parts = relative.split("/")
    if any(not part or part in {".", ".."} for part in parts):
        raise ValueError("vault path contains an invalid segment")
    return relative


def build_file_href(relative):
    """Build the canonical, fully encoded link to a vault file."""
    relative = normalise_vault_relative_path(relative)
    return f"{FILES_ROUTE}?p={quote(relative, safe='')}"
