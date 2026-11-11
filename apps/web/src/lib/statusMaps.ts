import type { BadgeTone } from "../components/StatusBadge";
import type {
  AuditOutcome,
  ChecklistImportance,
  CorpusSourceStatus,
  CorpusSourceType,
  DataLifecycleState,
  EvidenceVerificationState,
  ExperimentRunStatus,
  FeedbackLogSource,
  GovernanceStatus,
  JobStatus,
  MembershipRole,
  MembershipStatus,
  PipelineStageStatus,
  ReportDisplayStatus,
  ReportListStatus,
  ReviewDecision,
  RightsBasis,
  RubricChecklistOutcome,
  RubricVersionStatus,
  TargetedQuestionType,
  UserAccountStatus,
  WorkspaceStatus,
} from "./types";

export const workspaceStatusLabel: Record<
  WorkspaceStatus,
  { label: string; tone: BadgeTone }
> = {
  ACTIVE: { label: "Đang mở", tone: "success" },
  ARCHIVED: { label: "Đã đóng", tone: "neutral" },
};

export const documentStatusLabel: Record<
  ReportDisplayStatus,
  { label: string; tone: BadgeTone }
> = {
  DANG_NOP: { label: "Đang xử lý", tone: "warning" },
  DA_NOP: { label: "Đã nộp", tone: "success" },
  LOI: { label: "Lỗi", tone: "danger" },
  DA_CO_KET_QUA: { label: "Đã có kết quả", tone: "success" },
};

/**
 * Tone theo TUNG CHANG trong man "Lecturer / Report" (xem PipelineStageKey
 * trong lib/types.ts) -- tone suy ra THUAN TUY tu PipelineStageStatus (ap
 * dung chung cho moi chang), con LABEL thi tuy chang (vd RUNNING o chang
 * Duyet la "Đang lưu quyết định", o chang khac la "Đang xử lý") nen van
 * de lib/api.ts (deriveStages) tu ghep, chi tone la gom duoc ve 1 cho.
 */
export const pipelineStageStatusTone: Record<PipelineStageStatus, BadgeTone> = {
  WAITING: "neutral",
  NOT_STARTED: "info",
  RUNNING: "warning",
  DONE: "success",
  ERROR: "danger",
};

/**
 * Chip trong DANH SACH bao cao (StudentReportsTable, cot dem o
 * LecturerClassDetailPage) -- xem getListStatus/getListStatusChip trong
 * lib/api.ts. Thay the hoan toan cho `lecturerDocumentStatusLabel` kieu cu
 * (da bo cung luc voi field `lecturer_display_status`, xem lib/types.ts).
 */
export const reportListStatusLabel: Record<
  ReportListStatus,
  { label: string; tone: BadgeTone }
> = {
  SUBMITTED: { label: "Đã nộp", tone: "neutral" },
  PROCESSING: { label: "Đang xử lý", tone: "warning" },
  PUBLISHED: { label: "Đã công bố", tone: "success" },
  ERROR: { label: "Lỗi", tone: "danger" },
};

/**
 * Nhan "do quan trong" cua 1 checklist item (xem ChecklistImportance) --
 * dung chung cho ca Buoc 2 man "Tao rubric" (chon/sua nhan) va man "Xem
 * chi tiet rubric" (hien thi lai, chi doc).
 */
export const checklistImportanceLabel: Record<ChecklistImportance, { label: string; tone: BadgeTone }> = {
  CORE: { label: "Cốt lõi", tone: "danger" },
  REQUIRED: { label: "Bắt buộc", tone: "warning" },
  OPTIONAL: { label: "Không bắt buộc", tone: "neutral" },
};

/** Trang thai 1 rubric_version (xem RubricVersionStatus) -- dung o man "Xem chi tiet rubric". */
export const rubricVersionStatusLabel: Record<RubricVersionStatus, { label: string; tone: BadgeTone }> = {
  DRAFT: { label: "Nháp", tone: "neutral" },
  PUBLISHED: { label: "Đã công bố", tone: "success" },
  RETIRED: { label: "Đã ngừng dùng", tone: "neutral" },
};

