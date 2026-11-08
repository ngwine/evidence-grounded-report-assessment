"""Versioned, provenance checked Evidence Graph research adapter."""

from .contract import (
    GraphValidationError,
    make_chunk_reference,
    make_edge,
    make_node,
    make_span,
    validate_snapshot,
)
from .store import LocalGraphStore

__all__ = [
    "GraphValidationError",
    "LocalGraphStore",
    "make_chunk_reference",
    "make_edge",
    "make_node",
    "make_span",
    "validate_snapshot",
]
