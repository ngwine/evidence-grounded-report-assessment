/**
 * Cac type nay bam sat field name trong docs/architecture/data-dictionary.md
 * (W2.2) -- de khi backend that co API, chi can doi lop `lib/api.ts`, khong
 * can sua UI. Khong dung ten "class/lop" o tang code/API -- do chi la nhan
 * hien thi; entity ky thuat la Workspace (kind=COURSE).
 */

export type WorkspaceKind = "COURSE" | "RESEARCH";
export type WorkspaceStatus = "ACTIVE" | "ARCHIVED";

export interface Workspace {
  _id: string;
  workspace_key: string;
  kind: WorkspaceKind;
  name: string;
  status: WorkspaceStatus;
}

export type MembershipRole =
  | "STUDENT"
  | "LECTURER"
  | "OPERATOR"
  | "DATA_APPROVER";
export type MembershipStatus = "ACTIVE" | "REVOKED";

export interface Membership {
  _id: string;
  workspace_id: string;
  user_id: string;
  roles: MembershipRole[];
  status: MembershipStatus;
}

export type DocumentKind = "REPORT" | "CORPUS_SOURCE";
export type DocumentLifecycleState =
  | "ACTIVE"
  | "ARCHIVED"
  | "TOMBSTONED"
  | "PURGING"
  | "PURGED";

/** Logical report -- 1 bai nop cua sinh vien, co the co nhieu version */
export interface ReportDocument {
  _id: string;
  workspace_id: string;
  kind: DocumentKind;
  document_key: string;
  title: string;
  owner_user_id: string | null;
  lifecycle_state: DocumentLifecycleState;
}

export type ReportDisplayStatus =
  | "DANG_NOP"
  | "DA_NOP"
  | "LOI"
  | "DA_CO_KET_QUA";

/**
 * 1 lan nop cua 1 document (document_versions trong data dictionary).
 * `display_status` o day la trang thai GOP tu processing_state +
 * assessment_proposals/reviews/publications cua chinh version nay -- khong
 * phai field goc trong Mongo, backend se tinh va API tra ve san.
 */
export interface DocumentVersion {
  _id: string;
  document_id: string;
  version_no: number;
  file_object_id: string;
  /** Join tu file_objects.original_filename -- ten file GOC sinh vien da tai len cho dung lan nop nay (co the khac nhau giua cac version) */
  original_filename: string;
  /**
   * Join tu file_objects (ten field GIA DINH la size_bytes -- chua xac
   * nhan lai voi data-dictionary.md, nho Yen check lai ten field that roi
   * doi cho khop neu khac).
   */
  file_size_bytes: number;
  submitted_at: string; // ISO datetime (co gio:phut:giay), lay tu document_versions.created_at -- hien thi qua formatDateTime (lib/format.ts)
  /** Trang thai GOP theo goc nhin SINH VIEN (co nop duoc khong, loi khong) */
  display_status: ReportDisplayStatus;
}

/**
 * (2026-10-24) BO field `lecturer_display_status` tinh san kieu cu --
 * trang thai goc nhin GIANG VIEN gio SUY RA TRUC TIEP tu pipeline 5 chang
 * (xem PipelineStageKey/ReportPipelineDetail duoi day + lib/api.ts
 * deriveStages/getListStatus), vi theo yeu cau cua Yen 2026-10-24 trang
 * thai nay KHONG con la du lieu tinh nua ma la VONG DOI THAT, tien len
 * tung buoc do GIANG VIEN tu bam nut kich hoat (xem ReportListStatus).
 */

/** 1 document kem danh sach version cua no, dung cho bang mo rong o Workspace Detail */
export interface ReportDocumentWithVersions extends ReportDocument {
  versions: DocumentVersion[];
}

/**
 * 1 workspace ma user hien tai la thanh vien, kem ten giang vien de hien
 * thi o man danh sach -- ghep tu memberships + workspaces (kind=COURSE).
 */
export interface MyWorkspaceRow extends Workspace {
  lecturer_name: string;
}

/**
 * 1 workspace ma giang vien hien tai quan ly (membership role=LECTURER),
 * kem so luong bao cao dang cho giang vien duyet trong workspace do --
 * dung cho man "Lecturer / Class" (danh sach lop cua giang vien).
 */
export interface LecturerWorkspaceRow extends Workspace {
  /** Dem tu assessment_proposals co status = READY_FOR_REVIEW trong workspace nay */
  pending_review_count: number;
}

/**
 * Field toi thieu cua assessment_proposals (xem data-dictionary.md muc
 * 10.3) -- chi du de tinh so "cho duyet" cho man Lecturer Class List.
 * Khi lam man Lecturer Review that (xem features/review) se can day du
 * field: checklist_results, criterion_scores, rationale, evidence_ids...
 */
export type AssessmentProposalStatus =
  | "DRAFT"
  | "READY_FOR_REVIEW"
  | "ACCEPTED"
  | "REJECTED"
  | "SUPERSEDED";

export interface AssessmentProposal {
  _id: string;
  workspace_id: string;
  report_version_id: string;
  status: AssessmentProposalStatus;
}

/**
 * Tham so goi "Nop bao cao" (man Upload Popup, wireframe W2.4) -- 1 lan
 * nop co the la NEW (tao document moi, lan dau nop) hoac EXISTING (nop
 * them 1 phien ban moi cho 1 document da co san).
 */
export type SubmitReportMode = "NEW" | "EXISTING";

export interface SubmitReportParams {
  workspaceId: string;
  mode: SubmitReportMode;
  /** Bat buoc khi mode = EXISTING -- document can nop them phien ban */
  documentId?: string;
  /** Bat buoc khi mode = NEW -- tieu de bao cao moi */
  title?: string;
  file: File;
}

export interface SubmitReportResult {
  ok: boolean;
  /** Thong bao loi hien thi cho user khi ok = false (vd: sai dinh dang, qua dung luong) */
  error?: string;
  /** Document (kem versions moi nhat) sau khi nop thanh cong, khi ok = true */
  document?: ReportDocumentWithVersions;
}

export type SystemRole = "ADMIN";
export type UserAccountStatus = "ACTIVE" | "DISABLED" | "DELETED";

