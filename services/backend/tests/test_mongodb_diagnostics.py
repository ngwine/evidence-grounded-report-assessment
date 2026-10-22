"""Failure summaries expose only predefined categories/numeric event IDs."""

import json

from scripts.diagnose_mongodb_local import summarize


def test_diagnostics_do_not_echo_secrets_or_raw_logs():
    private = "do-not-publish-this-password"
    value = summarize(
        f"install: cannot create file: Permission denied; credential={private}\n"
        + json.dumps({"s": "F", "id": 12345, "msg": private, "attr": {"password": private}})
    )
    assert value == {"recognized_categories": ["FILE_PERMISSION_DENIED"],
                     "mongo_error_event_ids": [12345]}
    assert private not in json.dumps(value)


def test_unknown_logs_are_not_printed_as_fallback():
    assert summarize("unknown failure with private report contents") == {
        "recognized_categories": [], "mongo_error_event_ids": [],
    }
