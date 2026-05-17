(function (PrimeScoreApp) {
  function hideSuggestions() {
    const el = PrimeScoreApp.getById("leagueSuggestions");
    if (el) el.style.display = "none";
  }

  async function searchLeagueDropdown(query) {
    const suggestions = PrimeScoreApp.getById("leagueSuggestions");
    PrimeScoreApp.clearMessage("leagueError");

    if (!query || query.length < 3) {
      hideSuggestions();
      return;
    }

    try {
      const data = await PrimeScoreApp.apiFetch(
        `/api/search?q=${encodeURIComponent(query)}&type=competitions`,
      );
      const leagues = data.competitions || [];

      if (!suggestions) return;

      if (!leagues.length) {
        suggestions.innerHTML = `<div class="suggestion-empty">No leagues found.</div>`;
        suggestions.style.display = "block";
        return;
      }

      suggestions.innerHTML = leagues
        .map(
          (l) =>
            `<div class="suggestion-item" data-id="${PrimeScoreApp.escapeHtml(String(l.id))}" data-name="${PrimeScoreApp.escapeHtml(l.name)}">
              <span class="suggestion-name">${PrimeScoreApp.escapeHtml(l.name)}</span>
            </div>`,
        )
        .join("");

      suggestions.style.display = "block";

      suggestions.querySelectorAll(".suggestion-item").forEach((el) => {
        el.addEventListener("mousedown", async (e) => {
          e.preventDefault();
          const input = PrimeScoreApp.getById("leagueSearch");
          if (input) input.value = el.dataset.name;
          hideSuggestions();
          PrimeScoreApp.clearMessage("leagueError");
          try {
            await PrimeScoreApp.loadStanding?.(el.dataset.id);
          } catch (err) {
            PrimeScoreApp.showMessage(
              "leagueError",
              err.message || "Could not load standings.",
            );
          }
        });
      });
    } catch {
      hideSuggestions();
    }
  }

  const debouncedSearch = PrimeScoreApp.debounce(searchLeagueDropdown, 300);

  function wireLeagueSearch() {
    const input = PrimeScoreApp.getById("leagueSearch");
    if (!input) return;
    input.addEventListener("input", (e) =>
      debouncedSearch(e.target.value.trim()),
    );
    input.addEventListener("blur", () => setTimeout(hideSuggestions, 150));
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", wireLeagueSearch);
  } else {
    wireLeagueSearch();
  }

  PrimeScoreApp.searchLeagues = debouncedSearch;
})(window.PrimeScoreApp);