/**
 * users (data-dictionary.md muc 5.1) -- SUA LAI 2026-10-29 (Yen yeu cau
 * man Admin "Quan ly tai khoan/RBAC", UC-11): truoc day comment o day
 * noi "khong can system_roles/status o day", nhung UC-11 can hien thi +
 * doi dung field do (vai he thong ADMIN, khoa/mo tai khoan) nen them lai
 * cho khop data-dictionary.md. `roles` theo WORKSPACE (STUDENT/LECTURER/
 * OPERATOR/DATA_APPROVER) van nam o `Membership.roles`, KHONG o day --
 * `system_roles` chi danh cho vai toan he thong (hien chi co "ADMIN").
 *
 * ** GHI CHU QUAN TRONG **: data-dictionary.md HIEN KHONG co field luu MSSV
 * trong collection `users`. Field `student_id` o day la GIA DINH TAM THOI
 * de ve dung UI theo wireframe "Lecturer / Class Detail", CHUA duoc xac
 * nhan trong tai lieu ky thuat -- Yen/Quy can quyet dinh: them field nay
 * vao `users`, hay no thuoc ve `memberships` -- roi doi lai cho dung sau
 * khi chot.
 */
export interface UserProfile {
  _id: string;
  display_name: string;
  /** GIA DINH -- xem ghi chu tren interface */
  student_id?: string;
  /** GIA DINH demo (Admin): khong phai moi mock user deu co san field nay */
  email_normalized?: string;
  system_roles?: SystemRole[];
  status?: UserAccountStatus;
}

/**
 * 1 sinh vien trong 1 workspace, kem TOAN BO bao cao (documents, da gom
 * versions cua tung cai) cua chinh sinh vien do -- dung cho man "Lecturer
 * / Class Detail": moi dong la 1 sinh vien, mo rong ra thay danh sach cac
 * bao cao ho da nop (khac voi "mo rong 1 bao cao de thay cac phien ban"
 * ben man Student).
 */
export interface StudentReportsRow {
  student: UserProfile;
  documents: ReportDocumentWithVersions[];
}

/**
 * 1 dong trong man "Admin / Quan ly tai khoan" (UC-11) -- gop UserProfile
 * voi vai THEO WORKSPACE cua user do (tu memberships.roles, hien thi kem
 * ten workspace), de phan biet voi `system_roles` (vai toan he thong,
 * nam san tren UserProfile).
 */
export interface AdminUserRow extends UserProfile {
  workspaceRoles: { workspaceName: string; roles: MembershipRole[] }[];
}

/**
 * 1 dong trong man "Admin / Quan ly lop" (danh sach workspace) -- gop
 * Workspace voi so thanh vien ACTIVE (khong phan biet vai tro) de Admin
 * nhin nhanh lop nao co nguoi, lop nao chua. Chua co UC/FR nao ghi ro
 * "ai tao workspace" trong tai lieu ky thuat -- GIA DINH la viec cua
 * Admin (UC-11 "quan tri tai khoan, policy va van hanh"), can Quy xac
 * nhan lai sau.
 */
export interface AdminWorkspaceRow extends Workspace {
  memberCount: number;
}

/**
 * 1 dong trong bang thanh vien cua 1 workspace (man "Admin / Thanh vien
 * lop") -- gop Membership voi UserProfile cua chinh thanh vien do, de
 * Admin xem/gan ai la Giang vien, ai la Sinh vien trong lop nay.
 */
export interface AdminMembershipRow {
  membership: Membership;
  user: UserProfile;
}

export interface CreateWorkspaceParams {
  workspace_key: string;
  name: string;
  kind: WorkspaceKind;
}

/**
 * UC-14 (Giam sat hang doi xu ly, actor Giang vien + Quan tri vien) --
 * ban demo o day la man "Admin / Giam sat hang doi" rieng, MO PHONG hang
 * doi job tren toan he thong (khong tai su dung truc tiep
 * mockPipelineProgress vi man do la goc nhin CHI TIET tung buoc nho cua
 * 1 bao cao, con day la goc nhin TONG QUAN 1 job = 1 chang dang chay/loi)
 * -- GIA DINH toan bo cach mo hinh hoa "job" nay, chua co trong
 * data-dictionary.md, chi de Yen xem truoc hinh dung UI, can Quy xac
 * nhan lai khi lam API that.
 */
export type JobStatus = "QUEUED" | "RUNNING" | "DONE" | "ERROR" | "CANCELLED";

/**
 * Chi 3/5 chang cua PipelineStageKey la job xu ly NEN thuc su (theo
 * bo-use-case.md muc 6.1: "UC-14 ho tro Job cua UC-02, UC-04, UC-12,
 * UC-15, UC-17" -- UC-04 la "chay phan tich" = PROCESSING+SIMILARITY+
 * RUBRIC). REVIEW (Duyet, UC-05/06) va PUBLISH (Cong bo, UC-10) la HANH
 * DONG CUA NGUOI (giang vien tu bam), khong phai job chay nen co the bi
 * ket/can retry -- Yen phat hien 2026-10-24, bo ra khoi hang doi Admin.
 */
export type JobStageKey = Extract<PipelineStageKey, "PROCESSING" | "SIMILARITY" | "RUBRIC">;

export interface AdminJobRow {
  _id: string;
  documentId: string;
  documentTitle: string;
  documentKey: string;
  /** Phien ban (version_no) MOI NHAT cua document, dong bo cach hien thi voi man Sinh vien (DocumentVersionsTable) va Giang vien (LecturerReportDetailPage) -- Yen yeu cau 2026-10-24. */
  versionNo: number;
  ownerName: string;
  /** Ten + MA lop (workspace) chua bao cao nay -- Admin xem TOAN HE THONG (khong can vao tung workspace), cot nay de biet job thuoc lop nao. Can CA MA (workspace_key) vi 2 lop co the TRUNG TEN (Yen phat hien 2026-10-29, xem workspace_key trong Workspace). */
  workspaceName: string;
  workspaceKey: string;
  stage: JobStageKey;
  status: JobStatus;
  startedAt: string;
  retryCount: number;
}

/**
 * UC-15 (Quan ly nguon doi chieu / source corpus) -- SUA LAI 2026-10-29
 * (Yen phat hien): bo-use-case.md muc 7.9 ghi actor UC-15 la "Giang
 * vien" (bang use-case dong 169) va GV dang ky source kem "...license/
 * consent, purpose, retention va approver. Chi source APPROVED moi duoc
 * index...". Field "approver" nay khop voi role DATA_APPROVER da co san
 * trong Membership.roles (data-dictionary.md muc 5.3) -- nghia la nguoi
 * duyet la 1 vai tro THEO LOP (workspace), khong phai Quan tri vien he
 * thong. Vi vay man nay chuyen tu Admin (/admin/corpus, da go bo) sang
 * Lecturer (gan workspace_id, hien trong "Lecturer / Class Detail").
 *
 * GIA DINH (demo): vi mock hien chi co 1 tai khoan Giang vien duy nhat
 * (chua co user rieng mang role DATA_APPROVER), man demo cho phep CHINH
 * Giang vien dang nhap vua dang ky vua duyet -- thuc te can 1 user khac
 * voi role DATA_APPROVER trong workspace de duyet, can Quy xac nhan lai.
 */
