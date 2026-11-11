import {
  CURRENT_LECTURER_ID,
  CURRENT_USER_ID,
  lecturerByWorkspace,
  mockAssessmentProposals,
  mockAuditEvents,
  mockCorpusSources,
  mockDataLifecycle,
  mockDocumentVersions,
  mockDocuments,
  mockExperimentRuns,
  mockFeedbackLog,
  mockFileObjects,
  mockGovernanceRecords,
  mockJobs,
  mockMemberships,
  mockPipelineProgress,
  mockRubricScores,
  mockSimilarityMatches,
  mockTargetedQuestions,
  freshProgress,
  mockRubricVersions,
  mockRubrics,
  mockUsers,
  mockWorkspaces,
} from "./mockData";
import type { JobRecord, RawStageProgress } from "./mockData";
import type { BadgeTone } from "../components/StatusBadge";
import { reportListStatusLabel } from "./statusMaps";
import { formatDateTime } from "./format";
import type {
  AdminGovernanceRow,
  AdminJobRow,
  AdminLifecycleRow,
  AdminMembershipRow,
  AdminUserRow,
  AdminWorkspaceRow,
  AuditEventRow,
  CorpusSource,
  CorpusSourceStatus,
  CreateCorpusSourceParams,
  CreateRubricParams,
  CreateWorkspaceParams,
  DataLifecycleState,
  DocumentVersion,
  ExperimentRun,
  FeedbackLogEntry,
  FeedbackLogSource,
  GovernanceStatus,
  JobStageKey,
  LecturerWorkspaceRow,
  MyWorkspaceRow,
  PipelineStage,
  PipelineStageKey,
  PipelineStageStatus,
  ProcessingStepItem,
  PublicationDetail,
  ReportDisplayStatus,
  ReportDocument,
  ReportPipelineDetail,
  ReportDocumentWithVersions,
  ReportListStatus,
  ChecklistImportance,
  ReviewDecision,
  AssessmentProposalReview,
  SimilarityMatch,
  Rubric,
  RubricChecklistItem,
  RubricCriterion,
  RubricCriterionLevel,
  RubricVersion,
  RubricVersionStatus,
  StudentReportsRow,
  SystemHealthStageSummary,
  SystemHealthSummary,
  TargetedQuestion,
  Membership,
  MembershipRole,
  SubmitReportParams,
  SubmitReportResult,
  UserAccountStatus,
  Workspace,
  LoginDestination,
  LoginResult,
} from "./types";

/**
 * Lop gia lap goi API. Frontend chi duoc goi API (theo README: "Frontend
 * chi goi API; khong truy cap MongoDB, model hoac Search Provider truc
 * tiep") -- nen moi "join" du lieu o day la viec BACKEND that se lam, gio
 * dang mo phong tam bang mock data + delay gia lap network.
 *
 * Khi co API that: xoa noi dung cac ham ben duoi, thay bang
 * `fetch(`${BASE_URL}/workspaces?...`)` tuong ung -- giu nguyen chu ky ham
 * (ten + kieu tra ve) de khong phai sua lai UI.
 */

const FAKE_DELAY_MS = 350;

function delay<T>(value: T): Promise<T> {
  return new Promise((resolve) => setTimeout(() => resolve(value), FAKE_DELAY_MS));
}

/** Loi dang nhap (email khong ton tai, mat khau trong, hoac tai khoan
 * chua duoc gan vai tro nao) -- LoginPage.tsx bat loi nay de hien thong
 * bao, khong hien chi tiet ky thuat cho nguoi dung. */
export class LoginError extends Error {}

/**
 * POST /auth/login { email, password }
 * MOCK: chua co backend auth that (xem docs/architecture/c4.md,
 * OD-W21-02 con la open decision ve session cookie/token/SSO) -- nen
 * CHI kiem tra email co ton tai trong mockUsers va password khong rong,
 * KHONG kiem tra mat khau thuc. Sau khi "dang nhap" thanh cong, suy ra
 * danh sach LoginDestination tu system_roles + Membership.roles cua tai
 * khoan do (1 tai khoan co the co nhieu diem vao, vd vua ADMIN vua
 * LECTURER o workspace khac) -- LoginPage.tsx tu quyet dinh chuyen thang
 * (1 diem vao) hay cho chon (nhieu diem vao).
 */
export async function login(email: string, password: string): Promise<LoginResult> {
  const normalizedEmail = email.trim().toLowerCase();

  if (!normalizedEmail) {
    throw new LoginError("Vui lòng nhập email.");
  }
  if (!password) {
    throw new LoginError("Vui lòng nhập mật khẩu.");
  }

  const user = mockUsers.find((u) => u.email_normalized === normalizedEmail);
  if (!user || user.status === "DISABLED" || user.status === "DELETED") {
    throw new LoginError("Email hoặc mật khẩu không đúng.");
  }

  const destinations: LoginDestination[] = [];
  if (user.system_roles?.includes("ADMIN")) {
    destinations.push({ role: "Quản trị viên", homePath: "/admin/workspaces" });
  }

  const roleSet = new Set(
    mockMemberships
      .filter((m) => m.user_id === user._id && m.status === "ACTIVE")
      .flatMap((m) => m.roles),
  );
  if (roleSet.has("STUDENT")) {
    destinations.push({ role: "Sinh viên", homePath: "/workspaces" });
  }
  if (roleSet.has("LECTURER")) {
    destinations.push({ role: "Giảng viên", homePath: "/lecturer/workspaces" });
  }
  if (roleSet.has("OPERATOR")) {
    destinations.push({ role: "Experiment Operator", homePath: "/operator/runs" });
  }
  // DATA_APPROVER: chua co man hinh nao dung toi (xem statusMaps.ts), bo qua.

  if (destinations.length === 0) {
    throw new LoginError(
      "Tài khoản chưa được gán vai trò nào. Liên hệ Admin để được cấp quyền.",
    );
  }

  return delay({ user, destinations });
}

/**
 * GET /me/workspaces?kind=COURSE
 * Lay danh sach workspace (kind=COURSE) ma user hien tai co membership
 * ACTIVE voi role STUDENT.
 */
export async function getMyWorkspaces(): Promise<MyWorkspaceRow[]> {
  const myWorkspaceIds = mockMemberships
    .filter(
      (m) =>
        m.user_id === CURRENT_USER_ID &&
        m.status === "ACTIVE" &&
        m.roles.includes("STUDENT"),
    )
    .map((m) => m.workspace_id);

  const rows: MyWorkspaceRow[] = mockWorkspaces
    .filter((w) => w.kind === "COURSE" && myWorkspaceIds.includes(w._id))
    .map((w) => ({
      ...w,
      lecturer_name: lecturerByWorkspace[w._id] ?? "-",
    }));

  return delay(rows);
}

/** GET /workspaces/:workspaceId */
export async function getWorkspaceById(
  workspaceId: string,
): Promise<Workspace | undefined> {
  return delay(mockWorkspaces.find((w) => w._id === workspaceId));
}

/**
 * GET /me/workspaces?kind=COURSE&role=LECTURER
 * Lay danh sach workspace (kind=COURSE) ma giang vien hien tai co
 * membership ACTIVE voi role LECTURER, kem so bao cao dang cho duyet
 * (assessment_proposals.status = READY_FOR_REVIEW) trong tung workspace
 * -- dung cho man "Lecturer / Class".
 */
export async function getMyLecturerWorkspaces(): Promise<LecturerWorkspaceRow[]> {
  const myWorkspaceIds = mockMemberships
    .filter(
      (m) =>
        m.user_id === CURRENT_LECTURER_ID &&
        m.status === "ACTIVE" &&
        m.roles.includes("LECTURER"),
    )
    .map((m) => m.workspace_id);

  const rows: LecturerWorkspaceRow[] = mockWorkspaces
    .filter((w) => w.kind === "COURSE" && myWorkspaceIds.includes(w._id))
    .map((w) => ({
      ...w,
      pending_review_count: mockAssessmentProposals.filter(
        (p) => p.workspace_id === w._id && p.status === "READY_FOR_REVIEW",
      ).length,
    }));

  return delay(rows);
}

/**
 * GET /workspaces/:workspaceId/students?expand=documents
 * Danh sach sinh vien (membership ACTIVE, role STUDENT) trong 1 workspace,
 * moi sinh vien kem TOAN BO bao cao (document) ho da nop -- moi document
 * da gom san cac version cua no, sap xep version_no giam dan -- dung cho
 * man "Lecturer / Class Detail": mo rong 1 sinh vien de thay danh sach
 * cac bao cao ho da nop (khac man Student: mo rong 1 bao cao de thay cac
 * phien ban).
 */
export async function getStudentReportsInWorkspace(
  workspaceId: string,
): Promise<StudentReportsRow[]> {
  const studentIds = mockMemberships
    .filter(
      (m) =>
        m.workspace_id === workspaceId &&
        m.status === "ACTIVE" &&
        m.roles.includes("STUDENT"),
    )
    .map((m) => m.user_id);

  const rows: StudentReportsRow[] = studentIds
    .map((studentId): StudentReportsRow | null => {
      const student = mockUsers.find((u) => u._id === studentId);
      if (!student) return null;

      const documents: ReportDocumentWithVersions[] = mockDocuments
        .filter(
          (d) =>
            d.workspace_id === workspaceId &&
            d.owner_user_id === studentId &&
            d.lifecycle_state === "ACTIVE",
        )
        .map((d) => ({
          ...d,
          versions: mockDocumentVersions
            .filter((v) => v.document_id === d._id)
            .sort((a, b) => b.version_no - a.version_no),
        }))
        .sort((a, b) =>
          (b.versions[0]?.submitted_at ?? "").localeCompare(
            a.versions[0]?.submitted_at ?? "",
          ),
        );

      return { student, documents };
    })
    .filter((row): row is StudentReportsRow => row !== null)
    .sort((a, b) => a.student.display_name.localeCompare(b.student.display_name, "vi"));

  return delay(rows);
}

