import { useEffect, useRef, useState } from "react";
import type { UserProfile } from "../../lib/types";
import "./admin.css";

interface AdminUserComboboxProps {
  users: UserProfile[];
  value: string;
  onChange: (userId: string) => void;
  placeholder?: string;
}

/**
 * O chon 1 user co tim kiem (go ten/email de loc) -- Yen yeu cau
 * 2026-10-29, thay cho <select> thuong o form "Thêm thành viên" (man
 * Admin / Thanh vien lop) vi danh sach user co the dai, kho cuon tim
 * bang <select> thuong.
 */
export function AdminUserCombobox({
  users,
  value,
  onChange,
  placeholder,
}: AdminUserComboboxProps) {
  const [query, setQuery] = useState("");
  const [isOpen, setIsOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  const selectedUser = users.find((u) => u._id === value);

  useEffect(() => {
    if (!isOpen) return;

    function handleClickOutside(event: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }

    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [isOpen]);

  const normalizedQuery = query.trim().toLowerCase();
  const filteredUsers = users.filter((user) => {
    if (normalizedQuery.length === 0) return true;
    return (
      user.display_name.toLowerCase().includes(normalizedQuery) ||
      (user.email_normalized ?? "").toLowerCase().includes(normalizedQuery) ||
      (user.student_id ?? "").toLowerCase().includes(normalizedQuery)
    );
  });

  const displayValue = isOpen
    ? query
    : selectedUser
      ? `${selectedUser.display_name}${
          selectedUser.email_normalized ? ` · ${selectedUser.email_normalized}` : ""
        }${selectedUser.student_id ? ` · MSSV: ${selectedUser.student_id}` : ""}`
      : "";

  return (
    <div className="admin-user-combobox" ref={containerRef}>
      <input
        className="search-input"
        type="text"
        placeholder={placeholder ?? "Tìm theo tên, email hoặc MSSV"}
        value={displayValue}
        onFocus={() => {
          setIsOpen(true);
          setQuery("");
        }}
        onChange={(event) => setQuery(event.target.value)}
      />

      {isOpen && (
        <ul className="admin-user-combobox__list" role="listbox">
          {filteredUsers.length === 0 && (
            <li className="admin-user-combobox__empty">Không tìm thấy người dùng</li>
          )}
          {filteredUsers.map((user) => (
            <li key={user._id}>
              <button
                type="button"
                className="admin-user-combobox__option"
                onClick={() => {
                  onChange(user._id);
                  setIsOpen(false);
                  setQuery("");
                }}
              >
                <span className="admin-users__name">{user.display_name}</span>
                <span className="admin-users__email">
                  {user.email_normalized ?? "—"}
                  {user.student_id ? ` · MSSV: ${user.student_id}` : ""}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
