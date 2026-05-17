(function (PrimeScoreApp, window) {
  function showCompareTab(tabId, button) {
    const comparePage = PrimeScoreApp.getById("comparePage");
    if (!comparePage) {
      return;
    }

    comparePage.querySelectorAll(".tab-content").forEach((tab) => {
      tab.classList.remove("active");
      tab.style.display = "none";
    });

    comparePage.querySelectorAll(".tabs .tab-btn").forEach((tabButton) => {
      tabButton.classList.remove("active");
    });

    const activeTab = PrimeScoreApp.getById(tabId);
    if (activeTab) {
      activeTab.classList.add("active");
      activeTab.style.display = "";
    }

    button?.classList.add("active");
  }

  function togglePasswordVisibility(inputId) {
    const input = PrimeScoreApp.getById(inputId);
    if (!input) {
      return;
    }

    const button = input.parentElement?.querySelector(".toggle-password");
    const showingPassword = input.type === "text";

    input.type = showingPassword ? "password" : "text";

    if (button) {
      button.textContent = showingPassword ? "Show" : "Hide";
    }
  }

  function switchTab(tabName) {
    document.querySelectorAll("#loginPage .tab-btn").forEach((button) => {
      button.classList.toggle("active", button.dataset.tab === tabName);
    });

    document.querySelectorAll(".auth-form").forEach((form) => {
      form.classList.remove("active");
    });

    const targetForm =
      tabName === "register" ? PrimeScoreApp.getById("registerForm") : PrimeScoreApp.getById("loginForm");

    targetForm?.classList.add("active");
  }

  function showForgotPassword() {
    document.querySelectorAll("#loginPage .tab-btn").forEach((button) => {
      button.classList.remove("active");
    });

    document.querySelectorAll(".auth-form").forEach((form) => {
      form.classList.remove("active");
    });

    PrimeScoreApp.getById("forgotPasswordForm")?.classList.add("active");
  }

  function toggleProfileMenu() {
    PrimeScoreApp.getById("profileDropdown")?.classList.toggle("open");
  }

  function toggleSidebar() {
    const sidebar = PrimeScoreApp.getById("sidebar");
    const overlay = PrimeScoreApp.getById("sidebarOverlay");
    if (!sidebar) {
      return;
    }

    const isOpening = !document.body.classList.contains("sidebar-open");

    document.body.classList.toggle("sidebar-open", isOpening);
    document.body.classList.toggle("sidebar-closed", !isOpening);
    sidebar.classList.toggle("open", isOpening);
    overlay?.classList.toggle("show", isOpening);
  }

  window.showCompareTab = showCompareTab;
  window.togglePasswordVisibility = togglePasswordVisibility;
  window.switchTab = switchTab;
  window.showForgotPassword = showForgotPassword;
  window.toggleProfileMenu = toggleProfileMenu;
  window.toggleSidebar = toggleSidebar;
})(window.PrimeScoreApp, window);
