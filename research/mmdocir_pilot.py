"""Small, fixed MMDocIR text-only diagnostic using the existing LOCAL pipeline."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import time

import pymupdf

from research.core_mvp.assessment import _rank_local, validate_assessment_config
from research.core_mvp.documents import parse_document
from research.core_mvp.runner import _hardware, _load_encoder, _load_reranker, _repository_state
from research.governance import load_registry, validate_pack_manifest
from research.offline_retrieval.common import read_json, sha256_file, write_json


ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "var/datasets/raw/mmdocir-eval"
OUTPUT = ROOT / "research/results/rq2-mmdocir/local-text-p5-s20261018"
SEED = 20261018
TEXT_TYPES = {"text-only", "['Pure-text (Plain-text)']"}


class CachedEncoder:
    """Cache identical inputs by E5 prefix mode without changing embeddings."""

    def __init__(self, base):
        self.base = base
        self.mode = "document"
        self.cache = {}
        self.metadata = base.metadata

    def set_mode(self, mode):
        self.mode = mode
        self.base.set_mode(mode)

    def encode(self, texts):
        missing = list(dict.fromkeys(t for t in texts if (self.mode, t) not in self.cache))
        if missing:
            values = self.base.encode(missing)
            self.cache.update({(self.mode, t): value for t, value in zip(missing, values)})
        return [self.cache[(self.mode, t)] for t in texts]


def retrieved_pages(candidates):
    pages = set()
    for item in candidates:
        for span in item.get("source_spans", []):
            locator = span.get("locator", {})
            if locator.get("page_index") is not None:
                pages.add(int(locator["page_index"]))
    return pages


def validate_mmdocir_manifest(
    manifest_path: Path,
    *,
    raw_dir: Path = RAW,
    registry: dict | None = None,
) -> dict:
    """Bind approval to the exact files and selected PDFs this pilot reads."""

    manifest_path = Path(manifest_path)
    if manifest_path.parent.resolve() != raw_dir.resolve():
        raise ValueError("MMDocIR manifest must be beside the raw files used by this run")
    registry = registry if registry is not None else load_registry()
    validated = validate_pack_manifest(
        manifest_path,
        "EVIDENCE_RETRIEVAL_EXPERIMENT",
        registry=registry,
    )
    if validated["registry_id"] != "mmdocir":
        raise ValueError("MMDocIR pilot requires an MMDocIR pack manifest")
    manifest = read_json(manifest_path)
    expected_paths = {
        "annotations": "MMDocIR_annotations.jsonl",
        "pdf_archive": "doc_pdfs.rar",
    }
    catalog = next(entry for entry in registry["datasets"] if entry["id"] == "mmdocir")
    for key, filename in expected_paths.items():
        record = manifest["files"].get(key)
        if not isinstance(record, dict) or record.get("path") != filename:
            raise ValueError(f"MMDocIR files.{key} must be {filename}")
        if record.get("sha256") != catalog["source_sha256"][filename]:
            raise ValueError(f"MMDocIR files.{key} checksum differs from the registry")
    source_files = manifest.get("source", {}).get("files")
    if not isinstance(source_files, list):
        raise ValueError("MMDocIR source.files must list both raw inputs")
    declared_source = {item["name"] for item in source_files}
    if declared_source != set(expected_paths.values()):
        raise ValueError("MMDocIR source must declare both exact input files")
    split = manifest["split"]
    if split.get("seed") != SEED or len(split.get("document_ids", [])) != 5:
        raise ValueError("MMDocIR split must freeze five selected PDFs and the pilot seed")
    return manifest


def main(argv: list[str] | None = None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-manifest", type=Path, required=True)
    args = parser.parse_args(argv)
    approved_manifest = validate_mmdocir_manifest(args.dataset_manifest)
    approved_manifest_sha256 = sha256_file(args.dataset_manifest)
    started = time.perf_counter()
    annotation = RAW / "MMDocIR_annotations.jsonl"
    archive = RAW / "doc_pdfs.rar"
    if OUTPUT.exists():
        raise FileExistsError(f"Refusing to overwrite pilot: {OUTPUT}")
    rows = [json.loads(line) for line in annotation.read_text().splitlines()]
    eligible = [d for d in rows if any(q["type"] in TEXT_TYPES for q in d["questions"])]
    selected = sorted(eligible, key=lambda d: hashlib.sha256(f"{SEED}:{d['doc_name']}".encode()).hexdigest())[:5]
    if [document["doc_name"] for document in selected] != approved_manifest["split"]["document_ids"]:
        raise ValueError("Selected PDF set differs from the approved MMDocIR split")
    extracted = RAW / "pilot-p5"
    names = [d["doc_name"] for d in selected]
    if any(Path(name).name != name for name in names):
        raise ValueError("Unexpected archive name")
    if not all((extracted / "doc_pdfs" / name).is_file() for name in names):
        subprocess.run(["unar", "-q", "-D", "-o", str(extracted), str(archive), *["doc_pdfs/" + name for name in names]], check=True)
    config_path = ROOT / "research/configs/core-mvp-v0.json"
    config_sha256 = sha256_file(config_path)
    config = read_json(config_path)
    hybrid = validate_assessment_config(config["pipeline2"])
    baseline = {**hybrid, "dense_enabled": False, "reranker_enabled": False}
    encoder = CachedEncoder(_load_encoder(config["models"]))
    reranker = _load_reranker(config["models"])
    results = {"bm25": [], "local_bm25_e5_rrf_cross_encoder": []}
    per_query = []
    documents = []
    for document in selected:
        path = extracted / "doc_pdfs" / document["doc_name"]
        parsed = parse_document(path, role="student-report", **config["documents"])
        with pymupdf.open(path) as pdf:
            pages = len(pdf)
        docs = {x["chunk_id"]:x for x in parsed.chunks}
        documents.append({"file":path.name,"sha256":sha256_file(path),"pages":pages,"chunks":len(parsed.chunks)})
        for index, question in enumerate(document["questions"]):
            if question["type"] not in TEXT_TYPES:
                continue
            gold = set(question["page_id"])
            if not gold or any(not isinstance(p,int) or p<0 or p>=pages for p in gold):
                raise ValueError("Invalid gold page index")
            identifier = hashlib.sha256(f"{document['doc_name']}:{index}".encode()).hexdigest()[:20]
            # Only the question enters retrieval. Answers and gold pages remain evaluation-only.
            checklist = {"checklist_id":identifier,"query":question["Q"],"statement":"","requirements":[],"contradiction_patterns":[]}
            diagnostic = {"query_id":identifier,"document":path.name,"gold_pages_0_based":sorted(gold),"methods":{}}
            for name, method in (("bm25",baseline),("local_bm25_e5_rrf_cross_encoder",hybrid)):
                before=time.perf_counter()
                ranked, _ = _rank_local(checklist,parsed.chunks,config=method,encoder=encoder,reranker=reranker)
                assert all(x["chunk_id"] in docs for x in ranked)
                found = retrieved_pages(ranked)
                scores = {"any_gold_page_hit":int(bool(found & gold)),"gold_page_recall":len(found & gold)/len(gold),"all_gold_pages_found":int(gold<=found)}
                results[name].append(scores)
                diagnostic["methods"][name]={**scores,"evidence_chunks":len(ranked),"retrieved_pages_0_based":sorted(found),"seconds":time.perf_counter()-before}
            per_query.append(diagnostic)
        print(f"completed {path.name}, pages={pages}, chunks={len(parsed.chunks)}",flush=True)
    count=len(per_query)
    assert count>0 and all(len(v)==count for v in results.values())
    metrics={"dataset":"MMDocIR Evaluation Dataset","scope":"Text-only LOCAL retrieval; page coverage of the top-5 evidence chunks, not official page ranking Recall@K", "selection":{"seed":SEED,"eligible_documents":len(eligible),"selected_documents":documents,"rule":"first 5 eligible doc_names by SHA256(seed:doc_name); all text-only queries in those documents","accepted_question_types":sorted(TEXT_TYPES)},"query_count":count,"top_k_evidence_chunks":hybrid["top_k"],"methods":{name:{key:sum(r[key] for r in values)/count for key in values[0]} for name,values in results.items()},"per_query":per_query}
    input_sha256 = {
        "annotations": sha256_file(annotation),
        "pdf_archive": sha256_file(archive),
        "configuration": sha256_file(config_path),
    }
    if (
        input_sha256["annotations"] != approved_manifest["files"]["annotations"]["sha256"]
        or input_sha256["pdf_archive"] != approved_manifest["files"]["pdf_archive"]["sha256"]
        or input_sha256["configuration"] != config_sha256
        or sha256_file(args.dataset_manifest) != approved_manifest_sha256
    ):
        raise RuntimeError("Approved MMDocIR inputs changed during the experiment")
    OUTPUT.mkdir(parents=True)
    write_json(OUTPUT/"metrics.json",metrics)
    code_paths=[Path(__file__),ROOT/"research/core_mvp/assessment.py",ROOT/"research/core_mvp/documents.py",ROOT/"research/core_mvp/similarity.py",ROOT/"research/offline_retrieval/dense.py",ROOT/"services/backend/src/kltn_ai/integrations/parsing/pdf_parser.py",ROOT/"services/backend/src/kltn_ai/integrations/indexing/chunking.py"]
    manifest={"dataset":"MMDocIR","dataset_version":approved_manifest["dataset_version"],"source":"https://huggingface.co/datasets/MMDocIR/MMDocIR_Evaluation_Dataset","approval_evidence":approved_manifest["governance"]["approval_evidence"],"dataset_manifest_sha256":approved_manifest_sha256,"input_sha256":input_sha256,"configuration":{"bm25":baseline,"hybrid":hybrid,"models":config["models"]},"model_diagnostics":reranker.metadata,"code_sha256":{p.relative_to(ROOT).as_posix():sha256_file(p) for p in code_paths},"git":_repository_state(),"hardware":_hardware(),"total_wall_seconds":time.perf_counter()-started,"metrics_sha256":sha256_file(OUTPUT/"metrics.json"),"interpretation":"Fixed small feasibility pilot; no model selection or superiority claim; no OCR/image/table/layout-bbox benchmark, rubric grading, or claim verification."}
    write_json(OUTPUT/"run-manifest.json",manifest)
    print(json.dumps({"query_count":count,"methods":metrics['methods'],"seconds":manifest['total_wall_seconds']},indent=2))


if __name__=="__main__":
    main()