/** Ket qua 1 checklist sau khi cham (xem RubricChecklistOutcome) -- dung o bang "Ket qua cham diem", chang Rubric. */
export const rubricChecklistOutcomeLabel: Record<RubricChecklistOutcome, { label: string; tone: BadgeTone }> = {
  DAT: { label: "Đạt", tone: "success" },
  CHUA_DAT: { label: "Chưa đạt", tone: "danger" },
  KHONG_DU_CO_SO: { label: "Không đủ cơ sở", tone: "warning" },
};

/** Trang thai 1 tai khoan (users.status, data-dictionary.md muc 5.1) -- dung o man "Admin / Quan ly tai khoan". */
export const userAccountStatusLabel: Record<UserAccountStatus, { label: string; tone: BadgeTone }> = {
  ACTIVE: { label: "Đang hoạt động", tone: "success" },
  DISABLED: { label: "Đã khoá", tone: "danger" },
  DELETED: { label: "Đã xoá", tone: "neutral" },
};

/** Nhan tieng Viet cho 1 vai tro THEO WORKSPACE (Membership.roles) -- dung o man "Admin / Thanh vien lop". OPERATOR/DATA_APPROVER chua co man hinh nao dung toi, chi de san cho du voi data-dictionary.md. */
export const membershipRoleLabel: Record<MembershipRole, string> = {
  STUDENT: "Sinh viên",
  LECTURER: "Giảng viên",
  OPERATOR: "Operator",
  DATA_APPROVER: "Data Approver",
};

/** Trang thai 1 thanh vien trong workspace (Membership.status) -- dung o man "Admin / Thanh vien lop". */
export const membershipStatusLabel: Record<MembershipStatus, { label: string; tone: BadgeTone }> = {
  ACTIVE: { label: "Đang hoạt động", tone: "success" },
  REVOKED: { label: "Đã thu hồi", tone: "neutral" },
};

/** Trang thai 1 job trong hang doi (man "Admin / Giam sat hang doi", UC-14). */
export const jobStatusLabel: Record<JobStatus, { label: string; tone: BadgeTone }> = {
  QUEUED: { label: "Trong hàng đợi", tone: "neutral" },
  RUNNING: { label: "Đang xử lý", tone: "warning" },
  DONE: { label: "Hoàn tất", tone: "success" },
  ERROR: { label: "Lỗi", tone: "danger" },
  CANCELLED: { label: "Đã huỷ", tone: "neutral" },
};

/** Nhan CHANG tuong ung voi PipelineStageKey, dung rieng cho bang job cua man Admin (UC-14). */
export const jobStageLabel: Record<string, string> = {
  PROCESSING: "Tiến trình xử lý",
  SIMILARITY: "Similarity",
  RUBRIC: "Rubric",
  REVIEW: "Duyệt",
  PUBLISH: "Công bố",
};

/** Trang thai 1 nguon doi chieu (man "Admin / Quan ly nguon doi chieu", UC-15). */
export const corpusSourceStatusLabel: Record<CorpusSourceStatus, { label: string; tone: BadgeTone }> = {
  PENDING: { label: "Chờ duyệt", tone: "warning" },
  APPROVED: { label: "Đã duyệt", tone: "success" },
  REJECTED: { label: "Bị từ chối", tone: "danger" },
};

/** Loai 1 nguon doi chieu (UC-15). */
export const corpusSourceTypeLabel: Record<CorpusSourceType, string> = {
  INTERNAL_REPORT: "Báo cáo nội bộ",
  EXTERNAL_DOC: "Tài liệu bên ngoài",
  WEB: "Trang web",
};

/** Trang thai vong doi 1 bao cao (man "Admin / Vong doi du lieu", UC-17). */
export const dataLifecycleStateLabel: Record<DataLifecycleState, { label: string; tone: BadgeTone }> = {
  ACTIVE: { label: "Đang hoạt động", tone: "success" },
  ARCHIVED: { label: "Đã lưu trữ", tone: "neutral" },
  TOMBSTONED: { label: "Đã xoá (tombstone)", tone: "danger" },
};

/**
 * Nhan quyet dinh duyet (xem ReviewDecision) -- dung CHUNG cho ca proposal
 * Rubric (chang Duyet, AssessmentProposalReview) va TUNG match Similarity
 * (chang Similarity, SimilarityMatch -- them 2026-11-08 theo UC-05).
 */