/**
 * GET /workspaces/:workspaceId/documents/:documentId/pipeline (GIA DINH --
 * endpoint nay chua co trong tai lieu API, dat ten de mo phong) -- lay du
 * lieu gop cho man "Lecturer / Report" (wireframe gui 2026-10-18): 1 bao
 * cao (document) + version moi nhat + 5 CHANG xu ly (xem PipelineStageKey
 * trong lib/types.ts). Cach suy ra trang thai tung chang tu
 * `lecturer_display_status` o day la GIA DINH DEMO -- khi co API that,
 * BE se tra ve san tung chang (processing_state, similarity run, rubric
 * run, reviews, publications) thay vi suy luan nhu the nay.
 */
const STAGE_SEQUENCE: PipelineStageKey[] = ["PROCESSING", "SIMILARITY", "RUBRIC", "REVIEW", "PUBLISH"];

/** So buoc con cua cac chang co danh sach buoc nho (xem ProcessingStepItem) -- chang khong co trong day la chang "mot phat an nut xong" (Rubric/Duyet/Cong bo, GIA DINH, chua lam UI rieng). */
const STAGE_STEP_LABELS: Partial<Record<PipelineStageKey, string[]>> = {
  PROCESSING: ["Đã nhận file", "Đã đọc file", "Đang lập chỉ mục", "Sẵn sàng"],
  SIMILARITY: ["Đang phân tích", "Hoàn thành"],
  RUBRIC: ["Đang chấm điểm", "Hoàn thành"],
};

/**
 * Nhan RIENG cho 1 vai buoc con khi buoc do DA XONG (DONE), ghi de len
 * STAGE_STEP_LABELS (vd Rubric: buoc 1 hien "Đang chấm điểm" luc dang
 * chay nhung doi thanh "Đã chấm điểm" khi xong, theo wireframe gui kem
 * 2026-10-28) -- buoc nao KHONG co trong day thi giu nguyen nhan mac
 * dinh ca luc RUNNING lan DONE (vd "Hoàn thành" o buoc 2).
 */
const STAGE_STEP_DONE_LABELS: Partial<Record<PipelineStageKey, string[]>> = {
  RUBRIC: ["Đã chấm điểm", "Hoàn thành"],
};

/** Nhan rieng cho tung chang khi RUNNING/DONE (chang khong liet ke o day dung chu mac dinh "Đang xử lý"/"Hoàn tất") */
const STAGE_RUNNING_LABEL: Partial<Record<PipelineStageKey, string>> = {
  // Rieng REVIEW: KHONG con "chay ngam" nhu cac chang khac -- RUNNING o
  // day chi la 1 trang thai PRESET demo (vd doc_7, "dang co nguoi duyet
  // do") de hien UI tuong tac ngay, khong phai spinner that -- Yen yeu
  // cau 2026-10-28: "ko co tien trinh nhu may cai kia".
  REVIEW: "Đang duyệt",
};
const STAGE_NOT_STARTED_LABEL: Partial<Record<PipelineStageKey, string>> = {
  REVIEW: "Chưa duyệt",
};
const STAGE_DONE_LABEL: Partial<Record<PipelineStageKey, string>> = {
  // REVIEW DONE nghia la da duyet VA da cong bo (nut "Công bố" trong
  // ReviewPanel publish luon ca 2 -- Yen yeu cau 2026-10-28, gop chang
  // Cong bo vao Duyet, khong con hien rieng o UI).
  REVIEW: "Đã công bố",
  PUBLISH: "Đã công bố",
};

function buildSubSteps(
  stage: PipelineStageKey,
  raw: RawStageProgress,
  submittedAt: string,
): ProcessingStepItem[] | undefined {
  const labels = STAGE_STEP_LABELS[stage];
  if (!labels) return undefined;

  const stepsDone = raw.status === "DONE" ? labels.length : (raw.stepsDone ?? 0);

  const submittedAtLabel = formatDateTime(submittedAt);

  const doneLabels = STAGE_STEP_DONE_LABELS[stage];

  return labels.map((label, index) => {
    if (index < stepsDone) {
      return {
        key: `${stage}_${index + 1}`,
        label: doneLabels?.[index] ?? label,
        status: "DONE",
        timeLabel: `${submittedAtLabel} · đã xong`,
      };
    }
    if (index === stepsDone && raw.status === "RUNNING") {
      return { key: `${stage}_${index + 1}`, label, status: "RUNNING", timeLabel: `${submittedAtLabel} · đang chạy` };
    }
    return { key: `${stage}_${index + 1}`, label, status: "PENDING" };
  });
}

function stageStatusLabel(stage: PipelineStageKey, status: PipelineStageStatus): string {
  if (status === "ERROR") return "Lỗi";
  if (status === "RUNNING") return STAGE_RUNNING_LABEL[stage] ?? "Đang xử lý";
  if (status === "DONE") return STAGE_DONE_LABEL[stage] ?? "Hoàn tất";
  if (status === "NOT_STARTED") return STAGE_NOT_STARTED_LABEL[stage] ?? "Chưa bắt đầu";
  return "Đang chờ";
}

/**
 * Trang thai duyet TUNG MATCH Similarity rieng (UC-05, them 2026-11-08 --
 * xem ghi chu day du tren SimilarityMatch, lib/types.ts) -- cache mutable
 * giong CACH LAM voi `assessmentProposalCache` ben duoi (key o day la
 * SimilarityMatch._id, vi moi match la 1 quyet dinh DOC LAP, khac Rubric
 * chi co 1 proposal gop cho ca bao cao). Overlay LEN TREN du lieu tinh
 * trong mockSimilarityMatches moi lan doc (xem getSimilarityMatchesReviewed
 * duoi day) de GV duyet xong van giu nguyen ket qua khi quay lai/polling,
 * khong sua truc tiep vao mockSimilarityMatches (du lieu goc).
 */
const similarityMatchReviewCache: Record<
  string,
  { decision?: ReviewDecision; reasonText?: string; editedNote?: string; revision: number }
> = {};

/**
 * Tra ve mang SimilarityMatch cua 1 version, da gop (overlay) voi quyet
 * dinh duyet moi nhat trong similarityMatchReviewCache neu co -- dung
 * thay cho viec doc truc tiep mockSimilarityMatches[versionId] o MOI noi
 * can hien thi/duyet match, de luon thay dung trang thai GV vua duyet.
 */
function getSimilarityMatchesReviewed(versionId: string): SimilarityMatch[] {
  const raw = mockSimilarityMatches[versionId] ?? [];
  return raw.map((match) => {
    const reviewed = similarityMatchReviewCache[match._id];
    return reviewed ? { ...match, ...reviewed } : match;
  });
}

/**
 * Tim documentId + excerpt cua 1 SimilarityMatch tu matchId -- can cho
 * Feedback Log (FR-REV-04, xem appendFeedbackLogEntry) vi
 * mockSimilarityMatches chi key theo versionId, khong co documentId truc
 * tiep tren SimilarityMatch (xem ghi chu tren type, lib/types.ts).
 */
function findDocumentIdForSimilarityMatch(
  matchId: string,
): { documentId: string; excerpt: string } | undefined {
  for (const [versionId, matches] of Object.entries(mockSimilarityMatches)) {
    const match = matches.find((m) => m._id === matchId);
    if (match) {
      const version = mockDocumentVersions.find((v) => v._id === versionId);
      if (version) return { documentId: version.document_id, excerpt: match.excerpt };
    }
  }
  return undefined;
}

export interface SubmitSimilarityMatchReviewParams {
  matchId: string;
  decision: ReviewDecision;
  /** Revision GV dang giu luc bam nut -- xem ghi chu tren SimilarityMatch.revision. */
  expectedRevision: number;
  /** Bat buoc khi decision = EDIT hoac REJECT. */
  reasonText?: string;
  /** Chi dung khi decision = EDIT. */
  editedNote?: string;
}

let feedbackLogSeq = 0;

/**
 * Ghi THEM 1 dong vao Feedback Log (FR-REV-04, MUST -- xem ghi chu
 * FeedbackLogEntry, lib/types.ts) -- APPEND-ONLY, khong co ham sua/xoa
 * dong da ghi o dau trong file nay. Goi tu CA 3 noi GV Accept/Edit/Reject:
 * submitSimilarityMatchReview, submitProposalReview, submitTargetedQuestionReview.
 */
function appendFeedbackLogEntry(entry: {
  documentId: string;
  source: FeedbackLogSource;
  sourceItemId: string;
  itemLabel: string;
  decision: ReviewDecision;
  reasonText?: string;
}): void {
  feedbackLogSeq += 1;
  const actor = mockUsers.find((u) => u._id === CURRENT_LECTURER_ID);
  const logEntry: FeedbackLogEntry = {
    _id: `fb_${Date.now()}_${feedbackLogSeq}`,
    actorName: actor?.display_name ?? "Giảng viên",
    occurredAt: new Date().toISOString(),
    ...entry,
  };
  mockFeedbackLog.push(logEntry);
}

/**
 * POST duyet 1 SimilarityMatch RIENG (UC-05: "Match được Accept/Edit/Reject"
 * -- xem bo-use-case.md dong UC-05 + FR-SIM-05-07, FR-REV-01/02) -- KHAC
 * voi submitProposalReview ben duoi (duyet NGUYEN 1 proposal Rubric gop
 * cho ca bao cao): o day MOI LAN GOI chi duyet 1 match DUY NHAT, vi
 * Similarity khong co khai niem "1 khoi proposal" nhu Rubric. Nem
 * ReviewConflictError neu revision lech, cung co che optimistic
 * concurrency voi submitProposalReview.
 */
