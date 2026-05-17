(function (PrimeScoreApp) {
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
          </div>`,
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

  async function fetchTeams(query, leagueFilter) {
    const url = `/api/search?q=${encodeURIComponent(query)}&type=teams${leagueFilter ? `&league=${encodeURIComponent(leagueFilter)}` : ""}`;
    const data = await PrimeScoreApp.apiFetch(url);
    return (data.teams || []).map((t) => ({ id: t.id, name: t.name, crest: t.crest }));
  }

  async function fetchSquad(teamId) {
    const data = await PrimeScoreApp.apiFetch(
      `/api/teams/${encodeURIComponent(teamId)}/players`,
    );
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
                  </button>`,
              )
              .join("")}
          </div>
        </div>`,
      )
      .join("");

    listEl.querySelectorAll(".squad-player-btn").forEach((btn) => {
      btn.addEventListener("click", () =>
        onPlayerSelect({ id: btn.dataset.id, name: btn.dataset.name }),
      );
    });
  }

  function buildTeamInputs() {
    const container = PrimeScoreApp.getById("teamCompareInputs");
    const count = parseInt(PrimeScoreApp.getById("teamCompareCount")?.value || "2", 10);
    if (!container) return;

    container.innerHTML = "";

    for (let i = 0; i < count; i++) {
      const label = String.fromCharCode(65 + i);
      const wrapper = document.createElement("div");
      wrapper.className = "compare-input-group";
      wrapper.innerHTML = `
        <label>Team ${label}</label>
        <div class="autocomplete-wrapper">
          <input id="teamSearch${i}" type="text" placeholder="Search for a team…" autocomplete="off" />
          <div class="autocomplete-suggestions" id="teamSuggestions${i}" style="display:none"></div>
        </div>
      `;
      container.appendChild(wrapper);
      wireTeamAutocomplete(i);
    }
  }

  function wireTeamAutocomplete(index) {
    const input = PrimeScoreApp.getById(`teamSearch${index}`);
    if (!input) return;

    const search = PrimeScoreApp.debounce(async (query) => {
      if (query.length < 3) {
        hideSuggestions(`teamSuggestions${index}`);
        return;
      }
      try {
        const leagueFilter = PrimeScoreApp.getById("teamLeagueFilter")?.value || "";
        const teams = await fetchTeams(query, leagueFilter);
        showDropdown(
          `teamSuggestions${index}`,
          teams,
          (team) => {
            input.dataset.teamId = String(team.id);
            input.dataset.resolvedName = team.name;
          },
          `teamSearch${index}`,
        );
      } catch {
        hideSuggestions(`teamSuggestions${index}`);
      }
    }, 300);

    input.addEventListener("input", (e) => {
      delete input.dataset.teamId;
      delete input.dataset.resolvedName;
      search(e.target.value.trim());
    });
    input.addEventListener("blur", () =>
      setTimeout(() => hideSuggestions(`teamSuggestions${index}`), 150),
    );
  }

  async function resolveTeamInput(input, teamLabel, leagueFilter) {
    const typedValue = input?.value.trim() || "";
    if (!typedValue) throw new Error(`Enter Team ${teamLabel}.`);

    if (input.dataset.teamId && input.dataset.resolvedName === typedValue) {
      return { id: input.dataset.teamId, name: input.dataset.resolvedName };
    }

    if (/^\d+$/.test(typedValue)) {
      const resolved = await PrimeScoreApp.cachedLookupFetch(
        "teams",
        `id:${typedValue}`,
        `/api/resolve/team?q=${encodeURIComponent(typedValue)}`,
      );
      input.value = resolved.name || typedValue;
      input.dataset.teamId = String(resolved.id);
      input.dataset.resolvedName = resolved.name || typedValue;
      return { id: String(resolved.id), name: resolved.name || typedValue };
    }

    const query = new URLSearchParams({ q: typedValue });
    if (leagueFilter) query.set("league", leagueFilter);
    const resolved = await PrimeScoreApp.apiFetch(
      `/api/resolve/team?${query.toString()}`,
    );

    input.value = resolved.name || typedValue;
    input.dataset.teamId = String(resolved.id);
    input.dataset.resolvedName = resolved.name || typedValue;
    return { id: String(resolved.id), name: resolved.name || typedValue };
  }

  function updatePlayerCompareInputs() {
    const container = PrimeScoreApp.getById("playerCompareInputs");
    const count = parseInt(PrimeScoreApp.getById("playerCompareCount")?.value || "2", 10);
    if (!container) return;

    container.innerHTML = "";

    for (let i = 0; i < count; i++) {
      const label = String.fromCharCode(65 + i);
      const wrapper = document.createElement("div");
      wrapper.className = "compare-input-group";
      wrapper.id = `playerSlot${i}`;
      wrapper.innerHTML = `
        <label>Player ${label}</label>
        <div class="player-slot-selected" id="playerSlotSelected${i}" style="display:none">
          <span class="fav-tag">
            <span class="fav-tag-name" id="playerSlotName${i}"></span>
            <button class="fav-tag-remove" id="playerSlotClear${i}" aria-label="Clear">×</button>
          </span>
        </div>
        <div id="playerSlotPicker${i}">
          <div class="autocomplete-wrapper">
            <input type="text" id="playerTeamSearch${i}" placeholder="Search a team to pick a player…" autocomplete="off" />
            <div class="autocomplete-suggestions" id="playerTeamSuggestions${i}" style="display:none"></div>
          </div>
          <div id="playerSquadPanel${i}" style="display:none">
            <p class="squad-label" id="playerSquadLabel${i}"></p>
            <div class="squad-list" id="playerSquadList${i}"></div>
          </div>
        </div>
      `;
      container.appendChild(wrapper);
      wirePlayerSlot(i);
    }
  }

  function wirePlayerSlot(index) {
    const slot = PrimeScoreApp.getById(`playerSlot${index}`);
    if (!slot) return;

    PrimeScoreApp.getById(`playerSlotClear${index}`)?.addEventListener("click", () => {
      delete slot.dataset.playerId;
      PrimeScoreApp.getById(`playerSlotSelected${index}`).style.display = "none";
      PrimeScoreApp.getById(`playerSlotPicker${index}`).style.display = "block";
      const teamInput = PrimeScoreApp.getById(`playerTeamSearch${index}`);
      if (teamInput) teamInput.value = "";
      PrimeScoreApp.getById(`playerSquadPanel${index}`).style.display = "none";
    });

    const teamInput = PrimeScoreApp.getById(`playerTeamSearch${index}`);
    if (!teamInput) return;

    const search = PrimeScoreApp.debounce(async (query) => {
      if (query.length < 3) {
        hideSuggestions(`playerTeamSuggestions${index}`);
        return;
      }
      try {
        const teams = await fetchTeams(query, "");
        showDropdown(
          `playerTeamSuggestions${index}`,
          teams,
          async (team) => { await loadSquadForSlot(index, team); },
          `playerTeamSearch${index}`,
        );
      } catch {
        hideSuggestions(`playerTeamSuggestions${index}`);
      }
    }, 300);

    teamInput.addEventListener("input", (e) => search(e.target.value.trim()));
    teamInput.addEventListener("blur", () =>
      setTimeout(() => hideSuggestions(`playerTeamSuggestions${index}`), 150),
    );
  }

  async function loadSquadForSlot(index, team) {
    const squadPanel = PrimeScoreApp.getById(`playerSquadPanel${index}`);
    const squadLabel = PrimeScoreApp.getById(`playerSquadLabel${index}`);
    const squadList = PrimeScoreApp.getById(`playerSquadList${index}`);
    if (!squadPanel || !squadLabel || !squadList) return;

    squadLabel.textContent = `${team.name} — select a player:`;
    squadList.innerHTML = `<p class="squad-label">Loading…</p>`;
    squadPanel.style.display = "block";

    try {
      const players = await fetchSquad(team.id);
      renderSquad(squadList, players, (player) => {
        const slot = PrimeScoreApp.getById(`playerSlot${index}`);
        slot.dataset.playerId = player.id;
        PrimeScoreApp.getById(`playerSlotName${index}`).textContent = player.name;
        PrimeScoreApp.getById(`playerSlotSelected${index}`).style.display = "block";
        PrimeScoreApp.getById(`playerSlotPicker${index}`).style.display = "none";
      });
    } catch {
      squadList.innerHTML = `<p class="suggestion-empty">Could not load squad.</p>`;
    }
  }

  function getStandingsFallback(standings, team) {
    const row = (standings || []).find(
      (r) =>
        String(r.team_id || "") === String(team.id) ||
        String(r.team || "").toLowerCase() === String(team.name || "").toLowerCase(),
    );
    if (!row) return null;
    return {
      team_id: team.id,
      team_name: row.team || team.name,
      team_crest: row.team_crest || "",
      matches_played: row.played || 0,
      wins: row.won || 0,
      draws: row.drawn || 0,
      losses: row.lost || 0,
      goals_scored: row.goals_for || 0,
      goals_conceded: row.goals_against || 0,
      clean_sheets: 0,
    };
  }

  function formatStatValue(value) {
    if (typeof value === "number" && Number.isFinite(value)) {
      return Number.isInteger(value) ? String(value) : value.toFixed(1);
    }
    return PrimeScoreApp.escapeHtml(value ?? "");
  }

  function renderComparisonTable(rows, labels, valueSelector) {
    if (!rows.length) return '<p class="empty">No comparison data found.</p>';

    let html = '<table class="comparison-table"><thead><tr><th>Stat</th>';
    rows.forEach((row) => {
      html += `<th>${PrimeScoreApp.escapeHtml(row.name)}</th>`;
    });
    html += "</tr></thead><tbody>";

    labels.forEach(({ key, label }) => {
      const values = rows.map((row) => valueSelector(row.data, key, row));
      const numericValues = values.filter((v) => v !== null && v !== undefined);
      const highest = numericValues.length ? Math.max(...numericValues) : 0;
      html += `<tr><td>${label}</td>`;
      values.forEach((v) => {
        if (v === null || v === undefined) {
          html += `<td class="na">N/A</td>`;
        } else {
          const hi = highest > 0 && v === highest ? ' class="highlight"' : "";
          html += `<td${hi}>${formatStatValue(v)}</td>`;
        }
      });
      html += "</tr>";
    });

    html += "</tbody></table>";
    return html;
  }

  async function compareTeamsMultiple() {
    const resultElement = PrimeScoreApp.getById("teamComparisonResult");
    const runId = ++PrimeScoreApp.state.teamCompareRunId;
    const teamCount = parseInt(PrimeScoreApp.getById("teamCompareCount")?.value || "2", 10);
    const leagueFilter = PrimeScoreApp.getById("teamLeagueFilter")?.value || "";
    const resolvedTeams = [];

    if (resultElement) resultElement.innerHTML = "<p>Loading team comparison…</p>";

    try {
      for (let i = 0; i < teamCount; i++) {
        const label = String.fromCharCode(65 + i);
        const input = PrimeScoreApp.getById(`teamSearch${i}`);
        const team = await resolveTeamInput(input, label, leagueFilter);
        if (resolvedTeams.some((t) => t.id === team.id))
          throw new Error("Choose different teams for comparison.");
        resolvedTeams.push(team);
      }

      const standings = leagueFilter ? await PrimeScoreApp.fetchStandings(leagueFilter) : [];
      const teamStats = await Promise.all(
        resolvedTeams.map(async (team) => {
          try {
            const query = new URLSearchParams({ name: team.name });
            if (leagueFilter) query.set("league", leagueFilter);
            return await PrimeScoreApp.apiFetch(
              `/api/teams/${team.id}/statistics?${query.toString()}`,
            );
          } catch {
            return getStandingsFallback(standings, team);
          }
        }),
      );

      if (runId !== PrimeScoreApp.state.teamCompareRunId) return;

      const rows = resolvedTeams.map((team, i) => ({
        name: teamStats[i]?.team_name || team.name,
        data: teamStats[i] || getStandingsFallback(standings, team) || {},
      }));

      if (resultElement) {
        resultElement.innerHTML = renderComparisonTable(
          rows,
          [
            { key: "matches_played", label: "Matches" },
            { key: "wins", label: "Wins" },
            { key: "draws", label: "Draws" },
            { key: "losses", label: "Losses" },
            { key: "goals_scored", label: "Goals For" },
            { key: "goals_conceded", label: "Goals Against" },
            { key: "clean_sheets", label: "Clean Sheets" },
          ],
          (data, key) => data[key] ?? 0,
        );
      }
    } catch (error) {
      if (resultElement)
        resultElement.innerHTML = `<p class="error">${PrimeScoreApp.escapeHtml(error.message || "Team comparison failed.")}</p>`;
    }
  }

  async function comparePlayersMultiple() {
    const resultElement = PrimeScoreApp.getById("playerComparisonResult");
    const runId = ++PrimeScoreApp.state.playerCompareRunId;
    const count = parseInt(PrimeScoreApp.getById("playerCompareCount")?.value || "2", 10);
    const playerIds = [];

    for (let i = 0; i < count; i++) {
      const label = String.fromCharCode(65 + i);
      const slot = PrimeScoreApp.getById(`playerSlot${i}`);
      const id = slot?.dataset.playerId;
      if (!id) {
        if (resultElement)
          resultElement.innerHTML = `<p class="error">Select a player for slot ${label}.</p>`;
        return;
      }
      if (playerIds.includes(id)) {
        if (resultElement)
          resultElement.innerHTML = `<p class="error">Choose different players for comparison.</p>`;
        return;
      }
      playerIds.push(id);
    }

    if (resultElement) resultElement.innerHTML = "<p>Loading player comparison…</p>";

    try {
      const responses = await Promise.all(
        playerIds.map((id) => PrimeScoreApp.apiFetch(`/api/players/${id}/statistics`)),
      );

      if (runId !== PrimeScoreApp.state.playerCompareRunId) return;

      const rows = responses.map((p) => ({
        name: p.player_name || `Player ${p.player_id}`,
        data: p.statistics || {},
        available: p.stats_available !== false,
      }));

      if (resultElement) {
        resultElement.innerHTML = renderComparisonTable(
          rows,
          [
            { key: "appearances", label: "Appearances" },
            { key: "goals", label: "Goals" },
            { key: "assists", label: "Assists" },
            { key: "minutes", label: "Minutes Played" },
            { key: "shots", label: "Shots" },
            { key: "shots_on_target", label: "Shots on Target" },
            { key: "fouls_committed", label: "Fouls Committed" },
            { key: "yellow_cards", label: "Yellow Cards" },
            { key: "red_cards", label: "Red Cards" },
            { key: "rating", label: "Avg Rating" },
          ],
          (data, key, row) => {
            if (!row.available) return null;
            if (key === "rating") return data[key] || null;
            return data[key] ?? 0;
          },
        );
      }
    } catch (error) {
      if (resultElement)
        resultElement.innerHTML = `<p class="error">${PrimeScoreApp.escapeHtml(error.message || "Player comparison failed.")}</p>`;
    }
  }

  PrimeScoreApp.buildTeamInputs = buildTeamInputs;
  PrimeScoreApp.compareTeamsMultiple = compareTeamsMultiple;
  PrimeScoreApp.resolveTeamInput = resolveTeamInput;
  PrimeScoreApp.updatePlayerCompareInputs = updatePlayerCompareInputs;
  PrimeScoreApp.comparePlayersMultiple = comparePlayersMultiple;
})(window.PrimeScoreApp);
