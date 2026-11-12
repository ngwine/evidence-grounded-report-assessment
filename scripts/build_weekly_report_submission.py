"""Package real-report execution together with the existing dataset experiments.

Private inputs and rendered excerpts are written only to ignored var/submission.
The package is local: this command does not publish, email, commit, or upload it.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import importlib.metadata
import json
from collections import Counter
from pathlib import Path, PurePosixPath
from shutil import copy2
from urllib.parse import quote
from zipfile import ZIP_DEFLATED, ZipFile


REPO = Path(__file__).resolve().parents[1]
NAME = "BaoCaoTuan_KLTN_523H0087_52200229_19-10-2026_DATASET_VA_REPORT_V2"
STAGE = REPO / "var/submission" / NAME
ARCHIVE = STAGE.with_suffix(".zip")
CONFIG = REPO / "research/configs/core-mvp-v0.json"
RUBRIC = REPO / "research/configs/core-mvp-ai-course-report-rubric-v0.json"
PROJECT_REPOSITORY = "https://github.com/ngwine/evidence-grounded-report-assessment"


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for part in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(part)
    return h.hexdigest()


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write(relative: str, value: str):
    path = STAGE / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")


def copy(source: Path, relative: str):
    if not source.is_file() or source.is_symlink():
        raise ValueError(f"Invalid input {source}")
    destination = STAGE / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    copy2(source, destination)


def page_numbers(record):
    pages = set()
    for span in record.get("source_spans", []):
        loc = span.get("locator", {})
        page = loc.get("page_number")
        if page is None and loc.get("page_index") is not None:
            page = loc["page_index"] + 1
        if page is not None:
            pages.add(page)
    return sorted(pages)


def page_links(record, filename):
    pages = page_numbers(record)
    href = "inputs/" + ("sources/" if filename != "report.pdf" else "") + quote(filename)
    return " · ".join(
        f'<a href="{href}#page={p}">trang {p}</a>' for p in pages
    ) or f'<a href="{href}">mở PDF</a>'


def render_view(summary, similarity, assessment):
    e = html.escape
    matches = [m for m in similarity["matches"] if m.get("selected_for_manual_review") or m.get("selected_for_document_coverage")]
    cards = []
    for i, match in enumerate(matches, 1):
        alignment = match["alignment"]
        source_title = (
            "Artificial Intelligence: A Modern Approach"
            if match["source_name"] == "efdd4d1d4c2087fe1cbe03d9ced67f34.pdf"
            else match["source_name"]
        )
        status = match["classification_status"]
        label = match.get("similarity_type") or (
            "Khớp chữ chưa đủ bằng chứng" if match.get("provisional_similarity_type") == "VERBATIM"
            else "Ứng viên liên quan — chưa xác minh"
        )
        cards.append(f'''<article><h3>Cặp {i} · {e(label)}</h3>
<p class="meta">{e(status)} · semantic verification: {e(str(match.get('semantic_verification_status', 'NOT_RUN')))}</p>
<div class="columns"><section><h4>Report · {page_links(alignment['report'], 'report.pdf')}</h4>
<p>{e(alignment['report'].get('text',''))}</p></section>
<section><h4>{e(source_title)} · {page_links(alignment['source'], match['source_name'])}</h4>
<p>{e(alignment['source'].get('text',''))}</p></section></div>
<p class="meta">Dense: {match.get('dense_score')} · Cross-Encoder: {match.get('cross_encoder_score')}.
Đây là điểm xếp hạng, không phải xác suất đạo văn.</p></article>''')
    group_rows = "".join(
        f"<tr><td>{e(str(group['source_name']))}</td><td>{e(group['source_chunk_id'][:12])}…</td><td>{group['report_chunk_count']}</td><td>{'Không phải các bằng chứng độc lập' if group.get('warning') else 'Một cặp cần review'}</td></tr>"
        for group in similarity.get("review_source_groups", [])
    )
    rows, details = [], []
    for q in assessment["checklist_results"]:
        badge = "ok" if q["checklist_outcome"] == "MET" else "pending"
        spans = q.get("matched_evidence_spans", [])
        links = sorted({page_links(x["span"], "report.pdf") for x in spans})
        rows.append(f'<tr><td>{e(q["checklist_id"])}</td><td>{e(q["mode"])}</td><td class="{badge}">{e(q["checklist_outcome"])}</td><td>{"; ".join(links) or "Chưa đủ evidence"}</td></tr>')
        evidence = "".join(
            f'<li><strong>{e(x["requirement_id"])}</strong>: {e(x.get("matched_alternative", ""))} — {page_links(x["span"], "report.pdf")}</li>'
            for x in spans
        )
        excerpts = "".join(
            f'<blockquote>{e(x.get("excerpt", ""))}<br>{page_links(x, "report.pdf")}</blockquote>'
            for x in q.get("evidence_pack", [])
        )
        details.append(f'<details><summary>{e(q["checklist_id"])} · {e(q["checklist_outcome"])}</summary><p>{e(q["statement"])}</p><p>{e(q["rationale"])}</p><ul>{evidence}</ul><h4>Các đoạn được truy xuất</h4>{excerpts}</details>')
    return f'''<!doctype html><html lang="vi"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Kết quả hai pipeline trên report thật</title><style>
body{{font:16px/1.6 system-ui,sans-serif;color:#172c3f;background:#eef3f7;margin:0}}main{{max-width:1120px;margin:auto;padding:36px}}
header,article,details,.panel{{background:white;border:1px solid #dbe3eb;border-radius:12px;padding:24px;margin:18px 0}}
h1{{font-size:30px;line-height:1.3}}h2{{margin-top:38px}}h3,h4{{margin-top:0}}a{{color:#1266a4}}.meta{{font-size:14px;color:#56697c}}
.columns{{display:grid;grid-template-columns:1fr 1fr;gap:24px}}.columns p{{white-space:pre-wrap;overflow-wrap:anywhere}}
table{{width:100%;border-collapse:collapse;background:white}}td,th{{text-align:left;border:1px solid #dbe3eb;padding:10px;font-size:14px;overflow-wrap:anywhere}}
.ok{{color:#18774b;font-weight:700}}.pending{{color:#966500;font-weight:700}}blockquote{{border-left:3px solid #76a5c8;margin:14px 0;padding:12px 20px;background:#f5f9fc}}
summary{{cursor:pointer;font-weight:600}}@media(max-width:750px){{main{{padding:12px}}.columns{{grid-template-columns:1fr}}}}
@media print{{body{{background:white}}article,details{{break-inside:avoid}}}}
</style><main><header><p class="meta">KLTN · 523H0087 / 52200229 · 19/10/2026</p>
<h1>Chạy report thật qua hai pipeline</h1><p>Đầu vào: <a href="inputs/report.pdf">report.pdf (5 trang)</a>, ba PDF nguồn và rubric thử nghiệm đã dùng trước đó.</p>
<p>Report trình bày Hill Climbing, Go/Minimax và Sudoku/CSP. Rubric gồm 10 checklist được soạn để kiểm tra luồng xử lý trên report này; chưa phải rubric chuẩn của giảng viên.</p>
<p><a href="outputs/mvp-summary.json">Tổng hợp JSON</a> · <a href="outputs/run-manifest.json">Run manifest</a> · <a href="inputs/{RUBRIC.name}">Rubric</a></p></header>
<h2>Pipeline 1 · Tương đồng và nguồn đối chứng</h2><div class="panel"><p>{summary['pipeline1']['report_chunks']} report chunks → BM25 + E5 trên {summary['pipeline1']['source_chunks']} source chunks → RRF → Cross-Encoder → alignment và tổng hợp.</p>
<p><strong>{summary['pipeline1']['provisional_review_report_chunks']} đoạn cần review</strong>. Exact-match coverage: {summary['pipeline1']['exact_match_coverage_percentage']}%. Chưa có cặp đạt điều kiện VERBATIM tự động. Hệ thống không gán PARAPHRASE/SUMMARY vì chưa chạy bộ xác minh semantic đã được đánh giá.</p>
<p>{summary['pipeline1']['provisional_review_passage_coverage_percentage']}% là tỷ lệ token nằm trong các chunk được đưa vào hàng chờ review, không phải tỷ lệ tương đồng hoặc đạo văn.</p>
<a href="outputs/similarity-report.json">Toàn bộ kết quả Pipeline 1</a></div>
<table><thead><tr><th>Nguồn</th><th>Source chunk</th><th>Số đoạn report</th><th>Lưu ý</th></tr></thead><tbody>{group_rows}</tbody></table>{''.join(cards)}
<h2>Pipeline 2 · Rubric và evidence</h2><div class="panel"><p>Rubric compiler → LOCAL hoặc GRAPH → evidence verification → checklist → quy tắc điểm.</p>
<p><strong>{assessment['checklist_outcome_counts'].get('MET',0)} MET, {assessment['checklist_outcome_counts'].get('CANNOT_ASSESS',0)} CANNOT_ASSESS.</strong> Điểm tổng: chưa đề xuất; requires_lecturer_review = true.</p>
<p>Verification hiện đối chiếu các yêu cầu cụm từ đã khai báo trong rubric. LOCAL dùng retrieval/reranking; GRAPH dùng BM25 seeds và Personalized PageRank trên liên kết cấu trúc/từ vựng. Evidence nằm trong report; bước này chưa kiểm tra tính đúng của claim bằng PDF nguồn bên ngoài.</p>
<a href="outputs/assessment-report.json">Toàn bộ kết quả Pipeline 2</a></div>
<table><thead><tr><th>Checklist</th><th>Route</th><th>Kết quả</th><th>Trang evidence</th></tr></thead><tbody>{''.join(rows)}</tbody></table>{''.join(details)}
<footer class="meta">Bản xem được tạo từ các JSON của lượt chạy {summary['timings_seconds']['total_seconds']:.2f} giây. Nội dung PDF được giữ nguyên; links trang dùng số trang vật lý bắt đầu từ 1. Giải nén ZIP trước khi mở.</footer></main></html>'''


def acquisition_inventory(workbook: Path):
    specs = [
        ("MMDocIR", "mmdocir-eval/MMDocIR_annotations.jsonl", "812d14b22d92389a1d9b288c0143b0ffc31fba6d114322e2e75cab2528833e09", "https://huggingface.co/datasets/MMDocIR/MMDocIR_Evaluation_Dataset/resolve/main/MMDocIR_annotations.jsonl"),
        ("MMDocIR", "mmdocir-eval/doc_pdfs.rar", "360e0c7907f1c78012bbc9016623a0ec0d05cb3308ec6ded7c8b46e582b785df", "https://huggingface.co/datasets/MMDocIR/MMDocIR_Evaluation_Dataset/resolve/main/doc_miscellaneous/doc_pdfs.rar"),
        ("HoVer", "hover-v1.1/hover_dev_release_v1.1.json", "67c14858f2d7fcdb96b6fe3d538ffcd6f76e3ba594aa2c0cd4359f601101e89d", "https://raw.githubusercontent.com/hover-nlp/hover/main/data/hover/hover_dev_release_v1.1.json"),
        ("HoVer", "hover-v1.1/hover_train_release_v1.1.json", "1f1cd57abd616fa00c70bdc575ce77c16fc6cf1a6cffd5ff87c208030a336bb6", "https://raw.githubusercontent.com/hover-nlp/hover/main/data/hover/hover_train_release_v1.1.json"),
        ("HoVer", "hover-v1.1/hover_test_release_v1.1.json", "c58e7fc59b4962213a5a6d41d746384ee88a7645e36cb3a439969cf762c8ec24", "https://raw.githubusercontent.com/hover-nlp/hover/main/data/hover/hover_test_release_v1.1.json"),
        ("HoVer", "hover-v1.1/wiki_wo_links.db", "b188928e7cea71d6cc2f27a771ccf993ba8cff0f2df6708c3ce6a9a048298328", "https://nlp.cs.unc.edu/data/hover/wiki_wo_links.db"),
        ("HARMOGEN-R v1", "harmogen-r-v1/harmogenr_dataset_v1.zip", "70c8354490e58b7e0da11a4b7f2cfae18b7070af063666585845f3c1761e2b5a", "https://zenodo.org/records/17284944/files/harmogenr_dataset_v1.zip?download=1"),
    ]
    files = []
    for dataset, relative, expected, url in specs:
        path = REPO / "var/datasets/raw" / relative
        quarantined = path.with_name(path.stem + ".checksum-mismatch" + path.suffix)
        if not path.is_file() and quarantined.is_file():
            path = quarantined
        actual = digest(path) if path.is_file() else None
        status = (
            "NOT_COMPLETE" if actual is None else
            "DOWNLOADED_CHECKSUM_MATCH" if actual == expected else
            "CHECKSUM_MISMATCH_QUARANTINED"
        )
        files.append({"dataset": dataset, "file": relative, "local_file": path.relative_to(REPO).as_posix(), "official_url": url, "expected_sha256_from_workbook": expected, "sha256": actual, "status": status, "eligible_for_experiment": status == "DOWNLOADED_CHECKSUM_MATCH", "bytes": path.stat().st_size if actual else None})
    return {"workbook": workbook.name, "workbook_sha256": digest(workbook), "mapping_sheet": "Dataset mapping", "mapping_rows": [6,7,8], "approval_as_recorded_in_workbook": {"rights_status": "APPROVED", "approver": "Yến"}, "files": files, "use_in_this_submission": "MMDocIR: fixed 5-document / 7 text-only query LOCAL pilot. HoVer and HARMOGEN-R: acquisition and checksum verification; no model evaluation yet. PAN-PC-11 and QASPER benchmark outputs retained separately."}


def parse_args():
    parser = argparse.ArgumentParser(
        description="Build the private weekly package from an already verified run."
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        required=True,
        help="Directory containing report.pdf and source/*.pdf.",
    )
    parser.add_argument(
        "--workbook",
        type=Path,
        required=True,
        help="Dataset-mapping workbook used to record approval and checksums.",
    )
    parser.add_argument(
        "--base-dataset-zip",
        type=Path,
        required=True,
        help="Previously generated dataset-only weekly package.",
    )
    parser.add_argument(
        "--previous-report-package",
        type=Path,
        required=True,
        help="Private prior package containing the exact MMDocIR code snapshot.",
    )
    parser.add_argument(
        "--run-dir",
        type=Path,
        required=True,
        help="Completed Core MVP run directory.",
    )
    parser.add_argument(
        "--mmdocir-run-dir",
        type=Path,
        required=True,
        help="Completed MMDocIR pilot run directory.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    input_dir = args.input_dir.resolve()
    workbook = args.workbook.resolve()
    base_dataset_zip = args.base_dataset_zip.resolve()
    previous_report_package = args.previous_report_package.resolve()
    run_dir = args.run_dir.resolve()
    mmdocir_run_dir = args.mmdocir_run_dir.resolve()
    if STAGE.exists() or ARCHIVE.exists():
        raise FileExistsError("Refusing to overwrite an existing private submission")
    summary = read_json(run_dir / "mvp-summary.json")
    similarity = read_json(run_dir / "similarity-report.json")
    assessment = read_json(run_dir / "assessment-report.json")
    manifest = read_json(run_dir / "run-manifest.json")
    if summary["pipeline"] != "both" or manifest["selected_pipeline"] != "both":
        raise ValueError("Expected a completed both-pipeline run")
    inputs = manifest["inputs"]
    if digest(input_dir / "report.pdf") != inputs["report"]["sha256"]:
        raise ValueError("Report differs from executed input")
    for source in inputs["sources"]:
        if digest(input_dir / "source" / source["source_name"]) != source["sha256"]:
            raise ValueError("Source differs from executed input")
    if digest(CONFIG) != inputs["config"]["sha256"] or digest(RUBRIC) != inputs["rubric"]["sha256"]:
        raise ValueError("Run config/rubric has changed")
    for value in manifest["outputs"].values():
        if digest(run_dir / value["name"]) != value["sha256"]:
            raise ValueError("Run output checksum mismatch")
    mm = read_json(mmdocir_run_dir / "metrics.json")
    mm_manifest = read_json(mmdocir_run_dir / "run-manifest.json")
    if digest(mmdocir_run_dir / "metrics.json") != mm_manifest["metrics_sha256"]:
        raise ValueError("MMDocIR metric checksum mismatch")
    STAGE.mkdir(parents=True)
    with ZipFile(base_dataset_zip) as archive:
        prefix = base_dataset_zip.stem + "/"
        inventory = json.loads(archive.read(prefix + "package-manifest.json"))
        for item in inventory["files"]:
            relative = item["path"]
            if relative.startswith("00_BaoCaoTuan/") or relative in {
                "README.md", "package-manifest.json"
            }:
                continue
            if PurePosixPath(relative).is_absolute() or ".." in PurePosixPath(relative).parts:
                raise ValueError("Unsafe path in base package")
            data = archive.read(prefix + relative)
            if hashlib.sha256(data).hexdigest() != item["sha256"]:
                raise ValueError("Base package checksum mismatch")
            destination = STAGE / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(data)
    copy(input_dir / "report.pdf", "04_ReportThat/inputs/report.pdf")
    for source in inputs["sources"]:
        copy(input_dir / "source" / source["source_name"], "04_ReportThat/inputs/sources/" + source["source_name"])
    copy(CONFIG, "04_ReportThat/inputs/" + CONFIG.name)
    copy(RUBRIC, "04_ReportThat/inputs/" + RUBRIC.name)
    for name in ("similarity-report.json", "assessment-report.json", "mvp-summary.json", "run-manifest.json"):
        copy(run_dir / name, "04_ReportThat/outputs/" + name)
    for name in ("metrics.json", "run-manifest.json"):
        copy(mmdocir_run_dir / name, "05_MMDocIR_LOCAL/" + name)
    copy(REPO / "docs/benchmarks/mmdocir-local-text-pilot-result.md", "05_MMDocIR_LOCAL/mmdocir-local-text-pilot-result.md")
    copy(REPO / "docs/benchmarks/pipeline1-unverified-candidate-regression.md", "04_ReportThat/DOI_CHIEU_SUA_LOI_PIPELINE_1.md")
    copy(CONFIG, "03_MaNguon/research/configs/" + CONFIG.name)
    for directory in ("research/core_mvp", "research/offline_retrieval", "services/backend/src/kltn_ai/integrations/parsing", "services/backend/src/kltn_ai/integrations/indexing"):
        for source in (REPO / directory).glob("*.py"):
            copy(source, "03_MaNguon/" + source.relative_to(REPO).as_posix())
    copy(REPO / "research/core_mvp/README.md", "03_MaNguon/research/core_mvp/README.md")
    for source in (REPO / "research/tests").glob("test_core_mvp*.py"):
        copy(source, "03_MaNguon/research/tests/" + source.name)
    copy(REPO / "research/tests/test_similarity_unverified_candidates.py", "03_MaNguon/research/tests/test_similarity_unverified_candidates.py")
    for source in (REPO / "research/tests/fixtures/core_mvp").iterdir():
        if source.is_file():
            copy(source, "03_MaNguon/research/tests/fixtures/core_mvp/" + source.name)
    # The MMDocIR pilot predates the Pipeline 1 verification-boundary fix.
    # Keep the exact executed source snapshot under its own result directory;
    # current Core MVP code remains in 03_MaNguon for reproducing the report run.
    with ZipFile(previous_report_package) as previous:
        previous_prefix = previous_report_package.stem + "/"
        previous_manifest = json.loads(previous.read(previous_prefix + "package-manifest.json"))
        previous_hashes = {item["path"]: item["sha256"] for item in previous_manifest["files"]}
        for relative, expected in mm_manifest["code_sha256"].items():
            archived_relative = "03_MaNguon/" + relative
            data = previous.read(previous_prefix + archived_relative)
            actual = hashlib.sha256(data).hexdigest()
            if previous_hashes.get(archived_relative) != actual or actual != expected:
                raise ValueError(f"Previous package does not contain the executed MMDocIR snapshot: {relative}")
            destination = STAGE / "05_MMDocIR_LOCAL/code_snapshot" / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(data)
    requirements = sorted({f"{d.metadata['Name']}=={d.version}" for d in importlib.metadata.distributions() if d.metadata.get("Name")})
    write("03_MaNguon/requirements-observed.txt", "\n".join(requirements) + "\n")
    acquisition = acquisition_inventory(workbook)
    write("00_BaoCaoTuan/dataset-sources-and-checksums.json", json.dumps(acquisition,ensure_ascii=False,indent=2)+"\n")
    acquisition_labels = {
        "DOWNLOADED_CHECKSUM_MATCH": "Đã tải, checksum khớp Excel",
        "NOT_COMPLETE": "Chưa tải hoàn tất",
        "CHECKSUM_MISMATCH_QUARANTINED": "Đã tải; checksum khác Excel, tách riêng và chưa dùng thực nghiệm",
    }
    acquisition_table = "\n".join(f"| {x['dataset']} | `{Path(x['file']).name}` | {acquisition_labels[x['status']]} |" for x in acquisition['files'])
    write("00_BaoCaoTuan/NGUON_DU_LIEU_VA_CHECKSUM.md", "# Nguồn dữ liệu và checksum\n\nĐây là phụ lục tái lập, không phải một kết quả thực nghiệm riêng. Sheet `Dataset mapping`, dòng 6–8, ghi link, rights status APPROVED và approver Yến. File `dataset-sources-and-checksums.json` lưu URL chính thức, phiên bản/checksum và trạng thái tiếp nhận để xác định chính xác dữ liệu đã dùng. Raw corpus không được đóng vào ZIP.\n\n| Dataset | File | Trạng thái |\n|---|---|---|\n"+acquisition_table+"\n\nMMDocIR có 313 tài liệu và 1.658 câu hỏi; HoVer dev có 4.000 claims; HARMOGEN-R giữ v1 đúng bản trong Excel. MMDocIR đã chạy pilot text-only tại `05_MMDocIR_LOCAL`; HoVer và HARMOGEN-R mới ở bước tiếp nhận dữ liệu. SQLite corpus HoVer tải đủ và đọc được cấu trúc nhưng checksum khác bản ghi trong Excel, nên đã tách riêng và chưa dùng chạy thí nghiệm.\n")
    mm_rows = "\n".join(f"| `{d['file']}` | {d['pages']} | {d['chunks']} |" for d in mm['selection']['selected_documents'])
    write("05_MMDocIR_LOCAL/README.md", f'''# MMDocIR — kiểm thử LOCAL trên PDF thật

Chọn cố định 5 tài liệu có câu hỏi text-only bằng SHA256(seed:doc_name), seed
20261018; giữ toàn bộ câu thuộc hai type `text-only` và `['Pure-text (Plain-text)']`
trong các tài liệu đó. Tổng cộng {mm['query_count']} câu. Không chọn theo kết quả chạy.

| PDF | Số trang | Số chunks |
|---|---:|---:|
{mm_rows}

Code gọi đúng `_rank_local` của Pipeline 2, với PDF đi qua parser/chunker hiện
có. So sánh BM25-only và BM25 + E5 + RRF + Cross-Encoder, cùng cấu hình
candidate_depth=12, rerank_depth=8, top_k=5 và chunking 220/30.
Query chỉ gồm câu hỏi Q; A và gold page_id chỉ dùng sau retrieval để chấm.
Không sinh rubric hoặc dùng đáp án làm query.

Cả hai cấu hình tìm đủ trang gold trong union các trang của Top-5 evidence
chunks ở **7/7 câu**. Ba chỉ số any-gold-page hit, gold-page recall và
all-gold-pages-found đều bằng 1,0. Đây là phép kiểm tra nhỏ, chưa thấy khác biệt
giữa BM25 và hybrid. Chỉ số là **page coverage của Top-5 chunks**, không phải
official page-ranking Recall@5, bbox overlap hay chất lượng trả lời câu hỏi.
Thời gian: {mm_manifest['total_wall_seconds']:.2f} giây. Toàn bộ từng query ID,
gold pages và retrieved pages có trong `metrics.json` (không có nội dung PDF).

Để chạy lại: tải `MMDocIR_annotations.jsonl` và `doc_pdfs.rar` theo
`../00_BaoCaoTuan/dataset-sources-and-checksums.json`. Source snapshot chính
xác của lượt chạy nằm tại `code_snapshot`; sao chép nội dung thư mục đó vào
repo tương ứng, đặt raw data tại `var/datasets/raw/mmdocir-eval`, cài `unar`,
cache hai model theo config rồi chạy `python -m research.mmdocir_pilot`.
Script xác minh checksum và tự giải nén đúng 5 PDF đã chọn. Lượt chạy này chưa
đánh giá câu hỏi cần hình ảnh/bảng/layout hoặc tính đúng của claim.
''')
    write("04_ReportThat/XEM_KET_QUA.html", render_view(summary,similarity,assessment))
    routes = Counter(q["mode"] for q in assessment["checklist_results"])
    checklist_rows = "\n".join(f"| `{q['checklist_id']}` | {q['mode']} | {q['checklist_outcome']} |" for q in assessment['checklist_results'])
    repeated_groups = summary["pipeline1"].get("repeated_source_review_groups", 0)
    weekly = f'''# BÁO CÁO TIẾN ĐỘ TUẦN — 19/10/2026

**Đề tài:** Hệ thống hỗ trợ kiểm tra tính tương đồng và đánh giá báo cáo dựa trên bằng chứng
**Sinh viên:** 523H0087, 52200229
**Kho mã nguồn toàn bộ dự án:** [GitHub — evidence-grounded-report-assessment]({PROJECT_REPOSITORY})

Gói ZIP đính kèm là **snapshot phục vụ báo cáo tiến độ tuần**, không phải bản
sao đầy đủ của repository. Gói chỉ giữ report/nguồn dùng trong lượt chạy, kết
quả thực nghiệm, manifest và phần source snapshot cần để kiểm tra hoặc tái lập.
Cấu trúc toàn bộ project và lịch sử phiên bản được quản lý tại repository trên.
Raw benchmark corpora và model weights không được đóng vào ZIP.

## 1. Luồng thực thi trên report thật

Nhóm đã chạy cùng một báo cáo PDF thật qua cả hai pipeline. File đầu vào là
`report.pdf` (5 trang, nội dung Hill Climbing, Go/Minimax và Sudoku/CSP),
kèm ba nguồn đối chứng: `Go_(game).pdf` (39 trang), `Sudoku.pdf` (9 trang)
và *Artificial Intelligence: A Modern Approach* (1.166 trang). Report và
ba PDF nguồn giữ nguyên nội dung trong `04_ReportThat/inputs`.

Parser/chunker tạo **{summary['pipeline1']['report_chunks']} report chunks** và
**{summary['pipeline1']['source_chunks']} source chunks**. Pipeline 1 chạy
BM25 + multilingual E5-small → RRF → mMARCO Cross-Encoder → alignment và
document aggregation. Pipeline 2 chạy rubric compiler → LOCAL/GRAPH retrieval
→ evidence verification → checklist → score rule. Cả hai hoàn tất, sinh
Similarity Report, Assessment Report và run manifest; tổng thời gian
**{summary['timings_seconds']['total_seconds']:.2f} giây** trên CPU Apple Silicon.

Mở `04_ReportThat/XEM_KET_QUA.html` để xem các cặp đoạn, evidence của từng
checklist và liên kết đến trang PDF. Các JSON đầy đủ nằm trong thư mục
`04_ReportThat/outputs`.

## 2. Kết quả trên report

### Pipeline 1 — tương đồng

Có **{summary['pipeline1']['provisional_review_report_chunks']} đoạn cần người xem kiểm tra**.
Tỷ lệ token thuộc các chunk cần review là
{summary['pipeline1']['provisional_review_passage_coverage_percentage']:.2f}%; đây là khối lượng review,
không phải tỷ lệ tương đồng hoặc đạo văn. Chưa có cặp đạt điều kiện tự động
xác nhận VERBATIM; exact-match coverage là
{summary['pipeline1']['exact_match_coverage_percentage']:.1f}%.

Sau khi rà soát đầu ra, nhóm phát hiện 7/8 ứng viên cùng trỏ vào một source
chunk Sudoku, kể cả một chunk chứa caption/phân công. Retrieval score và độ
dài văn bản không đủ chứng minh PARAPHRASE hoặc SUMMARY. Nhóm đã sửa policy:
các ứng viên semantic vẫn được giữ cùng evidence để review, nhưng hai trường
nhãn đều để null và ghi `semantic_verification_status = NOT_RUN`. Các cặp
cùng source chunk được gom nhóm, không bị xóa; có {repeated_groups} nhóm lặp
được cảnh báo là không phải các bằng chứng độc lập. Lượt chạy lại giữ nguyên
toàn bộ 72 rank/score/features/alignment, chỉ sửa ranh giới kết luận.

### Pipeline 2 — rubric và bằng chứng

Rubric thử nghiệm gồm 4 tiêu chí, 10 checklist: {routes['LOCAL']} LOCAL và
{routes['GRAPH']} GRAPH. Kết quả là **9 MET, 1 CANNOT_ASSESS**. Mục
`REPORT_EVIDENCE.GO_LATENCY` chưa tìm được evidence thỏa yêu cầu về thời gian
phản hồi Go tính bằng milliseconds, nên hệ thống để trống điểm tổng và bật
`requires_lecturer_review`.

| Checklist | Route | Kết quả |
|---|---|---|
{checklist_rows}

Rubric này đã được soạn dựa trên nội dung report để kiểm tra luồng thực thi,
chưa phải rubric môn học được giảng viên ban hành. Verification hiện kiểm tra
cụm từ/yêu cầu đã khai báo và phủ định gần; GRAPH dùng BM25 seeds và
Personalized PageRank trên liên kết cấu trúc/từ vựng. Kết quả chứng minh hai
luồng xử lý hiện có chạy đến đầu ra và truy ngược evidence được. Chất lượng
chấm cần đánh giá tiếp bằng rubric độc lập và nhãn người chấm. Pipeline 2
trong lượt này chỉ lấy evidence trong report, chưa đối chiếu claim với ba PDF
nguồn bên ngoài. Cross-Encoder ghi nhận 59/248 cặp bị truncation; thông tin này
được giữ trong manifest để tiếp tục sửa độ dài đầu vào.

## 3. Thực nghiệm dataset

Nhóm giữ kết quả dataset bên cạnh lượt chạy report thật để theo dõi cả khả
năng thực thi lẫn chất lượng từng thành phần.

| Dataset / phạm vi | Thiết kế | Kết quả chính |
|---|---|---|
| PAN-PC-11 DEV0 / P1 source retrieval | 30 parent annotations, 320 query windows, 200 sources; A1–A5 | Parent-balanced Recall@10: BM25 0,8594; Dense 0,8219; RRF 0,8300; Dense+CE 0,6597; RRF+CE 0,7558 |
| QASPER v0.3 dev / P2 LOCAL paragraph retrieval | 281 papers, 1.005 questions; 646 câu đủ gold văn bản sau lọc | Hit@10: BM25 0,7693; E5 0,8669; RRF 0,8715 |
| MMDocIR / P2 LOCAL trên PDF | Chọn cố định 5 PDF bằng seed; 7 câu hỏi text-only; chạy parser/chunker và đúng hàm LOCAL của hệ thống | Cả BM25 và BM25+E5+RRF+CE tìm đủ trang gold trong Top-5 evidence chunks ở 7/7 câu |

PAN là lượt chạy ngày 01/10, được giữ nguyên; QASPER là lượt chạy ngày 18/10.
Ở PAN, cấu hình Cross-Encoder hiện tại làm giảm Top-10, nên cần sửa candidate
gating và truncation. Ở QASPER, RRF có Hit@10 cao nhất nhưng E5 có độ bao phủ
đủ bộ evidence cao hơn (0,7430 so với 0,7245). Nhóm chưa kết luận RRF tốt hơn
trên mọi chỉ số. Protocol, metric, cấu hình và manifest nằm ở
`01_Pipeline1_PAN_PC11` và `02_Pipeline2_QASPER`.
MMDocIR dùng 5 PDF dài tổng cộng 190 trang và có kết quả tại
`05_MMDocIR_LOCAL`. Ở pilot nhỏ này hai cấu hình cùng đạt 7/7, chưa cho thấy
hybrid tốt hơn BM25. Phép đo là coverage trang gold trong Top-5 chunks, không
phải official page-ranking Recall@5 hoặc bbox overlap.

## 4. Dataset đã xác định trong Excel

Sheet `Dataset mapping`, dòng 6–8, đã có link MMDocIR, HoVer, HARMOGEN-R,
quyền sử dụng APPROVED và người duyệt Yến. Nhóm đã kiểm tra lại các link
chính thức và tiếp nhận dữ liệu theo checksum ghi trong Excel:

| Dataset | File | Trạng thái |
|---|---|---|
{acquisition_table}

Các file tải được lưu local; ZIP chỉ giữ phụ lục nguồn/checksum tại
`00_BaoCaoTuan/NGUON_DU_LIEU_VA_CHECKSUM.md`, không đóng raw corpus. Phụ lục
này dùng để tái lập và không được tính như một kết quả thực nghiệm. MMDocIR phục vụ evidence retrieval trên PDF dài, HoVer
phục vụ multi-hop verification và HARMOGEN-R phục vụ rubric/human agreement.
MMDocIR đã có pilot text-only nêu trên; HoVer và HARMOGEN-R mới ở bước
tiếp nhận/kiểm tra dữ liệu, chưa có metric chạy mô hình trong gói này.
Riêng SQLite corpus HoVer tải đủ dung lượng và qua kiểm tra cấu trúc SQLite,
nhưng SHA-256 khác bản ghi tự tính trong Excel. File được tách riêng, chưa dùng
thực nghiệm; cần đối chiếu với bản đã mapping trước khi khóa phiên bản corpus.
Kết quả QASPER hiện vẫn được giữ là phép đo bổ sung.

## 5. Phần đang hoàn thiện

Nhóm ưu tiên nối dataset adapter cho các bộ đã tải, hoàn thiện verification
ngữ nghĩa và đánh giá bằng rubric độc lập. Với Pipeline 1, cần tiếp tục đo
false positives và paraphrase trên bộ cặp gán nhãn; với Pipeline 2, cần đối
chiếu điểm với giảng viên và kiểm tra claim bằng nguồn bên ngoài. Lượt chạy
report hiện tại cung cấp một đầu vào thật cùng hai đầu ra có thể kiểm tra
trực tiếp, đồng thời giữ các trạng thái chưa đủ evidence để review.
'''
    write("00_BaoCaoTuan/BaoCaoTuan_KLTN_523H0087_52200229_19-10-2026.md", weekly)
    write("README.md", '''# Báo cáo tuần — dataset và report thật

**523H0087 · 52200229 · 19/10/2026 · bản V2**

## Phạm vi gói nộp

Đây là **bản đóng gói để nộp báo cáo tuần cho GVHD**, không phải file export
toàn bộ repository. ZIP tập trung vào những nội dung cần xem trong tuần này:
report và nguồn đã chạy, output của hai pipeline, kết quả dataset, manifest,
checksum và source snapshot phục vụ tái lập. Raw benchmark corpora và model
weights không có trong gói.

**Toàn bộ project và lịch sử phiên bản:**
[GitHub — evidence-grounded-report-assessment](https://github.com/ngwine/evidence-grounded-report-assessment)

Nếu repository đang để private, cần cấp quyền GitHub cho GVHD để mở link.

Giải nén toàn bộ ZIP, rồi mở:

1. `00_BaoCaoTuan/BaoCaoTuan_KLTN_523H0087_52200229_19-10-2026.md`: báo cáo tuần.
2. `04_ReportThat/XEM_KET_QUA.html`: bản xem kết quả hai pipeline trên report thật, kèm evidence và link trang PDF.
3. `01_Pipeline1_PAN_PC11`, `02_Pipeline2_QASPER`: số liệu dataset, protocol và manifest.
4. `05_MMDocIR_LOCAL`: pilot trên 5 PDF thật / 7 câu hỏi, dùng nhánh LOCAL hiện có.

Nguồn tải, checksum và trạng thái tiếp nhận MMDocIR/HoVer/HARMOGEN-R nằm ở
`00_BaoCaoTuan/NGUON_DU_LIEU_VA_CHECKSUM.md`. Đây là phụ lục tái lập dữ liệu,
không phải một hạng mục kết quả riêng.

`04_ReportThat/inputs` có report PDF nguyên bản, ba PDF nguồn, rubric thử nghiệm và config đã chạy.
`04_ReportThat/outputs` chứa bốn JSON của lượt chạy V2; không dùng lại output cũ từng báo điểm 10/10 hoặc gợi ý PARAPHRASE/SUMMARY thiếu bước xác minh.
Rubric dùng để kiểm tra phần mềm trên report này, chưa phải rubric giảng viên hay nhãn chuẩn.
`04_ReportThat/DOI_CHIEU_SUA_LOI_PIPELINE_1.md` ghi đối chiếu trước–sau.

## Chạy lại report qua hai pipeline

Cài Python 3.12 và dependency trong `03_MaNguon/research/requirements-research.txt`.
Danh sách phiên bản của môi trường đã chạy được lưu ở `03_MaNguon/requirements-observed.txt`.
Tải/cache hai model đúng revision trong config: multilingual E5-small và mMARCO Cross-Encoder.
Từ thư mục `03_MaNguon`, chạy:

```bash
python -m research.core_mvp \\
  --report ../04_ReportThat/inputs/report.pdf \\
  --source '../04_ReportThat/inputs/sources/Go_(game).pdf' \\
  --source ../04_ReportThat/inputs/sources/Sudoku.pdf \\
  --source ../04_ReportThat/inputs/sources/efdd4d1d4c2087fe1cbe03d9ced67f34.pdf \\
  --rubric ../04_ReportThat/inputs/core-mvp-ai-course-report-rubric-v0.json \\
  --config ../04_ReportThat/inputs/core-mvp-v0.json \\
  --pipeline both --output-dir ../ket-qua-chay-lai
```

Nếu model được cache tại vị trí riêng, đặt `HF_HOME` tương ứng trước khi chạy.
Runner dùng model local, không gọi dịch vụ LLM. Phần parser/chunker được đính kèm trong `03_MaNguon/services`.

## Chạy lại dataset

QASPER: tải official dev v0.3 và kiểm tra SHA-256 trong manifest, rồi từ
`03_MaNguon` chạy `python -m research.qasper_pilot --input /path/qasper-dev-v0.3.json --dense --max-papers 281 --output-dir ../qasper-reproduction`.
PAN: cần tải và tạo derived corpus/manifest theo protocol, dùng cấu hình khóa
trong `01_Pipeline1_PAN_PC11/config` với code `03_MaNguon/P1_snapshot`.
Corpus benchmark và model weights không có trong ZIP.

Gói được chuẩn bị để nộp trực tiếp cho GVHD theo yêu cầu của người cung cấp report;
có report và trích đoạn nguồn, không được đưa tự động lên Git/public.
`package-manifest.json` ghi checksum toàn bộ file và nguồn ZIP dataset đã dùng.
''')
    files = sorted(p for p in STAGE.rglob("*") if p.is_file())
    package_manifest = {"schema_version": 3, "package_name": NAME, "project_repository_url": PROJECT_REPOSITORY, "package_scope": "WEEKLY_SUPERVISOR_SUBMISSION_SNAPSHOT_NOT_FULL_REPOSITORY", "supersedes_local_package": previous_report_package.name, "contains_student_report": True, "contains_report_source_pdfs": True, "contains_model_weights": False, "contains_raw_benchmark_corpora": False, "purpose": "User-requested private weekly submission to supervisor", "base_dataset_zip_sha256": digest(base_dataset_zip), "mmdocir_snapshot_source_zip_sha256": digest(previous_report_package), "real_report_run_id": manifest["run_id"], "files": [{"path":p.relative_to(STAGE).as_posix(),"bytes":p.stat().st_size,"sha256":digest(p)} for p in files]}
    write("package-manifest.json", json.dumps(package_manifest,ensure_ascii=False,indent=2)+"\n")
    with ZipFile(ARCHIVE,"x",compression=ZIP_DEFLATED,compresslevel=6) as archive:
        for source in sorted(p for p in STAGE.rglob("*") if p.is_file()):
            archive.write(source,arcname=NAME+"/"+source.relative_to(STAGE).as_posix())
    print(f"ZIP: {ARCHIVE}\nSIZE: {ARCHIVE.stat().st_size}\nSHA256: {digest(ARCHIVE)}")


if __name__ == "__main__":
    main()
