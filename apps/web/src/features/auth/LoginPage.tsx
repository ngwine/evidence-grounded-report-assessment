import { useState } from "react";
import type { FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { LoginError, login } from "../../lib/api";
import type { LoginDestination } from "../../lib/types";
import "./login.css";

/**
 * Theo data-dictionary.md muc 5.1, `users` la 1 bang DUY NHAT (1 email = 1 tai
 * khoan), vai tro (Student/Lecturer/Admin/Operator) KHONG phai thuoc tinh
 * chon luc dang nhap ma la suy ra TU TAI KHOAN (system_roles + Membership
 * theo workspace) -- 1 nguoi co the vua la ADMIN vua la LECTURER. Vi vay
 * doi thanh 1 FORM CHUNG (email + mat khau) cho ca 4 vai, khong con 4 nut
 * rieng theo vai nua.
 *
 * Dang nhap van la MOCK (xem lib/api.ts, ham login()) vi backend auth that
 * (session cookie/token/SSO) con la open decision (OD-W21-02,
 * docs/architecture/c4.md) -- khi co API that, thay NOI DUNG ham login()
 * trong lib/api.ts bang fetch() thuc, KHONG can sua trang nay.
 */
export function LoginPage() {
  const navigate = useNavigate();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Khi 1 tai khoan co NHIEU diem vao (vd vua ADMIN vua LECTURER), cho
  // nguoi dung tu chon o man hinh thu 2 -- KHAC voi vai cu phai chon
  // TRUOC khi dang nhap.
  const [destinations, setDestinations] = useState<LoginDestination[] | null>(null);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setIsSubmitting(true);
    try {
      const result = await login(email, password);
      if (result.destinations.length === 1) {
        navigate(result.destinations[0].homePath);
        return;
      }
      setDestinations(result.destinations);
    } catch (err) {
      setError(err instanceof LoginError ? err.message : "Có lỗi xảy ra, vui lòng thử lại.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="login-page">
      <div className="login-page__card">
        <div className="login-page__brand">
          <span className="login-page__logo" aria-hidden="true">
            CB
          </span>
          <span>Tên hệ thống</span>
        </div>

        {destinations === null ? (
          <>
            <h1 className="login-page__title">Đăng nhập</h1>
            <p className="login-page__subtitle">
              Nhập email và mật khẩu của bạn để tiếp tục.
            </p>

            <form className="login-page__form" onSubmit={handleSubmit}>
              <label className="login-page__field">
                <span className="login-page__field-label">Email</span>
                <input
                  type="email"
                  className="login-page__input"
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                  autoComplete="username"
                  required
                />
              </label>

              <label className="login-page__field">
                <span className="login-page__field-label">Mật khẩu</span>
                <input
                  type="password"
                  className="login-page__input"
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  autoComplete="current-password"
                  required
                />
              </label>

              {error && <p className="login-page__error">{error}</p>}

              <button
                type="submit"
                className="btn-primary login-page__submit"
                disabled={isSubmitting}
              >
                {isSubmitting ? "Đang đăng nhập..." : "Đăng nhập"}
              </button>
            </form>
          </>
        ) : (
          <>
            <h1 className="login-page__title">Chọn vai trò</h1>
            <p className="login-page__subtitle">
              Tài khoản này có nhiều vai trò — chọn 1 để tiếp tục.
            </p>

            <div className="login-page__role-list">
              {destinations.map((destination) => (
                <button
                  key={destination.homePath}
                  type="button"
                  className="login-page__role-card"
                  onClick={() => navigate(destination.homePath)}
                >
                  <span className="login-page__role-info">
                    <span className="login-page__role-name">{destination.role}</span>
                  </span>
                </button>
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
