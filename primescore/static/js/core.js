(function (window) {
  const PrimeScoreApp = window.PrimeScoreApp || {};

  PrimeScoreApp.state = {
    user: { username: "", displayName: "", email: "" },
    favourites: { favourite_teams: [], favourite_players: [], favourite_leagues: [] },
    teamCompareRunId: 0,
  };

  PrimeScoreApp.getById = (id) => document.getElementById(id);

  PrimeScoreApp.showElement = (element, displayValue = "") => {
    if (element) {
      element.style.display = displayValue;
    }
  };

  PrimeScoreApp.hideElement = (element) => {
    if (element) {
      element.style.display = "none";
    }
  };

  PrimeScoreApp.showMessage = (elementId, text, isError = true) => {
    const element = PrimeScoreApp.getById(elementId);
    if (!element) {
      return;
    }

    element.textContent = text;
    element.style.color = isError ? "var(--danger)" : "var(--primary)";
    element.style.display = "block";
  };

  PrimeScoreApp.clearMessage = (elementId) => {
    const element = PrimeScoreApp.getById(elementId);
    if (!element) {
      return;
    }

    element.textContent = "";
    element.style.display = "none";
  };

  PrimeScoreApp.debounce = (callback, delay = 300) => {
    let timeoutId;

    return (...args) => {
      clearTimeout(timeoutId);
      timeoutId = window.setTimeout(() => callback(...args), delay);
    };
  };

  PrimeScoreApp.parseCommaList = (value) =>
    (value || "")
      .split(",")
      .map((item) => item.trim())
      .filter(Boolean);

  PrimeScoreApp.escapeHtml = (value) =>
    String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#39;");

  PrimeScoreApp.apiFetch = async (url, options = {}) => {
    const response = await fetch(url, {
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      ...options,
    });

    if (!response.ok) {
      let message = response.statusText || "Request failed";

      try {
        const data = await response.json();
        message = data.error || message;
      } catch (error) {
        // Use the default message when the body is not JSON.
      }

      throw new Error(message);
    }

    return response.json();
  };

  PrimeScoreApp.updateDisplayedName = () => {
    const displayName = PrimeScoreApp.state.user.displayName || PrimeScoreApp.state.user.username || "User";

    ["displayName", "welcomeName"].forEach((elementId) => {
      const element = PrimeScoreApp.getById(elementId);
      if (element) {
        element.textContent = displayName;
      }
    });
  };

  window.PrimeScoreApp = PrimeScoreApp;
})(window);