export async function submitSimilarityMatchReview(
  params: SubmitSimilarityMatchReviewParams,
): Promise<void> {
  await delay(undefined);

  const current = similarityMatchReviewCache[params.matchId];
  const currentRevision = current?.revision ?? 1;
  if (currentRevision !== params.expectedRevision) {
    throw new ReviewConflictError();
  }

  similarityMatchReviewCache[params.matchId] = {
    decision: params.decision,
    reasonText: params.reasonText,
    editedNote: params.decision === "EDIT" ? params.editedNote : undefined,
    revision: currentRevision + 1,
  };

  const matchInfo = findDocumentIdForSimilarityMatch(params.matchId);
  if (matchInfo) {
    appendFeedbackLogEntry({
      documentId: matchInfo.documentId,
      source: "SIMILARITY",
      sourceItemId: params.matchId,
      itemLabel: matchInfo.excerpt,
      decision: params.decision,
      reasonText: params.reasonText,
    });
  }
}

/**
 * Suy ra 5 CHANG pipeline (xem PipelineStageKey) tu `mockPipelineProgress`
 * (nguon THAT, mutable -- xem ghi chu tren mockPipelineProgress trong
 * lib/mockData.ts) -- tach rieng ham PURE nay (khong async) de dung chung
 * o CA man "Lecturer / Report" (getReportPipelineDetail) LAN cai chip
 * trang thai o man danh sach bao cao (getListStatus/getListStatusChip),
 * dung 1 nguon suy luan duy nhat, tranh 2 cho hien thi bi lech nhau.
 *
 * Nhan `versionId` (document_VERSION_id, KHONG phai documentId) -- Yen
 * phat hien 2026-10-24: moi document_version phai co pipeline rieng (xem
 * ghi chu mockPipelineProgress trong lib/mockData.ts), nen moi loi goi
 * ham nay phai truyen dung _id cua VERSION dang xem/xu ly.
 */
function deriveStages(versionId: string, submittedAt: string): Record<PipelineStageKey, PipelineStage> {
  const progress = mockPipelineProgress[versionId];
  const result = {} as Record<PipelineStageKey, PipelineStage>;

  STAGE_SEQUENCE.forEach((stage, index) => {
    const raw: RawStageProgress = progress?.[stage] ?? { status: "NOT_TRIGGERED" };
    let status: PipelineStageStatus;

    if (raw.status === "ERROR") status = "ERROR";
    else if (raw.status === "DONE") status = "DONE";
    else if (raw.status === "RUNNING") status = "RUNNING";
    else {
      // NOT_TRIGGERED -- xem la da MO KHOA (NOT_STARTED, GV bam duoc) hay
      // con bi KHOA (WAITING, chang truoc chua xong) theo THU TU chang.
      const prevStage = STAGE_SEQUENCE[index - 1];
      const prevDone = !prevStage || progress?.[prevStage]?.status === "DONE";
      status = prevDone ? "NOT_STARTED" : "WAITING";
    }

    result[stage] = {
      status,
      statusLabel: stageStatusLabel(stage, status),
      steps: buildSubSteps(stage, raw, submittedAt),
      // Chi Similarity DONE moi co ket qua so khop (mang rong = Empty
      // state) -- xem mockSimilarityMatches trong lib/mockData.ts. Dung
      // getSimilarityMatchesReviewed (KHONG doc truc tiep
      // mockSimilarityMatches) de gop quyet dinh Accept/Edit/Reject GV da
      // duyet tung match (UC-05, xem similarityMatchReviewCache o tren).
      similarityMatches:
        stage === "SIMILARITY" && status === "DONE"
          ? getSimilarityMatchesReviewed(versionId)
          : undefined,
      // Chi Rubric DONE moi co bang "Ket qua cham diem" -- xem
      // mockRubricScores trong lib/mockData.ts (Yen yeu cau 2026-10-28).
      rubricScore: stage === "RUBRIC" && status === "DONE" ? mockRubricScores[versionId] : undefined,
    };
  });

  return result;
}

/**
 * Version MOI NHAT (version_no lon nhat) cua 1 document -- helper dung
 * chung o nhieu cho can "version dang song" (job, pipeline progress,
 * proposal...) vi cac bang mock gio luu THEO version_id, khong con THEO
 * document_id nua (xem ghi chu mockPipelineProgress, lib/mockData.ts).
 */
function getLatestVersion(documentId: string): DocumentVersion | undefined {
  return mockDocumentVersions
    .filter((v) => v.document_id === documentId)
    .sort((a, b) => b.version_no - a.version_no)[0];
}

/** Vai giay gia lap cho moi buoc con (PROCESSING/SIMILARITY) va cho ca chang khong co buoc con (RUBRIC/REVIEW/PUBLISH) -- mo phong do tre goi "backend" that. */
const STAGE_STEP_DELAY_MS = 1200;
const STAGE_SIMPLE_DELAY_MS = 1500;

/**
 * GV bam nut "Bắt đầu..." o 1 chang -- mo phong goi API that su kich hoat
 * backend xu ly chang do (xem ghi chu tren mockPipelineProgress). Chi cho
 * bat dau khi chang dang NOT_STARTED (UI da tu khoa nut, o day validate
 * lai cho chac). Tu chay tiep qua tung buoc con (neu co) bang setTimeout
 * CAP MODULE (khong phu thuoc component con mounted hay khong -- giong
 * backend that van chay du GV co dang xem trang hay khong), roi tu chuyen
 * DONE. Component goi lai getReportPipelineDetail theo chu ky (polling)
 * de thay tien do moi -- xem LecturerReportDetailPage.tsx.
 */
/**
 * "allowRerunFromDone" -- rieng Similarity cho phep bam "Chay lai" khi
 * da DONE (cac chang khac van chi bam duoc tu NOT_STARTED nhu truoc) --
 * Yen yeu cau 2026-10-27, theo wireframe co nut "Chay lai" o chang
 * Similarity.
 *
 * Tham so dau la `versionId` (document_version._id), KHONG phai
 * documentId nua -- GV chi duoc bam "Bat dau"/"Chay lai" tren VERSION
 * MOI NHAT (xem LecturerReportDetailPage.tsx: cac nut nay bi an khi dang
 * xem 1 phien ban cu hon).
 */
export async function startPipelineStage(
  versionId: string,
  stage: PipelineStageKey,
  allowRerunFromDone = false,
): Promise<void> {
  const progress = mockPipelineProgress[versionId];
  if (!progress) return delay(undefined);

  const current = deriveStages(versionId, "")[stage];
  const canRerun = allowRerunFromDone && current.status === "DONE";
  if (current.status !== "NOT_STARTED" && !canRerun) return delay(undefined);

  const stepLabels = STAGE_STEP_LABELS[stage];

  if (stepLabels) {
    progress[stage] = { status: "RUNNING", stepsDone: 0 };
    let stepsDone = 0;
    const tick = () => {
      stepsDone += 1;
      if (stepsDone >= stepLabels.length) {
        progress[stage] = { status: "DONE", stepsDone: stepLabels.length };
      } else {
        progress[stage] = { status: "RUNNING", stepsDone };
        setTimeout(tick, STAGE_STEP_DELAY_MS);
      }
    };
    setTimeout(tick, STAGE_STEP_DELAY_MS);
  } else {
    progress[stage] = { status: "RUNNING" };
    setTimeout(() => {
      progress[stage] = { status: "DONE" };
    }, STAGE_SIMPLE_DELAY_MS);
  }

  return delay(undefined);
}

/**
 * Man "Duyet" (chang REVIEW) -- SUA LAI 2026-10-28 cho dung
 * data-dictionary.md muc 10.3-10.4: 1 PROPOSAL DUY NHAT cho ca bao cao
 * (khong phai tung tieu chi/similarity rieng), suy ra 1 lan tu
 * mockRubricScores roi giu trong cache nay (mutable, giong
 * mockPipelineProgress) de GV duyet xong van con nguyen khi quay lai --
 * xem ghi chu day du tren AssessmentProposalReview o lib/types.ts.
 */
const assessmentProposalCache: Record<string, AssessmentProposalReview> = {};

function getOrInitAssessmentProposal(documentId: string): AssessmentProposalReview | undefined {
  const cached = assessmentProposalCache[documentId];
  if (cached) return cached;

  // mockRubricScores gio luu THEO version_id -- proposal luon ung voi
  // KET QUA CHAM CUA VERSION MOI NHAT (chi version moi nhat moi dang
  // "song", version cu da xong/dong bang -- xem ghi chu mockPipelineProgress).
  const latestVersion = getLatestVersion(documentId);
  const score = latestVersion ? mockRubricScores[latestVersion._id] : undefined;
  if (!score) return undefined;

  const proposal: AssessmentProposalReview = {
    _id: `proposal_${documentId}`,
    criteria: score.criteria,
    totalScore: score.totalScore,
    revision: 1,
  };
  assessmentProposalCache[documentId] = proposal;
  return proposal;
}

/** GET proposal cham diem can duyet cho 1 bao cao -- undefined = chua co proposal nao (Empty state, GIA DINH endpoint). */
export async function getAssessmentProposal(documentId: string): Promise<AssessmentProposalReview | undefined> {
  const proposal = getOrInitAssessmentProposal(documentId);
  return delay(proposal ? { ...proposal } : undefined);
}

/** Loi 409 REVISION_CONFLICT (data-dictionary.md muc 10.4: "conflict trả 409") -- ai do/noi khac da sua proposal nay truoc khi GV kip submit. */
export class ReviewConflictError extends Error {
  constructor() {
    super("REVISION_CONFLICT");
    this.name = "ReviewConflictError";
  }
}

export interface SubmitProposalReviewParams {
  documentId: string;
  decision: ReviewDecision;
  /** Revision GV dang giu luc bam nut (tu lan GET/sau lan duyet gan nhat) -- dung de phat hien xung dot. */
  expectedRevision: number;
  /** Bat buoc khi decision = EDIT hoac REJECT. */
  reasonText?: string;
  /** Chi dung khi decision = EDIT. */
  editedNote?: string;
  /** Chi dung khi decision = EDIT -- key = RubricCriterionScore._id. */
  editedCriterionScores?: Record<string, number>;
}

