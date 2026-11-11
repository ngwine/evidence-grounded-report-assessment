import { createBrowserRouter, Navigate } from "react-router-dom";
import { Layout } from "./Layout";
import { LoginPage } from "../features/auth/LoginPage";
import { AdminUsersPage } from "../features/admin/AdminUsersPage";
import { AdminWorkspacesPage } from "../features/admin/AdminWorkspacesPage";
import { AdminWorkspaceMembersPage } from "../features/admin/AdminWorkspaceMembersPage";
import { AdminJobsPage } from "../features/admin/AdminJobsPage";
import { AdminLifecyclePage } from "../features/admin/AdminLifecyclePage";
import { AdminPolicyPage } from "../features/admin/AdminPolicyPage";
import { AdminAuditLogPage } from "../features/admin/AdminAuditLogPage";
import { AdminSystemHealthPage } from "../features/admin/AdminSystemHealthPage";
import { OperatorRunListPage } from "../features/operator/OperatorRunListPage";
import { OperatorRunDetailPage } from "../features/operator/OperatorRunDetailPage";
import { LecturerQuestionsPage } from "../features/questions/LecturerQuestionsPage";
import { FeedbackLogPage } from "../features/feedback/FeedbackLogPage";
import { WorkspaceListPage } from "../features/workspaces/WorkspaceListPage";
import { WorkspaceDetailPage } from "../features/workspaces/WorkspaceDetailPage";
import { PublicationDetailPage } from "../features/workspaces/PublicationDetailPage";
import { LecturerClassListPage } from "../features/review/LecturerClassListPage";
import { LecturerClassDetailPage } from "../features/review/LecturerClassDetailPage";
import { LecturerReportDetailPage } from "../features/review/LecturerReportDetailPage";
import { LecturerCorpusPage } from "../features/review/LecturerCorpusPage";
import { RubricCreatePage } from "../features/rubrics/RubricCreatePage";
import { RubricDetailPage } from "../features/rubrics/RubricDetailPage";

export const router = createBrowserRouter([
  // Man "Dang nhap" (chon vai de xem) -- doc lap voi Layout vi chua co
  // user dang dang nhap de hien header -- Yen yeu cau 2026-10-29, xem
  // features/auth/LoginPage.tsx.
  { path: "/login", element: <LoginPage /> },
  {
    element: <Layout />,
    children: [
      { index: true, element: <Navigate to="/login" replace /> },
      { path: "workspaces", element: <WorkspaceListPage /> },
      { path: "workspaces/:workspaceId", element: <WorkspaceDetailPage /> },
      // Man "Xem publication" (UC-09, CORE, Sinh vien) -- Yen yeu cau
      // 2026-10-28, xem features/workspaces/PublicationDetailPage.tsx
      {
        path: "workspaces/:workspaceId/documents/:documentId/publication",
        element: <PublicationDetailPage />,
      },
      // Man "Lecturer / Class" + "Lecturer / Class Detail" -- xem features/review
      { path: "lecturer/workspaces", element: <LecturerClassListPage /> },
      {
        path: "lecturer/workspaces/:workspaceId",
        element: <LecturerClassDetailPage />,
      },
      // Man "Lecturer / Report" -- xu ly 1 bao cao da nop, xem features/review/LecturerReportDetailPage
      {
        path: "lecturer/workspaces/:workspaceId/documents/:documentId",
        element: <LecturerReportDetailPage />,
      },
      // Man "Nguon doi chieu cua lop" (UC-15) -- xem ghi chu CorpusSource,
      // lib/types.ts.
      {
        path: "lecturer/workspaces/:workspaceId/corpus",
        element: <LecturerCorpusPage />,
      },
      // Man "Targeted Questions" (UC-08, CONDITIONAL RQ3) -- feature rieng
      // features/questions, xem ghi chu RQ3_ENABLED trong lib/mockData.ts.
      {
        path: "lecturer/workspaces/:workspaceId/documents/:documentId/questions",
        element: <LecturerQuestionsPage />,
      },
      // Man "Feedback Log" (FR-REV-04, MUST) -- feature rieng features/feedback.
      {
        path: "lecturer/workspaces/:workspaceId/documents/:documentId/feedback-log",
        element: <FeedbackLogPage />,
      },
      // Man "Tao rubric" -- feature rieng features/rubrics (gan theo 1 workspace)
      {
        path: "lecturer/workspaces/:workspaceId/rubrics/new",
        element: <RubricCreatePage />,
      },
      // Man "Xem chi tiet rubric" -- GV xem lai 1 rubric da tao (Yen yeu cau 2026-10-25)
      {
        path: "lecturer/workspaces/:workspaceId/rubrics/:rubricId",
        element: <RubricDetailPage />,
      },
      // Man "Sua rubric" -- dung chung component voi "Tao rubric", chi cho
      // sua khi rubric dang DRAFT (Yen yeu cau 2026-10-27). Khai bao SAU
      // route ":rubricId" o tren cung khong sao vi React Router uu tien
      // segment tinh ("edit") hon segment dong (":rubricId") bat ke thu tu.
      {
        path: "lecturer/workspaces/:workspaceId/rubrics/:rubricId/edit",
        element: <RubricCreatePage />,
      },
      // Man "Admin" (UC-11) -- Yen yeu cau 2026-10-29: "Quan ly lop" la man
      // dau tien (tao lop, gan Giang vien/Sinh vien), roi den "Quan ly tai
      // khoan". 2 man con lai (UC-14 "Giam sat hang doi", UC-17 "Vong
      // doi du lieu") la ban DEMO theo yeu cau "lam thu xem" cua Yen
      // 2026-10-29. UC-15 ("Nguon doi chieu") DA CHUYEN sang Lecturer
      // (xem route "lecturer/workspaces/:workspaceId/corpus" duoi day)
      // vi actor dung la Giang vien, khong phai Admin -- xem ghi chu
      // CorpusSource, lib/types.ts.
      { path: "admin", element: <Navigate to="/admin/workspaces" replace /> },
      { path: "admin/workspaces", element: <AdminWorkspacesPage /> },
      {
        path: "admin/workspaces/:workspaceId",
        element: <AdminWorkspaceMembersPage />,
      },
      { path: "admin/users", element: <AdminUsersPage /> },
      { path: "admin/jobs", element: <AdminJobsPage /> },
      { path: "admin/lifecycle", element: <AdminLifecyclePage /> },
      // 3 man UC-11 con lai (Policy/Audit log/System health) -- them
      // 2026-11-08, xem ghi chu AdminGovernanceRow/AuditEventRow/
      // SystemHealthSummary trong lib/types.ts.
      { path: "admin/policy", element: <AdminPolicyPage /> },
      { path: "admin/audit-log", element: <AdminAuditLogPage /> },
      { path: "admin/system-health", element: <AdminSystemHealthPage /> },
      // Man "Experiment Operator" (UC-12) -- actor rieng, them vai moi o
      // man Dang nhap (xem features/auth/LoginPage.tsx), tai su dung
      // MembershipRole.OPERATOR da co san trong lib/types.ts.
      { path: "operator/runs", element: <OperatorRunListPage /> },
      { path: "operator/runs/:runId", element: <OperatorRunDetailPage /> },
    ],
  },
]);
