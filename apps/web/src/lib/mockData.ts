import type {
  AdminGovernanceRow,
  AssessmentProposal,
  AuditEventRow,
  CorpusSource,
  DocumentVersion,
  ExperimentRun,
  FeedbackLogEntry,
  JobStageKey,
  JobStatus,
  Membership,
  PipelineStageKey,
  ReportDocument,
  Rubric,
  RubricVersion,
  RubricScoreResult,
  SimilarityMatch,
  TargetedQuestion,
  UserProfile,
  Workspace,
} from "./types";

/**
 * Du lieu gia lap -- dung vai "database" phia backend.
 * Khi API that san sang, xoa file nay va tro `lib/api.ts` sang fetch() that.
 */

export const CURRENT_USER_ID = "u_yen";
/** User gia lap dang dang nhap voi vai tro LECTURER -- dung cho man "Lecturer / Class" */
export const CURRENT_LECTURER_ID = "u_hong";
/** User gia lap dang dang nhap voi system_roles=["ADMIN"] -- dung cho man "Admin" (UC-11) */
export const CURRENT_ADMIN_ID = "u_admin";
/**
 * User gia lap dang dang nhap voi vai Experiment Operator (UC-12, actor
 * RIENG, khac Giang vien/Admin) -- them 2026-11-08. Tai su dung
 * MembershipRole "OPERATOR" da co san trong data-dictionary.md muc 5.3
 * (gan 1 workspace demo, du dataset_manifests/experiment run thuc ra
 * KHONG scope theo workspace -- GIA DINH demo, chi de co 1 membership
 * hop le cho user nay, UI Operator khong dung workspace nay de loc gi
 * ca, xem OperatorRunListPage).
 */
export const CURRENT_OPERATOR_ID = "u_operator";

// ws_1/ws_2: 2 NHOM cung 1 mon "Mobile Apps Development", cung hoc ky
// (cung hoat dong song song, deu "Đang mở") -- SUA LAI 2026-10-29 (Yen
// yeu cau lam ro hon): truoc do workspace_key goi y 2 nien khoa khac
// nhau (de hieu nham la 1 lop cu/1 lop moi), doi lai thanh hau to -N1/-N2
// de the hien dung y "2 lop giong nhau, dang chay cung luc, chi khac ma
// lop (nhom)" -- demo truong hop TRUNG TEN nhung workspace_key KHAC
// NHAU. Theo data-dictionary.md muc 5.2: chi co unique index tren
// {workspace_key} (va {status,_id}), KHONG co unique tren `name` --
// nghia la 2 lop trung ten la HOP LE, chi ma lop (workspace_key) moi la
// dinh danh duy nhat nguoi dung nhin thay (ve mat ky thuat la _id).
export const mockWorkspaces: Workspace[] = [
  {
    _id: "ws_1",
    workspace_key: "MAD-2025-2026-N1",
    kind: "COURSE",
    name: "Mobile Apps Development",
    status: "ACTIVE",
  },
  {
    _id: "ws_2",
    workspace_key: "MAD-2025-2026-N2",
    kind: "COURSE",
    name: "Mobile Apps Development",
    status: "ACTIVE",
  },
];

/**
 * users (data-dictionary.md muc 5.1) -- xem ghi chu GIA DINH ve
 * `student_id` trong lib/types.ts (UserProfile). `email_normalized` o day
 * la email GIA DINH demo (dang <mssv_hoac_ten>@kltn.local), chua xac nhan
 * domain that -- chi de man Admin (UC-11) co cot email de hien/tim kiem.
 */
export const mockUsers: UserProfile[] = [
  {
    _id: CURRENT_USER_ID,
    display_name: "Vo Thi Kim Yen",
    student_id: "52200229",
    email_normalized: "52200229@kltn.local",
    status: "ACTIVE",
  },
  // Giang vien duy nhat cua workspace ws_1 -- truoc day CHI ton tai qua
  // lecturerByWorkspace (ten rieng, khong khop CURRENT_LECTURER_ID), gio
  // dong bo lai thanh 1 UserProfile nhu sinh vien (Yen yeu cau 2026-10-29).
  {
    _id: CURRENT_LECTURER_ID,
    display_name: "Nguyen Van A",
    email_normalized: "nguyenvana@kltn.local",
    // GIA DINH DEMO (them 2026-11-11): tai khoan nay vua LECTURER (qua
    // Membership mb_4) vua co system_roles=["ADMIN"] -- demo truong hop
    // 1 tai khoan co NHIEU diem vao sau dang nhap (xem LoginDestination,
    // lib/types.ts + man hinh "Chon vai tro" trong LoginPage.tsx).
    system_roles: ["ADMIN"],
    status: "ACTIVE",
  },
  // Giang vien cua ws_2 (Nhom 2, MAD-2025-2026-N2) -- Yen yeu cau
  // 2026-10-29: moi nhom gan 1 giang vien rieng, nhom nay CHUA co sinh
  // vien nao ca (chi co GV, chua co membership STUDENT nao trong ws_2).
  {
    _id: "u_lecturer_b",
    display_name: "Vo Van B",
    email_normalized: "vovanb@kltn.local",
    status: "ACTIVE",
  },
  {
    _id: "u_student_b",
    display_name: "Tran Thi B",
    student_id: "52200102",
    email_normalized: "52200102@kltn.local",
    status: "ACTIVE",
  },
  {
    _id: "u_student_c",
    display_name: "Le Van C",
    student_id: "52200103",
    email_normalized: "52200103@kltn.local",
    status: "ACTIVE",
  },
  // Tai khoan Admin duy nhat -- dung cho man "Admin / Quan ly tai khoan"
  // (UC-11). system_roles=["ADMIN"] la vai TOAN HE THONG, khac voi
  // Membership.roles (STUDENT/LECTURER...) la vai THEO WORKSPACE.
  {
    _id: CURRENT_ADMIN_ID,
    display_name: "Admin he thong",
    email_normalized: "admin@kltn.local",
    system_roles: ["ADMIN"],
    status: "ACTIVE",
  },
  // Experiment Operator (UC-12) -- them 2026-11-08, xem CURRENT_OPERATOR_ID.
  {
    _id: CURRENT_OPERATOR_ID,
    display_name: "Pham Thi Experiment",
    email_normalized: "operator@kltn.local",
    status: "ACTIVE",
  },
];

