(function (PrimeScoreApp) {
  async function loadSettings() {
    try {
      const data = await PrimeScoreApp.apiFetch("/api/notifications/settings");
      const map = {
        goals_notifications: "goalsNotifications",
        match_start_notifications: "matchStartNotifications",
        match_end_notifications: "matchEndNotifications",
        favourite_team_notifications: "favTeamNotifications",
        favourite_player_notifications: "favPlayerNotifications",
      };
      Object.entries(map).forEach(([apiKey, domId]) => {
        const el = PrimeScoreApp.getById(domId);
        if (el) el.checked = !!data[apiKey];
      });
    } catch (err) {
      PrimeScoreApp.showMessage("settingsMessage", err.message || "Could not load settings");
    }
  }

  async function saveSettings(e) {
    e?.preventDefault();
    try {
      const payload = {
        goals_notifications: PrimeScoreApp.getById("goalsNotifications")?.checked || false,
        match_start_notifications: PrimeScoreApp.getById("matchStartNotifications")?.checked || false,
        match_end_notifications: PrimeScoreApp.getById("matchEndNotifications")?.checked || false,
        favourite_team_notifications: PrimeScoreApp.getById("favTeamNotifications")?.checked || false,
        favourite_player_notifications: PrimeScoreApp.getById("favPlayerNotifications")?.checked || false,
      };
      await PrimeScoreApp.apiFetch("/api/notifications/settings", { method: "POST", body: JSON.stringify(payload) });
      PrimeScoreApp.showMessage("settingsMessage", "Saved", false);
    } catch (err) {
      PrimeScoreApp.showMessage("settingsMessage", err.message || "Could not save settings");
    }
  }

  PrimeScoreApp.loadSettings = loadSettings;
  PrimeScoreApp.saveSettings = saveSettings;
})(window.PrimeScoreApp);