/** POST duyet nguyen 1 proposal (Accept/Edit/Reject) -- nem ReviewConflictError neu revision lech (xem AssessmentProposalReview.revision). */
export async function submitProposalReview(params: SubmitProposalReviewParams): Promise<void> {
  const proposal = getOrInitAssessmentProposal(params.documentId);
  if (!proposal) return delay(undefined);

  await delay(undefined);

  if (proposal.revision !== params.expectedRevision) {
    throw new ReviewConflictError();
  }

  proposal.decision = params.decision;
  proposal.reasonText = params.reasonText;
  proposal.editedNote = params.decision === "EDIT" ? params.editedNote : undefined;
  proposal.editedCriterionScores = params.decision === "EDIT" ? params.editedCriterionScores : undefined;
  proposal.revision += 1;

  appendFeedbackLogEntry({
    documentId: params.documentId,
    source: "RUBRIC_PROPOSAL",
    sourceItemId: proposal._id,
    itemLabel: "Proposal chấm điểm Rubric",
    decision: params.decision,
    reasonText: params.reasonText,
  });
}

/**
 * Nut "Công bố" o man Duyet -- Yen xac nhan 2026-10-28: bam la PUBLISH
 * LUON (tu dong hoan tat ca chang Duyet lan Công bố), GV khong can mo
 * chang Công bố rieng bam lai.
 */
export async function publishReportReview(documentId: string): Promise<void> {
  // Luon ap dung cho VERSION MOI NHAT -- Duyet/Cong bo chi co y nghia
  // tren version dang "song" (xem ghi chu mockPipelineProgress).
  const latestVersion = getLatestVersion(documentId);
  const progress = latestVersion ? mockPipelineProgress[latestVersion._id] : undefined;
  if (!progress) return delay(undefined);
  progress.REVIEW = { status: "DONE" };
  progress.PUBLISH = { status: "DONE" };
  return delay(undefined);
}

/**
 * `viewVersionId` (tuy chon) -- SUA LAI 2026-10-24 (Yen phat hien): truoc
 * day luon tra ve pipeline cua VERSION MOI NHAT du dang xem version nao
 * (vi mockPipelineProgress dung chung cho ca document) -- gio moi version
 * co pipeline rieng, nen man "Lecturer / Report" co the truyen dung
 * _id cua version dang chon o dropdown de xem DUNG tien trinh/ket qua
 * cua version do (vd version cu da cong bo xong se hien DONE het, khong
 * con bi "an theo" version moi dang chay). Bo trong/khong tim thay = mac
 * dinh ve version moi nhat (currentVersion), giu nguyen hanh vi cu.
 */
export async function getReportPipelineDetail(
  documentId: string,
  viewVersionId?: string,
): Promise<ReportPipelineDetail | undefined> {
  const document = mockDocuments.find((d) => d._id === documentId);
  if (!document) return delay(undefined);

  const workspace = mockWorkspaces.find((w) => w._id === document.workspace_id);
  const student = mockUsers.find((u) => u._id === document.owner_user_id);
  const versions = mockDocumentVersions
    .filter((v) => v.document_id === documentId)
    .sort((a, b) => b.version_no - a.version_no);
  const currentVersion = versions[0];
  if (!workspace || !student || !currentVersion) return delay(undefined);

  const viewedVersion = versions.find((v) => v._id === viewVersionId) ?? currentVersion;

  const detail: ReportPipelineDetail = {
    workspaceId: workspace._id,
    workspaceName: workspace.name,
    documentId: document._id,
    documentTitle: currentVersion.original_filename ?? document.title,
    studentName: student.display_name,
    studentId: student.student_id ?? "—",
    versions,
    currentVersion,
    stages: deriveStages(viewedVersion._id, viewedVersion.submitted_at),
  };

  return delay(detail);
}

/**
 * Trang thai RUT GON (4 gia tri) dung cho DANH SACH bao cao
 * (StudentReportsTable, cot dem o LecturerClassDetailPage) -- xem
 * ReportListStatus trong lib/types.ts. Ham nay SYNC (khong delay) vi chi
 * tinh toan tu du lieu da co san trong bo nho, dung duoc truc tiep trong
 * vong lap render/dem so luong.
 */
export function getListStatus(version: DocumentVersion): ReportListStatus {
  const stages = deriveStages(version._id, version.submitted_at);
  const stageList = Object.values(stages);

  if (stageList.some((s) => s.status === "ERROR")) return "ERROR";
  if (stages.PUBLISH.status === "DONE") return "PUBLISHED";
  if (stages.PROCESSING.status === "NOT_STARTED") return "SUBMITTED";
  return "PROCESSING";
}

export function getListStatusChip(version: DocumentVersion): { label: string; tone: BadgeTone } {
  return reportListStatusLabel[getListStatus(version)];
}

/**
 * GET /workspaces/:workspaceId/documents?kind=REPORT&owner_user_id=me&expand=versions
 * Danh sach bao cao (document) da nop cua user hien tai trong 1 workspace,
 * moi document kem theo TAT CA version cua no (document_versions), sap xep
 * version_no giam dan (moi nhat len dau) -- dung cho bang mo rong o man
 * Workspace Detail.
 */
/**
 * Trang thai GOP theo goc nhin SINH VIEN (xem ReportDisplayStatus) --
 * SUA LAI 2026-10-28: truoc day doc THANG field `display_status` tinh
 * san tren DocumentVersion (co the bi LECH voi pipeline that, vd GV
 * huy cong bo), gio SUY RA TRUC TIEP tu deriveStages (mockPipelineProgress)
 * giong het cach GV xem (getListStatus o tren) -- 1 nguon suy luan duy
 * nhat, dung luc nao cung dung voi trang thai pipeline hien tai.
 */
function deriveStudentDisplayStatus(version: DocumentVersion): ReportDisplayStatus {
  const stages = deriveStages(version._id, version.submitted_at);
  const stageList = Object.values(stages);

  if (stageList.some((s) => s.status === "ERROR")) return "LOI";
  if (stages.PUBLISH.status === "DONE") return "DA_CO_KET_QUA";
  if (stages.PROCESSING.status === "NOT_STARTED") return "DANG_NOP";
  return "DA_NOP";
}

export async function getMyDocumentsInWorkspace(
  workspaceId: string,
): Promise<ReportDocumentWithVersions[]> {
  const rows: ReportDocumentWithVersions[] = mockDocuments
    .filter(
      (d) =>
        d.workspace_id === workspaceId &&
        d.owner_user_id === CURRENT_USER_ID &&
        d.lifecycle_state === "ACTIVE",
    )
    .map((d) => ({
      ...d,
      versions: mockDocumentVersions
        .filter((v) => v.document_id === d._id)
        .sort((a, b) => b.version_no - a.version_no)
        .map((v) => ({ ...v, display_status: deriveStudentDisplayStatus(v) })),
    }))
    // Bao cao vua nop/nop phien ban moi nhat nam tren cung -- sap xep theo
    // ngay nop cua chinh version moi nhat (versions[0], da sap xep o tren).
    .sort((a, b) =>
      (b.versions[0]?.submitted_at ?? "").localeCompare(
        a.versions[0]?.submitted_at ?? "",
      ),
    );

  return delay(rows);
}

/**
 * GET ket qua da cong bo cho 1 bao cao (man "Xem publication", `UC-09`
 * -- CORE, actor Sinh vien, xem ghi chu day du tren PublicationDetail o
 * lib/types.ts) -- undefined = chua cong bo (chang PUBLISH chua DONE)
 * hoac khong tim thay, UI phai tu chan khong cho vao thang URL khi chua
 * cong bo.
 */
export async function getPublicationDetail(
  documentId: string,
): Promise<PublicationDetail | undefined> {
  const document = mockDocuments.find((d) => d._id === documentId);
  if (!document) return delay(undefined);

  const workspace = mockWorkspaces.find((w) => w._id === document.workspace_id);
  const versions = mockDocumentVersions
    .filter((v) => v.document_id === documentId)
    .sort((a, b) => b.version_no - a.version_no);
  const currentVersion = versions[0];
  if (!workspace || !currentVersion) return delay(undefined);

  const stages = deriveStages(currentVersion._id, currentVersion.submitted_at);
  if (stages.PUBLISH.status !== "DONE") return delay(undefined);

  const detail: PublicationDetail = {
    workspaceId: workspace._id,
    workspaceName: workspace.name,
    documentId: document._id,
    documentTitle: currentVersion.original_filename ?? document.title,
    versionNo: currentVersion.version_no,
    // GIA DINH DEMO -- chua co field `published_at` rieng trong mock
    // pipeline progress, tam lay ngay nop lam ngay cong bo.
    publishedAt: currentVersion.submitted_at,
    rubricScore: mockRubricScores[currentVersion._id],
    // Dung getSimilarityMatchesReviewed (khong doc thang mockSimilarityMatches)
    // de SV thay dung ket qua CUOI CUNG (vd 1 match GV da Reject vi la
    // trich dan hop le se khong con bi hieu lam la "nghi van" nua). Luu y:
    // SimilarityMatch gio co them decision/reasonText/editedNote/revision
    // (noi bo GV, UC-05) -- PublicationDetailPage.tsx KHONG render cac
    // field nay cho SV (dung quy uoc UC-09 muc 7.8: "không hiển thị
    // proposal hoặc review history nội bộ"), chi la tai su dung CHUNG 1
    // type cho gon, UI tu gioi han field hien thi.
    similarityMatches: getSimilarityMatchesReviewed(currentVersion._id),
  };

  return delay(detail);
}

const ALLOWED_EXTENSIONS = [".pdf", ".docx"];
const MAX_FILE_SIZE_BYTES = 100 * 1024 * 1024; // 100MB -- theo yeu cau cua Yen

