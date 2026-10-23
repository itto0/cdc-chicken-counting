import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent, waitFor, act } from "@testing-library/react";
import { CreateUserModal } from "../CreateUserModal";
import { EditUserModal } from "../EditUserModal";
import { ResetPasswordModal } from "../ResetPasswordModal";
import { DeleteUserModal } from "../DeleteUserModal";
import type { UserItem } from "../../types";

describe("CreateUserModal", () => {
  it("renders nothing when isOpen is false", () => {
    const { container } = render(
      <CreateUserModal isOpen={false} onClose={vi.fn()} onSubmit={vi.fn()} />
    );
    expect(container.firstChild).toBeNull();
  });

  it("renders form fields when isOpen is true", () => {
    render(<CreateUserModal isOpen={true} onClose={vi.fn()} onSubmit={vi.fn()} />);

    const dialog = screen.getByRole("dialog");
    expect(dialog.getAttribute("aria-labelledby")).toBe("create-user-modal-title");
    expect(screen.getByRole("heading", { name: "Tambah Pengguna Baru" }).id).toBe(
      "create-user-modal-title"
    );
    expect(screen.getByText("Tambah Pengguna Baru")).toBeDefined();
    expect(screen.getByPlaceholderText("Contoh: op_johndoe")).toBeDefined();
    expect(screen.getByPlaceholderText("Minimal 6 karakter")).toBeDefined();
    expect(screen.getByRole("combobox")).toBeDefined();
  });

  it("shows validation error when username is whitespace-only", async () => {
    const onSubmit = vi.fn();
    render(<CreateUserModal isOpen={true} onClose={vi.fn()} onSubmit={onSubmit} />);

    const usernameInput = screen.getByPlaceholderText("Contoh: op_johndoe");
    const passwordInput = screen.getByPlaceholderText("Minimal 6 karakter");
    const submitBtn = screen.getByRole("button", { name: "Simpan Pengguna" });

    fireEvent.change(usernameInput, { target: { value: "   " } });
    fireEvent.change(passwordInput, { target: { value: "123456" } });
    fireEvent.click(submitBtn);

    expect(await screen.findByText("Nama pengguna tidak boleh kosong")).toBeDefined();
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("shows validation error when username is less than 3 characters", async () => {
    const onSubmit = vi.fn();
    render(<CreateUserModal isOpen={true} onClose={vi.fn()} onSubmit={onSubmit} />);

    const usernameInput = screen.getByPlaceholderText("Contoh: op_johndoe");
    const passwordInput = screen.getByPlaceholderText("Minimal 6 karakter");
    const submitBtn = screen.getByRole("button", { name: "Simpan Pengguna" });

    fireEvent.change(usernameInput, { target: { value: "ab" } });
    fireEvent.change(passwordInput, { target: { value: "123456" } });
    fireEvent.click(submitBtn);

    expect(await screen.findByText("Nama pengguna minimal 3 karakter")).toBeDefined();
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("shows validation error when password is less than 6 characters", async () => {
    const onSubmit = vi.fn();
    render(<CreateUserModal isOpen={true} onClose={vi.fn()} onSubmit={onSubmit} />);

    const usernameInput = screen.getByPlaceholderText("Contoh: op_johndoe");
    const passwordInput = screen.getByPlaceholderText("Minimal 6 karakter");
    const submitBtn = screen.getByRole("button", { name: "Simpan Pengguna" });

    fireEvent.change(usernameInput, { target: { value: "user_test" } });
    fireEvent.change(passwordInput, { target: { value: "12345" } });
    fireEvent.click(submitBtn);

    expect(await screen.findByText("Password minimal 6 karakter")).toBeDefined();
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("submits valid payload and triggers onClose", async () => {
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    const onClose = vi.fn();
    render(<CreateUserModal isOpen={true} onClose={onClose} onSubmit={onSubmit} />);

    fireEvent.change(screen.getByPlaceholderText("Contoh: op_johndoe"), {
      target: { value: "operator_b" },
    });
    fireEvent.change(screen.getByPlaceholderText("Minimal 6 karakter"), {
      target: { value: "password123" },
    });
    fireEvent.change(screen.getByRole("combobox"), {
      target: { value: "operator" },
    });

    fireEvent.click(screen.getByRole("button", { name: "Simpan Pengguna" }));

    await waitFor(() => {
      expect(onSubmit).toHaveBeenCalledWith({
        username: "operator_b",
        password: "password123",
        role: "operator",
        is_active: true,
      });
      expect(onClose).toHaveBeenCalled();
    });
  });

  it("displays error message when onSubmit rejects", async () => {
    const onSubmit = vi.fn().mockRejectedValue(new Error("Username sudah terdaftar"));
    render(<CreateUserModal isOpen={true} onClose={vi.fn()} onSubmit={onSubmit} />);

    fireEvent.change(screen.getByPlaceholderText("Contoh: op_johndoe"), {
      target: { value: "duplicate_user" },
    });
    fireEvent.change(screen.getByPlaceholderText("Minimal 6 karakter"), {
      target: { value: "password123" },
    });

    fireEvent.click(screen.getByRole("button", { name: "Simpan Pengguna" }));

    expect(await screen.findByText("Username sudah terdaftar")).toBeDefined();
  });

  it("calls onClose when Batal is clicked", () => {
    const onClose = vi.fn();
    render(<CreateUserModal isOpen={true} onClose={onClose} onSubmit={vi.fn()} />);

    fireEvent.click(screen.getByRole("button", { name: "Batal" }));
    expect(onClose).toHaveBeenCalled();
  });

  it("dismisses on Escape key press", () => {
    const onClose = vi.fn();
    render(<CreateUserModal isOpen={true} onClose={onClose} onSubmit={vi.fn()} />);

    fireEvent.keyDown(window, { key: "Escape" });
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("dismisses on backdrop click but not dialog content click", () => {
    const onClose = vi.fn();
    render(<CreateUserModal isOpen={true} onClose={onClose} onSubmit={vi.fn()} />);

    // Click inside content
    fireEvent.click(screen.getByText("Tambah Pengguna Baru"));
    expect(onClose).not.toHaveBeenCalled();

    // Click backdrop
    fireEvent.click(screen.getByRole("dialog"));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("disables close button and prevents dismissal while submitting", async () => {
    let resolveSubmit: () => void = () => {};
    const onSubmit = vi.fn().mockImplementation(
      () =>
        new Promise<void>((resolve) => {
          resolveSubmit = resolve;
        })
    );
    const onClose = vi.fn();
    render(<CreateUserModal isOpen={true} onClose={onClose} onSubmit={onSubmit} />);

    fireEvent.change(screen.getByPlaceholderText("Contoh: op_johndoe"), {
      target: { value: "operator_new" },
    });
    fireEvent.change(screen.getByPlaceholderText("Minimal 6 karakter"), {
      target: { value: "password123" },
    });

    const closeBtn = screen.getByRole("button", { name: "Tutup" });
    expect((closeBtn as HTMLButtonElement).disabled).toBe(false);

    fireEvent.click(screen.getByRole("button", { name: "Simpan Pengguna" }));

    // Is submitting
    expect((closeBtn as HTMLButtonElement).disabled).toBe(true);

    // Escape and backdrop click should not close while submitting
    fireEvent.keyDown(window, { key: "Escape" });
    fireEvent.click(screen.getByRole("dialog"));
    expect(onClose).not.toHaveBeenCalled();

    await act(async () => {
      resolveSubmit();
    });
  });
});

describe("EditUserModal", () => {
  const dummyAdmin: UserItem = {
    id: 1,
    username: "admin_user",
    role: "admin",
    is_active: true,
  };

  const dummyOperator: UserItem = {
    id: 2,
    username: "operator_user",
    role: "operator",
    is_active: true,
  };

  it("renders nothing when isOpen is false or user is null", () => {
    const { container: c1 } = render(
      <EditUserModal
        isOpen={false}
        onClose={vi.fn()}
        user={dummyAdmin}
        currentUserId={1}
        activeAdminCount={2}
        onSubmit={vi.fn()}
      />
    );
    expect(c1.firstChild).toBeNull();

    const { container: c2 } = render(
      <EditUserModal
        isOpen={true}
        onClose={vi.fn()}
        user={null}
        currentUserId={1}
        activeAdminCount={2}
        onSubmit={vi.fn()}
      />
    );
    expect(c2.firstChild).toBeNull();
  });

  it("disables is_active checkbox and shows warning when editing self", () => {
    render(
      <EditUserModal
        isOpen={true}
        onClose={vi.fn()}
        user={dummyAdmin}
        currentUserId={dummyAdmin.id}
        activeAdminCount={2}
        onSubmit={vi.fn()}
      />
    );

    const dialog = screen.getByRole("dialog");
    expect(dialog.getAttribute("aria-labelledby")).toBe("edit-user-modal-title");
    expect(screen.getByRole("heading", { name: "Ubah Data Pengguna" }).id).toBe(
      "edit-user-modal-title"
    );

    const checkbox = screen.getByRole("checkbox") as HTMLInputElement;
    expect(checkbox.disabled).toBe(true);
    expect(
      screen.getByText("Anda tidak dapat menonaktifkan akun yang sedang digunakan saat ini.")
    ).toBeDefined();
  });

  it("disables role select and is_active checkbox when target is the last active admin", () => {
    render(
      <EditUserModal
        isOpen={true}
        onClose={vi.fn()}
        user={dummyAdmin}
        currentUserId={99}
        activeAdminCount={1}
        onSubmit={vi.fn()}
      />
    );

    const roleSelect = screen.getByRole("combobox") as HTMLSelectElement;
    const checkbox = screen.getByRole("checkbox") as HTMLInputElement;

    expect(roleSelect.disabled).toBe(true);
    expect(checkbox.disabled).toBe(true);
    expect(
      screen.getByText("Peran tidak dapat diturunkan karena merupakan satu-satunya admin aktif.")
    ).toBeDefined();
    expect(
      screen.getByText(
        "Akun ini tidak dapat dinonaktifkan karena merupakan satu-satunya admin aktif."
      )
    ).toBeDefined();
  });

  it("allows editing role and status for non-self operator or when multiple admins exist", async () => {
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    const onClose = vi.fn();

    render(
      <EditUserModal
        isOpen={true}
        onClose={onClose}
        user={dummyOperator}
        currentUserId={1}
        activeAdminCount={2}
        onSubmit={onSubmit}
      />
    );

    const roleSelect = screen.getByRole("combobox") as HTMLSelectElement;
    const checkbox = screen.getByRole("checkbox") as HTMLInputElement;

    expect(roleSelect.disabled).toBe(false);
    expect(checkbox.disabled).toBe(false);

    fireEvent.change(roleSelect, { target: { value: "admin" } });
    fireEvent.click(checkbox); // toggles to false

    fireEvent.click(screen.getByRole("button", { name: "Simpan Perubahan" }));

    await waitFor(() => {
      expect(onSubmit).toHaveBeenCalledWith(2, { role: "admin", is_active: false });
      expect(onClose).toHaveBeenCalled();
    });
  });

  it("displays error message when onSubmit fails", async () => {
    const onSubmit = vi.fn().mockRejectedValue(new Error("Database error"));
    render(
      <EditUserModal
        isOpen={true}
        onClose={vi.fn()}
        user={dummyOperator}
        currentUserId={1}
        activeAdminCount={2}
        onSubmit={onSubmit}
      />
    );

    fireEvent.click(screen.getByRole("button", { name: "Simpan Perubahan" }));
    expect(await screen.findByText("Database error")).toBeDefined();
  });

  it("dismisses on Escape key press and backdrop click", () => {
    const onClose = vi.fn();
    render(
      <EditUserModal
        isOpen={true}
        onClose={onClose}
        user={dummyOperator}
        currentUserId={1}
        activeAdminCount={2}
        onSubmit={vi.fn()}
      />
    );

    fireEvent.click(screen.getByText("Ubah Data Pengguna"));
    expect(onClose).not.toHaveBeenCalled();

    fireEvent.keyDown(window, { key: "Escape" });
    expect(onClose).toHaveBeenCalledTimes(1);

    onClose.mockClear();
    fireEvent.click(screen.getByRole("dialog"));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("disables close button and prevents dismissal while submitting", async () => {
    let resolveSubmit: () => void = () => {};
    const onSubmit = vi.fn().mockImplementation(
      () =>
        new Promise<void>((resolve) => {
          resolveSubmit = resolve;
        })
    );
    const onClose = vi.fn();
    render(
      <EditUserModal
        isOpen={true}
        onClose={onClose}
        user={dummyOperator}
        currentUserId={1}
        activeAdminCount={2}
        onSubmit={onSubmit}
      />
    );

    const closeBtn = screen.getByRole("button", { name: "Tutup" });
    expect((closeBtn as HTMLButtonElement).disabled).toBe(false);

    fireEvent.click(screen.getByRole("button", { name: "Simpan Perubahan" }));

    expect((closeBtn as HTMLButtonElement).disabled).toBe(true);

    fireEvent.keyDown(window, { key: "Escape" });
    fireEvent.click(screen.getByRole("dialog"));
    expect(onClose).not.toHaveBeenCalled();

    await act(async () => {
      resolveSubmit();
    });
  });
});

describe("ResetPasswordModal", () => {
  const dummyUser: UserItem = {
    id: 5,
    username: "user_to_reset",
    role: "operator",
    is_active: true,
  };

  it("renders nothing when isOpen is false or user is null", () => {
    const { container: c1 } = render(
      <ResetPasswordModal isOpen={false} onClose={vi.fn()} user={dummyUser} onSubmit={vi.fn()} />
    );
    expect(c1.firstChild).toBeNull();

    const { container: c2 } = render(
      <ResetPasswordModal isOpen={true} onClose={vi.fn()} user={null} onSubmit={vi.fn()} />
    );
    expect(c2.firstChild).toBeNull();
  });

  it("validates password length < 6", async () => {
    const onSubmit = vi.fn();
    render(
      <ResetPasswordModal isOpen={true} onClose={vi.fn()} user={dummyUser} onSubmit={onSubmit} />
    );

    const dialog = screen.getByRole("dialog");
    expect(dialog.getAttribute("aria-labelledby")).toBe("reset-password-modal-title");
    expect(screen.getByRole("heading", { name: "Reset Password Pengguna" }).id).toBe(
      "reset-password-modal-title"
    );

    const inputs = screen.getAllByPlaceholderText(/minimal 6 karakter|ulangi password baru/i);
    fireEvent.change(inputs[0], { target: { value: "123" } });
    fireEvent.change(inputs[1], { target: { value: "123" } });

    fireEvent.click(screen.getByRole("button", { name: "Simpan Password Baru" }));

    expect(await screen.findByText("Password minimal 6 karakter")).toBeDefined();
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("validates mismatched confirmation password", async () => {
    const onSubmit = vi.fn();
    render(
      <ResetPasswordModal isOpen={true} onClose={vi.fn()} user={dummyUser} onSubmit={onSubmit} />
    );

    const inputs = screen.getAllByPlaceholderText(/minimal 6 karakter|ulangi password baru/i);
    fireEvent.change(inputs[0], { target: { value: "password123" } });
    fireEvent.change(inputs[1], { target: { value: "different123" } });

    fireEvent.click(screen.getByRole("button", { name: "Simpan Password Baru" }));

    expect(await screen.findByText("Konfirmasi password baru tidak cocok")).toBeDefined();
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("submits matching password successfully", async () => {
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    const onClose = vi.fn();
    render(
      <ResetPasswordModal isOpen={true} onClose={onClose} user={dummyUser} onSubmit={onSubmit} />
    );

    const inputs = screen.getAllByPlaceholderText(/minimal 6 karakter|ulangi password baru/i);
    fireEvent.change(inputs[0], { target: { value: "newSecret123" } });
    fireEvent.change(inputs[1], { target: { value: "newSecret123" } });

    fireEvent.click(screen.getByRole("button", { name: "Simpan Password Baru" }));

    await waitFor(() => {
      expect(onSubmit).toHaveBeenCalledWith(5, { new_password: "newSecret123" });
      expect(onClose).toHaveBeenCalled();
    });
  });

  it("displays error when onSubmit rejects", async () => {
    const onSubmit = vi.fn().mockRejectedValue(new Error("Akses ditolak"));
    render(
      <ResetPasswordModal isOpen={true} onClose={vi.fn()} user={dummyUser} onSubmit={onSubmit} />
    );

    const inputs = screen.getAllByPlaceholderText(/minimal 6 karakter|ulangi password baru/i);
    fireEvent.change(inputs[0], { target: { value: "newSecret123" } });
    fireEvent.change(inputs[1], { target: { value: "newSecret123" } });

    fireEvent.click(screen.getByRole("button", { name: "Simpan Password Baru" }));

    expect(await screen.findByText("Akses ditolak")).toBeDefined();
  });

  it("dismisses on Escape key press and backdrop click", () => {
    const onClose = vi.fn();
    render(
      <ResetPasswordModal isOpen={true} onClose={onClose} user={dummyUser} onSubmit={vi.fn()} />
    );

    fireEvent.click(screen.getByText("Reset Password Pengguna"));
    expect(onClose).not.toHaveBeenCalled();

    fireEvent.keyDown(window, { key: "Escape" });
    expect(onClose).toHaveBeenCalledTimes(1);

    onClose.mockClear();
    fireEvent.click(screen.getByRole("dialog"));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("disables close button and prevents dismissal while submitting", async () => {
    let resolveSubmit: () => void = () => {};
    const onSubmit = vi.fn().mockImplementation(
      () =>
        new Promise<void>((resolve) => {
          resolveSubmit = resolve;
        })
    );
    const onClose = vi.fn();
    render(
      <ResetPasswordModal isOpen={true} onClose={onClose} user={dummyUser} onSubmit={onSubmit} />
    );

    const inputs = screen.getAllByPlaceholderText(/minimal 6 karakter|ulangi password baru/i);
    fireEvent.change(inputs[0], { target: { value: "password123" } });
    fireEvent.change(inputs[1], { target: { value: "password123" } });

    const closeBtn = screen.getByRole("button", { name: "Tutup" });
    expect((closeBtn as HTMLButtonElement).disabled).toBe(false);

    fireEvent.click(screen.getByRole("button", { name: "Simpan Password Baru" }));

    expect((closeBtn as HTMLButtonElement).disabled).toBe(true);

    fireEvent.keyDown(window, { key: "Escape" });
    fireEvent.click(screen.getByRole("dialog"));
    expect(onClose).not.toHaveBeenCalled();

    await act(async () => {
      resolveSubmit();
    });
  });
});

describe("DeleteUserModal", () => {
  const dummyUser: UserItem = {
    id: 9,
    username: "doomed_user",
    role: "operator",
    is_active: false,
  };

  it("renders nothing when isOpen is false or user is null", () => {
    const { container: c1 } = render(
      <DeleteUserModal isOpen={false} onClose={vi.fn()} user={dummyUser} onConfirm={vi.fn()} />
    );
    expect(c1.firstChild).toBeNull();

    const { container: c2 } = render(
      <DeleteUserModal isOpen={true} onClose={vi.fn()} user={null} onConfirm={vi.fn()} />
    );
    expect(c2.firstChild).toBeNull();
  });

  it("renders confirmation message with username", () => {
    render(
      <DeleteUserModal isOpen={true} onClose={vi.fn()} user={dummyUser} onConfirm={vi.fn()} />
    );

    const dialog = screen.getByRole("dialog");
    expect(dialog.getAttribute("aria-labelledby")).toBe("delete-user-modal-title");
    expect(screen.getByRole("heading", { name: "Hapus Pengguna" }).id).toBe(
      "delete-user-modal-title"
    );
    expect(screen.getByText('"doomed_user"')).toBeDefined();
  });

  it("calls onConfirm with user.id and closes on confirmation", async () => {
    const onConfirm = vi.fn().mockResolvedValue(undefined);
    const onClose = vi.fn();

    render(
      <DeleteUserModal isOpen={true} onClose={onClose} user={dummyUser} onConfirm={onConfirm} />
    );

    fireEvent.click(screen.getByRole("button", { name: "Hapus Pengguna" }));

    await waitFor(() => {
      expect(onConfirm).toHaveBeenCalledWith(9);
      expect(onClose).toHaveBeenCalled();
    });
  });

  it("displays error message if onConfirm rejects", async () => {
    const onConfirm = vi.fn().mockRejectedValue(new Error("Tidak dapat menghapus admin aktif"));
    render(
      <DeleteUserModal isOpen={true} onClose={vi.fn()} user={dummyUser} onConfirm={onConfirm} />
    );

    fireEvent.click(screen.getByRole("button", { name: "Hapus Pengguna" }));

    expect(await screen.findByText("Tidak dapat menghapus admin aktif")).toBeDefined();
  });

  it("dismisses on Escape key press and backdrop click", () => {
    const onClose = vi.fn();
    render(
      <DeleteUserModal isOpen={true} onClose={onClose} user={dummyUser} onConfirm={vi.fn()} />
    );

    fireEvent.click(screen.getByRole("heading", { name: "Hapus Pengguna" }));
    expect(onClose).not.toHaveBeenCalled();

    fireEvent.keyDown(window, { key: "Escape" });
    expect(onClose).toHaveBeenCalledTimes(1);

    onClose.mockClear();
    fireEvent.click(screen.getByRole("dialog"));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("disables close button and prevents dismissal while deleting", async () => {
    let resolveDelete: () => void = () => {};
    const onConfirm = vi.fn().mockImplementation(
      () =>
        new Promise<void>((resolve) => {
          resolveDelete = resolve;
        })
    );
    const onClose = vi.fn();
    render(
      <DeleteUserModal isOpen={true} onClose={onClose} user={dummyUser} onConfirm={onConfirm} />
    );

    const closeBtn = screen.getByRole("button", { name: "Tutup" });
    expect((closeBtn as HTMLButtonElement).disabled).toBe(false);

    fireEvent.click(screen.getByRole("button", { name: "Hapus Pengguna" }));

    expect((closeBtn as HTMLButtonElement).disabled).toBe(true);

    fireEvent.keyDown(window, { key: "Escape" });
    fireEvent.click(screen.getByRole("dialog"));
    expect(onClose).not.toHaveBeenCalled();

    await act(async () => {
      resolveDelete();
    });
  });

  it("clears previous error when reopened", async () => {
    const onConfirm = vi.fn().mockRejectedValue(new Error("Tidak dapat menghapus"));
    const { rerender } = render(
      <DeleteUserModal isOpen={true} onClose={vi.fn()} user={dummyUser} onConfirm={onConfirm} />
    );

    fireEvent.click(screen.getByRole("button", { name: "Hapus Pengguna" }));
    expect(await screen.findByText("Tidak dapat menghapus")).toBeDefined();

    // Close the modal
    rerender(
      <DeleteUserModal isOpen={false} onClose={vi.fn()} user={dummyUser} onConfirm={onConfirm} />
    );
    expect(screen.queryByText("Tidak dapat menghapus")).toBeNull();

    // Reopen the modal
    rerender(
      <DeleteUserModal isOpen={true} onClose={vi.fn()} user={dummyUser} onConfirm={onConfirm} />
    );
    expect(screen.queryByText("Tidak dapat menghapus")).toBeNull();
  });
});