export type CorpusSourceType = "INTERNAL_REPORT" | "EXTERNAL_DOC" | "WEB";
export type CorpusSourceStatus = "PENDING" | "APPROVED" | "REJECTED";

export interface CorpusSource {
  _id: string;
  workspace_id: string;
  title: string;
  sourceType: CorpusSourceType;
  status: CorpusSourceStatus;
  submittedByName: string;
  submittedAt: string;
}

export interface CreateCorpusSourceParams {
  workspace_id: string;
  title: string;
  sourceType: CorpusSourceType;
}

/**
 * UC-17 (Quan ly vong doi du lieu: luu tru/tombstone/xoa vinh vien).
 * GIA DINH them 1 "trang thai vong doi" rieng cho document (ACTIVE mac
 * dinh cho moi bao cao hien co) -- data-dictionary.md chua dinh nghia
 * rieng field nay, can Quy xac nhan lai.
 */
export type DataLifecycleState = "ACTIVE" | "ARCHIVED" | "TOMBSTONED";

export interface AdminLifecycleRow {
  documentId: string;
  documentTitle: string;
  documentKey: string;
  /** Phien ban (version_no) MOI NHAT cua document -- xem ghi chu tren AdminJobRow. */
  versionNo: number;
  ownerName: string;
  /** Ten + MA lop (workspace) chua bao cao nay -- xem ghi chu tren AdminJobRow. */
  workspaceName: string;
  workspaceKey: string;
  state: DataLifecycleState;
  archivedAt?: string;
}

/**
 * rubrics (data-dictionary.md muc 8.1) -- 1 rubric gan theo 1 workspace
 * tu dau (co field workspace_id), dung cho nut "+ Tao rubric" o man
 * Lecturer Class Detail.
 */
export interface Rubric {
  _id: string;
  workspace_id: string;
  rubric_key: string;
  title: string;
  current_version_id: string;
  /** GIA DINH gia tri cu the -- dictionary chi noi chung "lifecycle_state" (xem muc 2.3), khong liet ke rieng cho rubrics */
  lifecycle_state: "ACTIVE" | "ARCHIVED";
  /**
   * ISO date string -- field dung chung BAT BUOC cho moi document theo
   * data-dictionary.md muc 2.2 ("Authoritative document bat buoc co"),
   * muc 8.1 chi ghi tat "common mutable fields" thay vi liet lai. Them
   * de hien thi "Tao luc..." o UI -- Yen yeu cau 2026-10-27.
   */
  created_at: string;
  /** Cung quy uoc nhu created_at -- "Document mutable them" o muc 2.2. */
  updated_at: string;
}

export type RubricVersionStatus = "DRAFT" | "PUBLISHED" | "RETIRED";

/**
 * 1 muc diem (vung [min,max]) trong 1 tieu chi -- rubric_versions.criteria[].levels[]
 * (data-dictionary.md muc 8.2 chi mo ta chung "Score rule/example", CHUA
 * liet ke ten field cu the -- GIA DINH theo docs/rubric/rubric-v1.md muc 2:
 * cac muc KHONG co ten/mo ta rieng tung tieu chi -- ten muc dung CHUNG cho
 * toan bo rubric, xem `RubricVersion.level_names` ben duoi; `levels[]` cua
 * 1 tieu chi chi con lai [min,max], gan theo THU TU voi `level_names`
 * (levels[0] <-> level_names[0], v.v). Quy uoc bien (theo rubric-v1.md
 * muc 2 -- vd [8.5,10.0] roi [7.0,8.5)): muc dau tien (index 0, tot nhat)
 * dong CA 2 dau (max PHAI bang dung weight cua tieu chi); cac muc con lai
 * dong o dau min, HO o dau max (max cua muc duoi = min cua muc tren, khong
 * trung). Quy uoc nay do Rubric Compiler/scoring engine (Quy thiet ke) ap
 * dung, UI o day chi luu [min,max] theo quy uoc tren.
 */
export interface RubricCriterionLevel {
  min: number;
  max: number;
}

/**
 * mode cua 1 checklist -- LOCAL (kiem tra trong pham vi 1 doan/section) vs
 * GRAPH (can doi chieu nhieu noi, multi-hop) -- dung thuat ngu da thong
 * nhat tu rubric-v1.md (Task 1) va data-dictionary.md (`analysis_runs.mode`).
 */
export type ChecklistMode = "LOCAL" | "GRAPH";

/**
 * Do quan trong cua 1 checklist -- CORE (Cot loi) / REQUIRED (Bat buoc) /
 * OPTIONAL (Khong bat buoc) -- theo docs/rubric/rubric-v1.md muc 4: he
 * thong TU DONG du doan nhan nay dua vao TU KHOA trong noi dung tieu
 * chi/checklist (vd chua "phai"/"bat buoc tuyet doi" -> CORE; chua
 * "nen"/"khuyen khich"/"tuy chon" -> OPTIONAL; con lai mac dinh ->
 * REQUIRED, vi theo Yen "thuong thi moi tieu chi deu bat buoc neu ko co
 * gi dac biet trong cau tu"). GV luon sua lai nhan nay duoc. Bo tu khoa cu
 * the o day la GIA DINH de demo -- can Quy/GVHD chot lai bo tu khoa that
 * (xem docs/rubric/rubric-notes-ui-data.md).
 */
export type ChecklistImportance = "CORE" | "REQUIRED" | "OPTIONAL";

/**
 * 1 checklist item -- rubric_versions.criteria[].checklists[]
 * (data-dictionary.md muc 8.2 chi mo ta chung "Atomic condition/evidence/
 * mode", CHUA liet ke ten field cu the -- `condition` o day la GIA DINH).
 * Duoc Rubric Compiler (EP-05-S09, PRODUCT_BACKLOG.md -- "Compiler
 * deterministic") tach tu criteria, KHONG phai AI/LLM phan tich tu do --
 * mock nay gia lap bang 1 quy tac don gian (xem lib/api.ts).
 */
export interface RubricChecklistItem {
  _id: string;
  checklist_key: string;
  criterion_key: string;
  condition: string;
  mode: ChecklistMode;
  /** GIA DINH -- data-dictionary.md muc 8.2 chua liet ke field nay, xem ChecklistImportance */
  importance: ChecklistImportance;
}