function validateFile(file: File): string | null {
  const name = file.name.toLowerCase();
  const hasValidExt = ALLOWED_EXTENSIONS.some((ext) => name.endsWith(ext));
  if (!hasValidExt) return "Chỉ chấp nhận file PDF hoặc DOCX.";
  if (file.size > MAX_FILE_SIZE_BYTES) {
    return "File vượt quá dung lượng tối đa 100MB.";
  }
  return null;
}

/** Bo tiep dau "." va phan duoi file -- dung lam tieu de bao cao khi SV khong nhap */
function titleFromFilename(filename: string): string {
  const lastDot = filename.lastIndexOf(".");
  return lastDot > 0 ? filename.slice(0, lastDot) : filename;
}

/**
 * POST /workspaces/:workspaceId/documents (mode=NEW)
 * POST /workspaces/:workspaceId/documents/:documentId/versions (mode=EXISTING)
 *
 * Nop 1 bao cao -- hoac tao document moi + version dau tien (NEW), hoac
 * them 1 version moi cho document da co san (EXISTING, "nop them phien
 * ban"). Mock nay tu validate file + ghi truc tiep vao mock "database";
 * backend that se nhan multipart upload, tao file_objects truoc roi moi
 * tao document_versions tro toi.
 */
export async function submitReportVersion(
  params: SubmitReportParams,
): Promise<SubmitReportResult> {
  const validationError = validateFile(params.file);
  if (validationError) {
    await delay(null);
    return { ok: false, error: validationError };
  }

  if (params.mode === "EXISTING" && !params.documentId) {
    await delay(null);
    return { ok: false, error: "Vui lòng chọn báo cáo cần nộp thêm phiên bản." };
  }

  await delay(null); // mô phỏng thời gian tải file lên server

  const fileObjectId = `fo_${Date.now()}`;
  mockFileObjects[fileObjectId] = {
    original_filename: params.file.name,
    size_bytes: params.file.size,
  };
  const submittedAt = new Date().toISOString(); // ISO datetime day du gio:phut:giay, dung format.ts de hien thi

  let document: ReportDocument;
  let existingVersions: DocumentVersion[];

  if (params.mode === "NEW") {
    // Tieu de khong bat buoc -- khong nhap thi lay theo ten file (bo duoi)
    const effectiveTitle =
      params.title?.trim() || titleFromFilename(params.file.name);
    document = {
      _id: `doc_${Date.now()}`,
      workspace_id: params.workspaceId,
      kind: "REPORT",
      document_key: effectiveTitle.toLowerCase().replace(/\s+/g, "_"),
      title: effectiveTitle,
      owner_user_id: CURRENT_USER_ID,
      lifecycle_state: "ACTIVE",
    };
    mockDocuments.push(document);
    existingVersions = [];
  } else {
    const found = mockDocuments.find((d) => d._id === params.documentId);
    if (!found) {
      return { ok: false, error: "Không tìm thấy báo cáo." };
    }
    document = found;
    existingVersions = mockDocumentVersions.filter(
      (v) => v.document_id === document._id,
    );
  }

  const nextVersionNo =
    existingVersions.reduce((max, v) => Math.max(max, v.version_no), 0) + 1;

  const newVersion: DocumentVersion = {
    _id: `dv_${Date.now()}`,
    document_id: document._id,
    version_no: nextVersionNo,
    file_object_id: fileObjectId,
    original_filename: params.file.name,
    file_size_bytes: params.file.size,
    submitted_at: submittedAt,
    display_status: "DANG_NOP",
  };
  mockDocumentVersions.push(newVersion);

  // Phien ban MOI (newVersion) co progress RIENG, khoi tao "chua lam gi"
  // (NOT_TRIGGERED ca 5 chang) -- SUA LAI 2026-10-24 (Yen phat hien):
  // truoc day ghi vao mockPipelineProgress[document._id], dung chung
  // cho CA document nen nop version moi se XOA LUON ket qua da xong cua
  // version cu (vo ly khi vd v1 da "Đã công bố" roi nop v2). Gio moi
  // version co key _id rieng nen v1 giu nguyen ket qua cu, v2 chay tu
  // dau doc lap -- dung voi data-dictionary.md (processing_state la
  // field cua document_version, khong phai document).
  mockPipelineProgress[newVersion._id] = freshProgress();

  return {
    ok: true,
    document: {
      ...document,
      versions: [newVersion, ...existingVersions].sort(
        (a, b) => b.version_no - a.version_no,
      ),
    },
  };
}

/** "" -> "_" + chu thuong, dung chung cho rubric_key/criterion_key/checklist_key tu title nhap tay */
function slugify(text: string, fallback: string): string {
  const slug = text.trim().toLowerCase().replace(/\s+/g, "_");
  return slug.length > 0 ? slug : fallback;
}

/**
 * GIA DINH -- bo tu khoa de Rubric Compiler tu gan nhan do quan trong
 * (ChecklistImportance) theo noi dung tieu chi, xem rubric-v1.md muc 4 +
 * docs/rubric/rubric-notes-ui-data.md. Mac dinh REQUIRED ("thuong thi moi
 * tieu chi deu bat buoc neu ko co gi dac biet trong cau tu" -- Yen).
 * Can Quy/GVHD chot lai bo tu khoa that.
 */
const CORE_KEYWORDS = ["phải có", "bắt buộc tuyệt đối", "tối thiểu phải", "cần phải"];
const OPTIONAL_KEYWORDS = ["nên", "khuyến khích", "tùy chọn", "có thể"];

function guessImportance(text: string): ChecklistImportance {
  const normalized = text.toLowerCase();
  if (CORE_KEYWORDS.some((kw) => normalized.includes(kw))) return "CORE";
  if (OPTIONAL_KEYWORDS.some((kw) => normalized.includes(kw))) return "OPTIONAL";
  return "REQUIRED";
}

/**
 * Tu breakpoints (diem chia giua cac muc, giam dan, do GV nhap) suy ra
 * [min,max] cho tung muc theo quy uoc rubric-v1.md muc 2: muc dau (tot
 * nhat) co max = dung weight; cac bien giua 2 muc KHONG lap (muc duoi
 * dung lam min cua minh, muc tren dung lam max -- dong/ho dau do scoring
 * engine xu ly, o day chi luu gia tri so).
 */
export function levelsFromBreakpoints(
  weight: number,
  breakpoints: number[],
): RubricCriterionLevel[] {
  const boundaries = [weight, ...breakpoints, 0];
  const levels: RubricCriterionLevel[] = [];
  for (let i = 0; i < boundaries.length - 1; i += 1) {
    levels.push({ min: boundaries[i + 1], max: boundaries[i] });
  }
  return levels;
}

/**
 * Nguoc lai levelsFromBreakpoints -- suy ra lai cac diem chia tu mang
 * [min,max] da luu, dung khi mo lai 1 rubric de SUA (RubricCreatePage
 * che do edit -- Yen yeu cau 2026-10-27 "gio minh lam phan sua di"), vi
 * form Buoc 1 lam viec voi "breakpoints" (xem CriterionDraft), khong
 * phai levels. level cuoi cung luon co min=0 (khong phai 1 diem chia),
 * nen bo qua.
 */
export function breakpointsFromLevels(levels: RubricCriterionLevel[]): number[] {
  return levels.slice(0, -1).map((level) => level.min);
}

/**
 * Buoc 1 cua man "Tao rubric": giang vien nhap tieu chi + diem chia muc
 * (CHUA co checklist), goi ham nay de "bien dich" thanh checklist truoc
 * khi luu that -- mo phong Rubric Compiler (EP-05-S09, PRODUCT_BACKLOG.md:
 * "Compiler deterministic; output schema/version ro"), KHONG phai AI/LLM
 * tu do phan tich van ban. Quy tac mock o day: moi tieu chi sinh dung 1
 * checklist mac dinh (mode LOCAL, importance tu doan theo tu khoa), giang
 * vien se duoc sua lai o buoc 2 truoc khi xac nhan -- logic bien dich
 * that se do Quy thiet ke rieng.
 */
export async function compileRubricChecklist(
  params: CreateRubricParams,
): Promise<RubricCriterion[]> {
  await delay(null);

  return params.criteria.map((criterion, index) => {
    const criterionKey = slugify(criterion.title, `tieu_chi_${index + 1}`);
    // Khong dien san noi dung checklist -- de trong de giang vien tu nhap
    // o Buoc 2, tranh truong hop GV quen sua va luu nham cau mac dinh.
    const checklist: RubricChecklistItem = {
      _id: `cl_draft_${index}`,
      checklist_key: `${criterionKey}_1`,
      criterion_key: criterionKey,
      condition: "",
      mode: "LOCAL",
      importance: guessImportance(criterion.title),
    };

    return {
      _id: `crit_draft_${index}`,
      criterion_key: criterionKey,
      title: criterion.title,
      weight: criterion.weight,
      levels: levelsFromBreakpoints(criterion.weight, criterion.breakpoints),
      checklists: [checklist],
    };
  });
}

/**
 * Buoc 2 -- giang vien da xem/sua checklist do compileRubricChecklist
 * sinh ra, bam "Luu nhap" hoac "Cong bo" de luu that thanh rubrics +
 * rubric_versions (version_no = 1 -- data-dictionary.md muc 8.1/8.2).
 *
 * `status` -- UC-03 (W1-04-bo-use-case.md muc 7.3) mo ta ro day la 2 buoc
 * TACH BIET: GV tao criterion/checklist truoc (o trang thai DRAFT, sua
 * thoai mai), roi MOI chu dong "publish rubric version; version nay tro
 * thanh immutable". Truoc day code luon hard-code PUBLISHED ngay khi tao,
 * Yen phan anh 2026-10-26 ("vay la gio minh sua theo nhu vay nhe, cho luu
 * nhap truoc di") -- gio GV duoc chon that.
 */