export const mockMemberships: Membership[] = [
  {
    _id: "mb_1",
    workspace_id: "ws_1",
    user_id: CURRENT_USER_ID,
    roles: ["STUDENT"],
    status: "ACTIVE",
  },
  // Giang vien quan ly workspace duy nhat -- dung cho man "Lecturer / Class"
  {
    _id: "mb_4",
    workspace_id: "ws_1",
    user_id: CURRENT_LECTURER_ID,
    roles: ["LECTURER"],
    status: "ACTIVE",
  },
  // Cac ban hoc cung lop ws_1 voi Yen -- dung cho man "Lecturer / Class Detail"
  {
    _id: "mb_8",
    workspace_id: "ws_1",
    user_id: "u_student_b",
    roles: ["STUDENT"],
    status: "ACTIVE",
  },
  {
    _id: "mb_9",
    workspace_id: "ws_1",
    user_id: "u_student_c",
    roles: ["STUDENT"],
    status: "ACTIVE",
  },
  // ws_2 (Nhom 2, cung mon/cung ky voi ws_1, trung ten khac ma lop) --
  // Yen yeu cau 2026-10-29: Vo Van B day nhom nay, CHUA co sinh vien nao.
  {
    _id: "mb_10",
    workspace_id: "ws_2",
    user_id: "u_lecturer_b",
    roles: ["LECTURER"],
    status: "ACTIVE",
  },
  // Experiment Operator (UC-12) -- xem ghi chu CURRENT_OPERATOR_ID. Gan
  // tam vao ws_1 cho hop le voi Membership (can workspace_id), UI Operator
  // (features/operator) KHONG dung workspace nay de loc du lieu.
  {
    _id: "mb_11",
    workspace_id: "ws_1",
    user_id: CURRENT_OPERATOR_ID,
    roles: ["OPERATOR"],
    status: "ACTIVE",
  },
];

/**
 * Ten giang vien hien thi theo workspace -- Yen yeu cau 2026-10-29: chi
 * con 1 workspace/1 giang vien duy nhat, dong bo voi UserProfile cua
 * CURRENT_LECTURER_ID o mockUsers (truoc day 2 noi ghi 2 ten khac nhau).
 */
export const lecturerByWorkspace: Record<string, string> = {
  ws_1: mockUsers.find((u) => u._id === CURRENT_LECTURER_ID)?.display_name ?? "-",
  ws_2: mockUsers.find((u) => u._id === "u_lecturer_b")?.display_name ?? "-",
};

export const mockDocuments: ReportDocument[] = [
  {
    _id: "doc_1",
    workspace_id: "ws_1",
    kind: "REPORT",
    document_key: "baocao_cuoiky",
    title: "baocao_cuoiky",
    owner_user_id: CURRENT_USER_ID,
    lifecycle_state: "ACTIVE",
  },
  {
    _id: "doc_2",
    workspace_id: "ws_1",
    kind: "REPORT",
    document_key: "baocao_giuaky",
    title: "baocao_giuaky",
    owner_user_id: CURRENT_USER_ID,
    lifecycle_state: "ACTIVE",
  },
  // Bao cao cua cac ban cung lop ws_1 -- dung cho man "Lecturer / Class Detail"
  // -- doi ten khop voi Yen (baocao_giuaky), Yen yeu cau 2026-10-29 de
  // dong bo loai bao cao giua cac sinh vien trong cung 1 lop.
  {
    _id: "doc_7",
    workspace_id: "ws_1",
    kind: "REPORT",
    document_key: "baocao_giuaky_b",
    title: "baocao_giuaky",
    owner_user_id: "u_student_b",
    lifecycle_state: "ACTIVE",
  },
  {
    _id: "doc_8",
    workspace_id: "ws_1",
    kind: "REPORT",
    document_key: "baocao_giuaky_c",
    title: "baocao_giuaky",
    owner_user_id: "u_student_c",
    lifecycle_state: "ACTIVE",
  },
];

/**
 * file_objects -- moi version tro ve dung 1 file_object (ten file GOC luc
 * sinh vien tai len + dung luong). Khac version co the dung ten file khac
 * nhau vi SV co the doi ten file moi khi nop lai.
 *
 * `size_bytes`: ten field GIA DINH -- chua xac nhan lai voi
 * data-dictionary.md, can doi lai cho khop neu ten field that khac.
 */
export const mockFileObjects: Record<
  string,
  { original_filename: string; size_bytes: number }
> = {
  fo_1a: { original_filename: "BaoCao_CuoiKy_v3_sua_loi.docx", size_bytes: 2_458_000 },
  fo_1b: { original_filename: "BaoCao_CuoiKy_v2.docx", size_bytes: 2_310_000 },
  fo_1c: { original_filename: "BaoCao_CuoiKy.docx", size_bytes: 1_980_000 },
  fo_2a: { original_filename: "BaoCao_GiuaKy.docx", size_bytes: 1_540_000 },
  fo_7a: { original_filename: "BaoCaoTuan2_TranThiB_v2.docx", size_bytes: 980_000 },
  fo_8a: { original_filename: "BaoCaoTuan3_LeVanC.pdf", size_bytes: 1_560_000 },
};

/** document_versions -- moi document co the co nhieu lan nop (version_no tang dan) */
export const mockDocumentVersions: DocumentVersion[] = [
  // baocao_cuoiky: nop lai 3 lan
  {
    _id: "dv_1a",
    document_id: "doc_1",
    version_no: 3,
    file_object_id: "fo_1a",
    original_filename: mockFileObjects.fo_1a.original_filename,
    file_size_bytes: mockFileObjects.fo_1a.size_bytes,
    submitted_at: "2026-01-03T08:14:32",
    display_status: "DANG_NOP",
  },
  {
    _id: "dv_1b",
    document_id: "doc_1",
    version_no: 2,
    file_object_id: "fo_1b",
    original_filename: mockFileObjects.fo_1b.original_filename,
    file_size_bytes: mockFileObjects.fo_1b.size_bytes,
    submitted_at: "2025-12-27T14:02:07",
    display_status: "DA_NOP",
  },
  {
    _id: "dv_1c",
    document_id: "doc_1",
    version_no: 1,
    file_object_id: "fo_1c",
    original_filename: mockFileObjects.fo_1c.original_filename,
    file_size_bytes: mockFileObjects.fo_1c.size_bytes,
    submitted_at: "2025-12-20T09:47:19",
    display_status: "LOI",
  },
  // baocao_giuaky: 1 lan nop
  {
    _id: "dv_2a",
    document_id: "doc_2",
    version_no: 1,
    file_object_id: "fo_2a",
    original_filename: mockFileObjects.fo_2a.original_filename,
    file_size_bytes: mockFileObjects.fo_2a.size_bytes,
    submitted_at: "2025-12-25T16:35:50",
    display_status: "DA_NOP",
  },
  // Tran Thi B -- baocao_tuan2: nop lai 2 lan, lan moi nhat dang cho duyet
  {
    _id: "dv_7a",
    document_id: "doc_7",
    version_no: 2,
    file_object_id: "fo_7a",
    original_filename: mockFileObjects.fo_7a.original_filename,
    file_size_bytes: mockFileObjects.fo_7a.size_bytes,
    submitted_at: "2025-10-06T12:29:54",
    display_status: "DA_NOP",
  },
  // Le Van C -- baocao_tuan3: 1 lan nop, da cong bo
  {
    _id: "dv_8a",
    document_id: "doc_8",
    version_no: 1,
    file_object_id: "fo_8a",
    original_filename: mockFileObjects.fo_8a.original_filename,
    file_size_bytes: mockFileObjects.fo_8a.size_bytes,
    submitted_at: "2025-10-02T18:03:38",
    display_status: "DA_CO_KET_QUA",
  },
];

