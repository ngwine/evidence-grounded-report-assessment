"""Tests for deterministic conversion of extracted PAN XML/TXT corpora."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from research.offline_retrieval.common import sha256_file
from research.offline_retrieval.runner import run_experiment
from research.pan_pilot.cli import main
from research.pan_pilot.converter import OUTPUT_NAMES, convert_pan_pilot


def _read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def _write_pan_fixture(
    root: Path,
    *,
    source_reference: str = "source-document1.txt",
    add_distractor: bool = False,
):
    source_dir = root / "src"
    suspicious_dir = root / "susp"
    labels_dir = root / "labels" / "03-artificial-high"
    source_dir.mkdir(parents=True)
    suspicious_dir.mkdir(parents=True)
    labels_dir.mkdir(parents=True)

    source_text = (
        "Opening source paragraph.\r\n\r\n"
        "Copied evidence is here and exact.\r\n\r\n"
        "A final paragraph that is deliberately long enough to require deterministic splitting."
    )
    suspicious_text = "Intro.\nParaphrased evidence fragment.\nOutro."
    (source_dir / "source-document1.txt").write_bytes(source_text.encode("utf-8"))
    if add_distractor:
        (source_dir / "source-document2.txt").write_text(
            "An unreferenced source document must remain in the candidate corpus.",
            encoding="utf-8",
        )
    (suspicious_dir / "suspicious-document1.txt").write_bytes(
        suspicious_text.encode("utf-8")
    )

    this_start = suspicious_text.index("Paraphrased")
    this_text = "Paraphrased evidence fragment."
    source_start = source_text.index("Copied evidence")
    source_span = "Copied evidence is here and exact."
    xml = (
        '<document reference="suspicious-document1.txt">'
        '<feature name="about" lang="en" />'
        f'<feature name="plagiarism" this_offset="{this_start}" '
        f'this_length="{len(this_text)}" source_reference="{source_reference}" '
        f'source_offset="{source_start}" source_length="{len(source_span)}" />'
        "</document>"
    )
    (labels_dir / "suspicious-document1-source-document1.xml").write_text(
        xml, encoding="utf-8"
    )
    (labels_dir / "no-plagiarism.xml").write_text(
        '<document reference="suspicious-document1.txt"></document>',
        encoding="utf-8",
    )
    return source_text, suspicious_text, source_start, source_span, this_text


class _EvidenceFixtureEncoder:
    metadata = {
        "backend": "injected_test",
        "model": "pan-evidence-fixture",
        "revision": "synthetic-v1",
        "scientific_result": False,
    }

    def set_mode(self, mode):
        self.mode = mode

    def encode(self, texts):
        return [
            [1.0, 0.0] if "evidence" in text.casefold() else [0.0, 1.0]
            for text in texts
        ]


def test_pan_pc_11_conversion_is_deterministic_and_preserves_raw_offsets(tmp_path):
    corpus = tmp_path / "corpus"
    source_text, _, source_start, source_span, query_text = _write_pan_fixture(
        corpus, add_distractor=True
    )
    first_dir = tmp_path / "first"
    second_dir = tmp_path / "second"

    first = convert_pan_pilot(
        dataset="pan-pc-11",
        input_root=corpus,
        output_dir=first_dir,
        dataset_version="official-extract-v1",
        split_name="training",
        max_chunk_chars=48,
    )
    second = convert_pan_pilot(
        dataset="PAN-PC-11",
        input_root=corpus,
        output_dir=second_dir,
        dataset_version="official-extract-v1",
        split_name="training",
        max_chunk_chars=48,
    )

    assert first.document_count == second.document_count == 2
    for filename in OUTPUT_NAMES.values():
        assert (first_dir / filename).read_bytes() == (second_dir / filename).read_bytes()

    documents = _read_jsonl(first_dir / "documents.jsonl")
    document = next(
        value for value in documents if value["source_reference"].endswith("source-document1.txt")
    )
    [query] = _read_jsonl(first_dir / "queries.jsonl")
    [qrel] = _read_jsonl(first_dir / "qrels.jsonl")
    chunks = _read_jsonl(first_dir / "chunks.jsonl")
    assert document["text"] == source_text
    assert document["version"].startswith("sha256:")
    assert query["text"] == query_text
    assert qrel["target_scope"] == "document"
    assert (qrel["raw_start"], qrel["raw_end"]) == (
        source_start,
        source_start + len(source_span),
    )
    assert qrel["annotated_source_span"]["raw_start"] == source_start
    assert len({chunk["chunk_id"] for chunk in chunks}) == len(chunks)
    for chunk in chunks:
        [span] = chunk["source_spans"]
        chunk_document = next(
            value for value in documents if value["document_id"] == chunk["document_id"]
        )
        assert chunk["document_version"] == chunk_document["version"]
        assert chunk["text"] == chunk_document["text"][
            span["raw_start"] : span["raw_end"]
        ]
        assert len(chunk["text"]) <= 48

    manifest = _read_json(first.manifest_path)
    assert manifest["governance"]["status"] == "PENDING"
    assert manifest["governance"]["allowed_purposes"] == ["RETRIEVAL_EXPERIMENT"]
    assert manifest["evaluation_role"] == "CORE_SOURCE_RETRIEVAL_DIAGNOSTIC"
    assert manifest["result_classification"] == "COMPONENT_DIAGNOSTIC"
    assert manifest["source_extract"]["no_plagiarism_xml_skipped"] == 1
    assert manifest["source"]["license"] == "CC-BY-4.0"
    assert manifest["split"]["document_ids"] == sorted(
        value["document_id"] for value in documents
    )
    assert manifest["split"]["query_ids"] == [query["query_id"]]
    for name in ("documents", "chunks", "queries", "qrels"):
        assert manifest["files"][name]["sha256"] == hashlib.sha256(
            (first_dir / OUTPUT_NAMES[name]).read_bytes()
        ).hexdigest()


def test_pan13_is_labeled_component_diagnostic_with_span_target(tmp_path):
    corpus = tmp_path / "pan13-test2"
    _, _, source_start, source_span, _ = _write_pan_fixture(corpus)
    output = tmp_path / "pack"

    convert_pan_pilot(
        dataset="pan13",
        input_root=corpus,
        output_dir=output,
        dataset_version="test2-extract-v1",
    )

    manifest = _read_json(output / "dataset-manifest.json")
    [qrel] = _read_jsonl(output / "qrels.jsonl")
    assert manifest["evaluation_role"] == "COMPONENT_DIAGNOSTIC_TEXT_ALIGNMENT"
    assert qrel["target_scope"] == "span"
    assert qrel["raw_start"] == source_start
    assert qrel["raw_end"] == source_start + len(source_span)


def test_converter_rejects_traversal_and_does_not_overwrite_by_default(tmp_path):
    corpus = tmp_path / "corpus"
    _write_pan_fixture(corpus, source_reference="../outside.txt")
    (corpus / "outside.txt").write_text("not allowed", encoding="utf-8")

    with pytest.raises(ValueError, match="Unsafe PAN file reference"):
        convert_pan_pilot(
            dataset="pan13",
            input_root=corpus,
            output_dir=tmp_path / "unsafe-output",
            dataset_version="v1",
        )

    safe_corpus = tmp_path / "safe-corpus"
    _write_pan_fixture(safe_corpus)
    output = tmp_path / "safe-output"
    convert_pan_pilot(
        dataset="pan13",
        input_root=safe_corpus,
        output_dir=output,
        dataset_version="v1",
    )
    with pytest.raises(FileExistsError, match="Refusing to overwrite"):
        convert_pan_pilot(
            dataset="pan13",
            input_root=safe_corpus,
            output_dir=output,
            dataset_version="v1",
        )


def test_cli_emits_the_five_runner_files(tmp_path, capsys):
    corpus = tmp_path / "corpus"
    _write_pan_fixture(corpus)
    output = tmp_path / "cli-output"

    assert (
        main(
            [
                "--dataset",
                "pan13",
                "--input-root",
                str(corpus),
                "--output-dir",
                str(output),
                "--dataset-version",
                "v1",
                "--max-chunk-chars",
                "64",
            ]
        )
        == 0
    )
    summary = json.loads(capsys.readouterr().out)
    assert summary["documents"] == 1
    assert summary["queries"] == 1
    assert {path.name for path in output.iterdir()} == set(OUTPUT_NAMES.values())


def test_pan_pc_pack_is_fail_closed_then_runs_all_baselines_after_test_approval(
    tmp_path,
):
    corpus = tmp_path / "corpus"
    _write_pan_fixture(corpus, add_distractor=True)
    output = tmp_path / "pack"
    manifest_path = convert_pan_pilot(
        dataset="pan-pc-11",
        input_root=corpus,
        output_dir=output,
        dataset_version="synthetic-v1",
        max_chunk_chars=64,
    ).manifest_path
    config = {
        "schema_version": 1,
        "experiment_id": "pan-pack-integration-test",
        "seed": 7,
        "methods": [
            "fixed_window_bm25",
            "structure_bm25",
            "structure_dense",
            "structure_hybrid_rrf",
        ],
        "candidate_retrieval_depth": 10,
        "retrieval_depth": 2,
        "metric_cutoffs": [1, 2],
        "fixed_window": {"size_tokens": 12, "stride_tokens": 6},
        "bm25": {"k1": 1.2, "b": 0.75},
        "dense": {
            "backend": "injected_test",
            "model": "pan-evidence-fixture",
            "revision": "synthetic-v1",
            "device": "cpu",
            "batch_size": 2,
            "query_prefix": "",
            "document_prefix": "",
        },
        "rrf": {"k": 60},
        "metrics": {"target_scope": "document", "gold_overlap_threshold": 0.5},
    }
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")

    with pytest.raises(ValueError, match="not APPROVED"):
        run_experiment(
            manifest_path,
            config_path,
            tmp_path / "denied-run",
            encoder=_EvidenceFixtureEncoder(),
            allow_test_encoder=True,
        )

    manifest = _read_json(manifest_path)
    manifest["governance"].update(
        {
            "status": "APPROVED",
            "rights_basis": "PROJECT_GENERATED_SYNTHETIC",
            "approver": "test-policy",
            "approved_at": "2026-09-25",
        }
    )
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, sort_keys=True), encoding="utf-8"
    )
    result = run_experiment(
        manifest_path,
        config_path,
        tmp_path / "approved-run",
        encoder=_EvidenceFixtureEncoder(),
        allow_test_encoder=True,
    )
    metrics = _read_json(result["metrics_path"])
    assert set(metrics) == {
        "fixed_window_bm25",
        "structure_bm25",
        "structure_dense",
        "structure_hybrid_rrf",
    }
    assert metrics["structure_hybrid_rrf"]["target_scope"] == "document"
    assert metrics["structure_hybrid_rrf"]["macro"]["2"]["recall"] == 1.0
    for file_name in ("documents", "chunks", "queries", "qrels"):
        assert manifest["files"][file_name]["sha256"] == sha256_file(
            output / OUTPUT_NAMES[file_name]
        )