export async function createRubric(
  params: CreateRubricParams,
  criteria: RubricCriterion[],
  status: RubricVersionStatus,
): Promise<Rubric> {
  await delay(null);

  const rubricId = `rub_${Date.now()}`;
  const versionId = `rubv_${Date.now()}`;

  const now = new Date().toISOString();
  const rubric: Rubric = {
    _id: rubricId,
    workspace_id: params.workspaceId,
    rubric_key: slugify(params.title, rubricId),
    title: params.title,
    current_version_id: versionId,
    lifecycle_state: "ACTIVE",
    created_at: now,
    updated_at: now,
  };

  const version: RubricVersion = {
    _id: versionId,
    workspace_id: params.workspaceId,
    rubric_id: rubricId,
    version_no: 1,
    status,
    level_names: params.levelNames,
    criteria,
  };

  mockRubrics.push(rubric);
  mockRubricVersions.push(version);

  return rubric;
}

/**
 * GET /workspaces/:workspaceId/rubrics (GIA DINH -- endpoint chua co
 * trong tai lieu API, dat ten de mo phong) -- danh sach rubric da tao
 * cho 1 lop, dung o man "Lecturer / Class Detail" de GV xac nhan truc
 * quan la rubric da LUU THAT (Yen phan anh 2026-10-25: bam "Xac nhan
 * hoan tat" xong khong thay gi doi khac tren man hinh, tuong nhu chua
 * luu). Sap xep moi nhat len dau (theo rubric._id tang dan ~ thu tu tao).
 */
export async function getRubricsInWorkspace(workspaceId: string): Promise<Rubric[]> {
  const rubrics = mockRubrics
    .filter((r) => r.workspace_id === workspaceId)
    .sort((a, b) => b._id.localeCompare(a._id));

  return delay(rubrics);
}

/** 1 rubric + version hien dang dung (current_version_id) -- du lieu gop cho man xem chi tiet rubric. */
export interface RubricDetail {
  rubric: Rubric;
  version: RubricVersion;
}

/**
 * GET /rubrics/:rubricId (GIA DINH) -- GV xem lai 1 rubric da tao: tieu
 * de, cac muc do dung chung, tung tieu chi (trong so, khoang diem) +
 * checklist cua tieu chi do (noi dung, mode, do quan trong) -- xem
 * RubricDetailPage.tsx. Luon tra ve VERSION HIEN DANG DUNG
 * (`rubric.current_version_id`), chua ho tro xem lai version cu (rubric
 * chi co 1 version duy nhat luc vua tao -- xem lai muc 8.2
 * data-dictionary.md ve clone version khi sua rubric da dung, chua lam
 * UI rieng cho viec nay).
 */
export async function getRubricDetail(rubricId: string): Promise<RubricDetail | undefined> {
  const rubric = mockRubrics.find((r) => r._id === rubricId);
  if (!rubric) return delay(undefined);

  const version = mockRubricVersions.find((v) => v._id === rubric.current_version_id);
  if (!version) return delay(undefined);

  return delay({ rubric, version });
}

/**
 * PATCH /rubrics/:rubricId (GIA DINH) -- sua lai noi dung 1 rubric dang
 * o trang thai DRAFT (RubricCreatePage che do edit -- Yen yeu cau
 * 2026-10-27). Ghi de TRUC TIEP len dung version hien tai (KHONG tang
 * version_no), vi day la sua ban nhap chua tung publish -- khac han
 * "clone de tao version moi" danh rieng cho rubric DA publish
 * (data-dictionary.md muc 8.2: "Published version la immutable. Sua
 * rubric da dung phai clone version" -- luong clone van chua lam UI).
 * Chan sua neu version hien tai KHONG con la DRAFT (vd GV mo 2 tab, 1
 * tab da publish truoc do).
 */
export async function updateRubricDraft(
  rubricId: string,
  params: CreateRubricParams,
  criteria: RubricCriterion[],
  status: RubricVersionStatus,
): Promise<Rubric> {
  await delay(null);

  const rubric = mockRubrics.find((r) => r._id === rubricId);
  if (!rubric) throw new Error("Không tìm thấy rubric để sửa.");

  const version = mockRubricVersions.find((v) => v._id === rubric.current_version_id);
  if (!version) throw new Error("Không tìm thấy phiên bản rubric để sửa.");
  if (version.status !== "DRAFT") {
    throw new Error("Rubric này đã công bố, không thể sửa trực tiếp.");
  }

  rubric.title = params.title;
  rubric.updated_at = new Date().toISOString();
  version.level_names = params.levelNames;
  version.criteria = criteria;
  version.status = status;

  return rubric;
}

/**
 * GET /admin/users -- danh sach TOAN BO user trong he thong, kem vai
 * theo workspace (tu memberships.roles, gop ten workspace) -- dung cho
 * man "Admin / Quan ly tai khoan" (UC-11, FR-AUTH-01-03). Chi Admin
 * (system_roles chua "ADMIN") moi duoc goi API nay khi co backend that.
 */
export async function getAllUsers(): Promise<AdminUserRow[]> {
  const rows: AdminUserRow[] = mockUsers.map((user) => {
    const workspaceRoles = mockMemberships
      .filter((m) => m.user_id === user._id && m.status === "ACTIVE")
      .map((m) => {
        const workspace = mockWorkspaces.find((w) => w._id === m.workspace_id);
        return { workspaceName: workspace?.name ?? "-", roles: m.roles };
      });

    return { ...user, workspaceRoles };
  });

  return delay(rows);
}

/**
 * PATCH /admin/users/:userId -- khoa/mo 1 tai khoan (users.status) --
 * dung cho man "Admin / Quan ly tai khoan". MUTATE truc tiep mockUsers,
 * giong cach mockPipelineProgress duoc mutate o cac ham khac trong file
 * nay -- khi co backend that se thay bang goi API PATCH that.
 */
export async function setUserAccountStatus(
  userId: string,
  status: UserAccountStatus,
): Promise<void> {
  await delay(null);

  const user = mockUsers.find((u) => u._id === userId);
  if (!user) throw new Error("Không tìm thấy tài khoản.");

  user.status = status;
}

/**
 * GET /admin/workspaces -- danh sach TOAN BO workspace (kind=COURSE va
 * RESEARCH, khong loc theo membership nhu getMyWorkspaces/getMyLecturer
 * Workspaces) kem so thanh vien ACTIVE -- dung cho man "Admin / Quan ly
 * lop" (xem ghi chu GIA DINH tren AdminWorkspaceRow, lib/types.ts).
 */
export async function getAllWorkspacesAdmin(): Promise<AdminWorkspaceRow[]> {
  const rows: AdminWorkspaceRow[] = mockWorkspaces.map((workspace) => ({
    ...workspace,
    memberCount: mockMemberships.filter(
      (m) => m.workspace_id === workspace._id && m.status === "ACTIVE",
    ).length,
  }));

  return delay(rows);
}

/**
 * POST /admin/workspaces -- tao 1 workspace (lop) moi, status mac dinh
 * ACTIVE -- dung cho nut "+ Tạo lớp" o man "Admin / Quan ly lop".
 */
export async function createWorkspace(
  params: CreateWorkspaceParams,
): Promise<Workspace> {
  await delay(null);

  // SUA LAI 2026-10-29 (Yen phat hien thieu kiem tra): data-dictionary.md
  // muc 5.2 ghi workspace_key co unique index -- truoc day createWorkspace
  // KHONG kiem tra, cho tao trung ma duoc (bug thuc, khong phai thiet
  // ke). So sanh khong phan biet hoa/thuong + bo khoang trang dau/cuoi vi
  // workspace_key la ma nguoi dung tu go, de tranh trung do khac chu hoa/
  // thuong (vd "mad-1" vs "MAD-1").
  const normalizedKey = params.workspace_key.trim().toLowerCase();
  const isDuplicate = mockWorkspaces.some(
    (w) => w.workspace_key.trim().toLowerCase() === normalizedKey,
  );
  if (isDuplicate) {
    throw new Error(`Mã lớp "${params.workspace_key.trim()}" đã tồn tại, vui lòng chọn mã khác.`);
  }

  const workspace: Workspace = {
    _id: `ws_${Date.now()}`,
    workspace_key: params.workspace_key,
    name: params.name,
    kind: params.kind,
    status: "ACTIVE",
  };
  mockWorkspaces.push(workspace);

  return workspace;
}

/**
 * PATCH /admin/workspaces/:workspaceId -- dong/mo lai 1 lop (status ACTIVE
 * <-> ARCHIVED) -- MUTATE truc tiep mockWorkspaces, cung pattern voi
 * setUserAccountStatus o tren.
 */
export async function setWorkspaceStatus(
  workspaceId: string,
  status: Workspace["status"],
): Promise<void> {
  await delay(null);

  const workspace = mockWorkspaces.find((w) => w._id === workspaceId);
  if (!workspace) throw new Error("Không tìm thấy lớp.");

  workspace.status = status;
}

/**
 * GET /admin/workspaces/:workspaceId/members -- danh sach thanh vien
 * (memberships, KHONG loc status de Admin thay duoc ca thanh vien da bi
 * thu hoi) kem UserProfile tuong ung -- dung cho man "Admin / Thanh vien
 * lop" (gan ai la Giang vien, ai la Sinh vien).
 */
export async function getWorkspaceMembers(
  workspaceId: string,
): Promise<AdminMembershipRow[]> {
  const rows: AdminMembershipRow[] = mockMemberships
    .filter((m) => m.workspace_id === workspaceId)
    .map((membership) => ({
      membership,
      user: mockUsers.find((u) => u._id === membership.user_id) ?? {
        _id: membership.user_id,
        display_name: "(không rõ)",
      },
    }));

  return delay(rows);
}

/**
 * POST /admin/workspaces/:workspaceId/members -- them 1 thanh vien vao
 * lop voi 1 vai tro (STUDENT/LECTURER/...). Neu user da co membership
 * ACTIVE trong lop nay roi thi bao loi thay vi tao trung.
 */