/**
 * assessment_proposals -- chi lay field toi thieu de tinh so "cho duyet"
 * o man Lecturer Class List (status = READY_FOR_REVIEW = AI da cham xong,
 * dang cho giang vien ACCEPT/EDIT/REJECT -- xem data-dictionary.md muc
 * 10.3 va 10.4). Chi con workspace ws_1 (Yen yeu cau 2026-10-29: 1 giang
 * vien, 1 workspace duy nhat) nen report_version_id khop thang voi
 * mockDocumentVersions (dv_1a, dv_2a, deu la bao cao cua Yen).
 */
export const mockAssessmentProposals: AssessmentProposal[] = [
  // ws_1 (workspace duy nhat) -- SUA LAI 2026-10-29 (Yen yeu cau: tat ca
  // 3 "baocao_giuaky" deu "Đã công bố") -- ca dv_2a/dv_7a/dv_8a gio deu
  // ACCEPTED, khong con bao cao nao dang "cho duyet" (READY_FOR_REVIEW)
  // trong lop nay nua -- dv_1a (baocao_cuoiky, Yen) dang "Đang xử lý",
  // chua co proposal vi RUBRIC chua chay toi.
  { _id: "ap_1", workspace_id: "ws_1", report_version_id: "dv_7a", status: "ACCEPTED" },
  { _id: "ap_2", workspace_id: "ws_1", report_version_id: "dv_2a", status: "ACCEPTED" },
  { _id: "ap_3", workspace_id: "ws_1", report_version_id: "dv_8a", status: "ACCEPTED" },
];

/**
 * rubrics / rubric_versions -- rong luc khoi dong, giang vien tao qua man
 * "Tao rubric" (features/rubrics) se push vao day, giong cach
 * mockDocuments/mockDocumentVersions duoc them khi sinh vien nop bao cao.
 */
export const mockRubrics: Rubric[] = [];
export const mockRubricVersions: RubricVersion[] = [];

/**
 * Trang thai THO (chua xu ly WAITING/NOT_STARTED, xem lib/api.ts
 * deriveStages) cua tung chang pipeline, luu THEO document_VERSION_id --
 * SUA LAI 2026-10-24 (Yen phat hien): truoc day luu theo document_id
 * dung chung cho moi version, nen nop version moi se XOA/GHI DE ket qua
 * da xong cua version cu (vo ly voi data-dictionary.md muc 6.3, noi
 * processing_state la field RIENG cua tung document_version). Gio moi
 * version co 1 progress object DOC LAP: version cu da xong giu nguyen
 * mai mai, version moi nop vao chay pipeline rieng tu dau (xem
 * lib/api.ts uploadReport: mockPipelineProgress[newVersion._id] =
 * freshProgress()). Day la NGUON CHINH -- moi thay doi (giang vien bam
 * nut) deu MUTATE truc tiep object nay (giong cach mockRubrics/
 * mockDocumentVersions duoc push them) -- khi co backend that, cho nay
 * se bi xoa hoan toan, thay bang goi API that (xem lib/api.ts
 * startPipelineStage).
 */
/**
 * 1 job trong mock "hang doi xu ly" cua man Admin (UC-14) -- xem ghi chu
 * AdminJobRow trong lib/types.ts.
 */
export interface JobRecord {
  _id: string;
  documentId: string;
  /** Version CU THE dang/da duoc xu ly boi job nay -- Yen phat hien 2026-10-24: pipeline/ket qua gio luu THEO VERSION (xem mockPipelineProgress), job cung phai gan dung 1 version, khong con ngam dinh "version moi nhat cua document" nua. */
  documentVersionId: string;
  stage: JobStageKey;
  status: JobStatus;
  startedAt: string;
  retryCount: number;
}

export interface RawStageProgress {
  status: "NOT_TRIGGERED" | "RUNNING" | "DONE" | "ERROR";
  /** Chi dung cho chang co buoc con (PROCESSING 4 buoc, SIMILARITY 2 buoc) -- so buoc DA XONG (khong tinh buoc dang RUNNING) */
  stepsDone?: number;
}

export function freshProgress(): Record<PipelineStageKey, RawStageProgress> {
  return {
    PROCESSING: { status: "NOT_TRIGGERED" },
    SIMILARITY: { status: "NOT_TRIGGERED" },
    RUBRIC: { status: "NOT_TRIGGERED" },
    REVIEW: { status: "NOT_TRIGGERED" },
    PUBLISH: { status: "NOT_TRIGGERED" },
  };
}

