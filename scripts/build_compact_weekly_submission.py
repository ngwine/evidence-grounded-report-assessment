"""Build the ELIT weekly package under the 20 MB upload limit.

The executed report run used three source PDFs.  One source is a 32.8 MB
textbook PDF which alone exceeds ELIT's limit after compression.  This
builder copies the verified V2 package, omits only that large binary, keeps
its checksum/provenance, and rewrites local links to an omission note.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from shutil import copytree
from zipfile import ZIP_DEFLATED, ZipFile


REPO = Path(__file__).resolve().parents[1]
SOURCE_NAME = "BaoCaoTuan_KLTN_523H0087_52200229_19-10-2026_DATASET_VA_REPORT_V2"
# The validated package was later copied to this shorter staging-directory name
# so the user-facing ZIP could keep a concise filename.
SOURCE = REPO / "var/submission/BaoCaoTuan_KLTN_523H0087_52200229"
SOURCE_ARCHIVE = REPO / "var/submission" / f"{SOURCE_NAME}.zip"
OUTPUT_NAME = "BaoCaoTuan_KLTN_523H0087_52200229_DUOI_20MB"
OUTPUT = REPO / "var/submission" / OUTPUT_NAME
ARCHIVE = OUTPUT.with_suffix(".zip")
LARGE_SOURCE = Path("04_ReportThat/inputs/sources/efdd4d1d4c2087fe1cbe03d9ced67f34.pdf")
LIMIT_BYTES = 20 * 1024 * 1024


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def replace_text(path: Path, replacements: list[tuple[str, str]]) -> None:
    value = path.read_text(encoding="utf-8")
    for old, new in replacements:
        if old not in value:
            raise ValueError(f"Expected text not found in {path}: {old!r}")
        value = value.replace(old, new)
    path.write_text(value, encoding="utf-8")


def main() -> None:
    if not SOURCE.is_dir():
        raise FileNotFoundError(f"Verified V2 staging directory is missing: {SOURCE}")
    if OUTPUT.exists() or ARCHIVE.exists():
        raise FileExistsError("Refusing to overwrite an existing compact submission")

    source_manifest_path = SOURCE / "package-manifest.json"
    source_manifest = json.loads(source_manifest_path.read_text(encoding="utf-8"))
    listed = {item["path"]: item for item in source_manifest["files"]}
    large_key = LARGE_SOURCE.as_posix()
    large_path = SOURCE / LARGE_SOURCE
    if large_key not in listed or not large_path.is_file():
        raise ValueError("Large source PDF is not present in the verified V2 package")
    if digest(large_path) != listed[large_key]["sha256"]:
        raise ValueError("Large source PDF no longer matches the V2 manifest")

    copytree(
        SOURCE,
        OUTPUT,
        ignore=lambda _directory, names: set(names).intersection(
            {LARGE_SOURCE.name, ".DS_Store"}
        ),
    )

    note_relative = Path("00_BaoCaoTuan/TEP_NGUON_LON_KHONG_DINH_KEM.md")
    note = OUTPUT / note_relative
    note.write_text(
        "# Tệp nguồn lớn không đóng trong ZIP\n\n"
        "Bản nộp này phải nhỏ hơn giới hạn **20 MB** của ELIT. Lượt chạy thực tế "
        "đã dùng đủ ba PDF nguồn, nhưng tệp sau được lược khỏi ZIP vì một mình "
        "nó đã vượt giới hạn sau khi nén:\n\n"
        f"- Tên tệp: `{LARGE_SOURCE.name}`\n"
        f"- Dung lượng: {large_path.stat().st_size:,} bytes\n"
        f"- SHA-256: `{digest(large_path)}`\n"
        "- Vai trò: nguồn đối chứng *Artificial Intelligence: A Modern Approach*\n\n"
        "Các đoạn evidence đã truy xuất từ nguồn này, page/span, điểm xếp hạng và "
        "kết quả của lượt chạy vẫn được giữ nguyên trong `04_ReportThat/outputs` "
        "và `04_ReportThat/XEM_KET_QUA.html`. Việc lược tệp chỉ nhằm đáp ứng giới "
        "hạn tải lên, không chạy lại hoặc thay đổi kết quả. Muốn tái lập chính xác, "
        "đặt lại PDF có cùng SHA-256 vào `04_ReportThat/inputs/sources/`.\n\n"
        "Toàn bộ mã nguồn dự án: "
        "https://github.com/ngwine/evidence-grounded-report-assessment\n",
        encoding="utf-8",
    )

    reports = list((OUTPUT / "00_BaoCaoTuan").glob("BaoCaoTuan_KLTN_*.md"))
    if len(reports) != 1:
        raise ValueError(f"Expected one weekly report, found: {reports}")
    report = reports[0]
    replace_text(report, [
        (
            "Report và\nba PDF nguồn giữ nguyên nội dung trong `04_ReportThat/inputs`.",
            "Report và hai PDF nguồn nhỏ được giữ trong `04_ReportThat/inputs`. "
            "Nguồn sách 32,8 MB đã được dùng khi chạy nhưng không đóng vào bản "
            "nộp do giới hạn 20 MB; checksum và cách tái lập nằm tại "
            "`00_BaoCaoTuan/TEP_NGUON_LON_KHONG_DINH_KEM.md`.",
        ),
        (
            "report/nguồn dùng trong lượt chạy, kết\nquả thực nghiệm",
            "report, các nguồn nhỏ, thông tin định danh nguồn lớn, kết\nquả thực nghiệm",
        ),
    ])

    readme = OUTPUT / "README.md"
    replace_text(readme, [
        (
            "report và nguồn đã chạy, output của hai pipeline, kết quả dataset, manifest,",
            "report, hai nguồn PDF nhỏ, thông tin nguồn lớn đã dùng, output của hai pipeline, kết quả dataset, manifest,",
        ),
        (
            "`04_ReportThat/inputs` có report PDF nguyên bản, ba PDF nguồn, rubric thử nghiệm và config đã chạy.",
            "`04_ReportThat/inputs` có report PDF nguyên bản, hai PDF nguồn nhỏ, rubric thử nghiệm và config đã chạy. Nguồn sách 32,8 MB đã dùng khi chạy được thay bằng checksum và hướng dẫn tại `00_BaoCaoTuan/TEP_NGUON_LON_KHONG_DINH_KEM.md` để ZIP đáp ứng giới hạn 20 MB của ELIT.",
        ),
        (
            "Đây là **bản đóng gói để nộp báo cáo tuần cho GVHD**, không phải file export",
            "Đây là **bản đóng gói dung lượng dưới 20 MB để nộp báo cáo tuần cho GVHD**, không phải file export",
        ),
    ])

    html_path = OUTPUT / "04_ReportThat/XEM_KET_QUA.html"
    html_value = html_path.read_text(encoding="utf-8")
    href_pattern = r'inputs/sources/efdd4d1d4c2087fe1cbe03d9ced67f34\.pdf#page=\d+'
    html_value, replaced = re.subn(
        href_pattern,
        "../00_BaoCaoTuan/TEP_NGUON_LON_KHONG_DINH_KEM.md",
        html_value,
    )
    if replaced == 0:
        raise ValueError("No large-PDF links found in rendered HTML")
    banner = (
        '<div class="panel"><strong>Lưu ý bản nộp dưới 20 MB:</strong> '
        'nguồn sách 32,8 MB đã dùng khi chạy không nằm trong ZIP; checksum và '
        'cách tái lập có tại <a href="../00_BaoCaoTuan/TEP_NGUON_LON_KHONG_DINH_KEM.md">ghi chú nguồn lớn</a>. '
        'Evidence trích xuất và kết quả vẫn được giữ nguyên.</div>'
    )
    marker = "<h2>Pipeline 1 · Tương đồng và nguồn đối chứng</h2>"
    if marker not in html_value:
        raise ValueError("Could not find insertion point in rendered HTML")
    html_path.write_text(html_value.replace(marker, banner + marker, 1), encoding="utf-8")

    copied_manifest = OUTPUT / "package-manifest.json"
    copied_manifest.unlink()
    files = sorted(path for path in OUTPUT.rglob("*") if path.is_file())
    compact_manifest = {
        **{key: value for key, value in source_manifest.items() if key != "files"},
        "schema_version": 4,
        "package_name": OUTPUT_NAME,
        "package_scope": "WEEKLY_SUPERVISOR_SUBMISSION_UNDER_20MB_NOT_FULL_REPOSITORY",
        "derived_from_package": SOURCE_NAME + ".zip",
        "derived_from_package_sha256": digest(SOURCE_ARCHIVE),
        "contains_student_report": True,
        "contains_report_source_pdfs": True,
        "contains_all_report_source_pdfs": False,
        "upload_limit_bytes": LIMIT_BYTES,
        "omitted_files": [{
            "path": large_key,
            "bytes": large_path.stat().st_size,
            "sha256": digest(large_path),
            "reason": "ELIT_20MB_UPLOAD_LIMIT",
            "results_unchanged": True,
            "provenance_note": note_relative.as_posix(),
        }],
        "files": [
            {
                "path": path.relative_to(OUTPUT).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": digest(path),
            }
            for path in files
        ],
    }
    copied_manifest.write_text(
        json.dumps(compact_manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    with ZipFile(ARCHIVE, "x", compression=ZIP_DEFLATED, compresslevel=9) as archive:
        for source in sorted(path for path in OUTPUT.rglob("*") if path.is_file()):
            archive.write(source, arcname=OUTPUT_NAME + "/" + source.relative_to(OUTPUT).as_posix())
    if ARCHIVE.stat().st_size >= LIMIT_BYTES:
        raise ValueError(f"Compact package is still too large: {ARCHIVE.stat().st_size} bytes")
    print(f"ZIP: {ARCHIVE}")
    print(f"SIZE: {ARCHIVE.stat().st_size}")
    print(f"SHA256: {digest(ARCHIVE)}")
    print(f"OMITTED: {large_key}")


if __name__ == "__main__":
    main()
