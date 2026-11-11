import { useEffect, useRef, useState } from "react";
import { Outlet, useLocation, useNavigate } from "react-router-dom";
import {
  CURRENT_ADMIN_ID,
  CURRENT_LECTURER_ID,
  CURRENT_OPERATOR_ID,
  CURRENT_USER_ID,
  mockUsers,
} from "../lib/mockData";
import "./Layout.css";

/**
 * Khung chung cho moi man hinh: header (ten he thong + user menu) + noi
 * dung thay doi theo route (Outlet) + footer. Khop voi header trong
 * wireframe Figma (W2.4).
 */
export function Layout() {
  // TODO: thay bang user/role that tu auth context khi co (xem features/auth)
  // SUA LAI 2026-10-29 (Yen phat hien header GV van hien "Vu Dinh Hong"):
  // truoc day currentLecturer la object rieng, khong lien ket voi
  // mockUsers/CURRENT_LECTURER_ID nen doi ten GV cho lecturerByWorkspace
  // khong anh huong toi day -- gio tra truc tiep tu mockUsers, 1 nguon
  // duy nhat giong currentStudent.
  const currentStudentProfile = mockUsers.find((u) => u._id === CURRENT_USER_ID);
  const currentStudent = {
    displayName: currentStudentProfile?.display_name ?? "-",
    studentId: currentStudentProfile?.student_id ?? "-",
  };
  const currentLecturer = {
    displayName:
      mockUsers.find((u) => u._id === CURRENT_LECTURER_ID)?.display_name ?? "-",
  };
  const currentAdmin = {
    displayName:
      mockUsers.find((u) => u._id === CURRENT_ADMIN_ID)?.display_name ?? "-",
  };
  const currentOperator = {
    displayName:
      mockUsers.find((u) => u._id === CURRENT_OPERATOR_ID)?.display_name ?? "-",
  };

  // Chua co auth that nen tam suy vai tro dang xem tu route (/lecturer/...,
  // /admin/..., /operator/...) de header hien dung ten/nhan phu hop -- SUA
  // LAI 2026-10-29 de them vai Admin (UC-11), roi 2026-11-08 them vai
  // Experiment Operator (UC-12).
  const location = useLocation();
  const navigate = useNavigate();
  const isLecturerView = location.pathname.startsWith("/lecturer");
  const isAdminView = location.pathname.startsWith("/admin");
  const isOperatorView = location.pathname.startsWith("/operator");

  const viewerDisplayName = isAdminView
    ? currentAdmin.displayName
    : isOperatorView
      ? currentOperator.displayName
      : isLecturerView
        ? currentLecturer.displayName
        : `${currentStudent.displayName} - ${currentStudent.studentId}`;
  const viewerInitial = (
    isAdminView
      ? currentAdmin.displayName
      : isOperatorView
        ? currentOperator.displayName
        : isLecturerView
          ? currentLecturer.displayName
          : currentStudent.displayName
  ).charAt(0);

  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const userMenuRef = useRef<HTMLDivElement>(null);

  // Bam ra ngoai thi dong dropdown
  useEffect(() => {
    if (!isMenuOpen) return;

    function handleClickOutside(event: MouseEvent) {
      if (
        userMenuRef.current &&
        !userMenuRef.current.contains(event.target as Node)
      ) {
        setIsMenuOpen(false);
      }
    }

    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [isMenuOpen]);

  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="app-header__brand">
          <span className="app-header__logo" aria-hidden="true">
            CB
          </span>
          <span>Ten he thong</span>
        </div>

        <div className="app-header__user" ref={userMenuRef}>
          <span>{viewerDisplayName}</span>
          <span className="app-header__avatar" aria-hidden="true">
            {viewerInitial}
          </span>
          <button
            type="button"
            className="app-header__menu-toggle"
            aria-label="Mở menu tài khoản"
            aria-haspopup="menu"
            aria-expanded={isMenuOpen}
            onClick={() => setIsMenuOpen((prev) => !prev)}
          >
            <svg
              className={`app-header__chevron${
                isMenuOpen ? " app-header__chevron--open" : ""
              }`}
              width="14"
              height="14"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2.5"
              strokeLinecap="round"
              strokeLinejoin="round"
              aria-hidden="true"
            >
              <polyline points="6 9 12 15 18 9" />
            </svg>
          </button>

          {isMenuOpen && (
            <div className="app-header__dropdown" role="menu">
              {/* TODO: gan action that khi co auth (xem ho so, dang xuat...) */}
              <button
                type="button"
                className="app-header__dropdown-item"
                role="menuitem"
              >
                Hồ sơ
              </button>
              <button
                type="button"
                className="app-header__dropdown-item"
                role="menuitem"
                onClick={() => {
                  setIsMenuOpen(false);
                  navigate("/login");
                }}
              >
                Đăng xuất
              </button>
            </div>
          )}
        </div>
      </header>

      <main className="app-content">
        <Outlet />
      </main>

      <footer className="app-footer">Copyright</footer>
    </div>
  );
}
