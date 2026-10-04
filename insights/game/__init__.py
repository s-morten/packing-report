"""Lazy re-exports.

The submodules here import each other and the metric modules import ``game.game_segments``, so
eagerly re-exporting at module scope closes the cycle
``metrics.low_level.xt -> game.game_segments -> game.game_facts -> metrics.low_level.xt`` and makes
``import metrics.low_level.xt`` fail unless ``game.game_facts`` happens to be imported first.
Resolving each name on first access (PEP 562) keeps ``from game import GameFacts`` working without
the ordering constraint.
"""

__all__ = [
    "GameFacts",
    "GameMetrics",
    "GamePrepare",
]

_EXPORTS = {
    "GameFacts": "game.game_facts",
    "GameMetrics": "game.game_metrics",
    "GamePrepare": "game.game_prepare",
}


def __getattr__(name):
    if name not in _EXPORTS:
        raise AttributeError(f"module 'game' has no attribute {name!r}")
    import importlib

    return getattr(importlib.import_module(_EXPORTS[name]), name)


def __dir__():
    return sorted(set(globals()) | set(_EXPORTS))
