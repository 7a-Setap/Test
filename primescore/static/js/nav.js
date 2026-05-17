(function (PrimeScoreApp) {
  function closeSidebar() {
    document.body.classList.remove("sidebar-open");
    document.body.classList.add("sidebar-closed");
    PrimeScoreApp.getById("sidebar")?.classList.remove("open");
    PrimeScoreApp.getById("sidebarOverlay")?.classList.remove("show");
  }

  async function loadPageData(pageName) {
    if (pageName === "home") {
      await PrimeScoreApp.loadHome?.();
    }
    if (pageName === "live") {
      await PrimeScoreApp.loadLiveMatches?.();
    }
    if (pageName === "fixtures") {
      await PrimeScoreApp.loadFixtures?.();
    }
    if (pageName === "results") {
      await PrimeScoreApp.loadResults?.();
    }
    if (pageName === "leagues") {
      await PrimeScoreApp.loadDefaultLeagues?.();
    }
    if (pageName === "favourites") {
      await PrimeScoreApp.loadFavourites?.();
    }
    if (pageName === "settings") {
      await PrimeScoreApp.loadSettings?.();
    }
    if (pageName === "profile") {
      await PrimeScoreApp.loadProfile?.();
    }
  }

  async function navigateTo(pageName) {
    document.querySelectorAll(".page").forEach((page) => page.classList.remove("active"));
    document.querySelectorAll(".sidebar-link").forEach((link) => link.classList.remove("active"));

    PrimeScoreApp.getById(`${pageName}Page`)?.classList.add("active");
    document.querySelector(`.sidebar-link[data-page="${pageName}"]`)?.classList.add("active");

    if (pageName === "login") {
      document.body.classList.add("unauth");
    } else {
      document.body.classList.remove("unauth");
    }

    closeSidebar();
    await loadPageData(pageName);
  }

  function wireNav() {
    document.querySelectorAll(".sidebar-link[data-page]").forEach((link) => {
      link.addEventListener("click", (event) => {
        event.preventDefault();
        navigateTo(link.dataset.page);
      });
    });
  }

  PrimeScoreApp.navigateTo = navigateTo;
  PrimeScoreApp.goToHome = () => navigateTo("home");
  PrimeScoreApp.closeSidebar = closeSidebar;
  PrimeScoreApp.wireNav = wireNav;
})(window.PrimeScoreApp);