/** 1 tieu chi trong rubric -- rubric_versions.criteria[] (data-dictionary.md muc 8.2) */
export interface RubricCriterion {
  _id: string;
  criterion_key: string;
  title: string;
  /**
   * Trong so theo DUNG thang diem goc cua mon hoc (GV tu quyet dinh, vd
   * mon cham thang 6 thi tong trong so cac tieu chi = 6) -- KHONG co quy
   * dinh tong phai bang 100 hay 10; UI chi hien thi tong hien tai de GV tu
   * theo doi, khong chan nhap (theo trao doi voi Yen).
   */
  weight: number;
  levels: RubricCriterionLevel[];
  checklists: RubricChecklistItem[];
}

/** rubric_versions (data-dictionary.md muc 8.2) */
export interface RubricVersion {
  _id: string;
  workspace_id: string;
  rubric_id: string;
  version_no: number;
  status: RubricVersionStatus;
  /**
   * Ten cac muc do danh gia -- CHUNG cho TOAN BO tieu chi trong rubric nay
   * (2-6 muc, vd ["Tot","Kha","Trung binh","Yeu"], thu tu tu tot nhat ->
   * kem nhat) -- theo docs/rubric/rubric-v1.md muc 2. GIA DINH ve vi tri
   * field nay: data-dictionary.md muc 8.2 CHUA co field nay o cap
   * rubric_versions (chi co `criteria[].levels[]` per-criterion) -- can
   * Quy/GVHD xac nhan bo sung (xem docs/rubric/rubric-notes-ui-data.md).
   */
  level_names: string[];
  criteria: RubricCriterion[];
}

/** Tham so goi "Tao rubric" (buoc 1 -- nhap tieu chi + diem chia muc, chua co checklist) */
export interface CreateRubricParams {
  workspaceId: string;
  title: string;
  /** Ten muc dung chung cho moi tieu chi, 2-6 muc, tu tot nhat -> kem nhat */
  levelNames: string[];
  criteria: Array<{
    title: string;
    weight: number;
    /**
     * Diem chia giua 2 muc lien tiep (KHONG phai [min,max] -- GV chi nhap
     * (so muc - 1) diem chia, giam dan, he thong tu suy ra [min,max] cua
     * tung muc + quy uoc dong/ho dau theo rubric-v1.md muc 2). Vd 4 muc
     * (Tot/Kha/TB/Yeu), weight=10 -> breakpoints=[8.5,7.0,5.0] sinh ra
     * Tot=[8.5,10.0], Kha=[7.0,8.5), TB=[5.0,7.0), Yeu=[0,5.0).
     */
    breakpoints: number[];
  }>;
}

/**
 * Man "Lecturer / Report" (xu ly 1 bao cao da nop) -- theo wireframe gui
 * 2026-10-18 (chi tham khao UI). Pipeline xu ly gop lam 5 CHANG, map tu
 * cac entity trong data-dictionary.md: Tien trinh xu ly ~ document_versions
 * processing_state (muc 6), Similarity ~ phan tich giong nhau (feature
 * "similarity" rieng, chua co bang trong dictionary muc 6-10 duoc dat
 * ten cu the), Rubric ~ cham theo rubric_versions (muc 8) qua analysis_runs
 * (muc 10), Duyet ~ reviews.decision (muc 10.4), Cong bo ~
 * publications.state (muc 10.5). GIA DINH toan bo cach gop 5 chang nay
 * (dictionary khong mo ta rieng 1 "pipeline view" nhu the) -- can Quy xac
 * nhan lai, danh dau de sau nay doi thanh goi API that de lay dung field.
 */
export type PipelineStageKey =
  | "PROCESSING"
  | "SIMILARITY"
  | "RUBRIC"
  | "REVIEW"
  | "PUBLISH";

/**
 * (2026-10-24) 5 trang thai, theo yeu cau cua Yen: pipeline KHONG con tu
 * chay/co san du lieu nua -- GIANG VIEN phai tu bam nut kich hoat tung
 * chang (xem lib/api.ts startPipelineStage).
 * - WAITING: bi KHOA, chang TRUOC chua xong nen chua bam duoc (nut an/mo).
 * - NOT_STARTED: da MO KHOA (chang truoc xong roi) nhung GV CHUA bam --
 *   nut hien ra, bam duoc.
 * - RUNNING: GV da bam, dang gia lap "goi backend" xu ly.
 * - DONE / ERROR: xong / loi.
 */
export type PipelineStageStatus = "WAITING" | "NOT_STARTED" | "RUNNING" | "DONE" | "ERROR";

/** 1 buoc nho trong 1 chang co nhieu buoc con (hien "Tien trinh xu ly" 4 buoc, "Similarity" 2 buoc) -- GIA DINH ten + so buoc, can Quy xac nhan lai processing that co nhung buoc nao */
export interface ProcessingStepItem {
  key: string;
  label: string;
  status: "DONE" | "RUNNING" | "PENDING";
  /** Hien thi dang text san (gia lap) -- vd "12/10/2025 09:10:00 (2 giây)" hoac "12/10/2025 09:10:37 · đang chạy" */
  timeLabel?: string;
}

/**
 * 1 doan trong bao cao bi phat hien trung/giong voi 1 nguon da duyet --
 * hang trong bang "Ket qua so khop" o chang Similarity khi DONE (Yen
 * yeu cau 2026-10-27, theo wireframe gui kem: co o Empty (mang rong) va
 * o co ket qua (bang) -- GIA DINH ten + cau truc field, chua co trong
 * data-dictionary.md muc rieng cho similarity, can Quy xac nhan lai khi
 * co API that.
 *
 * SUA LAI 2026-11-08: them `decision/reasonText/editedNote/revision` --
 * audit lai docs/week-01/W1-04-bo-use-case.md phat hien dong UC-05 ghi
 * ro dieu kien chap nhan la "Match được Accept/Edit/Reject; không tự kết
 * luận đạo văn" (FR-SIM-05-07, FR-REV-01/02), MAU THUAN voi quyet dinh
 * cu o day (2026-10-27/28, xem comment cu da xoa tren
 * AssessmentProposalReview + ReviewDecision ben duoi): truoc day doc
 * rieng bang FR-SIM-06/07 (chi noi "hien thi") roi ket luan Similarity
 * KHONG co accept/reject rieng tung doan, bo qua dong UC-05 trong bang
 * use-case. Rilakkuma xac nhan 2026-11-08: lam theo UC-05, MOI match la
 * 1 quyet dinh DOC LAP (khac Rubric -- Rubric chi co 1 proposal DUY NHAT
 * cho ca bao cao, xem AssessmentProposalReview). Khong co "diem" de sua
 * nhu Rubric (Similarity khong cham diem) nen Edit o day chi la GV tu
 * ghi chu/dieu chinh nhan dinh (editedNote), KHONG co editedCriterionScores
 * tuong tu.
 */
