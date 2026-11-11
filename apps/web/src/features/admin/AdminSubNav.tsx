import { Link } from "react-router-dom";
import "./admin.css";

interface AdminSubNavProps {
  active:
    | "workspaces"
    | "users"
    | "jobs"
    | "lifecycle"
    | "policy"
    | "audit-log"
    | "system-health";
}

/**
 * Thanh chuyen tab gon giua cac man Admin. Them 2026-11-08: 3 tab UC-11
 * con lai (Policy/Audit log/System health -- xem router.tsx va cac man
 * AdminPolicyPage/AdminAuditLogPage/AdminSystemHealthPage).
 */
export function AdminSubNav({ active }: AdminSubNavProps) {
  const items: Array<{ key: AdminSubNavProps["active"]; to: string; label: string }> = [
    { key: "workspaces", to: "/admin/workspaces", label: "Quản lý lớp" },
    { key: "users", to: "/admin/users", label: "Quản lý tài khoản" },
    { key: "jobs", to: "/admin/jobs", label: "Giám sát hàng đợi" },
    { key: "lifecycle", to: "/admin/lifecycle", label: "Vòng đời dữ liệu" },
    { key: "policy", to: "/admin/policy", label: "Cấu hình policy" },
    { key: "audit-log", to: "/admin/audit-log", label: "Audit log" },
    { key: "system-health", to: "/admin/system-health", label: "System health" },
  ];

  return (
    <nav className="admin-subnav" aria-label="Điều hướng Admin">
      {items.map((item) => (
        <Link
          key={item.key}
          to={item.to}
          className={`admin-subnav__item${
            active === item.key ? " admin-subnav__item--active" : ""
          }`}
        >
          {item.label}
        </Link>
      ))}
    </nav>
  );
}
