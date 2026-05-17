(function (PrimeScoreApp) {
  async function loadProfile() {
    try {
      const data = await PrimeScoreApp.apiFetch("/api/profile");

      PrimeScoreApp.state.user.username = data.username || PrimeScoreApp.state.user.username;
      PrimeScoreApp.state.user.email = data.email || "";
      PrimeScoreApp.state.user.displayName = data.display_name || PrimeScoreApp.state.user.displayName;
      PrimeScoreApp.updateDisplayedName();

      if (PrimeScoreApp.getById("profileUsername")) {
        PrimeScoreApp.getById("profileUsername").value = data.username || "";
      }
      if (PrimeScoreApp.getById("profileEmail")) {
        PrimeScoreApp.getById("profileEmail").value = data.email || "";
      }
      if (PrimeScoreApp.getById("profileDisplayName")) {
        PrimeScoreApp.getById("profileDisplayName").value = data.display_name || "";
      }
      if (PrimeScoreApp.getById("profileBio")) {
        PrimeScoreApp.getById("profileBio").value = data.bio || "";
      }
    } catch (error) {
      PrimeScoreApp.showMessage("profileMsg", error.message || "Could not load profile.");
    }
  }

  async function saveProfile(event) {
    event?.preventDefault();

    const username = PrimeScoreApp.getById("profileUsername")?.value.trim() || "";
    const email = PrimeScoreApp.getById("profileEmail")?.value.trim() || "";
    const displayName = PrimeScoreApp.getById("profileDisplayName")?.value.trim() || "";
    const bio = PrimeScoreApp.getById("profileBio")?.value.trim() || "";

    try {
      const data = await PrimeScoreApp.apiFetch("/api/profile", {
        method: "POST",
        body: JSON.stringify({
          username,
          email,
          display_name: displayName,
          bio,
        }),
      });

      PrimeScoreApp.state.user.username = data.username || username;
      PrimeScoreApp.state.user.email = data.email || email;
      PrimeScoreApp.state.user.displayName = data.display_name || displayName;
      PrimeScoreApp.updateDisplayedName();
      PrimeScoreApp.showMessage("profileMsg", "Profile updated.", false);
    } catch (error) {
      PrimeScoreApp.showMessage("profileMsg", error.message || "Could not save profile.");
    }
  }

  async function changePassword(event) {
    event?.preventDefault();

    const currentPassword = PrimeScoreApp.getById("currentPassword")?.value || "";
    const newPassword = PrimeScoreApp.getById("newPassword")?.value || "";

    if (!currentPassword || !newPassword) {
      PrimeScoreApp.showMessage("passwordMsg", "Enter both the current and new password.");
      return;
    }

    try {
      await PrimeScoreApp.apiFetch("/api/change-password", {
        method: "POST",
        body: JSON.stringify({
          current_password: currentPassword,
          new_password: newPassword,
        }),
      });

      PrimeScoreApp.getById("currentPassword").value = "";
      PrimeScoreApp.getById("newPassword").value = "";
      PrimeScoreApp.showMessage("passwordMsg", "Password updated.", false);
    } catch (error) {
      PrimeScoreApp.showMessage("passwordMsg", error.message || "Could not change password.");
    }
  }

  // ── Account deletion ─────────────────────────────────────────────────────

  function toggleDeleteAccountPanel(open) {
    const panel = PrimeScoreApp.getById("deleteAccountPanel");
    const toggleBtn = PrimeScoreApp.getById("deleteAccountToggle");
    if (!panel) return;

    if (open) {
      panel.style.display = "block";
      if (toggleBtn) toggleBtn.style.display = "none";
    } else {
      panel.style.display = "none";
      if (toggleBtn) toggleBtn.style.display = "";
      // Wipe the inputs so the password isn't sitting around in the DOM and
      // so the user starts fresh next time they open the panel.
      const passwordInput = PrimeScoreApp.getById("deleteAccountPassword");
      const confirmInput = PrimeScoreApp.getById("deleteAccountConfirm");
      if (passwordInput) passwordInput.value = "";
      if (confirmInput) confirmInput.value = "";
      PrimeScoreApp.clearMessage?.("deleteAccountMsg");
    }
  }

  async function deleteAccount() {
    PrimeScoreApp.clearMessage?.("deleteAccountMsg");

    const password = PrimeScoreApp.getById("deleteAccountPassword")?.value || "";
    const confirmation = (PrimeScoreApp.getById("deleteAccountConfirm")?.value || "").trim();

    if (!password) {
      PrimeScoreApp.showMessage("deleteAccountMsg", "Please enter your password.");
      return;
    }
    if (confirmation !== "DELETE") {
      PrimeScoreApp.showMessage("deleteAccountMsg", 'Type "DELETE" exactly to confirm.');
      return;
    }

    // Final OS-level confirm prompt — three gates total (password, typed
    // word, browser confirm) is a lot, but this is an irreversible action.
    if (!window.confirm(
      "This will permanently delete your account and all your favourites. Continue?"
    )) {
      return;
    }

    try {
      await PrimeScoreApp.apiFetch("/api/delete-account", {
        method: "POST",
        body: JSON.stringify({ password, confirmation }),
      });

      // Mirror the logout flow so the UI lands in a clean unauthenticated state.
      PrimeScoreApp.state.user = { username: "", displayName: "", email: "" };
      document.body.classList.add("unauth");
      PrimeScoreApp.hideElement?.(PrimeScoreApp.getById("profileSection"));
      PrimeScoreApp.closeSidebar?.();
      PrimeScoreApp.navigateTo?.("login");
    } catch (error) {
      PrimeScoreApp.showMessage(
        "deleteAccountMsg",
        error.message || "Could not delete account.",
      );
    }
  }

  PrimeScoreApp.loadProfile = loadProfile;
  PrimeScoreApp.saveProfile = saveProfile;
  PrimeScoreApp.changePassword = changePassword;
  PrimeScoreApp.toggleDeleteAccountPanel = toggleDeleteAccountPanel;
  PrimeScoreApp.deleteAccount = deleteAccount;
})(window.PrimeScoreApp);
