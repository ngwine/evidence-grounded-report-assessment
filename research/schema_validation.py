"""Validate generated output against the repository's Draft 2020-12 schemas.

Only the three checked-in schemas are registered. This is structural validation;
the provenance, relation/outcome, and scoring invariants in
``research.core_mvp.contracts`` remain separate checks.
"""

from __future__ import annotations

from functools import lru_cache
import json
from pathlib import Path
from typing import Any, Mapping

from jsonschema import Draft202012Validator
from referencing import Registry, Resource
from referencing.exceptions import NoSuchResource


_SCHEMA_DIR = Path(__file__).resolve().parent / "schemas"
_SCHEMA_FILES = {
    "similarity": "similarity-report-v1.schema.json",
    "assessment": "assessment-report-v1.schema.json",
    "evidence": "evidence-v1.schema.json",
}


class OutputSchemaError(ValueError):
    """A generated result violates its declared JSON Schema."""


def _deny_external_reference(uri: str) -> Resource:
    # The schema set is fixed in the repository. Never fetch a reference over
    # HTTP while validating a document that may contain private report text.
    raise NoSuchResource(ref=uri)


@lru_cache(maxsize=1)
def _validators() -> dict[str, Draft202012Validator]:
    schemas: dict[str, Mapping[str, Any]] = {}
    resources: list[tuple[str, Resource]] = []
    for kind, filename in _SCHEMA_FILES.items():
        schema = json.loads((_SCHEMA_DIR / filename).read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        schema_id = schema.get("$id")
        if not isinstance(schema_id, str) or not schema_id:
            raise ValueError(f"Schema {filename} requires a non-empty $id")
        schemas[kind] = schema
        resources.append((schema_id, Resource.from_contents(schema)))
    registry = Registry(retrieve=_deny_external_reference).with_resources(resources)
    return {
        kind: Draft202012Validator(schema, registry=registry)
        for kind, schema in schemas.items()
    }


def validate_json_schema(value: Any, *, kind: str) -> None:
    """Raise a content-safe error for the first structural contract violation.

    Error details contain only the JSON path and violated keyword, never the
    offending report/evidence value. Use the runtime contracts as well for
    cross-field and provenance rules JSON Schema cannot express here.
    """

    try:
        validator = _validators()[kind]
    except KeyError as exc:
        raise ValueError(f"Unknown output schema kind: {kind!r}") from exc
    error = next(validator.iter_errors(value), None)
    if error is None:
        return
    location = "$" + "".join(
        f"[{segment}]" if isinstance(segment, int) else f".{segment}"
        for segment in error.absolute_path
    )
    raise OutputSchemaError(
        f"{kind} output violates JSON Schema at {location} "
        f"({error.validator} constraint)"
    ) from None