export async function addWorkspaceMember(
  workspaceId: string,
  userId: string,
  role: MembershipRole,
): Promise<Membership> {
  await delay(null);

  // BUG DA SUA 2026-10-29 (Yen phat hien qua demo thuc te): truoc day ham
  // nay chi kiem tra membership dang ACTIVE roi LUON tao 1 dong moi --
  // neu user da tung bi thu hoi (REVOKED) truoc do, "Them thanh vien" lai
  // tao THEM 1 dong trung (user xuat hien 2 lan trong bang, 1 dong
  // REVOKED cu + 1 dong ACTIVE moi) thay vi khoi phuc lai dong cu. Gio
  // tim ca membership REVOKED de MO LAI (cap nhat roles + status) thay vi
  // tao moi, giu unique {workspace_id, user_id} giong index that trong
  // data-dictionary.md muc 5.3.
  const existingActive = mockMemberships.find(
    (m) => m.workspace_id === workspaceId && m.user_id === userId && m.status === "ACTIVE",
  );
  if (existingActive) {
    throw new Error("Người dùng này đã là thành viên đang hoạt động của lớp.");
  }

  const existingRevoked = mockMemberships.find(
    (m) => m.workspace_id === workspaceId && m.user_id === userId && m.status === "REVOKED",
  );
  if (existingRevoked) {
    existingRevoked.roles = [role];
    existingRevoked.status = "ACTIVE";
    return existingRevoked;
  }

  const membership: Membership = {
    _id: `mb_${Date.now()}`,
    workspace_id: workspaceId,
    user_id: userId,
    roles: [role],
    status: "ACTIVE",
  };
  mockMemberships.push(membership);

  return membership;
}

/**
 * PATCH /admin/memberships/:membershipId -- thu hoi hoac mo lai 1 thanh
 * vien (status ACTIVE <-> REVOKED) -- MUTATE truc tiep mockMemberships.
 */
export async function setMembershipStatus(
  membershipId: string,
  status: Membership["status"],
): Promise<void> {
  await delay(null);

  const membership = mockMemberships.find((m) => m._id === membershipId);
  if (!membership) throw new Error("Không tìm thấy thành viên.");

  membership.status = status;
}

/**
 * UC-14 -- xem ghi chu JobRecord (lib/mockData.ts) / AdminJobRow
 * (lib/types.ts). Goc nhin TONG QUAN toan he thong, doc lap voi
 * deriveStages (goc nhin chi tiet 1 bao cao o man Lecturer/Report).
 */
function jobToRow(job: JobRecord): AdminJobRow {
  const doc = mockDocuments.find((d) => d._id === job.documentId);
  const owner = doc ? mockUsers.find((u) => u._id === doc.owner_user_id) : undefined;
  const workspace = doc ? mockWorkspaces.find((w) => w._id === doc.workspace_id) : undefined;
  const latestVersion = mockDocumentVersions
    .filter((v) => v.document_id === job.documentId)
    .sort((a, b) => b.version_no - a.version_no)[0];

  return {
    _id: job._id,
    documentId: job.documentId,
    // Ten FILE cua version MOI NHAT, KHONG dung doc.title -- Yen phat
    // hien 2026-10-24: phai dong bo CACH HIEN THI TEN voi man Sinh vien/
    // Giang vien (xem StudentReportsTable.tsx/DocumentVersionsTable.tsx)
    // de doi chieu duoc, neu moi cho hien 1 kieu ten khac nhau se khong
    // biet co phai cung 1 bao cao hay khong.
    documentTitle: latestVersion?.original_filename ?? doc?.title ?? "(không rõ)",
    documentKey: doc?.document_key ?? "-",
    versionNo: latestVersion?.version_no ?? 1,
    ownerName: owner?.display_name ?? "-",
    workspaceName: workspace?.name ?? "-",
    workspaceKey: workspace?.workspace_key ?? "-",
    stage: job.stage,
    status: job.status,
    startedAt: job.startedAt,
    retryCount: job.retryCount,
  };
}

/** GET /admin/jobs -- toan bo hang doi (man "Admin / Giam sat hang doi", UC-14). */
export async function getJobs(): Promise<AdminJobRow[]> {
  const rows = mockJobs.map(jobToRow);
  return delay(rows);
}

/** POST /admin/jobs/:jobId/cancel -- huy 1 job dang RUNNING. */
export async function cancelJob(jobId: string): Promise<void> {
  await delay(null);

  const job = mockJobs.find((j) => j._id === jobId);
  if (!job) throw new Error("Không tìm thấy job.");
  if (job.status !== "RUNNING") {
    throw new Error("Chỉ có thể huỷ job đang chạy.");
  }

  job.status = "CANCELLED";
}

/**
 * POST /admin/jobs/:jobId/retry -- chay lai 1 job LOI/da huy, gia lap
 * RUNNING roi DONE sau STAGE_SIMPLE_DELAY_MS (giong startPipelineStage).
 */
export async function retryJob(jobId: string): Promise<void> {
  await delay(null);

  const job = mockJobs.find((j) => j._id === jobId);
  if (!job) throw new Error("Không tìm thấy job.");
  if (job.status !== "ERROR" && job.status !== "CANCELLED") {
    throw new Error("Chỉ có thể chạy lại job lỗi hoặc đã huỷ.");
  }

  job.status = "RUNNING";
  job.retryCount += 1;

  setTimeout(() => {
    job.status = "DONE";
  }, STAGE_SIMPLE_DELAY_MS);
}

/**
 * UC-15 (Lecturer / Nguon doi chieu cua lop) -- SUA LAI 2026-10-29: xem
 * ghi chu CorpusSource (lib/types.ts), chuyen tu Admin sang Lecturer,
 * gan theo workspace_id (Yen phat hien actor dung phai la Giang vien).
 */

/** GET /lecturer/workspaces/:workspaceId/corpus-sources -- nguon doi chieu CUA 1 LOP (man "Lecturer / Class Detail", UC-15). */
export async function getCorpusSourcesInWorkspace(workspaceId: string): Promise<CorpusSource[]> {
  const rows = mockCorpusSources.filter((s) => s.workspace_id === workspaceId);
  return delay(rows);
}

/** POST /lecturer/workspaces/:workspaceId/corpus-sources -- dang ky 1 nguon doi chieu moi cho lop, trang thai mac dinh PENDING. */
export async function createCorpusSource(
  params: CreateCorpusSourceParams,
): Promise<CorpusSource> {
  await delay(null);

  const lecturer = mockUsers.find((u) => u._id === CURRENT_LECTURER_ID);

  const source: CorpusSource = {
    _id: `src_${Date.now()}`,
    workspace_id: params.workspace_id,
    title: params.title,
    sourceType: params.sourceType,
    status: "PENDING",
    submittedByName: lecturer?.display_name ?? "Giảng viên",
    submittedAt: new Date().toISOString(),
  };
  mockCorpusSources.push(source);

  return source;
}

/**
 * PATCH /lecturer/corpus-sources/:sourceId -- duyet hoac tu choi 1 nguon
 * doi chieu dang PENDING. GIA DINH (demo): mock chi co 1 tai khoan Giang
 * vien nen CHINH GV dang nhap thuc hien luon buoc duyet nay -- dung ra
 * phai la 1 user khac mang role DATA_APPROVER trong workspace, can Quy
 * xac nhan lai (xem ghi chu CorpusSource, lib/types.ts).
 */
export async function setCorpusSourceStatus(
  sourceId: string,
  status: CorpusSourceStatus,
): Promise<void> {
  await delay(null);

  const source = mockCorpusSources.find((s) => s._id === sourceId);
  if (!source) throw new Error("Không tìm thấy nguồn.");

  source.status = status;
}

/**
 * UC-17 -- xem ghi chu DataLifecycleState (lib/types.ts). Dung chung
 * mockDocuments (toan bo bao cao trong he thong) ket hop
 * mockDataLifecycle (trang thai vong doi, mac dinh ACTIVE).
 */

/** GET /admin/data-lifecycle -- danh sach bao cao kem trang thai vong doi (man "Admin / Vòng đời dữ liệu", UC-17). */
export async function getDataLifecycleRows(): Promise<AdminLifecycleRow[]> {
  const rows: AdminLifecycleRow[] = mockDocuments.map((doc) => {
    const owner = mockUsers.find((u) => u._id === doc.owner_user_id);
    const workspace = mockWorkspaces.find((w) => w._id === doc.workspace_id);
    const lifecycle = mockDataLifecycle[doc._id] ?? { state: "ACTIVE" as DataLifecycleState };
    const latestVersion = mockDocumentVersions
      .filter((v) => v.document_id === doc._id)
      .sort((a, b) => b.version_no - a.version_no)[0];

    return {
      documentId: doc._id,
      // Ten FILE cua version MOI NHAT -- dong bo voi jobToRow o tren
      // (xem ghi chu tren jobToRow).
      documentTitle: latestVersion?.original_filename ?? doc.title,
      documentKey: doc.document_key,
      versionNo: latestVersion?.version_no ?? 1,
      ownerName: owner?.display_name ?? "-",
      workspaceName: workspace?.name ?? "-",
      workspaceKey: workspace?.workspace_key ?? "-",
      state: lifecycle.state,
      archivedAt: lifecycle.archivedAt,
    };
  });

  return delay(rows);
}

/** POST /admin/data-lifecycle/:documentId/archive -- luu tru 1 bao cao (ACTIVE -> ARCHIVED). */
export async function archiveDocumentLifecycle(documentId: string): Promise<void> {
  await delay(null);

  mockDataLifecycle[documentId] = {
    state: "ARCHIVED",
    archivedAt: new Date().toISOString(),
  };
}

/** POST /admin/data-lifecycle/:documentId/restore -- khoi phuc 1 bao cao da luu tru (ARCHIVED -> ACTIVE). */
export async function restoreDocumentLifecycle(documentId: string): Promise<void> {
  await delay(null);

  mockDataLifecycle[documentId] = { state: "ACTIVE" };
}