export const mockPipelineProgress: Record<string, Record<PipelineStageKey, RawStageProgress>> = {
  // dv_1a (baocao_cuoiky, Yen, v3 -- version MOI NHAT, "...v3_sua_loi"):
  // dang chay Tien trinh xu ly (buoc 2/4).
  dv_1a: {
    PROCESSING: { status: "RUNNING", stepsDone: 2 },
    SIMILARITY: { status: "NOT_TRIGGERED" },
    RUBRIC: { status: "NOT_TRIGGERED" },
    REVIEW: { status: "NOT_TRIGGERED" },
    PUBLISH: { status: "NOT_TRIGGERED" },
  },
  // dv_1b (v2, "...v2.docx"): da xu ly xong het Similarity/Rubric nhung
  // chua den luot GV duyet thi SV da nop tiep v3 -- Yen phat hien
  // 2026-10-24: truoc day khong co key o day nen bi tinh nham thanh
  // "chua lam gi" (hien "Đang xử lý" mai mai) du la version CU da xong
  // xu ly roi, khong con "song" nua.
  dv_1b: {
    PROCESSING: { status: "DONE", stepsDone: 4 },
    SIMILARITY: { status: "DONE", stepsDone: 2 },
    RUBRIC: { status: "DONE" },
    REVIEW: { status: "NOT_TRIGGERED" },
    PUBLISH: { status: "NOT_TRIGGERED" },
  },
  // dv_1c (v1, "BaoCao_CuoiKy.docx"): loi ngay buoc Tien trinh xu ly --
  // ly do SV phai nop lai (khop voi ten file v3 "..._sua_loi").
  dv_1c: {
    PROCESSING: { status: "ERROR", stepsDone: 1 },
    SIMILARITY: { status: "NOT_TRIGGERED" },
    RUBRIC: { status: "NOT_TRIGGERED" },
    REVIEW: { status: "NOT_TRIGGERED" },
    PUBLISH: { status: "NOT_TRIGGERED" },
  },
  // dv_2a (baocao_giuaky, Yen): da duyet va cong bo xong het.
  dv_2a: {
    PROCESSING: { status: "DONE", stepsDone: 4 },
    SIMILARITY: { status: "DONE", stepsDone: 2 },
    RUBRIC: { status: "DONE" },
    REVIEW: { status: "DONE" },
    PUBLISH: { status: "DONE" },
  },
  // dv_7a (baocao_giuaky, Tran Thi B): da duyet va cong bo xong het.
  dv_7a: {
    PROCESSING: { status: "DONE", stepsDone: 4 },
    SIMILARITY: { status: "DONE", stepsDone: 2 },
    RUBRIC: { status: "DONE" },
    REVIEW: { status: "DONE" },
    PUBLISH: { status: "DONE" },
  },
  // dv_8a (baocao_giuaky, Le Van C): da duyet va cong bo xong het.
  dv_8a: {
    PROCESSING: { status: "DONE", stepsDone: 4 },
    SIMILARITY: { status: "DONE", stepsDone: 2 },
    RUBRIC: { status: "DONE" },
    REVIEW: { status: "DONE" },
    PUBLISH: { status: "DONE" },
  },
};

/**
 * Ket qua "Similarity" (chang 2 trong pipeline) theo document_id -- CHI
 * co y nghia khi SIMILARITY stage da DONE (xem mockPipelineProgress o
 * tren + lib/api.ts deriveStages). KHONG co key (hoac mang rong) = trang
 * thai Empty ("Không phát hiện đoạn nào trùng khớp với các nguồn đã
 * duyệt"). Yen yeu cau 2026-10-27, theo wireframe gui kem 2 trang thai
 * (Empty vs co bang ket qua) -- GIA DINH du lieu mau, can Quy xac nhan
 * lai field/API that.
 */
export const mockSimilarityMatches: Record<string, SimilarityMatch[]> = {
  // dv_8a (BaoCaoTuan3_LeVanC.pdf): co 4 doan nghi van, giong wireframe mau.
  // context/highlightText/sourceExcerpt them de demo popup "Chi tiet doan
  // nghi van" (Yen yeu cau 2026-10-27).
  dv_8a: [
    {
      _id: "simm_1",
      excerpt:
        "Mô hình ứng dụng di động cho phép sinh viên theo dõi tiến độ học tập theo thời gian thực, đồng thời hỗ trợ giảng viên quản lý lớp học hiệu quả hơn.",
      location: "Trang 2, đoạn 3",
      sourceLabel: "Báo cáo giữa kỳ — lớp MAD-2024",
      similarityPercent: 87,
      context:
        "Trong quá trình khảo sát hiện trạng, nhóm nhận thấy quy trình chấm báo cáo thủ công tồn tại nhiều hạn chế về thời gian và tính nhất quán. Mô hình ứng dụng di động cho phép sinh viên theo dõi tiến độ học tập theo thời gian thực, đồng thời hỗ trợ giảng viên quản lý lớp học hiệu quả hơn. Đây là cơ sở để nhóm đề xuất giải pháp tự động hoá ở các chương tiếp theo.",
      highlightText:
        "Mô hình ứng dụng di động cho phép sinh viên theo dõi tiến độ học tập theo thời gian thực, đồng thời hỗ trợ giảng viên quản lý lớp học hiệu quả hơn.",
      sourceExcerpt:
        "Mô hình ứng dụng di động cho phép người học theo dõi tiến độ học tập theo thời gian thực, đồng thời hỗ trợ giảng viên quản lý lớp học một cách hiệu quả.",
      revision: 1,
    },
    {
      _id: "simm_2",
      excerpt: "Việc tách tầng rõ ràng giúp hệ thống dễ bảo trì và mở rộng trong tương lai.",
      location: "Trang 3, đoạn 1",
      sourceLabel: "Tài liệu tham khảo nội bộ — Chương 2",
      similarityPercent: 63,
      context:
        "Kiến trúc hệ thống được chia thành 3 tầng chính: tầng giao diện, tầng xử lý nghiệp vụ và tầng lưu trữ dữ liệu. Việc tách tầng rõ ràng giúp hệ thống dễ bảo trì và mở rộng trong tương lai. Nhóm lựa chọn kiến trúc này dựa trên các tài liệu tham khảo về thiết kế hệ thống phân tán.",
      highlightText:
        "Việc tách tầng rõ ràng giúp hệ thống dễ bảo trì và mở rộng trong tương lai.",
      sourceExcerpt:
        "Thiết kế phân tầng rõ ràng là yếu tố quan trọng giúp hệ thống dễ bảo trì, dễ mở rộng và thuận tiện khi nâng cấp về sau.",
      revision: 1,
    },
    {
      _id: "simm_3",
      excerpt:
        "Kết quả đo đạc ban đầu cho thấy thời gian phản hồi nằm trong ngưỡng chấp nhận được đối với một ứng dụng giáo dục quy mô vừa.",
      location: "Trang 5, đoạn 2",
      sourceLabel: "Báo cáo cuối kỳ — lớp MAD-2023",
      similarityPercent: 24,
      context:
        "Để đánh giá hiệu năng, nhóm tiến hành đo thời gian phản hồi trung bình của API trong điều kiện tải thông thường. Kết quả đo đạc ban đầu cho thấy thời gian phản hồi nằm trong ngưỡng chấp nhận được đối với một ứng dụng giáo dục quy mô vừa. Các số liệu chi tiết được trình bày ở Phụ lục B.",
      highlightText:
        "Kết quả đo đạc ban đầu cho thấy thời gian phản hồi nằm trong ngưỡng chấp nhận được đối với một ứng dụng giáo dục quy mô vừa.",
      sourceExcerpt:
        "Kết quả đo đạc cho thấy thời gian phản hồi trung bình nằm trong ngưỡng chấp nhận được đối với một hệ thống quy mô vừa và nhỏ.",
      // Demo 1 match DA duyet san (Accept) -- de UI co vi du trang thai
      // "Đã chấp nhận" ngay khi vao trang, khong phai bam het tu dau moi
      // thay duoc giao dien sau khi duyet.
      revision: 2,
      decision: "ACCEPT",
    },
    {
      _id: "simm_4",
      excerpt: "Sinh viên được khuyến khích tham gia các đồ án tốt nghiệp có tính ứng dụng cao.",
      location: "Trang 6, đoạn 4",
      sourceLabel: "Tài liệu công khai — Website khoa",
      similarityPercent: 14,
      context:
        "Khoa Công nghệ thông tin hiện đang đào tạo theo chương trình chuẩn đầu ra gắn với nhu cầu thực tế của doanh nghiệp. Sinh viên được khuyến khích tham gia các đồ án tốt nghiệp có tính ứng dụng cao. Đây cũng là định hướng mà nhóm theo đuổi khi lựa chọn đề tài này.",
      highlightText:
        "Sinh viên được khuyến khích tham gia các đồ án tốt nghiệp có tính ứng dụng cao.",
      sourceExcerpt:
        "Sinh viên được khuyến khích thực hiện các đồ án tốt nghiệp có tính ứng dụng thực tiễn cao, gắn liền với nhu cầu doanh nghiệp.",
      revision: 1,
    },
  ],
  // dv_2a (baocao_giuaky, Yen): dang cho duyet (chang Duyet) -- them 2
  // de xuat de demo bang "Duyet" co du lieu (Yen yeu cau 2026-10-28).
  dv_2a: [
    {
      _id: "simm_5",
      excerpt: "Hệ thống sử dụng kiến trúc microservices để tăng khả năng mở rộng.",
      location: "Trang 4, đoạn 1",
      sourceLabel: "Báo cáo giữa kỳ — lớp SE-2024",
      similarityPercent: 56,
      context:
        "Ở giai đoạn thiết kế, nhóm cân nhắc giữa kiến trúc monolith và phân tán. Hệ thống sử dụng kiến trúc microservices để tăng khả năng mở rộng. Lựa chọn này giúp từng thành phần có thể triển khai và nâng cấp độc lập.",
      highlightText: "Hệ thống sử dụng kiến trúc microservices để tăng khả năng mở rộng.",
      revision: 1,
    },
  ],
  // dv_7a: khong co key -- trang thai Empty.
};