export interface SimilarityMatch {
  _id: string;
  /** Doan van trong bao cao cua SV (hien toi da ~100 ky tu kem "...") */
  excerpt: string;
  /** Vi tri doan do trong bao cao (vd "Trang 3, đoạn 2") -- GIA DINH */
  location: string;
  /** Ten/nhan nguon bi trung (vd ten 1 bao cao/tai lieu da duyet khac) */
  sourceLabel: string;
  /** Link toi nguon do neu co (GIA DINH, co the chua co trong demo) */
  sourceUrl?: string;
  /** 0-100, sap xep giam dan o UI */
  similarityPercent: number;
  /** Loai tuong dong (vd "Trích dẫn", "Diễn giải lại"...) -- GIA DINH, co the chua xac dinh duoc (undefined) */
  matchType?: string;
  /**
   * Doan van DAY DU xung quanh doan nghi van (ca cau truoc/sau trong bao
   * cao cua SV) -- dung de hien thi + highlight trong popup "Chi tiet
   * doan nghi van" (khac voi `excerpt` o tren, vi `excerpt` chi 1 doan
   * ngan da cat bot de hien trong bang). GIA DINH -- Yen yeu cau
   * 2026-10-27, theo wireframe popup gui kem.
   */
  context?: string;
  /** Phan text trong `context` can duoc to mau nen de de nhin -- PHAI la substring chinh xac cua `context`. GIA DINH. */
  highlightText?: string;
  /**
   * Doan van tuong ung duoc trich TU NGUON -- GIA DINH, HIEN KHONG dung
   * trong UI nua (RubricDetailPage/popup Similarity chi hien ten/ID tai
   * lieu nguon, khong bia doan trich, vi evidence_items trong
   * data-dictionary.md muc 10.2 chi chac chan co source_document_version_id,
   * chua ro co luu quote_text rieng cho phia nguon hay khong -- Yen quyet
   * dinh 2026-10-27: giu field nay lai, cho den khi xac nhan voi Quy roi
   * doi UI lai sau neu backend that co tra ve).
   */
  sourceExcerpt?: string;

  /**
   * Optimistic concurrency cho duyet TUNG MATCH rieng (UC-05) -- cung quy
   * uoc voi AssessmentProposalReview.revision ben duoi: tang len sau MOI
   * lan duyet thanh cong, client gui kem revision dang giu luc submit,
   * lech revision -> server tra 409 REVISION_CONFLICT (xem
   * ReviewConflictError, lib/api.ts). Mock data khoi tao = 1.
   */
  revision: number;
  /** undefined = CHUA duyet match nay */
  decision?: ReviewDecision;
  /** Bat buoc nhap khi decision la EDIT hoac REJECT (FR-REV-01: "kèm reason khi cần") */
  reasonText?: string;
  /** Chi co y nghia khi decision = EDIT -- GV tu ghi chu/dieu chinh nhan dinh ve doan nay (vd xac dinh lai dung la trich dan hop le, khong phai dao van) */
  editedNote?: string;
}

/**
 * Ket qua 1 checklist con sau khi cham (hang CON trong bang "Ket qua
 * cham diem" o chang Rubric, thuoc 1 tieu chi cha) -- Yen yeu cau
 * 2026-10-28, theo wireframe gui kem (giong Similarity: co Loading +
 * Da xong, bang mo rong duoc theo tieu chi cha). GIA DINH cau truc +
 * 3 muc ket qua, chua co trong data-dictionary.md muc rieng cho ket
 * qua cham rubric (chi co rubric_versions.criteria[].checklists dinh
 * nghia DIEU KIEN, khong phai KET QUA cham), can Quy xac nhan lai khi
 * co API that.
 */
export type RubricChecklistOutcome = "DAT" | "CHUA_DAT" | "KHONG_DU_CO_SO";

/**
 * Quan he claim-evidence (data-dictionary.md muc 10.2, field
 * `verification_state`) -- SUPPORTED/CONTRADICTED/INSUFFICIENT, dung
 * nguyen ten tu dictionary (khong dich, vi la trang thai ky thuat noi
 * bo cua pipeline, UI se map sang nhan tieng Viet o statusMaps.ts).
 */
export type EvidenceVerificationState = "SUPPORTED" | "CONTRADICTED" | "INSUFFICIENT";

/**
 * 1 `evidence_item` (data-dictionary.md muc 10.2) lam bang chung cho 1
 * checklist -- them 2026-11-08 de thay the link placeholder "Xem bằng
 * chứng" cu (truoc chi la 1 <a href="#">, chua co man chi tiet thuc su).
 * Bam field theo dung dictionary: `sourceLabel` join tu
 * `source_document_version_id`, `locatorLabel` la hien thi GIA DINH cua
 * field `locator` (object, dictionary khong dinh nghia shape cu the --
 * dung chung quy uoc hien thi voi SimilarityMatch.location), `quoteText`
 * = `quote_text` (doan trich CHINH XAC tu nguon), `verificationState` =
 * `verification_state`, `verificationReasonCode` = `verification_reason_code`
 * (GIA DINH gia tri demo theo cac vi du trong dictionary: DIRECT_SUPPORT,
 * DIRECT_CONTRADICTION, CONTEXT_MISMATCH, SOURCE_AUTHORITY_UNKNOWN -- can
 * Quy xac nhan lai bo gia tri day du khi co API that).
 */
export interface EvidenceItem {
  _id: string;
  sourceLabel: string;
  locatorLabel: string;
  quoteText: string;
  verificationState: EvidenceVerificationState;
  verificationReasonCode?: string;
}

export interface RubricChecklistScore {
  _id: string;
  /** Noi dung dieu kien cua checklist (giong rubric_versions.criteria[].checklists[].condition) */
  condition: string;
  outcome: RubricChecklistOutcome;
  /**
   * Danh sach bang chung ho tro outcome nay (data-dictionary.md muc
   * 10.3: checklist_results[].evidence_ids -- la MANG, co the nhieu
   * bang chung cho 1 checklist). SUA LAI 2026-11-08: THAY THE field
   * `evidenceUrl?: string` cu (chi la link placeholder "#", chua co noi
   * dung thuc) bang danh sach EvidenceItem day du. Mang rong/undefined =
   * "Không có bằng chứng" (thuong di kem outcome = KHONG_DU_CO_SO).
   */
  evidence?: EvidenceItem[];
}

/** Ket qua cham cua 1 tieu chi cha (hang CHA, mo rong de xem checklist con) -- trong so lay tu rubric_versions.criteria[].weight, diem la GIA DINH DEMO tu he thong cham suy ra. */
export interface RubricCriterionScore {
  _id: string;
  title: string;
  weight: number;
  /** Tom tat ket qua cac checklist con (vd "2/3 checklist đạt, 1 chưa đạt") -- GIA DINH, hien o cot "Kết quả" cua hang cha */
  resultSummary: string;
  /** Diem de xuat cho tieu chi nay (GIA DINH DEMO) */
  score: number;
  checklists: RubricChecklistScore[];
}