export const reviewDecisionLabel: Record<ReviewDecision, { label: string; tone: BadgeTone }> = {
  ACCEPT: { label: "Đã chấp nhận", tone: "success" },
  EDIT: { label: "Đã chỉnh sửa", tone: "warning" },
  REJECT: { label: "Đã từ chối", tone: "danger" },
};

/**
 * Quan he claim-evidence cua 1 EvidenceItem (data-dictionary.md muc 10.2,
 * field verification_state) -- dung o man chi tiet bang chung (them
 * 2026-11-08, xem EvidenceItem trong lib/types.ts).
 */
export const evidenceVerificationStateLabel: Record<
  EvidenceVerificationState,
  { label: string; tone: BadgeTone }
> = {
  SUPPORTED: { label: "Hỗ trợ", tone: "success" },
  CONTRADICTED: { label: "Mâu thuẫn", tone: "danger" },
  INSUFFICIENT: { label: "Chưa đủ cơ sở", tone: "warning" },
};

/** Trạng thái 1 governance_record (xem GovernanceStatus) -- dùng ở màn "Admin / Cấu hình policy" (UC-11). */
export const governanceStatusLabel: Record<GovernanceStatus, { label: string; tone: BadgeTone }> = {
  PENDING: { label: "Chờ duyệt", tone: "warning" },
  APPROVED: { label: "Đã duyệt", tone: "success" },
  REJECTED: { label: "Bị từ chối", tone: "danger" },
  REVOKED: { label: "Đã thu hồi", tone: "danger" },
  EXPIRED: { label: "Đã hết hạn", tone: "neutral" },
};

/** Cơ sở quyền sử dụng dữ liệu (xem RightsBasis) -- dùng ở màn "Admin / Cấu hình policy". */
export const rightsBasisLabel: Record<RightsBasis, string> = {
  LICENSE: "Giấy phép (license)",
  CONSENT: "Có sự đồng ý (consent)",
  RESEARCH_USE_STATEMENT: "Cam kết dùng cho nghiên cứu",
  INTERNAL_APPROVAL: "Phê duyệt nội bộ",
  UNKNOWN: "Chưa rõ",
};

/** Kết quả 1 audit_event (xem AuditOutcome) -- dùng ở màn "Admin / Audit log". */
export const auditOutcomeLabel: Record<AuditOutcome, { label: string; tone: BadgeTone }> = {
  SUCCESS: { label: "Thành công", tone: "success" },
  FAILURE: { label: "Thất bại", tone: "danger" },
};

/** Trạng thái 1 run thực nghiệm (xem ExperimentRunStatus) -- dùng ở các màn Experiment Operator (UC-12). */
export const experimentRunStatusLabel: Record<ExperimentRunStatus, { label: string; tone: BadgeTone }> = {
  DRAFT: { label: "Nháp", tone: "neutral" },
  RUNNING: { label: "Đang chạy", tone: "warning" },
  DONE: { label: "Hoàn tất", tone: "success" },
  FAILED: { label: "Lỗi", tone: "danger" },
};

/** Loại 1 Targeted Question (xem TargetedQuestionType) -- dùng ở màn Lecturer / Targeted Questions (UC-08). */
export const targetedQuestionTypeLabel: Record<TargetedQuestionType, string> = {
  CLAIM_WITHOUT_EVIDENCE: "Claim chưa có bằng chứng",
  UNSUPPORTED_CONCLUSION: "Kết luận chưa được hỗ trợ",
  METHOD_NOT_EXPLAINED: "Phương pháp chưa giải thích",
  HIGH_SIMILARITY: "Nội dung tương đồng cao",
  INCONSISTENT: "Không nhất quán",
};

/** Nhan nguon 1 dong Feedback Log (xem FeedbackLogSource) -- dung o man "Lecturer / Feedback Log" (FR-REV-04). */
export const feedbackLogSourceLabel: Record<FeedbackLogSource, string> = {
  SIMILARITY: "Similarity",
  RUBRIC_PROPOSAL: "Rubric (proposal)",
  TARGETED_QUESTION: "Targeted Question",
};
