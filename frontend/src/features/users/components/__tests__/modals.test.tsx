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
    expect(screen.getByRole("heading", { name: "Add New User" }).id).toBe(
      "create-user-modal-title"
    );
    expect(screen.getByText("Add New User")).toBeDefined();
    expect(screen.getByText("Username")).toBeDefined();
    expect(screen.getByPlaceholderText("e.g. op_johndoe")).toBeDefined();
    expect(screen.getByText("Password")).toBeDefined();
    expect(screen.getByPlaceholderText("Minimum 6 characters")).toBeDefined();
    expect(screen.getByText("Role")).toBeDefined();
    expect(screen.getByRole("combobox")).toBeDefined();
    expect(screen.getByRole("option", { name: "Operator (Monitoring & Operations)" })).toBeDefined();
    expect(screen.getByRole("option", { name: "Admin (Full System Access)" })).toBeDefined();
    expect(screen.getByRole("button", { name: "Cancel" })).toBeDefined();
    expect(screen.getByRole("button", { name: "Save User" })).toBeDefined();
  });

  it("shows validation error when username is whitespace-only", async () => {
    const onSubmit = vi.fn();
    render(<CreateUserModal isOpen={true} onClose={vi.fn()} onSubmit={onSubmit} />);

    const usernameInput = screen.getByPlaceholderText("e.g. op_johndoe");
    const passwordInput = screen.getByPlaceholderText("Minimum 6 characters");
    const submitBtn = screen.getByRole("button", { name: "Save User" });

    fireEvent.change(usernameInput, { target: { value: "   " } });
    fireEvent.change(passwordInput, { target: { value: "123456" } });
    fireEvent.click(submitBtn);

    expect(await screen.findByText("Username cannot be empty")).toBeDefined();
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("shows validation error when username is less than 3 characters", async () => {
    const onSubmit = vi.fn();
    render(<CreateUserModal isOpen={true} onClose={vi.fn()} onSubmit={onSubmit} />);

    const usernameInput = screen.getByPlaceholderText("e.g. op_johndoe");
    const passwordInput = screen.getByPlaceholderText("Minimum 6 characters");
    const submitBtn = screen.getByRole("button", { name: "Save User" });

    fireEvent.change(usernameInput, { target: { value: "ab" } });
    fireEvent.change(passwordInput, { target: { value: "123456" } });
    fireEvent.click(submitBtn);

    expect(await screen.findByText("Username must be at least 3 characters")).toBeDefined();
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("shows validation error when password is less than 6 characters", async () => {
    const onSubmit = vi.fn();
    render(<CreateUserModal isOpen={true} onClose={vi.fn()} onSubmit={onSubmit} />);

    const usernameInput = screen.getByPlaceholderText("e.g. op_johndoe");
    const passwordInput = screen.getByPlaceholderText("Minimum 6 characters");
    const submitBtn = screen.getByRole("button", { name: "Save User" });

    fireEvent.change(usernameInput, { target: { value: "user_test" } });
    fireEvent.change(passwordInput, { target: { value: "12345" } });
    fireEvent.click(submitBtn);

    expect(await screen.findByText("Password must be at least 6 characters")).toBeDefined();
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("submits valid payload and triggers onClose", async () => {
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    const onClose = vi.fn();
    render(<CreateUserModal isOpen={true} onClose={onClose} onSubmit={onSubmit} />);

    fireEvent.change(screen.getByPlaceholderText("e.g. op_johndoe"), {
      target: { value: "operator_b" },
    });
    fireEvent.change(screen.getByPlaceholderText("Minimum 6 characters"), {
      target: { value: "password123" },
    });
    fireEvent.change(screen.getByRole("combobox"), {
      target: { value: "operator" },
    });

    fireEvent.click(screen.getByRole("button", { name: "Save User" }));

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
    const onSubmit = vi.fn().mockRejectedValue(new Error("Username already taken"));
    render(<CreateUserModal isOpen={true} onClose={vi.fn()} onSubmit={onSubmit} />);

    fireEvent.change(screen.getByPlaceholderText("e.g. op_johndoe"), {
      target: { value: "duplicate_user" },
    });
    fireEvent.change(screen.getByPlaceholderText("Minimum 6 characters"), {
      target: { value: "password123" },
    });

    fireEvent.click(screen.getByRole("button", { name: "Save User" }));

    expect(await screen.findByText("Username already taken")).toBeDefined();
  });

  it("calls onClose when Cancel is clicked", () => {
    const onClose = vi.fn();
    render(<CreateUserModal isOpen={true} onClose={onClose} onSubmit={vi.fn()} />);

    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
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
    fireEvent.click(screen.getByText("Add New User"));
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

    fireEvent.change(screen.getByPlaceholderText("e.g. op_johndoe"), {
      target: { value: "operator_new" },
    });
    fireEvent.change(screen.getByPlaceholderText("Minimum 6 characters"), {
      target: { value: "password123" },
    });

    const closeBtn = screen.getByRole("button", { name: "Close" });
    expect((closeBtn as HTMLButtonElement).disabled).toBe(false);

    fireEvent.click(screen.getByRole("button", { name: "Save User" }));

    // Is submitting
    expect((closeBtn as HTMLButtonElement).disabled).toBe(true);
    expect(screen.getByRole("button", { name: "Saving..." })).toBeDefined();

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
    expect(screen.getByRole("heading", { name: "Edit User" }).id).toBe(
      "edit-user-modal-title"
    );

    expect(screen.getByText("Username:")).toBeDefined();
    expect(screen.getByText("(cannot be changed)")).toBeDefined();
    expect(screen.getByText("Role")).toBeDefined();
    expect(screen.getByRole("option", { name: "Operator (Monitoring & Operations)" })).toBeDefined();
    expect(screen.getByRole("option", { name: "Admin (Full System Access)" })).toBeDefined();
    expect(screen.getByText("Account Status")).toBeDefined();
    expect(screen.getByText("Active Account")).toBeDefined();

    const checkbox = screen.getByRole("checkbox") as HTMLInputElement;
    expect(checkbox.disabled).toBe(true);
    expect(
      screen.getByText("You cannot deactivate the account currently in use.")
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
      screen.getByText("Role cannot be demoted because this is the only active admin.")
    ).toBeDefined();
    expect(
      screen.getByText(
        "This account cannot be deactivated because it is the only active admin."
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

    fireEvent.click(screen.getByRole("button", { name: "Save Changes" }));

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

    fireEvent.click(screen.getByRole("button", { name: "Save Changes" }));
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

    fireEvent.click(screen.getByText("Edit User"));
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

    const closeBtn = screen.getByRole("button", { name: "Close" });
    expect((closeBtn as HTMLButtonElement).disabled).toBe(false);

    fireEvent.click(screen.getByRole("button", { name: "Save Changes" }));

    expect((closeBtn as HTMLButtonElement).disabled).toBe(true);
    expect(screen.getByRole("button", { name: "Saving..." })).toBeDefined();

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
    expect(screen.getByRole("heading", { name: "Reset User Password" }).id).toBe(
      "reset-password-modal-title"
    );
    expect(screen.getByText("Reset password for:")).toBeDefined();
    expect(screen.getByText("New Password")).toBeDefined();
    expect(screen.getByText("Confirm New Password")).toBeDefined();

    const inputs = screen.getAllByPlaceholderText(/minimum 6 characters|re-enter new password/i);
    fireEvent.change(inputs[0], { target: { value: "123" } });
    fireEvent.change(inputs[1], { target: { value: "123" } });

    fireEvent.click(screen.getByRole("button", { name: "Reset Password" }));

    expect(await screen.findByText("Password must be at least 6 characters")).toBeDefined();
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("validates mismatched confirmation password", async () => {
    const onSubmit = vi.fn();
    render(
      <ResetPasswordModal isOpen={true} onClose={vi.fn()} user={dummyUser} onSubmit={onSubmit} />
    );

    const inputs = screen.getAllByPlaceholderText(/minimum 6 characters|re-enter new password/i);
    fireEvent.change(inputs[0], { target: { value: "password123" } });
    fireEvent.change(inputs[1], { target: { value: "different123" } });

    fireEvent.click(screen.getByRole("button", { name: "Reset Password" }));

    expect(await screen.findByText("New passwords do not match")).toBeDefined();
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("submits matching password successfully", async () => {
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    const onClose = vi.fn();
    render(
      <ResetPasswordModal isOpen={true} onClose={onClose} user={dummyUser} onSubmit={onSubmit} />
    );

    const inputs = screen.getAllByPlaceholderText(/minimum 6 characters|re-enter new password/i);
    fireEvent.change(inputs[0], { target: { value: "newSecret123" } });
    fireEvent.change(inputs[1], { target: { value: "newSecret123" } });

    fireEvent.click(screen.getByRole("button", { name: "Reset Password" }));

    await waitFor(() => {
      expect(onSubmit).toHaveBeenCalledWith(5, { new_password: "newSecret123" });
      expect(onClose).toHaveBeenCalled();
    });
  });

  it("displays error when onSubmit rejects", async () => {
    const onSubmit = vi.fn().mockRejectedValue(new Error("Access denied"));
    render(
      <ResetPasswordModal isOpen={true} onClose={vi.fn()} user={dummyUser} onSubmit={onSubmit} />
    );

    const inputs = screen.getAllByPlaceholderText(/minimum 6 characters|re-enter new password/i);
    fireEvent.change(inputs[0], { target: { value: "newSecret123" } });
    fireEvent.change(inputs[1], { target: { value: "newSecret123" } });

    fireEvent.click(screen.getByRole("button", { name: "Reset Password" }));

    expect(await screen.findByText("Access denied")).toBeDefined();
  });

  it("dismisses on Escape key press and backdrop click", () => {
    const onClose = vi.fn();
    render(
      <ResetPasswordModal isOpen={true} onClose={onClose} user={dummyUser} onSubmit={vi.fn()} />
    );

    fireEvent.click(screen.getByText("Reset User Password"));
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

    const inputs = screen.getAllByPlaceholderText(/minimum 6 characters|re-enter new password/i);
    fireEvent.change(inputs[0], { target: { value: "password123" } });
    fireEvent.change(inputs[1], { target: { value: "password123" } });

    const closeBtn = screen.getByRole("button", { name: "Close" });
    expect((closeBtn as HTMLButtonElement).disabled).toBe(false);

    fireEvent.click(screen.getByRole("button", { name: "Reset Password" }));

    expect((closeBtn as HTMLButtonElement).disabled).toBe(true);
    expect(screen.getByRole("button", { name: "Resetting..." })).toBeDefined();

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
    expect(screen.getByRole("heading", { name: "Delete User" }).id).toBe(
      "delete-user-modal-title"
    );
    expect(
      screen.getByText(/Are you sure you want to delete user account/)
    ).toBeDefined();
    expect(screen.getByText('"doomed_user"')).toBeDefined();
    expect(screen.getByText(/This action cannot be undone\./)).toBeDefined();
    expect(screen.getByRole("button", { name: "Cancel" })).toBeDefined();
    expect(screen.getByRole("button", { name: "Delete User" })).toBeDefined();
  });

  it("calls onConfirm with user.id and closes on confirmation", async () => {
    const onConfirm = vi.fn().mockResolvedValue(undefined);
    const onClose = vi.fn();

    render(
      <DeleteUserModal isOpen={true} onClose={onClose} user={dummyUser} onConfirm={onConfirm} />
    );

    fireEvent.click(screen.getByRole("button", { name: "Delete User" }));

    await waitFor(() => {
      expect(onConfirm).toHaveBeenCalledWith(9);
      expect(onClose).toHaveBeenCalled();
    });
  });

  it("displays error message if onConfirm rejects", async () => {
    const onConfirm = vi.fn().mockRejectedValue(new Error("Cannot delete active admin"));
    render(
      <DeleteUserModal isOpen={true} onClose={vi.fn()} user={dummyUser} onConfirm={onConfirm} />
    );

    fireEvent.click(screen.getByRole("button", { name: "Delete User" }));

    expect(await screen.findByText("Cannot delete active admin")).toBeDefined();
  });

  it("dismisses on Escape key press and backdrop click", () => {
    const onClose = vi.fn();
    render(
      <DeleteUserModal isOpen={true} onClose={onClose} user={dummyUser} onConfirm={vi.fn()} />
    );

    fireEvent.click(screen.getByRole("heading", { name: "Delete User" }));
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

    const closeBtn = screen.getByRole("button", { name: "Close" });
    expect((closeBtn as HTMLButtonElement).disabled).toBe(false);

    fireEvent.click(screen.getByRole("button", { name: "Delete User" }));

    expect((closeBtn as HTMLButtonElement).disabled).toBe(true);
    expect(screen.getByRole("button", { name: "Deleting..." })).toBeDefined();

    fireEvent.keyDown(window, { key: "Escape" });
    fireEvent.click(screen.getByRole("dialog"));
    expect(onClose).not.toHaveBeenCalled();

    await act(async () => {
      resolveDelete();
    });
  });

  it("clears previous error when reopened", async () => {
    const onConfirm = vi.fn().mockRejectedValue(new Error("Cannot delete user"));
    const { rerender } = render(
      <DeleteUserModal isOpen={true} onClose={vi.fn()} user={dummyUser} onConfirm={onConfirm} />
    );

    fireEvent.click(screen.getByRole("button", { name: "Delete User" }));
    expect(await screen.findByText("Cannot delete user")).toBeDefined();

    // Close the modal
    rerender(
      <DeleteUserModal isOpen={false} onClose={vi.fn()} user={dummyUser} onConfirm={onConfirm} />
    );
    expect(screen.queryByText("Cannot delete user")).toBeNull();

    // Reopen the modal
    rerender(
      <DeleteUserModal isOpen={true} onClose={vi.fn()} user={dummyUser} onConfirm={onConfirm} />
    );
    expect(screen.queryByText("Cannot delete user")).toBeNull();
  });
});
