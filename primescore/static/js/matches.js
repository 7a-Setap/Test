(function (PrimeScoreApp) {
  function renderMatchList(matches, containerId, emptyText) {
    const container = PrimeScoreApp.getById(containerId);
    if (!container) {
      return;
    }

    if (!matches.length) {
      container.innerHTML = `<p class="empty">${emptyText}</p>`;
      return;
    }

    container.innerHTML = matches
      .map(
        (match) => `
          <div class="match-card">
            <div class="teams">${PrimeScoreApp.escapeHtml(match.home_team)} vs ${PrimeScoreApp.escapeHtml(match.away_team)}</div>
            <div class="score">${match.home_score ?? "-"} : ${match.away_score ?? "-"}</div>
            <div class="meta">${PrimeScoreApp.escapeHtml(match.competition || "")} - ${new Date(
              match.date || match.match_date || ""
            ).toLocaleString()}</div>
            <div class="status">${PrimeScoreApp.escapeHtml(match.status || "")}</div>
          </div>
        `
      )
      .join("");
  }

  async function loadLiveMatches() {
    try {
      const data = await PrimeScoreApp.apiFetch("/api/matches/live");
      renderMatchList(data.matches || [], "liveMatchesList", "No live matches right now.");
    } catch (error) {
      PrimeScoreApp.showMessage("liveError", error.message || "Could not load live matches.");
    }
  }

  async function loadFixtures() {
    try {
      const leagueId = PrimeScoreApp.getById("fixturesLeague")?.value || "PL";
      const data = await PrimeScoreApp.apiFetch(`/api/fixtures?league_id=${encodeURIComponent(leagueId)}`);
      renderMatchList(data.fixtures || [], "fixturesList", "No upcoming fixtures.");
    } catch (error) {
      PrimeScoreApp.showMessage("fixturesError", error.message || "Could not load fixtures.");
    }
  }

  async function loadResults() {
    try {
      const leagueId = PrimeScoreApp.getById("resultsLeague")?.value || "PL";
      const data = await PrimeScoreApp.apiFetch(`/api/results?league_id=${encodeURIComponent(leagueId)}`);
      renderMatchList(data.results || [], "resultsList", "No recent results.");
    } catch (error) {
      PrimeScoreApp.showMessage("resultsError", error.message || "Could not load results.");
    }
  }

  async function fetchStandings(leagueId = "PL") {
    const data = await PrimeScoreApp.apiFetch(`/api/standings/lookup?league=${encodeURIComponent(leagueId || "PL")}`);
    return data.standings || [];
  }

  async function loadStanding(leagueId = "PL") {
    try {
      const data = await PrimeScoreApp.apiFetch(`/api/leagues/${encodeURIComponent(leagueId || "PL")}/standings`);
      PrimeScoreApp.renderLeagueTables([data], "leagueStandingsDisplay");
    } catch (error) {
      PrimeScoreApp.showMessage("leagueError", error.message || "Could not load standings.");
    }
  }

  async function loadDefaultLeagues() {
    await loadStanding("PL");
  }

  PrimeScoreApp.loadLiveMatches = loadLiveMatches;
  PrimeScoreApp.loadFixtures = loadFixtures;
  PrimeScoreApp.loadResults = loadResults;
  PrimeScoreApp.fetchStandings = fetchStandings;
  PrimeScoreApp.loadStanding = loadStanding;
  PrimeScoreApp.loadDefaultLeagues = loadDefaultLeagues;
})(window.PrimeScoreApp);
