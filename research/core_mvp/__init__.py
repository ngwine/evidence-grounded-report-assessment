"""Offline end-to-end research MVP for the two thesis pipelines.

The package intentionally uses file-backed artifacts and dependency injection.
It proves the research flow before MongoDB, API and UI integration; it is not a
production grading service.
"""

__all__ = ["run_core_mvp"]


def __getattr__(name: str):
    # A parser subprocess must not import retrieval/NumPy/model adapters merely
    # to load this package before applying its own resource limits.
    if name == "run_core_mvp":
        from .runner import run_core_mvp
        return run_core_mvp
    raise AttributeError(name)
