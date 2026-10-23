import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor, act } from "@testing-library/react";
import { ChangePasswordModal } from "../ChangePasswordModal";
import { usersApi } from "../../api/users.api";

describe("ChangePasswordModal", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("renders nothing when isOpen is false", () => {
    const { container } = render(
      <ChangePasswordModal isOpen={false} onClose={vi.fn()} />
    );
    expect(container.firstChild).toBeNull();
  });

  it("renders modal structure with role='dialog' and aria-modal='true' when isOpen is true", () => {
    render(<ChangePasswordModal isOpen={true} onClose={vi.fn()} />);

    const dialog = screen.getByRole("dialog");
    expect(dialog).toBeDefined();
    expect(dialog.getAttribute("aria-modal")).toBe("true");
    expect(dialog.getAttribute("aria-labelledby")).toBe("change-password-modal-title");
    expect(screen.getByRole("heading", { name: "Ganti Password Saya" }).id).toBe(
      "change-password-modal-title"
    );
    expect(screen.getByText("Ganti Password Saya")).toBeDefined();
    expect(screen.getByPlaceholderText("Masukkan password lama")).toBeDefined();
    expect(screen.getByPlaceholderText("Minimal 6 karakter")).toBeDefined();
    expect(screen.getByPlaceholderText("Ulangi password baru")).toBeDefined();
    expect(screen.getByRole("button", { name: "Perbarui Password" })).toBeDefined();
    expect(screen.getByRole("button", { name: "Batal" })).toBeDefined();
    expect(screen.getByRole("button", { name: "Tutup" })).toBeDefined();
  });

  it("shows validation error when current password is empty", async () => {
    const changePasswordSpy = vi.spyOn(usersApi, "changePassword");
    render(<ChangePasswordModal isOpen={true} onClose={vi.fn()} />);

    // Keep current password empty, fill new & confirm
    fireEvent.change(screen.getByPlaceholderText("Minimal 6 karakter"), {
      target: { value: "newsecret123" },
    });
    fireEvent.change(screen.getByPlaceholderText("Ulangi password baru"), {
      target: { value: "newsecret123" },
    });

    fireEvent.click(screen.getByRole("button", { name: "Perbarui Password" }));

    expect(await screen.findByText("Password saat ini wajib diisi")).toBeDefined();
    expect(changePasswordSpy).not.toHaveBeenCalled();
  });

  it("shows validation error when new password is less than 6 characters", async () => {
    const changePasswordSpy = vi.spyOn(usersApi, "changePassword");
    render(<ChangePasswordModal isOpen={true} onClose={vi.fn()} />);

    fireEvent.change(screen.getByPlaceholderText("Masukkan password lama"), {
      target: { value: "oldsecret123" },
    });
    fireEvent.change(screen.getByPlaceholderText("Minimal 6 karakter"), {
      target: { value: "12345" },
    });
    fireEvent.change(screen.getByPlaceholderText("Ulangi password baru"), {
      target: { value: "12345" },
    });

    fireEvent.click(screen.getByRole("button", { name: "Perbarui Password" }));

    expect(await screen.findByText("Password baru minimal 6 karakter")).toBeDefined();
    expect(changePasswordSpy).not.toHaveBeenCalled();
  });

  it("shows validation error when new password is identical to current password", async () => {
    const changePasswordSpy = vi.spyOn(usersApi, "changePassword");
    render(<ChangePasswordModal isOpen={true} onClose={vi.fn()} />);

    fireEvent.change(screen.getByPlaceholderText("Masukkan password lama"), {
      target: { value: "samesame123" },
    });
    fireEvent.change(screen.getByPlaceholderText("Minimal 6 karakter"), {
      target: { value: "samesame123" },
    });
    fireEvent.change(screen.getByPlaceholderText("Ulangi password baru"), {
      target: { value: "samesame123" },
    });

    fireEvent.click(screen.getByRole("button", { name: "Perbarui Password" }));

    expect(
      await screen.findByText("Password baru harus berbeda dari password saat ini")
    ).toBeDefined();
    expect(changePasswordSpy).not.toHaveBeenCalled();
  });

  it("shows validation error when confirm password does not match new password", async () => {
    const changePasswordSpy = vi.spyOn(usersApi, "changePassword");
    render(<ChangePasswordModal isOpen={true} onClose={vi.fn()} />);

    fireEvent.change(screen.getByPlaceholderText("Masukkan password lama"), {
      target: { value: "oldsecret123" },
    });
    fireEvent.change(screen.getByPlaceholderText("Minimal 6 karakter"), {
      target: { value: "newsecret123" },
    });
    fireEvent.change(screen.getByPlaceholderText("Ulangi password baru"), {
      target: { value: "differentsecret123" },
    });

    fireEvent.click(screen.getByRole("button", { name: "Perbarui Password" }));

    expect(await screen.findByText("Konfirmasi password baru tidak cocok")).toBeDefined();
    expect(changePasswordSpy).not.toHaveBeenCalled();
  });

  it("successfully calls usersApi.changePassword, displays success message, and closes after timeout", async () => {
    vi.useFakeTimers();
    const onClose = vi.fn();
    const changePasswordSpy = vi
      .spyOn(usersApi, "changePassword")
      .mockResolvedValue({ message: "Password updated successfully" });

    render(<ChangePasswordModal isOpen={true} onClose={onClose} />);

    fireEvent.change(screen.getByPlaceholderText("Masukkan password lama"), {
      target: { value: "currentpwd123" },
    });
    fireEvent.change(screen.getByPlaceholderText("Minimal 6 karakter"), {
      target: { value: "brandnewpwd456" },
    });
    fireEvent.change(screen.getByPlaceholderText("Ulangi password baru"), {
      target: { value: "brandnewpwd456" },
    });

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Perbarui Password" }));
    });

    expect(changePasswordSpy).toHaveBeenCalledWith({
      current_password: "currentpwd123",
      new_password: "brandnewpwd456",
    });

    expect(screen.getByText("Password berhasil diperbarui!")).toBeDefined();

    // Inputs and submit button should be disabled upon success
    const currentInput = screen.getByPlaceholderText("Masukkan password lama") as HTMLInputElement;
    const newInput = screen.getByPlaceholderText("Minimal 6 karakter") as HTMLInputElement;
    const confirmInput = screen.getByPlaceholderText("Ulangi password baru") as HTMLInputElement;
    const submitBtn = screen.getByRole("button", { name: "Perbarui Password" }) as HTMLButtonElement;

    expect(currentInput.disabled).toBe(true);
    expect(newInput.disabled).toBe(true);
    expect(confirmInput.disabled).toBe(true);
    expect(submitBtn.disabled).toBe(true);

    expect(onClose).not.toHaveBeenCalled();

    // Advance 1500ms
    act(() => {
      vi.advanceTimersByTime(1500);
    });

    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("displays server error message when API rejects", async () => {
    const changePasswordSpy = vi
      .spyOn(usersApi, "changePassword")
      .mockRejectedValue(new Error("Current password is incorrect"));

    render(<ChangePasswordModal isOpen={true} onClose={vi.fn()} />);

    fireEvent.change(screen.getByPlaceholderText("Masukkan password lama"), {
      target: { value: "wrongpassword" },
    });
    fireEvent.change(screen.getByPlaceholderText("Minimal 6 karakter"), {
      target: { value: "brandnewpwd456" },
    });
    fireEvent.change(screen.getByPlaceholderText("Ulangi password baru"), {
      target: { value: "brandnewpwd456" },
    });

    fireEvent.click(screen.getByRole("button", { name: "Perbarui Password" }));

    expect(await screen.findByText("Current password is incorrect")).toBeDefined();
    expect(changePasswordSpy).toHaveBeenCalledTimes(1);

    // Form inputs and submit button re-enabled after failure
    const submitBtn = screen.getByRole("button", { name: "Perbarui Password" }) as HTMLButtonElement;
    expect(submitBtn.disabled).toBe(false);
  });

  it("handles non-Error reject gracefully", async () => {
    vi.spyOn(usersApi, "changePassword").mockRejectedValue("Unknown string error");

    render(<ChangePasswordModal isOpen={true} onClose={vi.fn()} />);

    fireEvent.change(screen.getByPlaceholderText("Masukkan password lama"), {
      target: { value: "oldsecret123" },
    });
    fireEvent.change(screen.getByPlaceholderText("Minimal 6 karakter"), {
      target: { value: "brandnewpwd456" },
    });
    fireEvent.change(screen.getByPlaceholderText("Ulangi password baru"), {
      target: { value: "brandnewpwd456" },
    });

    fireEvent.click(screen.getByRole("button", { name: "Perbarui Password" }));

    expect(await screen.findByText("Gagal mengganti password")).toBeDefined();
  });

  it("dismisses on Escape key press when not submitting", () => {
    const onClose = vi.fn();
    render(<ChangePasswordModal isOpen={true} onClose={onClose} />);

    fireEvent.keyDown(window, { key: "Escape" });
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("dismisses on backdrop click but not on modal dialog content click", () => {
    const onClose = vi.fn();
    render(<ChangePasswordModal isOpen={true} onClose={onClose} />);

    // Click inside the dialog
    fireEvent.click(screen.getByText("Ganti Password Saya"));
    expect(onClose).not.toHaveBeenCalled();

    // Click backdrop
    const dialog = screen.getByRole("dialog");
    fireEvent.click(dialog);
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("calls onClose when Close (X) button is clicked", () => {
    const onClose = vi.fn();
    render(<ChangePasswordModal isOpen={true} onClose={onClose} />);

    fireEvent.click(screen.getByRole("button", { name: "Tutup" }));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("calls onClose when Batal button is clicked", () => {
    const onClose = vi.fn();
    render(<ChangePasswordModal isOpen={true} onClose={onClose} />);

    fireEvent.click(screen.getByRole("button", { name: "Batal" }));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("disables inputs, buttons, and blocks Escape/backdrop dismissals while submitting", async () => {
    let resolveApi!: (val: { message: string }) => void;
    const pendingPromise = new Promise<{ message: string }>((resolve) => {
      resolveApi = resolve;
    });
    vi.spyOn(usersApi, "changePassword").mockReturnValue(pendingPromise);

    const onClose = vi.fn();
    render(<ChangePasswordModal isOpen={true} onClose={onClose} />);

    fireEvent.change(screen.getByPlaceholderText("Masukkan password lama"), {
      target: { value: "currentpwd123" },
    });
    fireEvent.change(screen.getByPlaceholderText("Minimal 6 karakter"), {
      target: { value: "brandnewpwd456" },
    });
    fireEvent.change(screen.getByPlaceholderText("Ulangi password baru"), {
      target: { value: "brandnewpwd456" },
    });

    fireEvent.click(screen.getByRole("button", { name: "Perbarui Password" }));

    // While submitting:
    await waitFor(() => {
      expect(screen.getByText("Menyimpan...")).toBeDefined();
    });

    const submitBtn = screen.getByRole("button", { name: "Menyimpan..." }) as HTMLButtonElement;
    const cancelBtn = screen.getByRole("button", { name: "Batal" }) as HTMLButtonElement;
    const closeBtn = screen.getByRole("button", { name: "Tutup" }) as HTMLButtonElement;
    const currentInput = screen.getByPlaceholderText("Masukkan password lama") as HTMLInputElement;

    expect(submitBtn.disabled).toBe(true);
    expect(cancelBtn.disabled).toBe(true);
    expect(closeBtn.disabled).toBe(true);
    expect(currentInput.disabled).toBe(true);

    // Escape should not trigger onClose
    fireEvent.keyDown(window, { key: "Escape" });
    expect(onClose).not.toHaveBeenCalled();

    // Backdrop click should not trigger onClose
    const dialog = screen.getByRole("dialog");
    fireEvent.click(dialog);
    expect(onClose).not.toHaveBeenCalled();

    // Finish request
    await act(async () => {
      resolveApi({ message: "OK" });
    });

    await waitFor(() => {
      expect(screen.getByText("Password berhasil diperbarui!")).toBeDefined();
    });
  });

  it("resets fields and error state when reopened", () => {
    const { rerender } = render(<ChangePasswordModal isOpen={true} onClose={vi.fn()} />);

    fireEvent.change(screen.getByPlaceholderText("Masukkan password lama"), {
      target: { value: "mysecret" },
    });
    fireEvent.change(screen.getByPlaceholderText("Minimal 6 karakter"), {
      target: { value: "123" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Perbarui Password" }));

    expect(screen.getByText("Password baru minimal 6 karakter")).toBeDefined();

    // Close modal
    rerender(<ChangePasswordModal isOpen={false} onClose={vi.fn()} />);
    expect(screen.queryByText("Ganti Password Saya")).toBeNull();

    // Reopen modal
    rerender(<ChangePasswordModal isOpen={true} onClose={vi.fn()} />);
    expect(screen.getByText("Ganti Password Saya")).toBeDefined();
    expect(screen.queryByText("Password baru minimal 6 karakter")).toBeNull();
    const currentInput = screen.getByPlaceholderText("Masukkan password lama") as HTMLInputElement;
    expect(currentInput.value).toBe("");
  });
});