/** Toan bo bang "Ket qua cham diem" khi chang Rubric DONE -- Yen yeu cau 2026-10-28. */
export interface RubricScoreResult {
  criteria: RubricCriterionScore[];
  /** Tong diem de xuat (GIA DINH DEMO, "chi mang tinh de xuat" theo ghi chu cuoi bang) */
  totalScore: number;
}

export interface PipelineStage {
  status: PipelineStageStatus;
  /** Nhan phu hien ben canh tieu de chang (vd "Chưa bắt đầu", "Đang chờ", "Đang xử lý", "Đã công bố") */
  statusLabel: string;
  /** "Tien trinh xu ly", "Similarity" va (tu 2026-10-28) "Rubric" co danh sach buoc chi tiet; cac chang con lai (Duyet/Cong bo) chua co UI rieng, chi NOT_STARTED/WAITING/RUNNING/DONE don gian */
  steps?: ProcessingStepItem[];
  /** CHI co o chang Similarity khi status=DONE -- mang rong = khong phat hien doan nao trung khop (Empty state), co phan tu = hien bang "Ket qua so khop". */
  similarityMatches?: SimilarityMatch[];
  /** CHI co o chang Rubric khi status=DONE -- bang "Ket qua cham diem" (Yen yeu cau 2026-10-28). */
  rubricScore?: RubricScoreResult;
}

/** Du lieu gop cho 1 bao cao (document_version moi nhat) de hien thi man "Lecturer / Report" */
export interface ReportPipelineDetail {
  workspaceId: string;
  workspaceName: string;
  documentId: string;
  documentTitle: string;
  studentName: string;
  studentId: string;
  versions: DocumentVersion[];
  /** Version dang xem (mac dinh = moi nhat) */
  currentVersion: DocumentVersion;
  stages: Record<PipelineStageKey, PipelineStage>;
}

/**
 * Man "Duyet" (chang REVIEW) -- SUA LAI 2026-10-28 cho dung
 * docs/architecture/data-dictionary.md muc 10.3-10.4 +
 * docs/week-01/W1-03-dac-ta-yeu-cau-v1.md (FR-REV-01/02) sau khi Yen hoi
 * "co trong tai lieu ky thuat khong":
 *
 * - "proposal" (assessment_proposals, muc 10.3) la 1 KHOI DUY NHAT cho
 *   CA bao cao -- gom het criteria_scores/checklist_results/total_score
 *   cua 1 lan cham rubric, KHONG phai tung tieu chi/checklist rieng le.
 *   GV Accept/Edit/Reject nguyen 1 proposal (`reviews`, muc 10.4:
 *   decision + reason_text + edited_scores/edited_rationale, optimistic
 *   concurrency bang expected_proposal_revision -> conflict 409).
 * - SUA LAI 2026-11-08 (Rilakkuma xac nhan sau khi audit lai
 *   W1-04-bo-use-case.md): dong o tren tung ghi "Similarity KHONG nam
 *   trong co che proposal/review nay" dua theo FR-SIM-06/07 (chi noi
 *   "hien thi") NHUNG BO QUA dong UC-05 trong CHINH bang use-case, noi
 *   ghi ro dieu kien chap nhan la "Match được Accept/Edit/Reject; không
 *   tự kết luận đạo văn" (FR-SIM-05-07, FR-REV-01/02) -- day la MAU
 *   THUAN can sua. Similarity GIO CO Accept/Edit/Reject, nhung KHAC voi
 *   Rubric: KHONG gop thanh 1 proposal duy nhat, MOI SimilarityMatch la
 *   1 quyet dinh DOC LAP (xem decision/reasonText/editedNote/revision
 *   tren SimilarityMatch o tren) -- vi UC-05 noi "Match được
 *   Accept/Edit/Reject" (so nhieu, tung match), khong giong UC-06 noi
 *   ve 1 proposal gop. GV van thao tac o chang Similarity (khong phai
 *   chang Duyet/REVIEW) -- xem SimilarityResults/SimilarityMatchModal,
 *   features/review/LecturerReportDetailPage.tsx.
 *
 * KHAC voi 4 chang truoc: Duyet KHONG co "tien trinh chay" (khong
 * RUNNING/Bat dau) -- chang nay MO KHOA la GV thao tac truc tiep, roi tu
 * bam "Công bố" rieng (Yen xac nhan 2026-10-28: bam Công bố o day la
 * publish LUON, tu dong hoan tat ca chang Công bố, GV khong can mo chang
 * Công bố rieng bam lai).
 */
export type ReviewDecision = "ACCEPT" | "EDIT" | "REJECT";

/**
 * 1 `assessment_proposal` (data-dictionary.md muc 10.3) cho 1 bao cao,
 * GOP VOI 1 `review` (muc 10.4) GV tao ra khi duyet -- `criteria`/
 * `totalScore` la GIA DINH DEMO he thong de xuat SAN (tai su dung dung
 * cau truc voi RubricScoreResult o chang Rubric, vi cung 1 nguon du
 * lieu). Dat ten RIENG voi `AssessmentProposal` (dinh nghia toi gian o
 * tren, dung cho so dem o Lecturer Class List) de tranh trung ten -- 2
 * type nay NEN duoc gop lai khi lam API that, gio tach rieng cho nhanh,
 * khong dam dung lai cho dang dung o noi khac.
 */
export interface AssessmentProposalReview {
  _id: string;
  criteria: RubricCriterionScore[];
  totalScore: number;
  /** undefined = CHUA duyet */
  decision?: ReviewDecision;
  /** Bat buoc nhap khi decision la EDIT hoac REJECT (data-dictionary.md muc 10.4: reason_text) */
  reasonText?: string;
  /** Chi co y nghia khi decision = EDIT (data-dictionary.md muc 10.4: edited_rationale) */
  editedNote?: string;
  /** Chi co y nghia khi decision = EDIT -- diem GV tu sua lai cho tung tieu chi, key = RubricCriterionScore._id (data-dictionary.md muc 10.4: edited_scores) */
  editedCriterionScores?: Record<string, number>;
  /**
   * Optimistic concurrency, mo phong `expected_proposal_revision` o
   * data-dictionary.md muc 10.4 -- tang len sau MOI lan duyet thanh cong.
   * Client gui kem revision dang giu khi submit; lech revision (vd ai do
   * khac da duyet truoc) -> server tra 409 REVISION_CONFLICT.
   */
  revision: number;
}