/**
 * Ket qua "Rubric" (bang "Kết quả chấm điểm") khi chang Rubric DONE --
 * Yen yeu cau 2026-10-28, theo wireframe gui kem: moi tieu chi la 1 hang
 * CHA (mo rong duoc de xem checklist con), trong so tieu chi de rieng 1
 * cot. GIA DINH toan bo du lieu mau + cach tinh diem (demo), can Quy xac
 * nhan lai khi he thong cham that tra ve ket qua.
 */
export const mockRubricScores: Record<string, RubricScoreResult> = {
  // doc_8 (BaoCaoTuan3_LeVanC.pdf): 2 tieu chi, giong wireframe mau.
  // SUA LAI LAN 2 -- 2026-10-28 (Yen hoi "sao đạt 2 cái hết là 9 điểm
  // trong khi trọng số 40"): xem RubricCreatePage.tsx (totalWeight +
  // "mức Tốt phải chạm đúng trọng số") -- `weight` KHONG phai he so
  // nhan de tinh trung binh, ma la DIEM TOI DA cua chinh tieu chi do
  // (level cao nhat = dung bang weight). Vi vay score phai cung THANG
  // voi weight, khong phai thang 10 rieng. Sua lai: Tieu chi 1 (weight
  // 30, 1/2 dat + 1 khong du co so) -- GIA DINH ~nua so diem toi da =
  // 15; Tieu chi 2 (weight 40, 2/2 dat het) -- GIA DINH gan toi da = 35.
  // totalScore = TONG diem tung tieu chi (khong phai trung binh), vi
  // weight da la "so diem dong gop toi da", 15+35=50.
  dv_8a: {
    totalScore: 50,
    criteria: [
      {
        _id: "rc_1",
        title: "Tiêu chí 1 — Trình bày vấn đề",
        weight: 30,
        resultSummary: "1/2 checklist đạt, 1 không đủ cơ sở",
        score: 15,
        checklists: [
          {
            _id: "rcc_1_1",
            condition: "Nêu rõ bối cảnh và lý do chọn đề tài",
            outcome: "DAT",
            evidence: [
              {
                _id: "ev_1",
                sourceLabel: "BaoCaoTuan3_LeVanC.pdf — chính báo cáo này",
                locatorLabel: "Trang 1, đoạn 2",
                quoteText:
                  "Hiện nay việc chấm báo cáo thủ công tốn nhiều thời gian và thiếu nhất quán giữa các giảng viên, do đó nhóm đề xuất xây dựng hệ thống hỗ trợ đánh giá dựa trên bằng chứng.",
                verificationState: "SUPPORTED",
                verificationReasonCode: "DIRECT_SUPPORT",
              },
            ],
          },
          {
            _id: "rcc_1_2",
            condition: "Trình bày phạm vi và giới hạn của đề tài",
            outcome: "KHONG_DU_CO_SO",
            // KHONG_DU_CO_SO (CANNOT_ASSESS) -- khong tim thay evidence_item
            // nao ho tro/mau thuan ro rang, mang rong theo dung quy uoc.
            evidence: [],
          },
        ],
      },
      {
        _id: "rc_2",
        title: "Tiêu chí 2 — Phương pháp thực hiện",
        weight: 40,
        resultSummary: "2/2 checklist đạt",
        score: 35,
        checklists: [
          {
            _id: "rcc_2_1",
            condition: "Mô tả rõ quy trình/phương pháp sử dụng",
            outcome: "DAT",
            evidence: [
              {
                _id: "ev_2",
                sourceLabel: "BaoCaoTuan3_LeVanC.pdf — chính báo cáo này",
                locatorLabel: "Trang 4, đoạn 1",
                quoteText:
                  "Nhóm áp dụng quy trình gồm 3 bước: thu thập dữ liệu, xử lý qua pipeline phân tích và tổng hợp kết quả theo rubric đã định nghĩa.",
                verificationState: "SUPPORTED",
                verificationReasonCode: "DIRECT_SUPPORT",
              },
            ],
          },
          {
            _id: "rcc_2_2",
            condition: "Có dẫn chứng/số liệu minh hoạ cho phương pháp",
            outcome: "DAT",
            evidence: [
              {
                _id: "ev_3",
                sourceLabel: "BaoCaoTuan3_LeVanC.pdf — chính báo cáo này",
                locatorLabel: "Trang 5, đoạn 2",
                quoteText:
                  "Kết quả đo đạc ban đầu cho thấy thời gian phản hồi trung bình đạt 320ms trên tập 50 báo cáo mẫu, nằm trong ngưỡng chấp nhận được.",
                verificationState: "SUPPORTED",
                verificationReasonCode: "DIRECT_SUPPORT",
              },
              {
                _id: "ev_4",
                sourceLabel: "Phụ lục B — Bảng số liệu đo đạc",
                locatorLabel: "Trang 12, bảng 3",
                quoteText:
                  "Thời gian phản hồi trung bình: 320ms (min 180ms, max 540ms, n=50).",
                // Demo 1 evidence khac trang thai -- bang nay o PHU LUC,
                // khong noi ro co cung dieu kien do (tai, so may) voi so
                // lieu da neu trong than bai hay khong, nen chi la
                // INSUFFICIENT (chua du co so khang dinh chac chan),
                // KHONG phai mau thuan (CONTRADICTED).
                verificationState: "INSUFFICIENT",
                verificationReasonCode: "CONTEXT_MISMATCH",
              },
            ],
          },
        ],
      },
    ],
  },
  // doc_2 (baocao_giuaky, Yen): dang cho duyet -- them 1 tieu chi de
  // demo bang "Duyet" co du lieu (Yen yeu cau 2026-10-28). SUA LAI LAN 2
  // -- 2026-10-28: score cung thang voi weight (30), 1/1 dat het nen gan
  // toi da (28/30), khong phai thang 10 rieng -- xem ghi chu tren doc_8.
  dv_2a: {
    totalScore: 28,
    criteria: [
      {
        _id: "rc_3",
        title: "Tiêu chí 1 — Trình bày vấn đề",
        weight: 30,
        resultSummary: "1/1 checklist đạt",
        score: 28,
        checklists: [
          {
            _id: "rcc_3_1",
            condition: "Nêu rõ bối cảnh và lý do chọn đề tài",
            outcome: "DAT",
            evidence: [
              {
                _id: "ev_5",
                sourceLabel: "baocao_giuaky.pdf — chính báo cáo này",
                locatorLabel: "Trang 1, đoạn 1",
                quoteText:
                  "Trong bối cảnh chuyển đổi số, việc đánh giá báo cáo thủ công gặp nhiều hạn chế về thời gian xử lý và tính khách quan giữa các giảng viên khác nhau.",
                verificationState: "SUPPORTED",
                verificationReasonCode: "DIRECT_SUPPORT",
              },
            ],
          },
        ],
      },
    ],
  },
  // dv_7a: khong co key -- chua co ket qua cham (dang RUNNING o buoc Duyet).
};

