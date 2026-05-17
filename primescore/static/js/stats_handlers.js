(function (PrimeScoreApp) {
  // ── Shared dropdown helpers ──────────────────────────────────────────────

  function hideSuggestions(id) {
    const el = PrimeScoreApp.getById(id);
    if (el) el.style.display = "none";
  }

  function showDropdown(containerId, items, onSelect, inputId) {
    const container = PrimeScoreApp.getById(containerId);
    if (!container) return;

    if (!items.length) {
      container.innerHTML = `<div class="suggestion-empty">No results found.</div>`;
      container.style.display = "block";
      return;
    }

    container.innerHTML = items
      .map(
        (t) =>
          `<div class="suggestion-item" data-id="${PrimeScoreApp.escapeHtml(String(t.id))}" data-name="${PrimeScoreApp.escapeHtml(t.name)}">
            ${t.crest ? `<img src="${PrimeScoreApp.escapeHtml(t.crest)}" class="suggestion-crest" alt="">` : ""}
            <span class="suggestion-name">${PrimeScoreApp.escapeHtml(t.name)}</span>
          </div>`
      )
      .join("");

    container.style.display = "block";

    container.querySelectorAll(".suggestion-item").forEach((el) => {
      el.addEventListener("mousedown", (e) => {
        e.preventDefault();
        onSelect({ id: el.dataset.id, name: el.dataset.name });
        container.style.display = "none";
        const input = PrimeScoreApp.getById(inputId);
        if (input) input.value = el.dataset.name;
      });
    });
  }

  async function fetchTeams(query) {
    const data = await PrimeScoreApp.apiFetch(
      `/api/search?q=${encodeURIComponent(query)}&type=teams`
    );
    return (data.teams || []).map((t) => ({ id: t.id, name: t.name, crest: t.crest }));
  }

  async function fetchSquad(teamId) {
    const data = await PrimeScoreApp.apiFetch(`/api/teams/${encodeURIComponent(teamId)}/players`);
    return data.players || [];
  }

  function renderSquad(listEl, players, onPlayerSelect) {
    if (!players.length) {
      listEl.innerHTML = `<p class="suggestion-empty">No squad data available.</p>`;
      return;
    }

    const grouped = {};
    players.forEach((p) => {
      const pos = p.position || "Other";
      (grouped[pos] = grouped[pos] || []).push(p);
    });

    const posOrder = ["Goalkeeper", "Defender", "Midfielder", "Attacker", "Other"];
    const sorted = [
      ...posOrder.filter((p) => grouped[p]),
      ...Object.keys(grouped).filter((p) => !posOrder.includes(p)),
    ];

    listEl.innerHTML = sorted
      .map(
        (pos) => `
        <div class="squad-position-group">
          <span class="squad-position-label">${PrimeScoreApp.escapeHtml(pos)}s</span>
          <div class="squad-players">
            ${grouped[pos]
              .map(
                (p) =>
                  `<button class="squad-player-btn" data-id="${p.id}" data-name="${PrimeScoreApp.escapeHtml(p.name)}">
                    ${PrimeScoreApp.escapeHtml(p.name)}
                  </button>`
              )
              .join("")}
          </div>
        </div>`
      )
      .join("");

    listEl.querySelectorAll(".squad-player-btn").forEach((btn) => {
      btn.addEventListener("click", () =>
        onPlayerSelect({ id: btn.dataset.id, name: btn.dataset.name })
      );
    });
  }

  // ── Stats tab switcher ───────────────────────────────────────────────────

  function showStatsTab(tabId, button) {
    const statsPage = PrimeScoreApp.getById("statsPage");
    if (!statsPage) {
      return;
    }

    statsPage.querySelectorAll(".tab-content").forEach((tab) => {
      tab.classList.remove("active");
      tab.style.display = "none";
    });

    statsPage.querySelectorAll(".tabs .tab-btn").forEach((tabButton) => {
      tabButton.classList.remove("active");
    });

    const activeTab = PrimeScoreApp.getById(tabId);
    if (activeTab) {
      activeTab.classList.add("active");
      activeTab.style.display = "";
    }

    button?.classList.add("active");
  }

  function formatMetricValue(value) {
    if (typeof value === "number" && Number.isFinite(value)) {
      return Number.isInteger(value) ? String(value) : value.toFixed(1);
    }
    return PrimeScoreApp.escapeHtml(value ?? "");
  }

  function renderMetricGrid(items) {
    return `
      <div class="stat-grid stats-detail-grid">
        ${items
          .map(
            (item) => `
              <div class="card metric-card">
                <strong>${formatMetricValue(item.value)}</strong>
                <span>${PrimeScoreApp.escapeHtml(item.label)}</span>
              </div>
            `
          )
          .join("")}
      </div>
    `;
  }

  function renderTeamStatsCard(teamStats) {
    const advancedMetricsNote =
      teamStats.advanced_stats_matches > 0
        ? `Advanced metrics averaged from the latest ${teamStats.advanced_stats_matches} finished match${teamStats.advanced_stats_matches === 1 ? "" : "es"}.`
        : "Advanced match metrics are currently unavailable for this team.";

    return `
      <div class="card stats-detail-card">
        <div class="stats-detail-header">
          <div>
            <h3>${PrimeScoreApp.escapeHtml(teamStats.team_name || "Team")}</h3>
            <p class="subtitle">${PrimeScoreApp.escapeHtml(advancedMetricsNote)}</p>
          </div>
          ${
            teamStats.team_crest
              ? `<img src="${PrimeScoreApp.escapeHtml(teamStats.team_crest)}" alt="${PrimeScoreApp.escapeHtml(teamStats.team_name || "Team crest")}" class="stats-detail-crest" />`
              : ""
          }
        </div>
        ${renderMetricGrid([
          { label: "Matches", value: teamStats.matches_played ?? 0 },
          { label: "Wins", value: teamStats.wins ?? 0 },
          { label: "Draws", value: teamStats.draws ?? 0 },
          { label: "Losses", value: teamStats.losses ?? 0 },
          { label: "Goals Scored", value: teamStats.goals_scored ?? 0 },
          { label: "Goals Conceded", value: teamStats.goals_conceded ?? 0 },
          { label: "Clean Sheets", value: teamStats.clean_sheets ?? 0 },
          { label: "Avg Possession (%)", value: teamStats.average_possession ?? 0 },
          { label: "Avg Shots", value: teamStats.average_shots ?? 0 },
          { label: "Avg Shots on Target", value: teamStats.average_shots_on_target ?? 0 },
          { label: "Avg Fouls", value: teamStats.average_fouls_committed ?? 0 },
          { label: "Avg Corners", value: teamStats.average_corners ?? 0 },
        ])}
      </div>
    `;
  }

  function renderPlayerStatsCard(playerStats) {
    const playerMetrics = playerStats.statistics || {};
    const teamLine = [playerStats.current_team, playerStats.position].filter(Boolean).join(" - ");

    return `
      <div class="card stats-detail-card">
        <div class="stats-detail-header">
          <div>
            <h3>${PrimeScoreApp.escapeHtml(playerStats.player_name || "Player")}</h3>
            <p class="subtitle">${PrimeScoreApp.escapeHtml(teamLine || "Individual player statistics")}</p>
          </div>
        </div>
        ${renderMetricGrid([
          { label: "Goals", value: playerMetrics.goals ?? 0 },
          { label: "Assists", value: playerMetrics.assists ?? 0 },
          { label: "Appearances", value: playerMetrics.appearances ?? 0 },
          { label: "Minutes", value: playerMetrics.minutes ?? 0 },
          { label: "Rating", value: playerMetrics.rating || "N/A" },
          { label: "Shots", value: playerMetrics.shots ?? 0 },
          { label: "Shots on Target", value: playerMetrics.shots_on_target ?? 0 },
          { label: "Fouls Committed", value: playerMetrics.fouls_committed ?? 0 },
          { label: "Yellow Cards", value: playerMetrics.yellow_cards ?? 0 },
          { label: "Red Cards", value: playerMetrics.red_cards ?? 0 },
        ])}
      </div>
    `;
  }

  async function viewTeamStats() {
    const resultElement = PrimeScoreApp.getById("individualTeamStatsResult");
    const teamInput = PrimeScoreApp.getById("teamStatsSearch");
    const leagueFilter = PrimeScoreApp.getById("statsLeagueFilter")?.value || "";

    if (resultElement) {
      resultElement.innerHTML = "<p>Loading team statistics...</p>";
    }

    try {
      const resolvedTeam = await PrimeScoreApp.resolveTeamInput?.(teamInput, "", leagueFilter);
      const query = new URLSearchParams({ name: resolvedTeam.name });
      if (leagueFilter) {
        query.set("league", leagueFilter);
      }

      const teamStats = await PrimeScoreApp.apiFetch(
        `/api/teams/${resolvedTeam.id}/statistics?${query.toString()}`
      );

      if (resultElement) {
        resultElement.innerHTML = renderTeamStatsCard(teamStats);
      }
    } catch (error) {
      if (resultElement) {
        resultElement.innerHTML = `<p class="error">${PrimeScoreApp.escapeHtml(error.message || "Team statistics could not be loaded.")}</p>`;
      }
    }
  }

  async function viewPlayerStats() {
    const resultElement = PrimeScoreApp.getById("individualPlayerStatsResult");
    const slot = PrimeScoreApp.getById("statsPlayerSlot");
    const playerId = slot?.dataset.playerId;

    if (!playerId) {
      if (resultElement)
        resultElement.innerHTML = `<p class="error">Select a player using the squad picker above.</p>`;
      return;
    }

    if (resultElement) resultElement.innerHTML = "<p>Loading player statistics...</p>";

    try {
      const playerStats = await PrimeScoreApp.apiFetch(`/api/players/${playerId}/statistics`);
      if (resultElement) resultElement.innerHTML = renderPlayerStatsCard(playerStats);
    } catch (error) {
      if (resultElement)
        resultElement.innerHTML = `<p class="error">${PrimeScoreApp.escapeHtml(error.message || "Player statistics could not be loaded.")}</p>`;
    }
  }

  async function loadStatsSquad(team) {
    const squadPanel = PrimeScoreApp.getById("statsPlayerSquadPanel");
    const squadLabel = PrimeScoreApp.getById("statsPlayerSquadLabel");
    const squadList  = PrimeScoreApp.getById("statsPlayerSquadList");
    if (!squadPanel || !squadLabel || !squadList) return;

    squadLabel.textContent = `${team.name} — select a player:`;
    squadList.innerHTML = `<p class="squad-label">Loading…</p>`;
    squadPanel.style.display = "block";

    try {
      const players = await fetchSquad(team.id);
      renderSquad(squadList, players, (player) => {
        const slot = PrimeScoreApp.getById("statsPlayerSlot");
        slot.dataset.playerId = player.id;
        PrimeScoreApp.getById("statsPlayerName").textContent = player.name;
        PrimeScoreApp.getById("statsPlayerSelected").style.display = "block";
        PrimeScoreApp.getById("statsPlayerPicker").style.display = "none";
      });
    } catch {
      squadList.innerHTML = `<p class="suggestion-empty">Could not load squad.</p>`;
    }
  }

  function initialiseStatsPage() {
    const teamInput   = PrimeScoreApp.getById("teamStatsSearch");
    const leagueFilter = PrimeScoreApp.getById("statsLeagueFilter");
    const playerTeamInput = PrimeScoreApp.getById("playerStatsTeamSearch");

    // Team autocomplete
    if (teamInput) {
      const searchTeams = PrimeScoreApp.debounce(async (query) => {
        if (query.length < 3) { hideSuggestions("teamStatsSuggestions"); return; }
        try {
          const leagueFilter = PrimeScoreApp.getById("statsLeagueFilter")?.value || "";
          const data = await PrimeScoreApp.apiFetch(
            `/api/search?q=${encodeURIComponent(query)}&type=teams${leagueFilter ? `&league=${encodeURIComponent(leagueFilter)}` : ""}`
          );
          const items = (data.teams || []).map((t) => ({ id: t.id, name: t.name, crest: t.crest }));
          showDropdown("teamStatsSuggestions", items, (team) => {
            teamInput.dataset.teamId = String(team.id);
            teamInput.dataset.resolvedName = team.name;
          }, "teamStatsSearch");
        } catch { hideSuggestions("teamStatsSuggestions"); }
      }, 300);

      teamInput.addEventListener("input", (e) => {
        delete teamInput.dataset.teamId;
        delete teamInput.dataset.resolvedName;
        searchTeams(e.target.value.trim());
      });
      teamInput.addEventListener("blur", () =>
        setTimeout(() => hideSuggestions("teamStatsSuggestions"), 150)
      );
    }

    // Clear league filter resets team selection
    leagueFilter?.addEventListener("change", () => {
      if (teamInput) {
        delete teamInput.dataset.teamId;
        delete teamInput.dataset.resolvedName;
      }
    });

    // Player squad picker — team search
    if (playerTeamInput) {
      const searchPlayerTeam = PrimeScoreApp.debounce(async (query) => {
        if (query.length < 3) { hideSuggestions("playerStatsTeamSuggestions"); return; }
        try {
          const items = await fetchTeams(query);
          showDropdown("playerStatsTeamSuggestions", items, (team) => {
            loadStatsSquad(team);
          }, "playerStatsTeamSearch");
        } catch { hideSuggestions("playerStatsTeamSuggestions"); }
      }, 300);

      playerTeamInput.addEventListener("input", (e) => searchPlayerTeam(e.target.value.trim()));
      playerTeamInput.addEventListener("blur", () =>
        setTimeout(() => hideSuggestions("playerStatsTeamSuggestions"), 150)
      );
    }

    // Clear button resets squad picker
    PrimeScoreApp.getById("statsPlayerClear")?.addEventListener("click", () => {
      const slot = PrimeScoreApp.getById("statsPlayerSlot");
      delete slot.dataset.playerId;
      PrimeScoreApp.getById("statsPlayerSelected").style.display = "none";
      PrimeScoreApp.getById("statsPlayerPicker").style.display = "block";
      PrimeScoreApp.getById("statsPlayerSquadPanel").style.display = "none";
      if (playerTeamInput) playerTeamInput.value = "";
    });
  }

  PrimeScoreApp.initialiseStatsPage = initialiseStatsPage;
  PrimeScoreApp.loadStatsPage = () => {};
  PrimeScoreApp.showStatsTab = showStatsTab;
  PrimeScoreApp.viewTeamStats = viewTeamStats;
  PrimeScoreApp.viewPlayerStats = viewPlayerStats;
})(window.PrimeScoreApp);