/**
 * Chip RUT GON (4 gia tri) dung cho DANH SACH bao cao (StudentReportsTable,
 * cot dem o LecturerClassDetailPage) -- suy tu pipeline 5 chang o tren
 * (xem lib/api.ts getListStatus), KHONG phai field rieng luu san. Thay the
 * hoan toan cho `LecturerReportDisplayStatus` kieu cu (da bo, xem ghi chu
 * tren DocumentVersion).
 * - SUBMITTED ("Đã nộp"): chua bam nut nao (PROCESSING con NOT_STARTED).
 * - PROCESSING ("Đang xử lý"): da bam it nhat 1 chang, chua cong bo xong.
 * - PUBLISHED ("Đã công bố"): chang Cong bo = DONE.
 * - ERROR ("Lỗi"): co chang nao loi.
 */
export type ReportListStatus = "SUBMITTED" | "PROCESSING" | "PUBLISHED" | "ERROR";

/**
 * Man "Xem publication" (`UC-09` trong bo-use-case.md, CORE, actor Sinh
 * vien) -- Yen yeu cau 2026-10-28, sau khi audit tai lieu ky thuat phat
 * hien SV chua co man nao de xem ket qua da cong bo (chi thay badge "Đã
 * có kết quả", khong bam vao dau duoc). Theo UC-09 muc 7.8: "chỉ cho
 * sinh viên được cấp quyền xem publication, KHONG hien thi proposal
 * hoặc review history nội bộ" -- vi vay type nay CHI chua GIA TRI CUOI
 * CUNG (diem, ket qua checklist, similarity report), KHONG co cac
 * truong decision/reasonText/editedNote/revision nhu
 * AssessmentProposalReview (nhung truong do la noi bo GV, SV khong duoc
 * thay).
 */
export interface PublicationDetail {
  workspaceId: string;
  workspaceName: string;
  documentId: string;
  documentTitle: string;
  versionNo: number;
  /** GIA DINH DEMO -- lay tu luc GV bam "Công bố" (xem lib/api.ts publishReportReview) */
  publishedAt: string;
  /** undefined = chang Rubric chua co ket qua cham cho bao cao nay (hiem, GIA DINH DEMO) */
  rubricScore?: RubricScoreResult;
  /** Mang rong = khong phat hien doan nao trung khop (giong Empty state ben GV) */
  similarityMatches: SimilarityMatch[];
}

/**
 * ==========================================================================
 * UC-11 (phần còn lại): Policy/Governance, Audit log, System health
 * ==========================================================================
 * Thêm 2026-11-08. 3 màn demo cho Admin, theo đúng quy ước "ban DEMO theo
 * yêu cầu làm thử xem" đã áp dụng cho AdminJobsPage/AdminLifecyclePage.
 */

/**
 * `governance_records` (data-dictionary.md mục 7.1) -- bản ghi quyền sử
 * dụng dữ liệu (license/consent/retention) cho 1 resource (DOCUMENT/
 * DATASET/MODEL/RUBRIC). Dùng làm màn "Admin / Cấu hình policy" (UC-11:
 * "Cấu hình/audit/job vận hành an toàn"). Field bám sát dictionary; chỉ
 * `resourceLabel`/`workspaceName` là GIA ĐỊNH hiển thị (join tên thay vì
 * chỉ hiện ObjectId).
 */
export type GovernanceResourceType = "DOCUMENT" | "DATASET" | "MODEL" | "RUBRIC";
export type GovernanceStatus = "PENDING" | "APPROVED" | "REJECTED" | "REVOKED" | "EXPIRED";
export type RightsBasis =
  | "LICENSE"
  | "CONSENT"
  | "RESEARCH_USE_STATEMENT"
  | "INTERNAL_APPROVAL"
  | "UNKNOWN";

export interface AdminGovernanceRow {
  _id: string;
  resourceType: GovernanceResourceType;
  /** GIA ĐỊNH hiển thị -- join tên thay vì chỉ hiện resource_id */
  resourceLabel: string;
  /** undefined = resource toàn hệ thống (vd dataset công khai đã duyệt) */
  workspaceName?: string;
  rightsBasis: RightsBasis;
  allowedPurposes: string[];
  status: GovernanceStatus;
  approverName?: string;
  approvedAt?: string;
  validUntil?: string;
  /** Optimistic concurrency -- cùng quy ước revision ở AssessmentProposalReview/SimilarityMatch. */
  revision: number;
}

/**
 * `audit_events` (data-dictionary.md mục 11.3) -- append-only, KHÔNG lưu
 * raw content/token/password/stack trace (xem ghi chú trong dictionary).
 * Dùng cho màn "Admin / Audit log", CHỈ ĐỌC (đúng tính chất append-only).
 */
export type AuditOutcome = "SUCCESS" | "FAILURE";

export interface AuditEventRow {
  _id: string;
  /** undefined = hành động hệ thống không gắn 1 workspace cụ thể */
  workspaceName?: string;
  actorName: string;
  actorType: "USER" | "SYSTEM";
  /** vd "REVIEW.SUBMIT", "PUBLICATION.PUBLISH", "ACCOUNT.DISABLE" -- GIA ĐỊNH quy ước đặt tên action, dictionary không liệt kê danh sách cụ thể */
  action: string;
  resourceType: string;
  /** GIA ĐỊNH hiển thị -- join tên thay vì chỉ hiện resource_id */
  resourceLabel: string;
  outcome: AuditOutcome;
  reasonCode?: string;
  beforeRevision?: number;
  afterRevision?: number;
  occurredAt: string;
}

/**
 * Màn "Admin / System health" -- KHÔNG có bảng riêng trong
 * data-dictionary.md, tính toán GIA ĐỊNH DEMO từ `jobs` (mục 9.1, xem
 * JobRecord/AdminJobRow): đếm job theo trạng thái/chặng, cảnh báo job
 * "kẹt" (RUNNING quá lâu -- GIA ĐỊNH ngưỡng demo, chưa có `heartbeat_at`
 * thật để biết lease có hết hạn hay không).
 */
export interface SystemHealthStageSummary {
  stage: JobStageKey;
  queued: number;
  running: number;
  error: number;
  /** vd job RUNNING quá X phút (GIA ĐỊNH ngưỡng demo) -- nghi ngờ bị kẹt/lease hết hạn */
  stale: number;
}

export interface SystemHealthSummary {
  stages: SystemHealthStageSummary[];
  totalJobs: number;
  totalError: number;
  totalStale: number;
  /** Thời điểm tính toán -- GIA ĐỊNH DEMO, đứng vai "last checked at" */
  checkedAt: string;
}

