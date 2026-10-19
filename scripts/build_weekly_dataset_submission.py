"""Build the 18 October weekly submission from allowlisted benchmark artifacts.

The package contains experiment reports, metrics, manifests, and the code used
to produce them. The prior PAN metrics retain de-identified per-query metric
values needed for the paired analysis, but no query text or rankings. It
excludes raw dataset text, student reports, model weights, and local caches.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from shutil import copy2
from zipfile import ZIP_DEFLATED, ZipFile


REPO = Path(__file__).resolve().parents[1]
NAME = "BaoCaoTuan_KLTN_523H0087_52200229_18-10-2026_DATASET_FINAL"
STAGE = REPO / "submission" / NAME
ARCHIVE = REPO / "submission" / f"{NAME}.zip"
DRAFT = REPO / "submission/BaoCaoTuan_KLTN_523H0087_52200229_18-10-2026_DATASET"
PRIOR = REPO / "submission/BaoCaoTuan_KLTN_523H0087_52200229_12-10-2026"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def add_file(entries: dict[str, Path], path: str, source: Path) -> None:
    if path in entries or not source.is_file():
        raise ValueError(f"Missing or duplicate package entry: {path} <- {source}")
    entries[path] = source


def collect(qasper_run: Path) -> dict[str, Path]:
    entries: dict[str, Path] = {}
    add_file(entries, "README.md", DRAFT / "README.md")
    add_file(
        entries,
        "00_BaoCaoTuan/BaoCaoTuan_KLTN_523H0087_52200229_18-10-2026.md",
        DRAFT
        / "00_BaoCaoTuan/BaoCaoTuan_KLTN_523H0087_52200229_18-10-2026.md",
    )

    p1 = PRIOR / "02_KetQuaThucNghiem"
    for filename in (
        "pan-pc-11-cross-encoder-ablation-dev0-result.md",
        "pan-pc-11-parent-bootstrap-dev0-result.md",
    ):
        add_file(entries, f"01_Pipeline1_PAN_PC11/{filename}", p1 / filename)
    for filename in ("metrics.json", "run_manifest.json"):
        add_file(
            entries,
            f"01_Pipeline1_PAN_PC11/outputs/{filename}",
            p1 / "outputs" / filename,
        )
    add_file(
        entries,
        "01_Pipeline1_PAN_PC11/config/pan-pc-11-cross-encoder-dev0-v1.json",
        PRIOR
        / "03_Protocol_Va_CauHinh/pan-pc-11-cross-encoder-dev0-v1.json",
    )
    for filename in ("RQ1_SIMILARITY_PROTOCOL.md", "pan-pc-11-split-readiness.md"):
        add_file(
            entries,
            f"01_Pipeline1_PAN_PC11/protocol/{filename}",
            PRIOR / "03_Protocol_Va_CauHinh" / filename,
        )

    for filename in ("metrics.json", "run_manifest.json"):
        add_file(
            entries,
            f"02_Pipeline2_QASPER/outputs/{filename}",
            qasper_run / filename,
        )
    add_file(
        entries,
        "02_Pipeline2_QASPER/qasper-v03-local-evidence-dev-result.md",
        REPO / "docs/benchmarks/qasper-v03-local-evidence-dev-result.md",
    )
    for path in sorted((REPO / "research/qasper_pilot").glob("*.py")):
        add_file(
            entries,
            f"03_MaNguon/research/qasper_pilot/{path.name}",
            path,
        )
    add_file(
        entries,
        "03_MaNguon/research/qasper_pilot/README.md",
        REPO / "research/qasper_pilot/README.md",
    )
    add_file(entries, "03_MaNguon/research/__init__.py", REPO / "research/__init__.py")
    for path in sorted((REPO / "research/offline_retrieval").glob("*.py")):
        add_file(
            entries,
            f"03_MaNguon/research/offline_retrieval/{path.name}",
            path,
        )
    add_file(
        entries,
        "03_MaNguon/research/tests/test_qasper_pilot.py",
        REPO / "research/tests/test_qasper_pilot.py",
    )
    add_file(
        entries,
        "03_MaNguon/research/requirements-research.txt",
        REPO / "research/requirements-research.txt",
    )
    p1_snapshot = PRIOR / "04_MaNguonTaiLap/research"
    p1_sources = [
        p1_snapshot / "__init__.py",
        p1_snapshot / "README.md",
        p1_snapshot / "requirements-research.txt",
    ]
    for directory in ("offline_retrieval", "offline_retrieval/analysis", "pan_pilot"):
        p1_sources.extend(sorted((p1_snapshot / directory).glob("*.py")))
        if (p1_snapshot / directory / "README.md").is_file():
            p1_sources.append(p1_snapshot / directory / "README.md")
    p1_sources.extend(sorted((p1_snapshot / "tests").glob("test_*.py")))
    fixture_dir = p1_snapshot / "tests/fixtures/retrieval_pilot_v1"
    for filename in (
        "chunks.jsonl", "config.json", "dataset-manifest.json",
        "documents.jsonl", "qrels.jsonl", "queries.jsonl",
    ):
        p1_sources.append(fixture_dir / filename)
    for path in p1_sources:
        relative = path.relative_to(PRIOR / "04_MaNguonTaiLap")
        add_file(entries, f"03_MaNguon/P1_snapshot/{relative.as_posix()}", path)
    return entries


def validate_run(qasper_run: Path) -> None:
    p1_metrics = json.loads(
        (PRIOR / "02_KetQuaThucNghiem/outputs/metrics.json").read_text(
            encoding="utf-8"
        )
    )
    qasper_metrics = json.loads((qasper_run / "metrics.json").read_text(encoding="utf-8"))
    qasper_manifest = json.loads(
        (qasper_run / "run_manifest.json").read_text(encoding="utf-8")
    )
    if not isinstance(p1_metrics, dict) or not isinstance(qasper_metrics, dict):
        raise ValueError("Benchmark metrics must be JSON objects")
    p1_manifest = json.loads(
        (PRIOR / "02_KetQuaThucNghiem/outputs/run_manifest.json").read_text(
            encoding="utf-8"
        )
    )
    if p1_manifest.get("artifacts", {}).get("metrics", {}).get("sha256") != sha256(
        PRIOR / "02_KetQuaThucNghiem/outputs/metrics.json"
    ):
        raise ValueError("PAN metrics checksum differs from its run manifest")
    if not isinstance(qasper_manifest, dict):
        raise ValueError("QASPER run manifest must be a JSON object")
    if qasper_metrics.get("dataset") != "QASPER v0.3 dev":
        raise ValueError("Expected QASPER v0.3 dev metrics")
    if qasper_metrics.get("scope", {}).get("papers_selected") != 281:
        raise ValueError("The weekly dataset ZIP must contain the full 281-paper dev diagnostic")
    if set(qasper_metrics.get("methods", {})) != {
        "bm25", "e5_dense", "bm25_e5_rrf"
    }:
        raise ValueError("Expected BM25, E5 Dense and RRF metrics")
    metric_hash = sha256(qasper_run / "metrics.json")
    if qasper_manifest.get("artifacts", {}).get("metrics.json", {}).get("sha256") != metric_hash:
        raise ValueError("QASPER metrics checksum differs from run manifest")
    if qasper_manifest.get("source", {}).get("extracted_dev_sha256") != (
        "2ae7ee62a65b1c4225791c70de80c2aad4e8998cf1fd4f09a53103db4f21af93"
    ):
        raise ValueError("QASPER dev input checksum differs from locked source")
    source_hashes = qasper_manifest.get("code_sha256", {})
    for key, source in {
        "qasper_benchmark": REPO / "research/qasper_pilot/benchmark.py",
        "bm25": REPO / "research/offline_retrieval/bm25.py",
        "dense": REPO / "research/offline_retrieval/dense.py",
        "rrf": REPO / "research/offline_retrieval/rrf.py",
    }.items():
        if source_hashes.get(key) != sha256(source):
            raise ValueError(f"QASPER manifest code checksum does not match {source}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--qasper-run", type=Path, required=True)
    args = parser.parse_args()
    qasper_run = args.qasper_run.resolve()
    validate_run(qasper_run)
    entries = collect(qasper_run)
    if ARCHIVE.exists():
        raise FileExistsError(f"Refusing to overwrite existing ZIP: {ARCHIVE}")
    for relative, source in sorted(entries.items()):
        destination = STAGE / relative
        if destination.resolve() == source.resolve():
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            if sha256(destination) != sha256(source):
                raise FileExistsError(f"Refusing to overwrite changed file: {destination}")
            continue
        copy2(source, destination)

    inventory = {
        "schema_version": 1,
        "package_name": NAME,
        "scope": "Two real-dataset component benchmarks: PAN-PC-11 and QASPER",
        "contains_raw_benchmark_dataset_text": False,
        "contains_student_report": False,
        "contains_deidentified_per_query_metrics": True,
        "contains_per_query_predictions": False,
        "files": [
            {
                "path": relative,
                "bytes": source.stat().st_size,
                "sha256": sha256(source),
            }
            for relative, source in sorted(entries.items())
        ],
    }
    manifest = STAGE / "package-manifest.json"
    manifest.write_text(
        json.dumps(inventory, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    allowed_paths = set(entries) | {"package-manifest.json"}
    actual_paths = {
        path.relative_to(STAGE).as_posix()
        for path in STAGE.rglob("*")
        if path.is_file() or path.is_symlink()
    }
    if actual_paths != allowed_paths:
        raise ValueError(f"Unexpected or missing package files: {actual_paths ^ allowed_paths}")
    if any(path.is_symlink() for path in STAGE.rglob("*")):
        raise ValueError("Symlinks are not permitted in the submission")
    with ZipFile(ARCHIVE, "x", compression=ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(STAGE.rglob("*")):
            if path.is_file():
                archive.write(path, arcname=f"{NAME}/{path.relative_to(STAGE).as_posix()}")
    print(f"ZIP: {ARCHIVE}")
    print(f"Files: {len(entries) + 1}")
    print(f"SHA-256: {sha256(ARCHIVE)}")


if __name__ == "__main__":
    main()
