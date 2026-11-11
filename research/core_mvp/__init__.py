"""Offline end-to-end research MVP for the two thesis pipelines.

The package intentionally uses file-backed artifacts and dependency injection.
It proves the research flow before MongoDB, API and UI integration; it is not a
production grading service.
"""

from .runner import run_core_mvp

__all__ = ["run_core_mvp"]
