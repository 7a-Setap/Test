(function (PrimeScoreApp) {
  async function handleLogin(e) {
    e.preventDefault();
    PrimeScoreApp.clearMessage("loginError");
    const username = PrimeScoreApp.getById("loginUsername")?.value.trim() || "";
    const password = PrimeScoreApp.getById("loginPassword")?.value || "";
    if (!username || !password) return PrimeScoreApp.showMessage("loginError", "Please enter username and password.");
    try {
      const data = await PrimeScoreApp.apiFetch("/api/login", {
        method: "POST",
        body: JSON.stringify({ username, password }),
      });
      PrimeScoreApp.state.user = { username: data.username, displayName: data.display_name || "", email: data.email || "" };
      PrimeScoreApp.updateDisplayedName();
      PrimeScoreApp.showElement(PrimeScoreApp.getById("firstTimeMessage"), data.first_time_user ? "" : "none");
      document.body.classList.remove("unauth");
      PrimeScoreApp.showElement(PrimeScoreApp.getById("profileSection"), "flex");
      PrimeScoreApp.closeSidebar?.();
      PrimeScoreApp.navigateTo("home");
    } catch (err) {
      PrimeScoreApp.showMessage("loginError", err.message || "Login failed.");
    }
  }

  async function handleRegister(e) {
    e.preventDefault();
    PrimeScoreApp.clearMessage("registerError");
    const username = PrimeScoreApp.getById("registerUsername").value.trim();
    const email = PrimeScoreApp.getById("registerEmail").value.trim();
    const password = PrimeScoreApp.getById("registerPassword").value;
    const confirm = PrimeScoreApp.getById("registerPasswordConfirm").value;
    if (!username || !email || !password || !confirm) return PrimeScoreApp.showMessage("registerError", "All fields are required.");
    if (password !== confirm) return PrimeScoreApp.showMessage("registerError", "Passwords do not match.");
    if (password.length < 8) return PrimeScoreApp.showMessage("registerError", "Password must be at least 8 characters.");
    if (!email.includes("@")) return PrimeScoreApp.showMessage("registerError", "Please enter a valid email address.");
    try {
      await PrimeScoreApp.apiFetch("/api/register", {
        method: "POST",
        body: JSON.stringify({ username, email, password }),
      });
      window.switchTab?.("login");
      PrimeScoreApp.showMessage("loginError", "Registration successful. Please log in.", false);
    } catch (err) {
      PrimeScoreApp.showMessage("registerError", err.message || "Registration failed.");
    }
  }

  async function handleForgotPassword(e) {
    e?.preventDefault();
    PrimeScoreApp.clearMessage("forgotError");
    const email = PrimeScoreApp.getById("forgotEmail")?.value.trim();
    if (!email) return PrimeScoreApp.showMessage("forgotError", "Please enter your email.");
    try {
      await PrimeScoreApp.apiFetch("/api/forgot-password", {
        method: "POST",
        body: JSON.stringify({ email }),
      });
      PrimeScoreApp.showMessage("forgotError", "If that email exists, a reset link was sent.", false);
    } catch (err) {
      PrimeScoreApp.showMessage("forgotError", err.message || "Could not send reset link.");
    }
  }

  PrimeScoreApp.handleLogin = handleLogin;
  PrimeScoreApp.handleRegister = handleRegister;
  PrimeScoreApp.handleForgotPassword = handleForgotPassword;
  PrimeScoreApp.logout = async () => {
    try {
      await PrimeScoreApp.apiFetch("/api/logout", { method: "POST" });
    } catch (e) {
      console.warn("Logout error", e);
    }
    PrimeScoreApp.state.user = { username: "", displayName: "", email: "" };
    document.body.classList.add("unauth");
    PrimeScoreApp.hideElement(PrimeScoreApp.getById("profileSection"));
    PrimeScoreApp.closeSidebar?.();
    PrimeScoreApp.navigateTo?.("login");
  };
})(window.PrimeScoreApp);
