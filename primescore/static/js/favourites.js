(function (PrimeScoreApp) {
  const LEGACY_LEAGUE_NAMES = {
    PL: "Premier League",
    CL: "UEFA Champions League",
    BL1: "Bundesliga",
    SA: "Serie A",
    PD: "La Liga",
    FL1: "Ligue 1",
    ELC: "Championship",
    EL: "UEFA Europa League",
    WC: "FIFA World Cup",
    EC: "UEFA European Championship",
  };

  const editState = {
    teams: [],
    players: [],
    leagues: [],
  };

  const LIMITS = { teams: 5, players: 10, leagues: 3 };

  function cap(str) {
    return str.charAt(0).toUpperCase() + str.slice(1);
  }

  function renderTags(type) {
    const container = PrimeScoreApp.getById(`fav${cap(type)}Tags`);
    if (!container) return;

    if (!editState[type].length) {
      container.innerHTML = "";
      return;
    }

    container.innerHTML = editState[type]
      .map(
        (item) =>
          `<span class="fav-tag">
            ${item.crest ? `<img src="${PrimeScoreApp.escapeHtml(item.crest)}" class="fav-tag-crest" alt="">` : ""}
            <span class="fav-tag-name">${PrimeScoreApp.escapeHtml(item.name)}</span>
            <button class="fav-tag-remove" data-type="${PrimeScoreApp.escapeHtml(type)}" data-id="${PrimeScoreApp.escapeHtml(String(item.id))}" aria-label="Remove">×</button>
          </span>`,
      )
      .join("");

    container.querySelectorAll(".fav-tag-remove").forEach((btn) => {
      btn.addEventListener("click", () =>
        removeFavItem(btn.dataset.type, btn.dataset.id),
      );
    });
  }

  function addFavItem(type, item) {
    if (editState[type].some((i) => String(i.id) === String(item.id))) return;
    if (editState[type].length >= LIMITS[type]) {
      PrimeScoreApp.showMessage(
        "favMsg",
        `Maximum ${LIMITS[type]} ${type} allowed.`,
      );
      return;
    }
    editState[type].push(item);
    renderTags(type);
  }

  function removeFavItem(type, id) {
    editState[type] = editState[type].filter(
      (i) => String(i.id) !== String(id),
    );
    renderTags(type);
  }

  // --- Dropdown helpers ---
  function showSuggestions(suggestionsId, inputId, items, onSelect) {
    const container = PrimeScoreApp.getById(suggestionsId);
    if (!container) return;

    if (!items.length) {
      container.innerHTML = `<div class="suggestion-empty">No results found.</div>`;
      container.style.display = "block";
      return;
    }

    container.innerHTML = items
      .map(
        (item) =>
          `<div class="suggestion-item" data-id="${PrimeScoreApp.escapeHtml(String(item.id))}">
            ${item.crest ? `<img src="${PrimeScoreApp.escapeHtml(item.crest)}" class="suggestion-crest" alt="">` : ""}
            <span class="suggestion-name">${PrimeScoreApp.escapeHtml(item.name)}</span>
            ${item.subtitle ? `<span class="suggestion-sub">${PrimeScoreApp.escapeHtml(item.subtitle)}</span>` : ""}
          </div>`,
      )
      .join("");

    container.style.display = "block";

    container.querySelectorAll(".suggestion-item").forEach((el) => {
      el.addEventListener("mousedown", (e) => {
        e.preventDefault();
        const id = el.dataset.id;
        const item = items.find((i) => String(i.id) === String(id));
        if (item) onSelect(item);
        container.style.display = "none";
        const input = PrimeScoreApp.getById(inputId);
        if (input) input.value = "";
      });
    });
  }

  function hideSuggestions(id) {
    const el = PrimeScoreApp.getById(id);
    if (el) el.style.display = "none";
  }

  async function loadSquadForTeam(team) {
    const squadPanel = PrimeScoreApp.getById("favPlayersSquad");
    const squadLabel = PrimeScoreApp.getById("favPlayersSquadLabel");
    const squadList = PrimeScoreApp.getById("favPlayersSquadList");
    if (!squadPanel || !squadLabel || !squadList) return;

    squadLabel.textContent = `${team.name} — loading squad…`;
    squadList.innerHTML = "";
    squadPanel.style.display = "block";

    try {
      const data = await PrimeScoreApp.apiFetch(
        `/api/teams/${encodeURIComponent(team.id)}/players`,
      );
      const players = data.players || [];

      if (!players.length) {
        squadList.innerHTML = `<p class="suggestion-empty">No squad data available for this team.</p>`;
        return;
      }

      squadLabel.textContent = `${team.name} — click a player to add:`;

      const grouped = {};
      players.forEach((p) => {
        const pos = p.position || "Other";
        (grouped[pos] = grouped[pos] || []).push(p);
      });

      const posOrder = [
        "Goalkeeper",
        "Defender",
        "Midfielder",
        "Attacker",
        "Other",
      ];
      const sortedPositions = [
        ...posOrder.filter((p) => grouped[p]),
        ...Object.keys(grouped).filter((p) => !posOrder.includes(p)),
      ];

      squadList.innerHTML = sortedPositions
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

      squadList.querySelectorAll(".squad-player-btn").forEach((btn) => {
        btn.addEventListener("click", () => {
          addFavItem("players", { id: btn.dataset.id, name: btn.dataset.name });
          // Highlight if already added
          btn.classList.toggle(
            "squad-player-added",
            editState.players.some(
              (p) => String(p.id) === String(btn.dataset.id),
            ),
          );
        });
      });
    } catch {
      squadList.innerHTML = `<p class="suggestion-empty">Could not load squad.</p>`;
    }
  }

  const searchTeams = PrimeScoreApp.debounce(async function (query) {
    if (query.length < 3) {
      hideSuggestions("favTeamsSuggestions");
      return;
    }
    try {
      const data = await PrimeScoreApp.apiFetch(
        `/api/search?q=${encodeURIComponent(query)}&type=teams`,
      );
      const items = (data.teams || []).map((t) => ({
        id: t.id,
        name: t.name,
        crest: t.crest,
      }));
      showSuggestions("favTeamsSuggestions", "favTeamsSearch", items, (item) =>
        addFavItem("teams", item),
      );
    } catch {
      hideSuggestions("favTeamsSuggestions");
    }
  }, 300);

  const searchPlayersTeam = PrimeScoreApp.debounce(async function (query) {
    if (query.length < 3) {
      hideSuggestions("favPlayersTeamSuggestions");
      return;
    }
    try {
      const data = await PrimeScoreApp.apiFetch(
        `/api/search?q=${encodeURIComponent(query)}&type=teams`,
      );
      const items = (data.teams || []).map((t) => ({
        id: t.id,
        name: t.name,
        crest: t.crest,
      }));
      showSuggestions(
        "favPlayersTeamSuggestions",
        "favPlayersTeamSearch",
        items,
        (team) => {
          loadSquadForTeam(team);
        },
      );
    } catch {
      hideSuggestions("favPlayersTeamSuggestions");
    }
  }, 300);

  const searchLeagues = PrimeScoreApp.debounce(async function (query) {
    if (query.length < 3) {
      hideSuggestions("favLeaguesSuggestions");
      return;
    }
    try {
      const data = await PrimeScoreApp.apiFetch(
        `/api/search?q=${encodeURIComponent(query)}&type=competitions`,
      );
      const items = (data.competitions || []).map((l) => ({
        id: l.id,
        name: l.name,
      }));
      showSuggestions(
        "favLeaguesSuggestions",
        "favLeaguesSearch",
        items,
        (item) => addFavItem("leagues", item),
      );
    } catch {
      hideSuggestions("favLeaguesSuggestions");
    }
  }, 300);

  function wireSearchInputs() {
    const configs = [
      {
        inputId: "favTeamsSearch",
        suggestionsId: "favTeamsSuggestions",
        handler: searchTeams,
      },
      {
        inputId: "favPlayersTeamSearch",
        suggestionsId: "favPlayersTeamSuggestions",
        handler: searchPlayersTeam,
      },
      {
        inputId: "favLeaguesSearch",
        suggestionsId: "favLeaguesSuggestions",
        handler: searchLeagues,
      },
    ];

    configs.forEach(({ inputId, suggestionsId, handler }) => {
      const input = PrimeScoreApp.getById(inputId);
      if (!input) return;
      input.addEventListener("input", (e) => handler(e.target.value.trim()));
      input.addEventListener("blur", () =>
        setTimeout(() => hideSuggestions(suggestionsId), 150),
      );
    });
  }

  async function resolveTeam(id) {
    try {
      const data = await PrimeScoreApp.apiFetch(
        `/api/resolve/team-by-id?id=${encodeURIComponent(id)}`,
      );
      return {
        id: data.id ?? id,
        name: data.name || `Team ${id}`,
        crest: data.crest,
      };
    } catch {
      return { id, name: `Team ${id}` };
    }
  }

  async function resolvePlayer(id) {
    try {
      const data = await PrimeScoreApp.apiFetch(
        `/api/resolve/player-by-id?id=${encodeURIComponent(id)}`,
      );
      return { id: data.id ?? id, name: data.name || `Player ${id}` };
    } catch {
      return { id, name: `Player ${id}` };
    }
  }

  async function resolveLeague(idOrCode) {
    if (LEGACY_LEAGUE_NAMES[idOrCode]) {
      return { id: idOrCode, name: LEGACY_LEAGUE_NAMES[idOrCode] };
    }
    try {
      const data = await PrimeScoreApp.apiFetch(
        `/api/resolve/league-by-id?id=${encodeURIComponent(idOrCode)}`,
      );
      return {
        id: data.id ?? idOrCode,
        name: data.name || `League ${idOrCode}`,
      };
    } catch {
      return { id: idOrCode, name: `League ${idOrCode}` };
    }
  }

  function renderFavouriteList(items, containerId) {
    const container = PrimeScoreApp.getById(containerId);
    if (!container) return;

    if (!items.length) {
      container.innerHTML = '<p class="message">None saved.</p>';
      return;
    }

    container.innerHTML = `
      <ul class="list">
        ${items
          .map((item) => {
            const name = typeof item === "object" ? item.name : item;
            const crest = typeof item === "object" ? item.crest : null;
            return `<li>
              ${crest ? `<img src="${PrimeScoreApp.escapeHtml(crest)}" style="width:20px;height:20px;object-fit:contain;vertical-align:middle;margin-right:6px;" alt="">` : ""}
              ${PrimeScoreApp.escapeHtml(String(name))}
            </li>`;
          })
          .join("")}
      </ul>`;
  }

  function renderFavourites() {
    renderFavouriteList(editState.teams, "favTeamsList");
    renderFavouriteList(editState.players, "favPlayersList");
    renderFavouriteList(editState.leagues, "favLeaguesList");
  }

  // --- Load ---
  async function loadFavourites() {
    try {
      const data = await PrimeScoreApp.apiFetch("/api/favourites");
      const teamIds = (data.favourite_teams || []).map(String);
      const playerIds = (data.favourite_players || []).map(String);
      const leagueIds = (data.favourite_leagues || []).map(String);

      const [teams, players, leagues] = await Promise.all([
        Promise.all(teamIds.map(resolveTeam)),
        Promise.all(playerIds.map(resolvePlayer)),
        Promise.all(leagueIds.map(resolveLeague)),
      ]);

      editState.teams = teams;
      editState.players = players;
      editState.leagues = leagues;

      renderFavourites();
      renderTags("teams");
      renderTags("players");
      renderTags("leagues");
      wireSearchInputs();
    } catch (error) {
      PrimeScoreApp.showMessage(
        "favMsg",
        error.message || "Could not load favourites.",
      );
    }
  }

  async function saveFavourites(event) {
    event?.preventDefault();

    const payload = {
      favourite_teams: editState.teams.map((i) => parseInt(i.id, 10)),
      favourite_players: editState.players.map((i) => parseInt(i.id, 10)),
      favourite_leagues: editState.leagues.map((i) => String(i.id)),
    };

    try {
      await PrimeScoreApp.apiFetch("/api/favourites", {
        method: "POST",
        body: JSON.stringify(payload),
      });

      renderFavourites();
      PrimeScoreApp.showMessage("favMsg", "Favourites saved.", false);
      PrimeScoreApp.loadFavouritesSummary?.();
    } catch (error) {
      PrimeScoreApp.showMessage(
        "favMsg",
        error.message || "Could not save favourites.",
      );
    }
  }

  PrimeScoreApp.loadFavourites = loadFavourites;
  PrimeScoreApp.renderFavourites = renderFavourites;
  PrimeScoreApp.saveFavourites = saveFavourites;
  PrimeScoreApp.removeFavItem = removeFavItem;
})(window.PrimeScoreApp);
