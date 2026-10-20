"""Small, fixed MMDocIR text-only diagnostic using the existing LOCAL pipeline."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import time

import pymupdf

from research.core_mvp.assessment import _rank_local, validate_assessment_config
from research.core_mvp.documents import parse_document
from research.core_mvp.runner import _hardware, _load_encoder, _load_reranker, _repository_state
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


def main():
    started = time.perf_counter()
    annotation = RAW / "MMDocIR_annotations.jsonl"
    archive = RAW / "doc_pdfs.rar"
    assert sha256_file(annotation) == "812d14b22d92389a1d9b288c0143b0ffc31fba6d114322e2e75cab2528833e09"
    assert sha256_file(archive) == "360e0c7907f1c78012bbc9016623a0ec0d05cb3308ec6ded7c8b46e582b785df"
    if OUTPUT.exists():
        raise FileExistsError(f"Refusing to overwrite pilot: {OUTPUT}")
    rows = [json.loads(line) for line in annotation.read_text().splitlines()]
    eligible = [d for d in rows if any(q["type"] in TEXT_TYPES for q in d["questions"])]
    selected = sorted(eligible, key=lambda d: hashlib.sha256(f"{SEED}:{d['doc_name']}".encode()).hexdigest())[:5]
    extracted = RAW / "pilot-p5"
    names = [d["doc_name"] for d in selected]
    if any(Path(name).name != name for name in names):
        raise ValueError("Unexpected archive name")
    if not all((extracted / "doc_pdfs" / name).is_file() for name in names):
        subprocess.run(["unar", "-q", "-D", "-o", str(extracted), str(archive), *["doc_pdfs/" + name for name in names]], check=True)
    config_path = ROOT / "research/configs/core-mvp-v0.json"
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
    OUTPUT.mkdir(parents=True)
    write_json(OUTPUT/"metrics.json",metrics)
    code_paths=[Path(__file__),ROOT/"research/core_mvp/assessment.py",ROOT/"research/core_mvp/documents.py",ROOT/"research/core_mvp/similarity.py",ROOT/"research/offline_retrieval/dense.py",ROOT/"services/backend/src/kltn_ai/integrations/parsing/pdf_parser.py",ROOT/"services/backend/src/kltn_ai/integrations/indexing/chunking.py"]
    manifest={"dataset":"MMDocIR","source":"https://huggingface.co/datasets/MMDocIR/MMDocIR_Evaluation_Dataset","approval_evidence":"Dataset mapping row 6, workbook *52200229*4.xlsx: APPROVED, approver Yến","input_sha256":{"annotations":sha256_file(annotation),"pdf_archive":sha256_file(archive),"configuration":sha256_file(config_path)},"configuration":{"bm25":baseline,"hybrid":hybrid,"models":config["models"]},"model_diagnostics":reranker.metadata,"code_sha256":{p.relative_to(ROOT).as_posix():sha256_file(p) for p in code_paths},"git":_repository_state(),"hardware":_hardware(),"total_wall_seconds":time.perf_counter()-started,"metrics_sha256":sha256_file(OUTPUT/"metrics.json"),"interpretation":"Fixed small feasibility pilot; no model selection or superiority claim; no OCR/image/table/layout-bbox benchmark, rubric grading, or claim verification."}
    write_json(OUTPUT/"run-manifest.json",manifest)
    print(json.dumps({"query_count":count,"methods":metrics['methods'],"seconds":manifest['total_wall_seconds']},indent=2))


if __name__=="__main__":
    main()
