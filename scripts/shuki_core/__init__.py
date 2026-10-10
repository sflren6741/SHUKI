"""SHUKI core services shared by the dashboard and its feature plugins."""

from pathlib import Path

# Compatibility boundaries for features not yet moved into plugins/<id>.
# Presence chooses distribution; existing settings["plugins"] chooses activation.
# Checking presence never imports optional code. A present feature with a broken
# dependency still raises its real import error when the server loads it.
CORE_FEATURES = frozenset({"chat", "tasks", "calendar", "news", "decisions"})
FEATURE_MARKERS = {
    "achievements": "plugins/achievements/manifest.json",
    "trading": "plugins/trading/manifest.json",
    "operations": "plugins/operations/manifest.json",
    "visualize": "plugins/visualize/manifest.json",
    "journal": "plugins/journal/manifest.json",
    "game": "plugins/game/manifest.json",
    "english": "plugins/english/manifest.json",
    "habit": "plugins/habit/manifest.json",
    "finance": "plugins/finance/manifest.json",
    "crossword": "plugins/crossword/manifest.json",
    "styleguide": "plugins/styleguide/manifest.json",
    "meeting": "plugins/meeting/manifest.json",
}
PLUGIN_SKILLS = {"crossword-gen": "crossword", "visualize": "visualize"}
FEATURE_ROUTES = {
    **{feature: feature for feature in FEATURE_MARKERS},
    "control": "operations", "review": "operations", "notifications": "operations",
    "rec-dismiss": "operations", "decisions": "decisions", "gaps": "decisions",
    "bgm": "game",
}
_SCRIPTS = Path(__file__).resolve().parent.parent
_activation = {}


def configure_features(activation):
    """Read existing feature switches once, before loading the server's modules."""
    global _activation
    _activation = activation if isinstance(activation, dict) else {}


def feature_enabled(feature):
    if feature in CORE_FEATURES:
        return True
    marker = FEATURE_MARKERS.get(feature)
    state = _activation.get(feature, {})
    return bool(marker and (_SCRIPTS / marker).is_file()
                and not (isinstance(state, dict) and state.get("enabled") is False))


def route_enabled(path):
    owner = FEATURE_ROUTES.get(path.strip("/").split("/", 1)[0])
    integration = {"/journal/growth": "game", "/game/reflection": "journal"}.get(path.rstrip("/"))
    return ((owner is None or feature_enabled(owner))
            and (integration is None or feature_enabled(integration)))