/**
 * POST /admin/data-lifecycle/:documentId/purge -- xoa vinh vien (tombstone),
 * KHONG the hoan tac -- chi doi trang thai trong mock, khong xoa thuc document
 * de khong lam vo cac man khac dang tham chieu toi (demo minh hoa, chua
 * phai xoa du lieu thuc nhu UC-17 mo ta).
 */
export async function purgeDocumentLifecycle(documentId: string): Promise<void> {
  await delay(null);

  mockDataLifecycle[documentId] = {
    state: "TOMBSTONED",
    archivedAt: mockDataLifecycle[documentId]?.archivedAt ?? new Date().toISOString(),
  };
}

/**
 * ==========================================================================
 * UC-11 (phần còn lại): Policy/Governance, Audit log, System health
 * ==========================================================================
 * Thêm 2026-11-08 -- xem ghi chú AdminGovernanceRow/AuditEventRow/
 * SystemHealthSummary trong lib/types.ts.
 */

/** GET /admin/governance-records -- màn "Admin / Cấu hình policy" (UC-11). */
export async function getGovernanceRecords(): Promise<AdminGovernanceRow[]> {
  return delay([...mockGovernanceRecords]);
}

/**
 * PATCH /admin/governance-records/:id -- duyệt/từ chối/thu hồi 1
 * governance_record. Optimistic concurrency bằng `revision`, cùng quy
 * ước với submitProposalReview/submitSimilarityMatchReview.
 */
export async function setGovernanceRecordStatus(
  recordId: string,
  status: GovernanceStatus,
  expectedRevision: number,
): Promise<void> {
  await delay(undefined);

  const record = mockGovernanceRecords.find((r) => r._id === recordId);
  if (!record) throw new Error("Không tìm thấy governance record.");
  if (record.revision !== expectedRevision) {
    throw new ReviewConflictError();
  }

  record.status = status;
  record.revision += 1;
  if (status === "APPROVED") {
    const admin = mockUsers.find((u) => u.system_roles?.includes("ADMIN"));
    record.approverName = admin?.display_name ?? "Admin hệ thống";
    record.approvedAt = new Date().toISOString();
  }
}

/** GET /admin/audit-events -- màn "Admin / Audit log" (UC-11), CHỈ ĐỌC (append-only, không có hành động sửa/xoá). */
export async function getAuditEvents(): Promise<AuditEventRow[]> {
  const rows = [...mockAuditEvents].sort(
    (a, b) => new Date(b.occurredAt).getTime() - new Date(a.occurredAt).getTime(),
  );
  return delay(rows);
}

/** Ngưỡng demo coi 1 job RUNNING là "nghi ngờ kẹt" -- GIA ĐỊNH, chưa có `heartbeat_at`/`lease_expires_at` thật (data-dictionary.md mục 9.1) để biết chắc. */
const STALE_JOB_THRESHOLD_MS = 10 * 60 * 1000;

/**
 * GET /admin/system-health -- màn "Admin / System health" (UC-11). KHÔNG
 * có bảng riêng trong data-dictionary.md -- tính GIA ĐỊNH DEMO từ
 * `mockJobs` (cùng nguồn với AdminJobsPage, xem jobToRow): đếm theo
 * chặng/trạng thái + cảnh báo job RUNNING quá lâu (nghi ngờ kẹt).
 */
export async function getSystemHealthSummary(): Promise<SystemHealthSummary> {
  const now = Date.now();
  const stageKeys: JobStageKey[] = ["PROCESSING", "SIMILARITY", "RUBRIC"];

  const stages: SystemHealthStageSummary[] = stageKeys.map((stage) => {
    const jobsInStage = mockJobs.filter((j) => j.stage === stage);
    return {
      stage,
      queued: jobsInStage.filter((j) => j.status === "QUEUED").length,
      running: jobsInStage.filter((j) => j.status === "RUNNING").length,
      error: jobsInStage.filter((j) => j.status === "ERROR").length,
      stale: jobsInStage.filter(
        (j) => j.status === "RUNNING" && now - new Date(j.startedAt).getTime() > STALE_JOB_THRESHOLD_MS,
      ).length,
    };
  });

  const summary: SystemHealthSummary = {
    stages,
    totalJobs: mockJobs.length,
    totalError: mockJobs.filter((j) => j.status === "ERROR").length,
    totalStale: stages.reduce((sum, s) => sum + s.stale, 0),
    checkedAt: new Date().toISOString(),
  };

  return delay(summary);
}

/**
 * ==========================================================================
 * UC-08 (CONDITIONAL, RQ3): Targeted Questions
 * ==========================================================================
 * Thêm 2026-11-08 -- xem ghi chú TargetedQuestion trong lib/types.ts.
 */

/** GET /lecturer/documents/:documentId/targeted-questions -- màn "Lecturer / Targeted Questions" (UC-08, chỉ khi RQ3=ENABLED). */
export async function getTargetedQuestions(documentId: string): Promise<TargetedQuestion[]> {
  return delay([...(mockTargetedQuestions[documentId] ?? [])]);
}

export interface SubmitTargetedQuestionReviewParams {
  questionId: string;
  decision: ReviewDecision;
  expectedRevision: number;
  /** Bắt buộc khi decision = EDIT hoặc REJECT (FR-QST-02). */
  reasonText?: string;
  /** Chỉ dùng khi decision = EDIT. */
  editedQuestionText?: string;
}

/** POST .../targeted-questions/:questionId/review -- Accept/Edit/Reject 1 câu hỏi TRƯỚC KHI export (FR-QST-02). */
export async function submitTargetedQuestionReview(
  params: SubmitTargetedQuestionReviewParams,
): Promise<void> {
  await delay(undefined);

  const question = Object.values(mockTargetedQuestions)
    .flat()
    .find((q) => q._id === params.questionId);
  if (!question) throw new Error("Không tìm thấy câu hỏi.");
  if (question.revision !== params.expectedRevision) {
    throw new ReviewConflictError();
  }

  question.decision = params.decision;
  question.reasonText = params.reasonText;
  question.editedQuestionText = params.decision === "EDIT" ? params.editedQuestionText : undefined;
  question.revision += 1;

  appendFeedbackLogEntry({
    documentId: question.documentId,
    source: "TARGETED_QUESTION",
    sourceItemId: question._id,
    itemLabel: question.questionText,
    decision: params.decision,
    reasonText: params.reasonText,
  });
}

/**
 * GET .../targeted-questions/export -- xuất câu hỏi đã Accept/Edit (FR-QST-02:
 * "review/edit/reject TRƯỚC KHI export" -- REJECT thì không export). Mock
 * trả về chuỗi JSON để UI tự tạo file download, chưa có endpoint file thật.
 */
export async function exportTargetedQuestionsJson(documentId: string): Promise<string> {
  const questions = (mockTargetedQuestions[documentId] ?? []).filter(
    (q) => q.decision === "ACCEPT" || q.decision === "EDIT",
  );
  const exportRows = questions.map((q) => ({
    question: q.decision === "EDIT" ? q.editedQuestionText ?? q.questionText : q.questionText,
    type: q.type,
    linkedTo: q.linkedTo,
    decision: q.decision,
  }));
  return delay(JSON.stringify(exportRows, null, 2));
}

/**
 * ==========================================================================
 * UC-12 (CORE, actor Experiment Operator): Chạy, so sánh và xuất thực nghiệm
 * ==========================================================================
 * Thêm 2026-11-08 -- xem ghi chú ExperimentRun trong lib/types.ts.
 */

/** GET /operator/runs -- màn "Experiment Operator / Danh sách run" (UC-12). */
export async function getExperimentRuns(): Promise<ExperimentRun[]> {
  const rows = [...mockExperimentRuns].sort(
    (a, b) => new Date(b.startedAt).getTime() - new Date(a.startedAt).getTime(),
  );
  return delay(rows);
}

/** GET /operator/runs/:runId -- chi tiết 1 run (manifest đầy đủ + metric, FR-EXP-01/02). */
export async function getExperimentRun(runId: string): Promise<ExperimentRun | undefined> {
  return delay(mockExperimentRuns.find((r) => r._id === runId));
}

/**
 * ==========================================================================
 * Feedback Log (FR-REV-04, MUST)
 * ==========================================================================
 * Them 2026-11-08 -- xem ghi chu FeedbackLogEntry trong lib/types.ts +
 * appendFeedbackLogEntry o tren (noi GHI, duy nhat 3 cho goi: UC-05/UC-06/
 * UC-08). 2 ham duoi day CHI DOC (dung quy uoc append-only/bat bien cua
 * FR-REV-04).
 */

/**
 * GET feedback log cua 1 bao cao -- GIA DINH DEMO ve phan quyen: ai xem
 * duoc trang "Lecturer / Report" (GV cua lop chua bao cao do) thi xem
 * duoc log nay, chua co kiem tra rieng theo FR-REV-04 "đúng quyền" (can
 * Quy xac nhan lai khi co API that + mo hinh phan quyen chi tiet hon).
 */
export async function getFeedbackLog(documentId: string): Promise<FeedbackLogEntry[]> {
  const rows = mockFeedbackLog
    .filter((entry) => entry.documentId === documentId)
    .sort((a, b) => new Date(b.occurredAt).getTime() - new Date(a.occurredAt).getTime());
  return delay(rows);
}

/** GET .../feedback-log/export -- xuat TOAN BO log (ca Accept/Edit/Reject) cho error analysis (FR-REV-04). Mock tra chuoi JSON, UI tu tao file download (giong exportTargetedQuestionsJson). */
export async function exportFeedbackLogJson(documentId: string): Promise<string> {
  const rows = mockFeedbackLog.filter((entry) => entry.documentId === documentId);
  return delay(JSON.stringify(rows, null, 2));
}
