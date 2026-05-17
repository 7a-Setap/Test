(function (PrimeScoreApp) {
  function renderMatchCards(matches, containerId, emptyText) {
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
            ${match.status ? `<div class="status">${PrimeScoreApp.escapeHtml(match.status)}</div>` : ""}
          </div>
        `
      )
      .join("");
  }

  function renderLeagueTables(tables, containerId) {
    const container = PrimeScoreApp.getById(containerId);
    if (!container) {
      return;
    }

    if (!tables.length) {
      container.innerHTML = '<p class="empty">No standings available.</p>';
      return;
    }

    container.innerHTML = tables
      .map((table) => {
        const rows = (table.standings || [])
          .map(
            (row) => `
              <tr>
                <td>${row.position}</td>
                <td><img src="${row.team_crest || ""}" class="crest" alt="" />${PrimeScoreApp.escapeHtml(row.team)}</td>
                <td>${row.played}</td>
                <td>${row.won}</td>
                <td>${row.drawn}</td>
                <td>${row.lost}</td>
                <td>${row.goals_for}</td>
                <td>${row.goals_against}</td>
                <td>${row.goal_difference}</td>
                <td>${row.points}</td>
              </tr>
            `
          )
          .join("");

        return `
          <div class="table-card">
            <h4>${PrimeScoreApp.escapeHtml(table.competition)} (${PrimeScoreApp.escapeHtml(table.season)})</h4>
            <table class="standings">
              <thead>
                <tr>
                  <th>#</th><th>Team</th><th>P</th><th>W</th><th>D</th><th>L</th><th>GF</th><th>GA</th><th>GD</th><th>Pts</th>
                </tr>
              </thead>
              <tbody>${rows}</tbody>
            </table>
          </div>
        `;
      })
      .join("");
  }

  async function loadFavouritesSummary() {
    try {
      const data = await PrimeScoreApp.apiFetch("/api/favourites");

      PrimeScoreApp.state.favourites = {
        favourite_teams: data.favourite_teams || [],
        favourite_players: data.favourite_players || [],
        favourite_leagues: data.favourite_leagues || [],
      };

      PrimeScoreApp.getById("teamsCount")?.replaceChildren(document.createTextNode(String(PrimeScoreApp.state.favourites.favourite_teams.length)));
      PrimeScoreApp.getById("playersCount")?.replaceChildren(document.createTextNode(String(PrimeScoreApp.state.favourites.favourite_players.length)));
      PrimeScoreApp.getById("leaguesCount")?.replaceChildren(document.createTextNode(String(PrimeScoreApp.state.favourites.favourite_leagues.length)));

      PrimeScoreApp.showSummaryTab?.("teams");
    } catch (error) {
      console.error("[loadFavouritesSummary]", error);
    }
  }

  function showSummaryTab(which, event) {
    event?.preventDefault?.();

    document.querySelectorAll(".summary-tab").forEach((button) => {
      button.classList.toggle("active", button.textContent.toLowerCase().includes(which));
    });

    const key =
      which === "players" ? "favourite_players" : which === "leagues" ? "favourite_leagues" : "favourite_teams";
    const items = PrimeScoreApp.state.favourites[key] || [];
    const content = PrimeScoreApp.getById("summaryContent");

    if (!content) {
      return;
    }

    if (!items.length) {
      content.innerHTML = '<p class="message">No favourites yet.</p>';
      return;
    }

    content.innerHTML = `
      <ul class="list">
        ${items
          .map((item) => `<li><span>${PrimeScoreApp.escapeHtml(item.name || item)}</span></li>`)
          .join("")}
      </ul>
    `;
  }

  async function loadHome() {
    try {
      const data = await PrimeScoreApp.apiFetch("/api/home-screen");
      renderMatchCards(data.live_matches || [], "liveMatchesHome", "No live matches right now.");
      renderMatchCards(data.upcoming_fixtures || [], "upcomingFixturesHome", "No upcoming fixtures.");
      renderMatchCards(data.recent_results || [], "recentResultsHome", "No recent results.");
      renderLeagueTables(data.league_tables || [], "leagueTablesHome");
      await loadFavouritesSummary();
    } catch (error) {
      console.error("[loadHome]", error);
    }
  }

  PrimeScoreApp.showSummaryTab = showSummaryTab;
  PrimeScoreApp.loadHome = loadHome;
  PrimeScoreApp.renderMatchCards = renderMatchCards;
  PrimeScoreApp.renderLeagueTables = renderLeagueTables;
  PrimeScoreApp.loadFavouritesSummary = loadFavouritesSummary;
})(window.PrimeScoreApp);
