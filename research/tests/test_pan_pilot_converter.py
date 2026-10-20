"""Tests for deterministic conversion of extracted PAN XML/TXT corpora."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

import research.pan_pilot.converter as pan_converter
from research.offline_retrieval.common import sha256_file
from research.offline_retrieval.runner import run_experiment
from research.pan_pilot.cli import main
from research.pan_pilot.converter import OUTPUT_NAMES, convert_pan_pilot


def _read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def _split_groups(pack: Path):
    manifest = _read_json(pack / "dataset-manifest.json")
    queries = _read_jsonl(pack / "queries.jsonl")
    documents = _read_jsonl(pack / "documents.jsonl")
    return {
        "parents": set(manifest["split"]["parent_annotation_ids"]),
        "suspicious": {
            query["annotation_provenance"]["suspicious_document"]
            for query in queries
        },
        "sources": {document["source_reference"] for document in documents},
    }


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


def _write_sampling_fixture(
    root: Path,
    *,
    annotation_count: int = 6,
    distractor_count: int = 6,
    query_word_count: int = 8,
) -> None:
    source_dir = root / "src"
    suspicious_dir = root / "susp"
    source_dir.mkdir(parents=True)
    suspicious_dir.mkdir(parents=True)
    for index in range(annotation_count):
        source_text = f"source evidence {index} with enough text"
        query_text = " ".join(f"word{index}_{word}" for word in range(query_word_count))
        source_name = f"source-document{index}.txt"
        suspicious_name = f"suspicious-document{index}.txt"
        (source_dir / source_name).write_text(source_text, encoding="utf-8")
        (suspicious_dir / suspicious_name).write_text(query_text, encoding="utf-8")
        label_dir = root / "labels" / ("manual" if index % 2 == 0 else "artificial")
        label_dir.mkdir(parents=True, exist_ok=True)
        (label_dir / f"annotation-{index}.xml").write_text(
            (
                f'<document reference="{suspicious_name}">'
                f'<feature name="plagiarism" this_offset="0" '
                f'this_length="{len(query_text)}" source_reference="{source_name}" '
                f'source_offset="0" source_length="{len(source_text)}" />'
                "</document>"
            ),
            encoding="utf-8",
        )
    for index in range(distractor_count):
        (source_dir / f"source-document-distractor-{index}.txt").write_text(
            f"negative distractor {index}", encoding="utf-8"
        )

    # Official PAN-PC distributions include metadata XML for both source and
    # suspicious documents.  A source XML must never become a positive query.
    (source_dir / "source-document0.xml").write_text(
        (
            '<document reference="source-document0.txt">'
            '<feature name="plagiarism" this_offset="0" this_length="6" '
            'source_reference="source-document1.txt" source_offset="0" '
            'source_length="6" /></document>'
        ),
        encoding="utf-8",
    )


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
    assert manifest["source"]["license"] is None
    assert manifest["source"]["terms"] == "Free of charge for research purposes"
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


def test_sampling_is_seeded_stratified_bounded_and_does_not_read_full_corpus(
    tmp_path, monkeypatch
):
    corpus = tmp_path / "corpus"
    _write_sampling_fixture(corpus)
    reads: list[Path] = []
    original_read = pan_converter._read_utf8_exact

    def track_read(path: Path) -> str:
        reads.append(path)
        return original_read(path)

    monkeypatch.setattr(pan_converter, "_read_utf8_exact", track_read)
    first_dir = tmp_path / "first"
    first = convert_pan_pilot(
        dataset="pan-pc-11",
        input_root=corpus,
        output_dir=first_dir,
        dataset_version="sample-v1",
        max_positive_annotations=2,
        max_candidate_documents=4,
        seed=17,
    )
    manifest = _read_json(first.manifest_path)

    assert first.document_count == 4
    assert first.query_count == 2
    assert manifest["source_extract"]["plagiarism_annotation_count_available"] == 6
    assert manifest["source_extract"]["non_suspicious_xml_skipped"] == 1
    assert manifest["sampling"]["positive_annotations_selected"] == 2
    assert manifest["sampling"]["relevant_source_documents_selected"] == 2
    assert manifest["sampling"]["distractor_documents_selected"] == 2
    assert len(manifest["sampling"]["selected_annotation_ids"]) == 2
    assert len(manifest["sampling"]["selected_annotation_ids_sha256"]) == 64
    assert manifest["sampling"]["full_corpus_result"] is False

    # Four selected candidate sources plus two selected suspicious documents;
    # unselected source/suspicious text is never opened.
    assert len(set(reads)) == 6
    assert not any(path.name == "source-document0.xml" for path in reads)

    reads.clear()
    second_dir = tmp_path / "second"
    convert_pan_pilot(
        dataset="pan-pc-11",
        input_root=corpus,
        output_dir=second_dir,
        dataset_version="sample-v1",
        max_positive_annotations=2,
        max_candidate_documents=4,
        seed=17,
    )
    for filename in OUTPUT_NAMES.values():
        assert (first_dir / filename).read_bytes() == (second_dir / filename).read_bytes()


def test_prior_manifest_exclusions_create_repeatable_pairwise_disjoint_splits(
    tmp_path,
):
    corpus = tmp_path / "corpus"
    _write_sampling_fixture(
        corpus,
        annotation_count=24,
        distractor_count=24,
    )
    dev0 = tmp_path / "dev0"
    dev1 = tmp_path / "dev1"
    dev1_repeat = tmp_path / "dev1-repeat"
    test0 = tmp_path / "test0"

    convert_pan_pilot(
        dataset="pan-pc-11",
        input_root=corpus,
        output_dir=dev0,
        dataset_version="fixture-v1",
        split_name="DEV0",
        max_positive_annotations=3,
        max_candidate_documents=6,
        seed=101,
    )
    dev0_manifest = dev0 / "dataset-manifest.json"
    for output in (dev1, dev1_repeat):
        convert_pan_pilot(
            dataset="pan-pc-11",
            input_root=corpus,
            output_dir=output,
            dataset_version="fixture-v1",
            split_name="DEV1",
            max_positive_annotations=3,
            max_candidate_documents=6,
            seed=102,
            exclude_manifests=[dev0_manifest],
        )
    convert_pan_pilot(
        dataset="pan-pc-11",
        input_root=corpus,
        output_dir=test0,
        dataset_version="fixture-v1",
        split_name="TEST0",
        max_positive_annotations=3,
        max_candidate_documents=6,
        seed=103,
        exclude_manifests=[
            dev0_manifest,
            dev1 / "dataset-manifest.json",
        ],
    )

    for filename in OUTPUT_NAMES.values():
        assert (dev1 / filename).read_bytes() == (
            dev1_repeat / filename
        ).read_bytes()

    groups = [_split_groups(path) for path in (dev0, dev1, test0)]
    for group in groups:
        assert len(group["parents"]) == 3
        assert len(group["suspicious"]) == 3
        assert len(group["sources"]) == 6
    for left_index, left in enumerate(groups):
        for right in groups[left_index + 1 :]:
            assert left["parents"].isdisjoint(right["parents"])
            assert left["suspicious"].isdisjoint(right["suspicious"])
            assert left["sources"].isdisjoint(right["sources"])

    dev1_data = _read_json(dev1 / "dataset-manifest.json")
    assert dev1_data["governance"]["status"] == "PENDING"
    assert dev1_data["exclusions"]["policy"] == "prior-derived-split-disjoint-v1"
    assert dev1_data["exclusions"]["manifest_count"] == 1
    assert dev1_data["exclusions"]["union_counts"] == {
        "parent_annotation_ids": 3,
        "suspicious_documents": 3,
        "candidate_source_documents": 6,
    }
    [prior] = dev1_data["exclusions"]["manifests"]
    assert prior["manifest_sha256"] == hashlib.sha256(
        dev0_manifest.read_bytes()
    ).hexdigest()
    assert prior["documents_sha256"] == hashlib.sha256(
        (dev0 / "documents.jsonl").read_bytes()
    ).hexdigest()
    assert prior["queries_sha256"] == hashlib.sha256(
        (dev0 / "queries.jsonl").read_bytes()
    ).hexdigest()
    assert dev1_data["sampling"]["source_documents_excluded"] == 6
    assert dev1_data["sampling"]["annotations_excluded"] >= 3

    test0_data = _read_json(test0 / "dataset-manifest.json")
    assert test0_data["governance"]["status"] == "PENDING"
    assert test0_data["exclusions"]["manifest_count"] == 2
    assert test0_data["exclusions"]["union_counts"] == {
        "parent_annotation_ids": 6,
        "suspicious_documents": 6,
        "candidate_source_documents": 12,
    }
    assert len(test0_data["exclusions"]["union_checksums"][
        "candidate_source_documents_sha256"
    ]) == 64


def test_exclusion_manifest_companions_are_checksum_and_corpus_bound(tmp_path):
    corpus = tmp_path / "corpus"
    _write_sampling_fixture(corpus, annotation_count=8, distractor_count=8)
    dev0 = tmp_path / "dev0"
    dev0_manifest = convert_pan_pilot(
        dataset="pan-pc-11",
        input_root=corpus,
        output_dir=dev0,
        dataset_version="fixture-v1",
        max_positive_annotations=2,
        max_candidate_documents=4,
    ).manifest_path

    with (dev0 / "queries.jsonl").open("ab") as stream:
        stream.write(b" ")
    with pytest.raises(ValueError, match="queries checksum mismatch"):
        convert_pan_pilot(
            dataset="pan-pc-11",
            input_root=corpus,
            output_dir=tmp_path / "tampered",
            dataset_version="fixture-v1",
            max_positive_annotations=2,
            max_candidate_documents=4,
            exclude_manifests=[dev0_manifest],
        )

    # Restore the declared companion, then prove the manifest cannot be used
    # against a different extraction inventory.
    queries = (dev0 / "queries.jsonl").read_bytes().rstrip() + b"\n"
    (dev0 / "queries.jsonl").write_bytes(queries)
    other_corpus = tmp_path / "other-corpus"
    _write_sampling_fixture(other_corpus, annotation_count=8, distractor_count=8)
    (other_corpus / "src" / "source-document-extra.txt").write_text(
        "changes metadata inventory", encoding="utf-8"
    )
    with pytest.raises(ValueError, match="input fingerprint"):
        convert_pan_pilot(
            dataset="pan-pc-11",
            input_root=other_corpus,
            output_dir=tmp_path / "wrong-corpus",
            dataset_version="fixture-v1",
            max_positive_annotations=2,
            max_candidate_documents=4,
            exclude_manifests=[dev0_manifest],
        )


def test_cli_accepts_repeated_exclusion_manifests(tmp_path, capsys):
    corpus = tmp_path / "corpus"
    _write_sampling_fixture(corpus, annotation_count=18, distractor_count=18)
    earlier_manifests = []
    for index, seed in enumerate((201, 202)):
        output = tmp_path / f"prior-{index}"
        earlier_manifests.append(
            convert_pan_pilot(
                dataset="pan-pc-11",
                input_root=corpus,
                output_dir=output,
                dataset_version="fixture-v1",
                max_positive_annotations=2,
                max_candidate_documents=4,
                seed=seed,
                exclude_manifests=earlier_manifests,
            ).manifest_path
        )

    output = tmp_path / "cli-output-excluded"
    argv = [
        "--dataset",
        "pan-pc-11",
        "--input-root",
        str(corpus),
        "--output-dir",
        str(output),
        "--dataset-version",
        "fixture-v1",
        "--max-positive-annotations",
        "2",
        "--max-candidate-documents",
        "4",
        "--seed",
        "203",
    ]
    for manifest in earlier_manifests:
        argv.extend(["--exclude-manifest", str(manifest)])
    assert main(argv) == 0
    capsys.readouterr()
    manifest = _read_json(output / "dataset-manifest.json")
    assert manifest["exclusions"]["manifest_count"] == 2
    assert manifest["governance"]["status"] == "PENDING"


def test_converter_skips_and_reports_zero_length_annotations(tmp_path):
    corpus = tmp_path / "corpus"
    _write_sampling_fixture(
        corpus,
        annotation_count=1,
        distractor_count=0,
    )
    zero_length_xml = corpus / "labels" / "manual" / "zero-length.xml"
    zero_length_xml.write_text(
        (
            '<document reference="suspicious-document0.txt">'
            '<feature name="plagiarism" this_offset="0" this_length="0" '
            'source_reference="source-document0.txt" source_offset="0" '
            'source_length="6" /></document>'
        ),
        encoding="utf-8",
    )

    output = tmp_path / "pack"
    result = convert_pan_pilot(
        dataset="pan-pc-11",
        input_root=corpus,
        output_dir=output,
        dataset_version="zero-length-v1",
        max_positive_annotations=10,
        max_candidate_documents=1,
    )

    manifest = _read_json(result.manifest_path)
    assert manifest["source_extract"]["zero_length_annotations_skipped"] == 1
    assert manifest["source_extract"]["plagiarism_annotation_count_available"] == 1
    assert result.query_count == 1


def test_long_annotation_is_windowed_to_256_unicode_words_with_shared_qrel(tmp_path):
    corpus = tmp_path / "corpus"
    _write_sampling_fixture(
        corpus,
        annotation_count=1,
        distractor_count=0,
        query_word_count=600,
    )
    output = tmp_path / "pack"
    convert_pan_pilot(
        dataset="pan13",
        input_root=corpus,
        output_dir=output,
        dataset_version="long-query-v1",
        max_positive_annotations=1,
        max_candidate_documents=1,
        max_query_word_tokens=256,
        query_stride_word_tokens=128,
    )

    queries = _read_jsonl(output / "queries.jsonl")
    qrels = _read_jsonl(output / "qrels.jsonl")
    assert len(queries) == len(qrels) == 4
    assert {query["parent_annotation_id"] for query in queries} == {
        qrel["parent_annotation_id"] for qrel in qrels
    }
    assert all(query["query_window"]["word_token_count"] <= 256 for query in queries)
    assert sorted(query["query_window"]["token_start"] for query in queries) == [
        0,
        128,
        256,
        344,
    ]
    assert len({(qrel["document_id"], qrel["raw_start"], qrel["raw_end"]) for qrel in qrels}) == 1


def test_source_archive_checksum_and_converter_provenance_are_recorded(
    tmp_path, monkeypatch
):
    corpus = tmp_path / "corpus"
    _write_pan_fixture(corpus)
    archive = tmp_path / "pan13-text-alignment-test-and-training.zip"
    archive.write_bytes(b"synthetic archive fixture")
    monkeypatch.setattr(
        pan_converter,
        "_md5_file",
        lambda path: pan_converter.EXPECTED_ARCHIVE_MD5["pan13"][path.name],
    )
    output = tmp_path / "pack"
    convert_pan_pilot(
        dataset="pan13",
        input_root=corpus,
        output_dir=output,
        dataset_version="archive-v1",
        source_archives=[archive],
    )
    manifest = _read_json(output / "dataset-manifest.json")
    [record] = manifest["source"]["archives"]
    assert record["name"] == archive.name
    assert record["size_bytes"] == archive.stat().st_size
    assert record["provider_checksum_verified"] is True
    assert record["local_sha256"] == hashlib.sha256(archive.read_bytes()).hexdigest()
    provenance = manifest["transformation"]["converter_provenance"]
    assert len(provenance["code_sha256"]) == 64
    assert len(provenance["git_commit"]) == 40
    assert isinstance(provenance["git_dirty"], bool)


def test_known_archive_with_wrong_provider_md5_is_rejected(tmp_path):
    corpus = tmp_path / "corpus"
    _write_pan_fixture(corpus)
    archive = tmp_path / "pan13-text-alignment-test-and-training.zip"
    archive.write_bytes(b"not the provider archive")
    with pytest.raises(ValueError, match="Provider MD5 mismatch"):
        convert_pan_pilot(
            dataset="pan13",
            input_root=corpus,
            output_dir=tmp_path / "pack",
            dataset_version="archive-v1",
            source_archives=[archive],
        )


def test_pan_pc_requires_bounded_positive_sampling_and_keeps_all_relevant_sources(
    tmp_path,
):
    corpus = tmp_path / "corpus"
    _write_sampling_fixture(corpus, annotation_count=3, distractor_count=0)
    with pytest.raises(ValueError, match="bounded max_positive_annotations"):
        convert_pan_pilot(
            dataset="pan-pc-11",
            input_root=corpus,
            output_dir=tmp_path / "unbounded",
            dataset_version="v1",
            max_positive_annotations=None,
        )
    with pytest.raises(ValueError, match="smaller than the number of relevant"):
        convert_pan_pilot(
            dataset="pan-pc-11",
            input_root=corpus,
            output_dir=tmp_path / "too-small",
            dataset_version="v1",
            max_positive_annotations=3,
            max_candidate_documents=2,
        )


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
    archive = tmp_path / "locally-renamed-pan13.zip"
    archive.write_bytes(b"local fixture")

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
                "--max-positive-annotations",
                "1",
                "--max-candidate-documents",
                "1",
                "--seed",
                "19",
                "--source-archive",
                str(archive),
            ]
        )
        == 0
    )
    summary = json.loads(capsys.readouterr().out)
    assert summary["documents"] == 1
    assert summary["queries"] == 1
    assert {path.name for path in output.iterdir()} == set(OUTPUT_NAMES.values())
    manifest = _read_json(output / "dataset-manifest.json")
    assert manifest["sampling"]["seed"] == 19
    assert manifest["source"]["archives"][0]["provider_checksum_verified"] is False


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
            "classification": "SYNTHETIC_PUBLIC",
            "contains_pii": False,
            "retention": "Ephemeral generated test fixture",
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