/**
 * UC-14 (Admin / Giam sat hang doi xu ly) -- xem ghi chu JobStatus/
 * AdminJobRow trong lib/types.ts. Day la mock "hang doi" DOC LAP voi
 * mockPipelineProgress (goc nhin khac, khong can dong bo tuyet doi) --
 * du lieu demo: 1 job dang RUNNING (doc_1), 1 job LOI de demo nut
 * "Chay lai", con lai DONE de bang khong trong rong.
 */
export const mockJobs: JobRecord[] = [
  { _id: "job_1", documentId: "doc_1", documentVersionId: "dv_1a", stage: "PROCESSING", status: "RUNNING", startedAt: "2026-10-23T09:12:00Z", retryCount: 0 },
  { _id: "job_2", documentId: "doc_7", documentVersionId: "dv_7a", stage: "SIMILARITY", status: "ERROR", startedAt: "2026-10-22T14:30:00Z", retryCount: 1 },
  { _id: "job_3", documentId: "doc_2", documentVersionId: "dv_2a", stage: "RUBRIC", status: "DONE", startedAt: "2026-10-20T08:00:00Z", retryCount: 0 },
  { _id: "job_4", documentId: "doc_8", documentVersionId: "dv_8a", stage: "SIMILARITY", status: "DONE", startedAt: "2026-10-21T10:00:00Z", retryCount: 0 },
];

/**
 * UC-15 (Lecturer / Nguon doi chieu cua lop) -- xem ghi chu CorpusSource
 * trong lib/types.ts (chuyen tu Admin sang Lecturer, gan workspace_id).
 */
export const mockCorpusSources: CorpusSource[] = [
  {
    _id: "src_1",
    workspace_id: "ws_1",
    title: "Báo cáo KLTN khoá 2023 — Mobile Apps Development",
    sourceType: "INTERNAL_REPORT",
    status: "APPROVED",
    submittedByName: "Nguyen Van A",
    submittedAt: "2026-09-01T03:00:00Z",
  },
  {
    _id: "src_2",
    workspace_id: "ws_1",
    title: "Hướng dẫn trình bày báo cáo khoa học (Khoa CNTT)",
    sourceType: "EXTERNAL_DOC",
    status: "APPROVED",
    submittedByName: "Nguyen Van A",
    submittedAt: "2026-09-02T03:00:00Z",
  },
  {
    _id: "src_3",
    workspace_id: "ws_1",
    title: "developer.android.com — Architecture guide",
    sourceType: "WEB",
    status: "PENDING",
    submittedByName: "Nguyen Van A",
    submittedAt: "2026-10-20T07:40:00Z",
  },
];

/**
 * UC-17 (Admin / Quan ly vong doi du lieu) -- xem ghi chu
 * DataLifecycleState trong lib/types.ts. Mac dinh ACTIVE cho moi
 * document hien co, demo 1 dong ARCHIVED de thay duoc nut "Khoi phuc".
 */
export const mockDataLifecycle: Record<string, { state: "ACTIVE" | "ARCHIVED" | "TOMBSTONED"; archivedAt?: string }> = {
  doc_1: { state: "ACTIVE" },
  doc_2: { state: "ACTIVE" },
  doc_7: { state: "ARCHIVED", archivedAt: "2026-10-15T02:00:00Z" },
  doc_8: { state: "ACTIVE" },
};

/**
 * ==========================================================================
 * UC-11 (phần còn lại): Policy/Governance, Audit log
 * ==========================================================================
 * Thêm 2026-11-08 -- xem ghi chú AdminGovernanceRow/AuditEventRow trong
 * lib/types.ts.
 */
