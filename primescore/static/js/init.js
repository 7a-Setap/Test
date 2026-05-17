(function (PrimeScoreApp, window) {
  function bindAuthForms() {
    PrimeScoreApp.getById("loginForm")?.addEventListener("submit", PrimeScoreApp.handleLogin);
    PrimeScoreApp.getById("loginButton")?.addEventListener("click", PrimeScoreApp.handleLogin);

    PrimeScoreApp.getById("registerForm")?.addEventListener("submit", PrimeScoreApp.handleRegister);
    PrimeScoreApp.getById("registerButton")?.addEventListener("click", PrimeScoreApp.handleRegister);

    PrimeScoreApp.getById("forgotPasswordButton")?.addEventListener("click", PrimeScoreApp.handleForgotPassword);
  }

  function bindCompareControls() {
    PrimeScoreApp.getById("teamCompareCount")?.addEventListener("change", PrimeScoreApp.buildTeamInputs);
    PrimeScoreApp.getById("playerCompareCount")?.addEventListener("change", PrimeScoreApp.updatePlayerCompareInputs);
  }

  async function bootstrapSession() {
    try {
      const sessionData = await PrimeScoreApp.apiFetch("/api/session");

      PrimeScoreApp.state.user = {
        username: sessionData.username || "",
        displayName: sessionData.display_name || "",
        email: sessionData.email || "",
      };

      document.body.classList.remove("unauth");
      PrimeScoreApp.showElement(PrimeScoreApp.getById("profileSection"), "flex");
      PrimeScoreApp.updateDisplayedName();
      PrimeScoreApp.closeSidebar?.();
      PrimeScoreApp.navigateTo?.("home");
    } catch (error) {
      document.body.classList.add("unauth");
      PrimeScoreApp.hideElement(PrimeScoreApp.getById("profileSection"));
      PrimeScoreApp.closeSidebar?.();
      PrimeScoreApp.navigateTo?.("login");
    }
  }

  function init() {
    PrimeScoreApp.wireNav?.();
    PrimeScoreApp.buildTeamInputs?.();
    PrimeScoreApp.updatePlayerCompareInputs?.();

    bindAuthForms();
    bindCompareControls();

    const footerYear = PrimeScoreApp.getById("footerYear");
    if (footerYear) {
      footerYear.textContent = new Date().getFullYear();
    }

    document.body.classList.add("unauth");
    bootstrapSession();
  }

  document.addEventListener("DOMContentLoaded", init);

  window.navigateTo = PrimeScoreApp.navigateTo;
  window.goToHome = PrimeScoreApp.goToHome;
  window.closeSidebar = PrimeScoreApp.closeSidebar;
  window.compareTeamsMultiple = PrimeScoreApp.compareTeamsMultiple;
  window.updateTeamCompareInputs = PrimeScoreApp.buildTeamInputs;
  window.comparePlayersMultiple = PrimeScoreApp.comparePlayersMultiple;
  window.updatePlayerCompareInputs = PrimeScoreApp.updatePlayerCompareInputs;
  window.searchLeagues = PrimeScoreApp.searchLeagues;
  window.logout = PrimeScoreApp.logout;
  window.showSummaryTab = PrimeScoreApp.showSummaryTab;
  window.refreshLiveMatches = () => PrimeScoreApp.loadHome?.();
  window.saveNotificationSettings = PrimeScoreApp.saveSettings;
})(window.PrimeScoreApp, window);
