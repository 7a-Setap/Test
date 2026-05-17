(function (PrimeScoreApp) {
  function normaliseItems(items) {
    return (items || []).map((item) => String(item)).filter(Boolean);
  }

  function applyFavouriteState(
    data,
    { preferNewestHomeLeague = false, selectedLeague = null } = {},
  ) {
    const favouriteTeams = normaliseItems(data.favourite_teams);
    const favouritePlayers = normaliseItems(data.favourite_players);
    const favouriteLeagues = normaliseItems(data.favourite_leagues);
    const favouriteTeamIds = normaliseItems(data.favourite_team_ids);
    const favouritePlayerIds = normaliseItems(data.favourite_player_ids);
    const favouriteLeagueCodes = normaliseItems(data.favourite_league_codes);

    PrimeScoreApp.state.favourites = {
      favourite_teams: favouriteTeams,
      favourite_players: favouritePlayers,
      favourite_leagues: favouriteLeagues,
      favourite_team_ids: favouriteTeamIds,
      favourite_player_ids: favouritePlayerIds,
      favourite_league_codes: favouriteLeagueCodes,
    };

    PrimeScoreApp.state.favouriteLeagueOptions = favouriteLeagues.map(
      (name, index) => ({
        name,
        code: favouriteLeagueCodes[index] || name,
      }),
    );

    if (selectedLeague?.code) {
      PrimeScoreApp.state.homeLeagueCode = String(selectedLeague.code);
      PrimeScoreApp.state.homeLeagueName = selectedLeague.name || "";
    }

    const newestLeague = PrimeScoreApp.state.favouriteLeagueOptions.at(-1);
    const currentLeagueStillSaved =
      PrimeScoreApp.state.favouriteLeagueOptions.some(
        (league) => league.code === PrimeScoreApp.state.homeLeagueCode,
      );

    if (preferNewestHomeLeague && newestLeague) {
      PrimeScoreApp.state.homeLeagueCode = newestLeague.code;
      PrimeScoreApp.state.homeLeagueName = newestLeague.name;
    } else if (
      !PrimeScoreApp.state.homeLeagueCode ||
      !currentLeagueStillSaved
    ) {
      PrimeScoreApp.state.homeLeagueCode =
        newestLeague?.code || PrimeScoreApp.state.homeLeagueCode || "";
      PrimeScoreApp.state.homeLeagueName =
        newestLeague?.name || PrimeScoreApp.state.homeLeagueName || "";
    }
  }

  // Match looks "live" when API-Football has a minute counter for it
  // (or the status string mentions live / in-play / first/second half).
  function _isLiveMatch(match) {
    if (match.minute != null && match.minute !== "") return true;
    const status = String(match.status || "").toLowerCase();
    return (
      status.includes("live") ||
      status.includes("in play") ||
      status.includes("first half") ||
      status.includes("second half") ||
      status.includes("half time") ||
      status.includes("extra time")
    );
  }

  // Icon for an event subtype returned by /api/matches/:id/events.
  function _eventIcon(subtype) {
    switch (subtype) {
      case "yellow_card":
        return '<span class="event-icon event-yellow" title="Yellow card">🟨</span>';
      case "red_card":
        return '<span class="event-icon event-red" title="Red card">🟥</span>';
      case "substitution":
        return '<span class="event-icon event-sub" title="Substitution">⇄</span>';
      case "goal":
      case "penalty_goal":
      case "own_goal":
        return '<span class="event-icon event-goal" title="Goal">⚽</span>';
      default:
        return '<span class="event-icon">•</span>';
    }
  }

  function _renderEventRow(event) {
    const minuteStr =
      event.minute != null
        ? `${event.minute}${event.extra_minute ? "+" + event.extra_minute : ""}'`
        : "";
    const player = event.player || "";
    const team = event.team || "";
    const subtypeLabel = event.subtype === "substitution"
      ? (event.assist ? `${event.assist} → ${player}` : player)
      : player;
    return `
      <li class="event-row">
        <span class="event-minute">${PrimeScoreApp.escapeHtml(minuteStr)}</span>
        ${_eventIcon(event.subtype)}
        <span class="event-player">${PrimeScoreApp.escapeHtml(subtypeLabel)}</span>
        <span class="event-team">${PrimeScoreApp.escapeHtml(team)}</span>
      </li>
    `;
  }

  // ── Lineup / formation rendering ─────────────────────────────────────────

  // "K. De Bruyne" → "De Bruyne"; "Salah" → "Salah".  Keeps the surname
  // (or surnames) and drops the leading initial — fits nicely on a token.
  function _lastNameOnly(fullName) {
    if (!fullName) return "";
    const parts = String(fullName).trim().split(/\s+/);
    if (parts.length === 1) return parts[0];
    // Drop the first token if it looks like an initial ("K." or "M-A.")
    if (/\.$/.test(parts[0])) return parts.slice(1).join(" ");
    return fullName;
  }

  function _renderMiniPitch(teamData) {
    if (!teamData) return "";
    const startXI = teamData.start_xi || [];
    if (!startXI.length) return "";

    // Find the formation's bounding box from the grid coordinates so we
    // can place players proportionally regardless of the formation shape
    // (3-5-2, 4-3-3, 4-2-3-1 all just work).
    let maxLine = 0;
    let maxPos = 0;
    startXI.forEach((p) => {
      if (!p.grid) return;
      const [line, pos] = String(p.grid).split(":").map(Number);
      if (line > maxLine) maxLine = line;
      if (pos > maxPos) maxPos = pos;
    });
    if (maxLine === 0) maxLine = 1;
    if (maxPos === 0) maxPos = 1;

    const tokens = startXI
      .map((p) => {
        if (!p.grid) return "";
        const [line, pos] = String(p.grid).split(":").map(Number);
        // Line 1 = GK → render at the BOTTOM of the pitch (own goal).
        // Highest line → render at the TOP (attacking direction).
        const yPercent = 100 - ((line - 0.5) / maxLine) * 100;
        const xPercent = ((pos - 0.5) / maxPos) * 100;
        const number = p.number != null ? p.number : "";
        const name = _lastNameOnly(p.name);
        return `
          <div class="formation-player" style="top:${yPercent}%; left:${xPercent}%">
            <span class="formation-number">${PrimeScoreApp.escapeHtml(String(number))}</span>
            <span class="formation-name">${PrimeScoreApp.escapeHtml(name)}</span>
          </div>
        `;
      })
      .join("");

    const subsList = (teamData.substitutes || [])
      .map((p) => {
        const num = p.number != null ? `${p.number}. ` : "";
        return `<li>${PrimeScoreApp.escapeHtml(num + (p.name || ""))}</li>`;
      })
      .join("");

    return `
      <div class="formation-block">
        <div class="formation-header">
          ${teamData.team_logo ? `<img src="${PrimeScoreApp.escapeHtml(teamData.team_logo)}" class="crest-xs" alt="" />` : ""}
          <strong>${PrimeScoreApp.escapeHtml(teamData.team_name || "Team")}</strong>
          <span class="formation-meta">${PrimeScoreApp.escapeHtml(teamData.formation || "")}${teamData.coach ? " · " + PrimeScoreApp.escapeHtml(teamData.coach) : ""}</span>
        </div>
        <div class="formation-pitch">${tokens}</div>
        ${subsList ? `<details class="formation-subs"><summary>Substitutes</summary><ul>${subsList}</ul></details>` : ""}
      </div>
    `;
  }

  // ── Tabbed details panel (Lineups + Events) ─────────────────────────────

  // Build the tab + content scaffolding inside the panel on first open.
  function _initialiseDetailsPanel(panelEl, matchId) {
    // H2H tab only makes sense if we have both team IDs (cached on the panel
    // by renderMatchCards via data attributes).
    const hasTeamIds = panelEl.dataset.homeId && panelEl.dataset.awayId;
    const h2hTab = hasTeamIds
      ? `<button type="button" class="match-details-tab" data-tab="h2h">H2H</button>`
      : "";
    const h2hContent = hasTeamIds
      ? `<div class="match-details-content" data-tab="h2h" style="display:none">
           <p class="message">Click to load head-to-head.</p>
         </div>`
      : "";

    panelEl.innerHTML = `
      <div class="match-details-tabs">
        <button type="button" class="match-details-tab active" data-tab="lineups">Lineups</button>
        <button type="button" class="match-details-tab" data-tab="events">Events</button>
        ${h2hTab}
      </div>
      <div class="match-details-content" data-tab="lineups">
        <p class="message">Loading lineups…</p>
      </div>
      <div class="match-details-content" data-tab="events" style="display:none">
        <p class="message">Click to load events.</p>
      </div>
      ${h2hContent}
    `;

    // Tab switching — lazy loads each tab the first time it's opened.
    panelEl.querySelectorAll(".match-details-tab").forEach((tabBtn) => {
      tabBtn.addEventListener("click", () => {
        const targetTab = tabBtn.dataset.tab;
        panelEl.querySelectorAll(".match-details-tab").forEach((btn) =>
          btn.classList.toggle("active", btn.dataset.tab === targetTab),
        );
        panelEl.querySelectorAll(".match-details-content").forEach((contentEl) => {
          contentEl.style.display = contentEl.dataset.tab === targetTab ? "" : "none";
        });
        if (targetTab === "lineups") {
          _ensureLineupsLoaded(panelEl, matchId);
        } else if (targetTab === "events") {
          _ensureEventsLoaded(panelEl, matchId);
        } else if (targetTab === "h2h") {
          _ensureH2HLoaded(panelEl, matchId);
        }
      });
    });

    // Default tab is Lineups — kick off the fetch right away.
    _ensureLineupsLoaded(panelEl, matchId);
  }

  // ── H2H rendering ────────────────────────────────────────────────────────

  function _renderH2HSummary(summary, homeName, awayName) {
    const total = summary?.total || 0;
    if (!total) {
      return `<p class="message">No previous finished meetings on record.</p>`;
    }
    return `
      <div class="h2h-summary">
        <div class="h2h-summary-team">
          <span class="h2h-summary-count">${summary.home_wins}</span>
          <span class="h2h-summary-label">${PrimeScoreApp.escapeHtml(homeName || "Home")} wins</span>
        </div>
        <div class="h2h-summary-team h2h-summary-draws">
          <span class="h2h-summary-count">${summary.draws}</span>
          <span class="h2h-summary-label">Draws</span>
        </div>
        <div class="h2h-summary-team">
          <span class="h2h-summary-count">${summary.away_wins}</span>
          <span class="h2h-summary-label">${PrimeScoreApp.escapeHtml(awayName || "Away")} wins</span>
        </div>
      </div>
      <p class="subtitle h2h-total">From the last ${total} finished meetings</p>
    `;
  }

  function _renderH2HFixtureRow(fixture) {
    const dateStr = fixture.date
      ? new Date(fixture.date).toLocaleDateString()
      : "";
    const scoreStr =
      fixture.home_score != null && fixture.away_score != null
        ? `${fixture.home_score} : ${fixture.away_score}`
        : "vs";
    return `
      <li class="h2h-row">
        <span class="h2h-date">${PrimeScoreApp.escapeHtml(dateStr)}</span>
        <span class="h2h-comp">${PrimeScoreApp.escapeHtml(fixture.competition || "")}</span>
        <span class="h2h-teams">
          ${PrimeScoreApp.escapeHtml(fixture.home_team || "")}
          <strong class="h2h-score">${PrimeScoreApp.escapeHtml(scoreStr)}</strong>
          ${PrimeScoreApp.escapeHtml(fixture.away_team || "")}
        </span>
      </li>
    `;
  }

  async function _ensureH2HLoaded(panelEl, matchId) {
    const target = panelEl.querySelector('.match-details-content[data-tab="h2h"]');
    if (!target || target.dataset.loaded === "true") return;
    target.dataset.loaded = "true";

    const homeId = panelEl.dataset.homeId;
    const awayId = panelEl.dataset.awayId;
    const homeName = panelEl.dataset.homeName || "";
    const awayName = panelEl.dataset.awayName || "";

    if (!homeId || !awayId) {
      target.innerHTML = `<p class="message">Team identifiers unavailable — can't load head-to-head.</p>`;
      return;
    }

    target.innerHTML = `<p class="message">Loading head-to-head…</p>`;
    try {
      const url = `/api/matches/${matchId}/h2h?home_id=${encodeURIComponent(homeId)}&away_id=${encodeURIComponent(awayId)}`;
      const data = await PrimeScoreApp.apiFetch(url);
      const fixtures = data.fixtures || [];
      if (!fixtures.length) {
        target.innerHTML = `<p class="message">No previous meetings on record between these teams.</p>`;
        return;
      }
      target.innerHTML = `
        ${_renderH2HSummary(data.summary, homeName, awayName)}
        <ul class="h2h-list">${fixtures.map(_renderH2HFixtureRow).join("")}</ul>
      `;
    } catch (err) {
      console.warn("[h2h]", matchId, err);
      target.innerHTML = `<p class="message">Could not load head-to-head — try again shortly.</p>`;
      target.dataset.loaded = "false";
    }
  }

  async function _ensureLineupsLoaded(panelEl, matchId) {
    const target = panelEl.querySelector('.match-details-content[data-tab="lineups"]');
    if (!target || target.dataset.loaded === "true") return;
    target.dataset.loaded = "true";
    try {
      const data = await PrimeScoreApp.apiFetch(`/api/matches/${matchId}/lineups`);
      const home = data.home;
      const away = data.away;
      if (!home && !away) {
        target.innerHTML = `<p class="message">Lineups not yet available for this match.</p>`;
        target.dataset.loaded = "false"; // allow retry later when published
        return;
      }
      target.innerHTML = `
        <div class="formation-stack">
          ${_renderMiniPitch(home) || `<p class="message">Home lineup unavailable.</p>`}
          ${_renderMiniPitch(away) || `<p class="message">Away lineup unavailable.</p>`}
        </div>
      `;
    } catch (err) {
      console.warn("[lineups]", matchId, err);
      target.innerHTML = `<p class="message">Could not load lineups — try again shortly.</p>`;
      target.dataset.loaded = "false";
    }
  }

  async function _ensureEventsLoaded(panelEl, matchId) {
    const target = panelEl.querySelector('.match-details-content[data-tab="events"]');
    if (!target || target.dataset.loaded === "true") return;
    target.dataset.loaded = "true";
    target.innerHTML = `<p class="message">Loading match events…</p>`;
    try {
      const data = await PrimeScoreApp.apiFetch(`/api/matches/${matchId}/events`);
      const events = data.events || [];
      if (!events.length) {
        target.innerHTML = `<p class="message">No events recorded yet.</p>`;
      } else {
        target.innerHTML = `<ul class="event-list">${events.map(_renderEventRow).join("")}</ul>`;
      }
    } catch (err) {
      console.warn("[match events]", matchId, err);
      target.innerHTML = `<p class="message">Could not load events — try again shortly.</p>`;
      target.dataset.loaded = "false";
    }
  }

  // Open / close the details panel under a match card. First open builds
  // the tab scaffolding; subsequent toggles just show/hide.
  function _toggleMatchDetails(matchId, panelEl) {
    if (!panelEl) return;
    const isOpen = panelEl.dataset.open === "true";
    if (isOpen) {
      panelEl.style.display = "none";
      panelEl.dataset.open = "false";
      return;
    }

    panelEl.style.display = "block";
    panelEl.dataset.open = "true";

    if (panelEl.dataset.initialised !== "true") {
      panelEl.dataset.initialised = "true";
      _initialiseDetailsPanel(panelEl, matchId);
    }
  }

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
      .map((match, idx) => {
        const isLive = _isLiveMatch(match);
        const minute =
          isLive && match.minute != null
            ? `<span class="live-minute">${PrimeScoreApp.escapeHtml(String(match.minute))}'</span>`
            : "";
        const panelId = `${containerId}-details-${idx}`;
        // Pass team IDs + names through to the panel via data attributes so
        // the H2H tab can query the backend without an extra lookup.
        const homeIdAttr = match.home_team_id != null ? `data-home-id="${PrimeScoreApp.escapeHtml(String(match.home_team_id))}"` : "";
        const awayIdAttr = match.away_team_id != null ? `data-away-id="${PrimeScoreApp.escapeHtml(String(match.away_team_id))}"` : "";
        const homeNameAttr = match.home_team ? `data-home-name="${PrimeScoreApp.escapeHtml(match.home_team)}"` : "";
        const awayNameAttr = match.away_team ? `data-away-name="${PrimeScoreApp.escapeHtml(match.away_team)}"` : "";
        return `
          <div class="match-card${isLive ? " match-card-live" : ""}">
            <div class="teams">${PrimeScoreApp.escapeHtml(match.home_team)} vs ${PrimeScoreApp.escapeHtml(match.away_team)}</div>
            <div class="score">${match.home_score ?? "-"} : ${match.away_score ?? "-"} ${minute}</div>
            <div class="meta">${PrimeScoreApp.escapeHtml(match.competition || "")} - ${new Date(
              match.date || match.match_date || "",
            ).toLocaleString()}</div>
            ${match.status ? `<div class="status">${PrimeScoreApp.escapeHtml(match.status)}</div>` : ""}
            ${
              match.match_id
                ? `<button class="btn-secondary match-details-toggle" data-match-id="${match.match_id}" data-panel-id="${panelId}" type="button">View details</button>
                   <div id="${panelId}" class="match-details-panel" style="display:none" data-open="false" data-initialised="false" ${homeIdAttr} ${awayIdAttr} ${homeNameAttr} ${awayNameAttr}></div>`
                : ""
            }
          </div>
        `;
      })
      .join("");

    // Wire up the per-card details panel toggles (Lineups + Events tabs)
    container.querySelectorAll(".match-details-toggle").forEach((btn) => {
      btn.addEventListener("click", () => {
        const matchId = btn.dataset.matchId;
        const panel = document.getElementById(btn.dataset.panelId);
        _toggleMatchDetails(matchId, panel);
      });
    });
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

    const table = tables[0];
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
        `,
      )
      .join("");

    container.innerHTML = `
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
  }

  // ── Favourite card renderers ──────────────────────────────────────────────

  function renderFormDots(form) {
    return (form || "")
      .split("")
      .map((letter) => {
        const cls =
          letter === "W" ? "form-w" : letter === "L" ? "form-l" : "form-d";
        return `<span class="form-dot ${cls}">${letter}</span>`;
      })
      .join("");
  }

  function renderTeamStatCard(team) {
    const gd = team.goal_difference;
    const gdStr =
      gd != null ? (gd > 0 ? "+" + gd : String(gd)) : "-";

    return `
      <article class="card team-stat-card">
        <div class="section-header">
          <div>
            <h4>${PrimeScoreApp.escapeHtml(team.team_name || "Team")}</h4>
            <p class="subtitle">${PrimeScoreApp.escapeHtml(team.league_name || "")}${team.season ? ` &middot; ${team.season}` : ""}</p>
          </div>
          ${team.team_crest ? `<img src="${PrimeScoreApp.escapeHtml(team.team_crest)}" class="crest" alt="${PrimeScoreApp.escapeHtml(team.team_name || "")}" />` : ""}
        </div>
        <div class="stat-grid team-stat-grid">
          <div><strong>${team.position ?? "-"}</strong><span>Pos</span></div>
          <div><strong>${team.points ?? "-"}</strong><span>Pts</span></div>
          <div><strong>${team.played ?? "-"}</strong><span>Played</span></div>
          <div><strong>${team.won ?? "-"}</strong><span>Won</span></div>
          <div><strong>${team.drawn ?? "-"}</strong><span>Drawn</span></div>
          <div><strong>${team.lost ?? "-"}</strong><span>Lost</span></div>
          <div><strong>${team.goals_for ?? "-"}</strong><span>GF</span></div>
          <div><strong>${team.goals_against ?? "-"}</strong><span>GA</span></div>
          <div><strong>${gdStr}</strong><span>GD</span></div>
        </div>
        ${team.form ? `<p class="subtitle form-string">Form: ${renderFormDots(team.form)}</p>` : ""}
      </article>
    `;
  }

  function renderPlayerStatCard(player) {
    return `
      <article class="card player-stat-card">
        <div class="section-header">
          <div>
            <h4>${PrimeScoreApp.escapeHtml(player.player_name || "Player")}</h4>
            <p class="subtitle">${PrimeScoreApp.escapeHtml(player.current_team || "Unknown team")}${player.position ? ` - ${PrimeScoreApp.escapeHtml(player.position)}` : ""}</p>
          </div>
          ${player.photo ? `<img src="${PrimeScoreApp.escapeHtml(player.photo)}" class="crest player-photo" alt="${PrimeScoreApp.escapeHtml(player.player_name || "Player")}" />` : ""}
        </div>
        <div class="stat-grid">
          <div><strong>${player.statistics?.goals ?? 0}</strong><span>Goals</span></div>
          <div><strong>${player.statistics?.assists ?? 0}</strong><span>Assists</span></div>
          <div><strong>${player.statistics?.appearances ?? 0}</strong><span>Apps</span></div>
          <div><strong>${player.statistics?.minutes ?? 0}</strong><span>Minutes</span></div>
          <div><strong>${player.statistics?.yellow_cards ?? 0}</strong><span>Yellows</span></div>
          <div><strong>${player.statistics?.red_cards ?? 0}</strong><span>Reds</span></div>
        </div>
        ${player.statistics?.rating ? `<p class="subtitle">Rating: ${PrimeScoreApp.escapeHtml(player.statistics.rating)}</p>` : ""}
      </article>
    `;
  }

  function renderLeagueStatCard(league) {
    const rows = (league.top_teams || [])
      .map(
        (row) => `
        <tr>
          <td>${row.position}</td>
          <td>
            ${row.team_crest ? `<img src="${PrimeScoreApp.escapeHtml(row.team_crest)}" class="crest-xs" alt="" />` : ""}
            ${PrimeScoreApp.escapeHtml(row.team)}
          </td>
          <td>${row.played}</td>
          <td>${row.points}</td>
        </tr>
      `,
      )
      .join("");

    return `
      <article class="card league-stat-card">
        <div class="section-header">
          <div>
            <h4>${PrimeScoreApp.escapeHtml(league.league_name || "League")}</h4>
            <p class="subtitle">Season ${PrimeScoreApp.escapeHtml(league.season || "")}</p>
          </div>
          ${league.league_logo ? `<img src="${PrimeScoreApp.escapeHtml(league.league_logo)}" class="crest" alt="${PrimeScoreApp.escapeHtml(league.league_name || "")}" />` : ""}
        </div>
        <table class="mini-standings">
          <thead>
            <tr><th>#</th><th>Team</th><th>P</th><th>Pts</th></tr>
          </thead>
          <tbody>${rows}</tbody>
        </table>
      </article>
    `;
  }

  // ── Tab switching & card carousel ─────────────────────────────────────────

  function _getStatsForTab(which) {
    if (which === "teams") return PrimeScoreApp.state.favouriteTeamStats || [];
    if (which === "players") return PrimeScoreApp.state.favouritePlayerStats || [];
    if (which === "leagues") return PrimeScoreApp.state.favouriteLeagueStats || [];
    return [];
  }

  // Returns the full list of IDs/codes for the given tab so we know the true
  // total even before all stats are lazy-loaded.
  function _getIdsForTab(which) {
    const favs = PrimeScoreApp.state.favourites || {};
    if (which === "teams") return favs.favourite_team_ids || [];
    if (which === "players") return favs.favourite_player_ids || [];
    if (which === "leagues") return favs.favourite_league_codes || [];
    return [];
  }

  function _renderSummaryNav(index, total) {
    const prevBtn = PrimeScoreApp.getById("summaryPrev");
    const nextBtn = PrimeScoreApp.getById("summaryNext");
    const posLabel = PrimeScoreApp.getById("summaryPosition");
    const hasMany = total > 1;

    if (posLabel) {
      posLabel.textContent = total > 0 ? `${index + 1} of ${total}` : "";
    }
    if (prevBtn) prevBtn.disabled = !hasMany;
    if (nextBtn) nextBtn.disabled = !hasMany;
  }

  function _renderSummaryCard(which, index) {
    const stats = _getStatsForTab(which);
    const item = stats[index];
    if (!item) return "";
    if (which === "teams") return renderTeamStatCard(item);
    if (which === "players") return renderPlayerStatCard(item);
    if (which === "leagues") return renderLeagueStatCard(item);
    return "";
  }

  // Fetch a single stat card from the server and cache it in the state array.
  // Silently updates the DOM only if the user is still looking at the same slot.
  async function _lazyLoadStat(which, index) {
    const ids = _getIdsForTab(which);
    const id = ids[index];
    if (id == null) return;

    const typeMap = { teams: "team", players: "player", leagues: "league" };
    const url = `/api/favourite-stats?type=${typeMap[which]}&id=${encodeURIComponent(id)}`;

    try {
      const stat = await PrimeScoreApp.apiFetch(url);
      const stats = _getStatsForTab(which);
      stats[index] = stat;

      // Only repaint if the user hasn't navigated away while we were fetching
      if (
        PrimeScoreApp.state.summaryActiveTab === which &&
        (PrimeScoreApp.state.summaryIndex?.[which] ?? 0) === index
      ) {
        const content = PrimeScoreApp.getById("summaryContent");
        if (content) content.innerHTML = _renderSummaryCard(which, index);
      }
    } catch (err) {
      console.warn("[_lazyLoadStat] failed for", which, index, err);
      // Stat slot stays undefined so navigating away and back will retry automatically.
      // Update the DOM to show a useful error instead of a stuck "Loading…".
      if (
        PrimeScoreApp.state.summaryActiveTab === which &&
        (PrimeScoreApp.state.summaryIndex?.[which] ?? 0) === index
      ) {
        const content = PrimeScoreApp.getById("summaryContent");
        if (content)
          content.innerHTML = `<p class="message">Could not load stats right now — navigate away and back to retry.</p>`;
      }
    }
  }

  function showSummaryTab(which, event) {
    event?.preventDefault?.();

    // Mark the clicked tab active
    document.querySelectorAll(".summary-tab").forEach((button) => {
      button.classList.toggle(
        "active",
        button.textContent.toLowerCase().includes(which),
      );
    });

    // Remember which tab is open
    PrimeScoreApp.state.summaryActiveTab = which;

    // Ensure per-tab index tracking exists
    if (!PrimeScoreApp.state.summaryIndex) {
      PrimeScoreApp.state.summaryIndex = { teams: 0, players: 0, leagues: 0 };
    }

    const content = PrimeScoreApp.getById("summaryContent");
    if (!content) return;

    // Total comes from the IDs list (true count), not the sparse stats array
    const ids = _getIdsForTab(which);
    const total = ids.length;
    const stats = _getStatsForTab(which);

    if (!total) {
      content.innerHTML = `<p class="message">No favourite ${which} yet.</p>`;
      _renderSummaryNav(0, 0);
      return;
    }

    // Clamp saved index to valid range (handles tab switching after items change)
    const tabKey = which;
    PrimeScoreApp.state.summaryIndex[tabKey] = Math.min(
      Math.max(PrimeScoreApp.state.summaryIndex[tabKey] || 0, 0),
      total - 1,
    );

    const index = PrimeScoreApp.state.summaryIndex[tabKey];
    _renderSummaryNav(index, total);

    if (stats[index]) {
      content.innerHTML = _renderSummaryCard(which, index);
    } else {
      // Stat not yet loaded — show placeholder and kick off a lazy fetch
      content.innerHTML = `<p class="message">Loading ${which} stats…</p>`;
      _lazyLoadStat(which, index);
    }
  }

  async function cycleSummaryItem(direction) {
    const which = PrimeScoreApp.state.summaryActiveTab || "teams";
    const ids = _getIdsForTab(which);
    if (ids.length <= 1) return;

    if (!PrimeScoreApp.state.summaryIndex) {
      PrimeScoreApp.state.summaryIndex = { teams: 0, players: 0, leagues: 0 };
    }

    const current = PrimeScoreApp.state.summaryIndex[which] || 0;
    const nextIndex = (current + direction + ids.length) % ids.length;
    PrimeScoreApp.state.summaryIndex[which] = nextIndex;

    const stats = _getStatsForTab(which);
    const content = PrimeScoreApp.getById("summaryContent");

    _renderSummaryNav(nextIndex, ids.length);

    if (stats[nextIndex]) {
      // Already in cache — instant render
      if (content) content.innerHTML = _renderSummaryCard(which, nextIndex);
    } else {
      // Not yet loaded — show placeholder and fetch from backend
      if (content) content.innerHTML = `<p class="message">Loading…</p>`;
      await _lazyLoadStat(which, nextIndex);
    }
  }

  // ── League switcher ───────────────────────────────────────────────────────

  function renderHomeLeagueSwitcher(selectedLeague = null) {
    const leagueName = PrimeScoreApp.getById("homeLeagueName");
    const leaguePosition = PrimeScoreApp.getById("homeLeaguePosition");
    const previousButton = PrimeScoreApp.getById("homeLeaguePrev");
    const nextButton = PrimeScoreApp.getById("homeLeagueNext");
    const favouriteLeagues = PrimeScoreApp.state.favouriteLeagueOptions || [];

    const effectiveLeagueName =
      selectedLeague?.name ||
      PrimeScoreApp.state.homeLeagueName ||
      favouriteLeagues.find(
        (league) => league.code === PrimeScoreApp.state.homeLeagueCode,
      )?.name ||
      "Premier League";

    if (leagueName) {
      leagueName.textContent = effectiveLeagueName;
    }

    const currentIndex = favouriteLeagues.findIndex(
      (league) => league.code === PrimeScoreApp.state.homeLeagueCode,
    );
    const hasMultipleLeagues = favouriteLeagues.length > 1;

    if (leaguePosition) {
      if (!favouriteLeagues.length) {
        leaguePosition.textContent = "Default league";
      } else if (currentIndex >= 0) {
        leaguePosition.textContent = `League ${currentIndex + 1} of ${favouriteLeagues.length}`;
      } else {
        leaguePosition.textContent = "Favourite league";
      }
    }

    if (previousButton) {
      previousButton.disabled = !hasMultipleLeagues;
    }

    if (nextButton) {
      nextButton.disabled = !hasMultipleLeagues;
    }
  }

  // ── Data loading ──────────────────────────────────────────────────────────

  async function loadFavouritesSummary(options = {}) {
    try {
      const data = await PrimeScoreApp.apiFetch("/api/favourites");
      applyFavouriteState(data, options);

      // Pre-size each stat array to the user's full favourite count using a
      // sparse Array so the nav shows the correct "N of Total" immediately.
      // Index 0 of each may already be populated from the home-screen response;
      // all other slots stay undefined until the user navigates to them.
      const presizeStats = (existing, count) => {
        const arr = new Array(count);
        (existing || []).forEach((item, i) => {
          if (item != null) arr[i] = item;
        });
        return arr;
      };
      PrimeScoreApp.state.favouriteTeamStats = presizeStats(
        PrimeScoreApp.state.favouriteTeamStats,
        (data.favourite_team_ids || []).length,
      );
      PrimeScoreApp.state.favouritePlayerStats = presizeStats(
        PrimeScoreApp.state.favouritePlayerStats,
        (data.favourite_player_ids || []).length,
      );
      PrimeScoreApp.state.favouriteLeagueStats = presizeStats(
        PrimeScoreApp.state.favouriteLeagueStats,
        (data.favourite_league_codes || []).length,
      );

      PrimeScoreApp.getById("teamsCount")?.replaceChildren(
        document.createTextNode(
          String(PrimeScoreApp.state.favourites.favourite_teams.length),
        ),
      );
      PrimeScoreApp.getById("playersCount")?.replaceChildren(
        document.createTextNode(
          String(PrimeScoreApp.state.favourites.favourite_players.length),
        ),
      );
      PrimeScoreApp.getById("leaguesCount")?.replaceChildren(
        document.createTextNode(
          String(PrimeScoreApp.state.favourites.favourite_leagues.length),
        ),
      );

      PrimeScoreApp.showSummaryTab?.("teams");
      renderHomeLeagueSwitcher(options.selectedLeague);
    } catch (error) {
      console.error("[loadFavouritesSummary]", error);
    }
  }

  async function loadHome(forceReload = false, preferredLeagueCode = null) {
    if (!forceReload && PrimeScoreApp.state.homeRequestPromise) {
      return PrimeScoreApp.state.homeRequestPromise;
    }

    PrimeScoreApp.state.homeRequestPromise = (async () => {
      try {
        const leagueCode =
          preferredLeagueCode || PrimeScoreApp.state.homeLeagueCode || "";
        const mode = PrimeScoreApp.state.matchFeedMode || "all";
        const params = new URLSearchParams();
        if (leagueCode) params.set("league", leagueCode);
        params.set("mode", mode);
        const url = `/api/home-screen?${params.toString()}`;
        const data = await PrimeScoreApp.apiFetch(url);

        if (data.selected_league?.code) {
          PrimeScoreApp.state.homeLeagueCode = String(
            data.selected_league.code,
          );
          PrimeScoreApp.state.homeLeagueName = data.selected_league.name || "";
        }

        // Store all favourite stats in state before tabs render
        PrimeScoreApp.state.favouriteTeamStats =
          data.favourite_team_stats || [];
        PrimeScoreApp.state.favouritePlayerStats =
          data.favourite_player_stats || [];
        PrimeScoreApp.state.favouriteLeagueStats =
          data.favourite_league_stats || [];

        renderMatchCards(
          data.live_matches || [],
          "liveMatchesHome",
          "No live matches right now.",
        );
        renderMatchCards(
          data.upcoming_fixtures || [],
          "upcomingFixturesHome",
          "No upcoming fixtures.",
        );
        renderMatchCards(
          data.recent_results || [],
          "recentResultsHome",
          "No recent results.",
        );
        renderLeagueTables(data.league_tables || [], "leagueTablesHome");
        await loadFavouritesSummary({ selectedLeague: data.selected_league });
      } catch (error) {
        console.error("[loadHome]", error);
      } finally {
        PrimeScoreApp.state.homeRequestPromise = null;
      }
    })();

    return PrimeScoreApp.state.homeRequestPromise;
  }

  async function setMatchFeedMode(mode) {
    PrimeScoreApp.state.matchFeedMode = mode;
    const allBtn = PrimeScoreApp.getById("toggleAllMatches");
    const myBtn = PrimeScoreApp.getById("toggleMyTeams");
    if (allBtn) allBtn.classList.toggle("active", mode === "all");
    if (myBtn) myBtn.classList.toggle("active", mode === "my_teams");
    await loadHome(true);
  }

  async function cycleHomeLeague(direction) {
    const favouriteLeagues = PrimeScoreApp.state.favouriteLeagueOptions || [];
    if (favouriteLeagues.length < 2) {
      return;
    }

    const currentIndex = favouriteLeagues.findIndex(
      (league) => league.code === PrimeScoreApp.state.homeLeagueCode,
    );
    const safeIndex =
      currentIndex >= 0 ? currentIndex : favouriteLeagues.length - 1;
    const nextIndex =
      (safeIndex + direction + favouriteLeagues.length) %
      favouriteLeagues.length;
    const nextLeague = favouriteLeagues[nextIndex];

    PrimeScoreApp.state.homeLeagueCode = nextLeague.code;
    PrimeScoreApp.state.homeLeagueName = nextLeague.name;
    renderHomeLeagueSwitcher(nextLeague);
    await loadHome(true, nextLeague.code);
  }

  PrimeScoreApp.showSummaryTab = showSummaryTab;
  PrimeScoreApp.cycleSummaryItem = cycleSummaryItem;
  PrimeScoreApp.loadHome = loadHome;
  PrimeScoreApp.renderMatchCards = renderMatchCards;
  PrimeScoreApp.renderLeagueTables = renderLeagueTables;
  PrimeScoreApp.loadFavouritesSummary = loadFavouritesSummary;
  PrimeScoreApp.cycleHomeLeague = cycleHomeLeague;
  PrimeScoreApp.setMatchFeedMode = setMatchFeedMode;
})(window.PrimeScoreApp);