export const mockGovernanceRecords: AdminGovernanceRow[] = [
  {
    _id: "gov_1",
    resourceType: "RUBRIC",
    resourceLabel: "Rubric đánh giá báo cáo giữa kỳ (MAD-2025-2026-N1)",
    workspaceName: "Mobile Apps Development (N1)",
    rightsBasis: "INTERNAL_APPROVAL",
    allowedPurposes: ["Chấm điểm nội bộ", "Nghiên cứu (ẩn danh)"],
    status: "APPROVED",
    approverName: "Admin he thong",
    approvedAt: "2026-09-01T08:00:00Z",
    revision: 2,
  },
  {
    _id: "gov_2",
    resourceType: "DATASET",
    resourceLabel: "pan13-text-alignment v1.0 (đối chiếu similarity)",
    rightsBasis: "LICENSE",
    allowedPurposes: ["Nghiên cứu", "Benchmark nội bộ"],
    status: "APPROVED",
    approverName: "Admin he thong",
    approvedAt: "2026-08-15T10:00:00Z",
    validUntil: "2027-08-15T00:00:00Z",
    revision: 1,
  },
  {
    _id: "gov_3",
    resourceType: "DOCUMENT",
    resourceLabel: "Corpus nội bộ — Báo cáo giữa kỳ lớp SE-2024",
    workspaceName: "Mobile Apps Development (N1)",
    rightsBasis: "CONSENT",
    allowedPurposes: ["Đối chiếu similarity trong lớp"],
    // PENDING -- Admin chua duyet, demo cho nut Approve/Reject co du lieu.
    status: "PENDING",
    revision: 1,
  },
  {
    _id: "gov_4",
    resourceType: "MODEL",
    resourceLabel: "reranker-vi-base v0.3",
    rightsBasis: "RESEARCH_USE_STATEMENT",
    allowedPurposes: ["Nghiên cứu", "Không dùng thương mại"],
    // REVOKED -- demo trang thai bi thu hoi (vd license thay doi).
    status: "REVOKED",
    approverName: "Admin he thong",
    approvedAt: "2026-05-01T00:00:00Z",
    revision: 3,
  },
];

/**
 * `audit_events` (data-dictionary.md mục 11.3) -- demo gồm vài hành động
 * đã xảy ra trong các màn khác của app (duyệt corpus UC-15, duyệt review
 * UC-05/06, công bố UC-10, khoá tài khoản UC-11, retry job UC-14) để màn
 * Audit log có dữ liệu khớp với các màn còn lại, không phải số liệu rời rạc.
 */
export const mockAuditEvents: AuditEventRow[] = [
  {
    _id: "audit_1",
    workspaceName: "Mobile Apps Development (N1)",
    actorName: "Nguyen Van A",
    actorType: "USER",
    action: "REVIEW.SUBMIT",
    resourceType: "assessment_proposal",
    resourceLabel: "Proposal — baocao_giuaky (Võ Thị Kim Yến)",
    outcome: "SUCCESS",
    beforeRevision: 1,
    afterRevision: 2,
    occurredAt: "2026-10-28T09:15:00Z",
  },
  {
    _id: "audit_2",
    workspaceName: "Mobile Apps Development (N1)",
    actorName: "Nguyen Van A",
    actorType: "USER",
    action: "PUBLICATION.PUBLISH",
    resourceType: "publication",
    resourceLabel: "Publication — baocao_giuaky (Võ Thị Kim Yến), v1",
    outcome: "SUCCESS",
    occurredAt: "2026-10-28T09:16:00Z",
  },
  {
    _id: "audit_3",
    actorName: "Admin he thong",
    actorType: "USER",
    action: "ACCOUNT.DISABLE",
    resourceType: "user",
    resourceLabel: "Tài khoản bị khoá (demo)",
    outcome: "SUCCESS",
    occurredAt: "2026-10-29T14:02:00Z",
  },
  {
    _id: "audit_4",
    workspaceName: "Mobile Apps Development (N1)",
    actorName: "Nguyen Van A",
    actorType: "USER",
    action: "CORPUS_SOURCE.APPROVE",
    resourceType: "corpus_source",
    resourceLabel: "Nguồn đối chiếu đã duyệt (UC-15)",
    outcome: "SUCCESS",
    beforeRevision: 1,
    afterRevision: 2,
    occurredAt: "2026-10-27T11:30:00Z",
  },
  {
    _id: "audit_5",
    actorType: "SYSTEM",
    actorName: "Hệ thống (worker)",
    action: "JOB.RETRY",
    resourceType: "job",
    resourceLabel: "Job SIMILARITY — BaoCaoTuan2_TranThiB.docx",
    // FAILURE -- demo 1 action khong thanh cong, de UI audit log co ca 2 outcome.
    outcome: "FAILURE",
    reasonCode: "WORKER_TIMEOUT",
    occurredAt: "2026-10-22T14:31:00Z",
  },
  {
    _id: "audit_6",
    actorName: "Admin he thong",
    actorType: "USER",
    action: "DATA_LIFECYCLE.PURGE",
    resourceType: "document",
    resourceLabel: "Báo cáo đã xoá vĩnh viễn (UC-17, demo)",
    outcome: "SUCCESS",
    occurredAt: "2026-10-29T16:45:00Z",
  },
];

/**
 * ==========================================================================
 * UC-08 (CONDITIONAL, RQ3): Targeted Questions
 * ==========================================================================
 * Thêm 2026-11-08 -- gate RQ3 coi là LUÔN BẬT cho demo (xem ghi chú
 * TargetedQuestion trong lib/types.ts). Key = documentId, giống quy ước
 * mockSimilarityMatches (key = versionId) nhưng ở đây dùng documentId vì
 * câu hỏi gắn với TOÀN BỘ báo cáo (không phân biệt version) trong demo.
 */
export const RQ3_ENABLED = true;