/**
 * ==========================================================================
 * UC-08 (CONDITIONAL, RQ3): Review và export Targeted Questions
 * ==========================================================================
 * Thêm 2026-11-08. `FR-QST-01`: câu hỏi phải liên kết issue/evidence/
 * rubric. `FR-QST-02`: Giảng viên review/edit/reject trước khi export.
 * Chỉ bật khi gate RQ3=ENABLED (bo-use-case.md dòng UC-08: "mở rộng có
 * điều kiện... Chỉ khi gate RQ3=ENABLED") -- demo coi gate này LUÔN BẬT
 * (xem RQ3_ENABLED trong lib/mockData.ts), GIA ĐỊNH toàn bộ cấu trúc câu
 * hỏi vì data-dictionary.md chưa có bảng riêng cho feature này.
 */
export type TargetedQuestionType =
  | "CLAIM_WITHOUT_EVIDENCE"
  | "UNSUPPORTED_CONCLUSION"
  | "METHOD_NOT_EXPLAINED"
  | "HIGH_SIMILARITY"
  | "INCONSISTENT";

export interface TargetedQuestion {
  _id: string;
  documentId: string;
  questionText: string;
  type: TargetedQuestionType;
  /** Liên kết issue/evidence/rubric cụ thể (FR-QST-01) -- GIA ĐỊNH hiển thị dạng text, vd tên tiêu chí/checklist hoặc vị trí trong báo cáo */
  linkedTo: string;
  /** undefined = CHƯA review */
  decision?: ReviewDecision;
  /** Bắt buộc khi decision = EDIT hoặc REJECT */
  reasonText?: string;
  /** Chỉ có ý nghĩa khi decision = EDIT -- GV tự sửa lại nội dung câu hỏi trước khi export */
  editedQuestionText?: string;
  /** Optimistic concurrency -- cùng quy ước revision ở nơi khác. */
  revision: number;
}

/**
 * ==========================================================================
 * UC-12 (CORE, actor Experiment Operator): Chạy, so sánh và xuất thực nghiệm
 * ==========================================================================
 * Thêm 2026-11-08. Actor RIÊNG (Experiment Operator), KHÔNG phải Giảng
 * viên/Admin -- thêm 1 vai mới ở màn Đăng nhập (xem features/auth/LoginPage.tsx).
 * `FR-EXP-01`: run manifest lưu commit/dataset/config/model/seed/hardware/
 * timing. `FR-EXP-02`: runner tái tạo prediction/metric/bảng từ config
 * khoá. `FR-EXP-03`: test split không được dùng chọn model/threshold.
 * Field bám `dataset_manifests` (data-dictionary.md mục 7.2) + mô tả
 * FR-EXP-01 cho phần run riêng (dataset_manifests là bảng cho DATASET,
 * không phải cho 1 RUN cụ thể -- GIA ĐỊNH thêm `ExperimentRun` cho đúng
 * "run manifest" FR-EXP-01 nói tới, link tới `datasetKey`/`datasetVersion`
 * của dataset_manifests).
 */
export type ExperimentRunStatus = "DRAFT" | "RUNNING" | "DONE" | "FAILED";
export type ResearchQuestion = "RQ1" | "RQ2" | "RQ3";

export interface ExperimentMetric {
  name: string;
  value: number;
  unit?: string;
}

export interface ExperimentRun {
  _id: string;
  runKey: string;
  rq: ResearchQuestion;
  /** FR-EXP-01: commit code đã dùng để chạy run này */
  commitHash: string;
  datasetKey: string;
  datasetVersion: string;
  /** GIA ĐỊNH hiển thị dạng text, vd "official test split, seed=42" (dataset_manifests.split_spec, mục 7.2, là object chưa định nghĩa field cụ thể) */
  splitSpec: string;
  modelName: string;
  seed: number;
  hardware: string;
  startedAt: string;
  finishedAt?: string;
  status: ExperimentRunStatus;
  metrics: ExperimentMetric[];
}

/**
 * ==========================================================================
 * Feedback Log (FR-REV-04, MUST): "bất biến và xuất được cho error
 * analysis đúng quyền"
 * ==========================================================================
 * Them 2026-11-08. KHONG co bang rieng trong data-dictionary.md -- GIA
 * DINH DEMO: moi lan GV Accept/Edit/Reject (Similarity UC-05 / Rubric
 * proposal UC-06 / Targeted Questions UC-08) deu GHI THEM 1 dong vao day
 * (append-only, KHONG co API sua/xoa dong da ghi -- dung quy uoc "bat
 * bien" cua FR-REV-04), xem appendFeedbackLogEntry trong lib/api.ts.
 * KHAC voi Audit log (Admin, toan he thong, audit_events muc 11.3): day
 * la log GAN THEO 1 BAO CAO cu the, phuc vu GV xem lai lich su quyet
 * dinh + xuat cho error analysis -- quyen xem GIA DINH DEMO la GV cua
 * lop chua bao cao do (chua co phan quyen rieng, xem ghi chu
 * getFeedbackLog).
 */
export type FeedbackLogSource = "SIMILARITY" | "RUBRIC_PROPOSAL" | "TARGETED_QUESTION";

export interface FeedbackLogEntry {
  _id: string;
  documentId: string;
  source: FeedbackLogSource;
  /** _id cua SimilarityMatch / AssessmentProposalReview / TargetedQuestion lien quan */
  sourceItemId: string;
  /** GIA DINH hien thi -- mo ta ngan gon item luc ghi log (vd doan excerpt Similarity, "Proposal rubric", cau hoi Targeted Question) */
  itemLabel: string;
  decision: ReviewDecision;
  actorName: string;
  /** Bat buoc khi decision = EDIT hoac REJECT, dung quy uoc voi cac noi khac. */
  reasonText?: string;
  occurredAt: string;
}

/* ==========================================================================
 * Dang nhap (man "Dang nhap", feature auth) -- them 2026-11-11. CHUA co
 * API auth that (xem docs/architecture/c4.md, OD-W21-02: session cookie
 * hay token/SSO van con la open decision) -- 2 type duoi day phuc vu ham
 * login() mock trong lib/api.ts. Khi co API that: giu nguyen 2 type nay,
 * chi thay NOI DUNG ham login() bang fetch() thuc.
 * ==========================================================================
 */

/**
 * 1 "diem vao" ma 1 tai khoan co the chon SAU KHI dang nhap thanh cong --
 * suy tu UserProfile.system_roles (vd ADMIN) + Membership.roles (vd
 * STUDENT/LECTURER/OPERATOR) CUA TAI KHOAN DO, khac voi man "chon vai" cu
 * (4 nut co dinh, khong can dang nhap) truoc day.
 */
export interface LoginDestination {
  role: string;
  homePath: string;
}

export interface LoginResult {
  user: UserProfile;
  destinations: LoginDestination[];
}