export const mockTargetedQuestions: Record<string, TargetedQuestion[]> = {
  // doc_8 (BaoCaoTuan3_LeVanC.pdf) -- cung bao cao da co similarity/rubric
  // o tren, de cac man lien ket chung 1 bao cao tham khao duoc.
  doc_8: [
    {
      _id: "tq_1",
      documentId: "doc_8",
      questionText:
        "Báo cáo nêu \"thời gian phản hồi nằm trong ngưỡng chấp nhận được\" — bạn có thể trích dẫn số liệu đo đạc cụ thể (giá trị, đơn vị, điều kiện đo) để làm rõ căn cứ cho kết luận này không?",
      type: "CLAIM_WITHOUT_EVIDENCE",
      linkedTo: "Tiêu chí 2 — Phương pháp thực hiện · Trang 5, đoạn 2",
      revision: 1,
    },
    {
      _id: "tq_2",
      documentId: "doc_8",
      questionText:
        "Phần giới thiệu đề cập đến việc tách tầng kiến trúc giúp dễ bảo trì, nhưng báo cáo chưa giải thích CÁCH đo lường \"dễ bảo trì\" — bạn dùng tiêu chí/chỉ số nào để đánh giá điều này?",
      type: "METHOD_NOT_EXPLAINED",
      linkedTo: "Tiêu chí 1 — Trình bày vấn đề · Trang 3, đoạn 1",
      // Demo 1 cau da duoc GV Accept truoc -- de UI co vi du trang thai da duyet.
      decision: "ACCEPT",
      revision: 2,
    },
    {
      _id: "tq_3",
      documentId: "doc_8",
      questionText:
        "Đoạn mô tả mô hình ứng dụng di động có độ tương đồng 87% với 1 báo cáo khác (xem chặng Similarity) — bạn có thể giải thích đây là trích dẫn có ghi nguồn hay là diễn giải độc lập của nhóm?",
      type: "HIGH_SIMILARITY",
      linkedTo: "Similarity match simm_1 · Trang 2, đoạn 3",
      revision: 1,
    },
  ],
  // dv_2a/doc_2 (baocao_giuaky, Yen) -- 1 cau demo khac loai, cho bao cao dang cho duyet.
  doc_2: [
    {
      _id: "tq_4",
      documentId: "doc_2",
      questionText:
        "Kết luận ở phần cuối cho rằng giải pháp \"đáp ứng tốt yêu cầu người dùng\", nhưng phần kết quả không có khảo sát hoặc số liệu người dùng — kết luận này dựa trên căn cứ nào?",
      type: "UNSUPPORTED_CONCLUSION",
      linkedTo: "Tiêu chí 1 — Trình bày vấn đề · Trang 6",
      revision: 1,
    },
  ],
};

/**
 * ==========================================================================
 * UC-12 (CORE, actor Experiment Operator): Chạy, so sánh và xuất thực nghiệm
 * ==========================================================================
 * Thêm 2026-11-08 -- xem ghi chú ExperimentRun trong lib/types.ts. 3 run
 * demo, mỗi RQ (RQ1/RQ2/RQ3) 1 cái, trạng thái khác nhau để UI có đủ case.
 */
export const mockExperimentRuns: ExperimentRun[] = [
  {
    _id: "run_1",
    runKey: "rq1-similarity-baseline-2026-10-20",
    rq: "RQ1",
    commitHash: "a3f9c21",
    datasetKey: "pan13-text-alignment",
    datasetVersion: "1.0",
    splitSpec: "official test split, seed=42",
    modelName: "bm25+rerank-vi-base-v0.3",
    seed: 42,
    hardware: "1x RTX 4090, 32GB RAM",
    startedAt: "2026-10-20T08:00:00Z",
    finishedAt: "2026-10-20T09:12:00Z",
    status: "DONE",
    metrics: [
      { name: "Recall@10", value: 0.82 },
      { name: "MRR", value: 0.74 },
      { name: "nDCG@10", value: 0.79 },
      { name: "Span F1", value: 0.68 },
      { name: "Latency p50", value: 420, unit: "ms" },
    ],
  },
  {
    _id: "run_2",
    runKey: "rq2-evidence-grounded-rubric-v1",
    rq: "RQ2",
    commitHash: "7b21ef0",
    datasetKey: "kltn-rubric-eval",
    datasetVersion: "0.2",
    splitSpec: "held-out split, seed=7 (không dùng để chọn model/threshold — FR-EXP-03)",
    modelName: "rubric-rule-engine-v1 + reranker-vi-base-v0.3",
    seed: 7,
    hardware: "1x RTX 4090, 32GB RAM",
    startedAt: "2026-10-25T13:00:00Z",
    finishedAt: "2026-10-25T14:40:00Z",
    status: "DONE",
    metrics: [
      { name: "Evidence Recall", value: 0.77 },
      { name: "Evidence Precision", value: 0.81 },
      { name: "3-state macro-F1", value: 0.71 },
      { name: "Grounding rate", value: 0.9 },
      { name: "Agreement vs GV", value: 0.73 },
    ],
  },
  {
    _id: "run_3",
    runKey: "rq3-targeted-questions-pilot",
    rq: "RQ3",
    commitHash: "7b21ef0",
    datasetKey: "kltn-rubric-eval",
    datasetVersion: "0.2",
    splitSpec: "pilot subset, seed=7",
    modelName: "question-generator-v0.1",
    seed: 7,
    hardware: "1x RTX 4090, 32GB RAM",
    startedAt: "2026-10-29T10:00:00Z",
    status: "RUNNING",
    metrics: [],
  },
];

/**
 * Feedback Log (FR-REV-04, MUST) -- xem ghi chu FeedbackLogEntry,
 * lib/types.ts. Append-only: moi lan GV Accept/Edit/Reject (Similarity/
 * Rubric proposal/Targeted Questions) deu them 1 dong moi vao day (xem
 * appendFeedbackLogEntry, lib/api.ts) -- KHONG sua/xoa dong da ghi.
 * Seed 2 dong khop voi 2 quyet dinh demo da co san tu truoc (simm_3
 * Similarity ACCEPT, tq_2 Targeted Question ACCEPT -- xem
 * mockSimilarityMatches/mockTargetedQuestions o tren), de man Feedback
 * Log khong rong tu dau cho doc_8.
 */
export const mockFeedbackLog: FeedbackLogEntry[] = [
  {
    _id: "fb_1",
    documentId: "doc_8",
    source: "SIMILARITY",
    sourceItemId: "simm_3",
    itemLabel: "Đoạn mô tả mô hình ứng dụng di động (87% tương đồng)",
    decision: "ACCEPT",
    actorName: "Vũ Đình Hồng",
    occurredAt: "2026-11-05T09:12:00Z",
  },
  {
    _id: "fb_2",
    documentId: "doc_8",
    source: "TARGETED_QUESTION",
    sourceItemId: "tq_2",
    itemLabel: "Câu hỏi về tiêu chí \"dễ bảo trì\" chưa giải thích cách đo",
    decision: "ACCEPT",
    actorName: "Vũ Đình Hồng",
    occurredAt: "2026-11-06T10:30:00Z",
  },
];
