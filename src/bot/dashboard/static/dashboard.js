(function () {
  const root = document.documentElement;
  const saved = localStorage.getItem("dashboard.theme");
  const initial = saved || (window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
  root.setAttribute("data-theme", initial);

  document.addEventListener("click", function (e) {
    const btn = e.target.closest("[data-theme-toggle]");
    if (!btn) return;
    const next = root.getAttribute("data-theme") === "dark" ? "light" : "dark";
    root.setAttribute("data-theme", next);
    localStorage.setItem("dashboard.theme", next);
    window.dispatchEvent(new CustomEvent("dashboard:themechange", { detail: { theme: next } }));
  });

  const REFRESH_MS = 15000;
  const refreshKey = "dashboard.autoRefresh";
  let refreshTimer = null;
  const refreshBtn = document.querySelector("[data-auto-refresh-toggle]");

  function setRefreshUi(on) {
    document.body.setAttribute("data-auto-refresh", on ? "on" : "off");
    if (refreshBtn) refreshBtn.classList.toggle("active", !!on);
  }

  function refreshOnce() {
    const hasRefreshTargets = document.querySelector("[data-refresh]");
    if (hasRefreshTargets) {
      window.location.reload();
      return;
    }
    if (window.dashboardCharts) window.dashboardCharts.renderAll();
  }

  function startRefresh() {
    stopRefresh();
    refreshTimer = setInterval(refreshOnce, REFRESH_MS);
  }
  function stopRefresh() {
    if (refreshTimer) clearInterval(refreshTimer);
    refreshTimer = null;
  }

  if (refreshBtn) {
    refreshBtn.addEventListener("click", function () {
      const next = document.body.getAttribute("data-auto-refresh") !== "on";
      setRefreshUi(next);
      localStorage.setItem(refreshKey, next ? "on" : "off");
      if (next) startRefresh(); else stopRefresh();
    });
  }

  const savedRefresh = localStorage.getItem(refreshKey);
  if (savedRefresh === "on") {
    setRefreshUi(true);
    startRefresh();
  } else {
    setRefreshUi(false);
  }

  document.addEventListener("visibilitychange", function () {
    if (document.visibilityState === "hidden") stopRefresh();
    else if (document.body.getAttribute("data-auto-refresh") === "on") startRefresh();
  });

  window.confirmTyped = function (form, expected) {
    const input = form.querySelector('input[name="confirm"]');
    if (!input || input.value !== expected) {
      alert("Type " + expected + " to confirm.");
      return false;
    }
    return true;
  };

  function serializeForm(form) {
    const fd = new FormData(form);
    const params = new URLSearchParams();
    for (const [k, v] of fd.entries()) {
      params.append(k, v);
    }
    return params;
  }

  const settingsForm = document.getElementById("settings-form");
  if (settingsForm) {
    const out = document.getElementById("preview-output");
    document.getElementById("preview-btn").addEventListener("click", async function () {
      out.textContent = "Loading...";
      try {
        const res = await fetch("/settings/preview", { method: "POST", body: serializeForm(settingsForm) });
        const data = await res.json();
        if (!res.ok) {
          out.textContent = "Error: " + (data.error || res.status);
          return;
        }
        out.textContent = "# bot.yaml\n" + data.bot_yaml + "\n# symbols.yaml\n" + data.symbols_yaml;
      } catch (err) {
        out.textContent = "Error: " + err;
      }
    });
    settingsForm.addEventListener("submit", async function (e) {
      e.preventDefault();
      const confirmInput = settingsForm.querySelector('input[name="confirm"]');
      if (!confirmInput || confirmInput.value !== "SAVE") {
        alert("Type SAVE to confirm.");
        return;
      }
      const res = await fetch("/settings/save", { method: "POST", body: serializeForm(settingsForm) });
      if (res.redirected) {
        window.location.href = res.url;
      } else if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        out.textContent = "Save failed: " + (data.detail || res.status);
      } else {
        window.location.reload();
      }
    });
  }

  const backtestForm = document.getElementById("backtest-form");
  if (backtestForm) {
    const out = document.getElementById("backtest-output");
    backtestForm.addEventListener("submit", async function (e) {
      e.preventDefault();
      out.textContent = "Starting backtest...";
      try {
        const fd = new FormData(backtestForm);
        const res = await fetch("/backtests/run", { method: "POST", body: fd });
        const data = await res.json();
        if (!res.ok) {
          out.textContent = "Error: " + (data.detail || res.status);
          return;
        }
        out.textContent = "Started ts=" + data.ts + " pid=" + data.pid
          + "\nLog: " + data.log + "\nReport (when done): " + data.report
          + "\nCommand:\n  " + (data.cmd || []).join(" ");
        refreshJobs();
      } catch (err) {
        out.textContent = "Error: " + err;
      }
    });
  }

  function escapeHtml(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  }

  async function refreshJobs() {
    const table = document.getElementById("backtest-jobs");
    if (!table) return;
    try {
      const res = await fetch("/api/backtests");
      if (!res.ok) return;
      const data = await res.json();
      const tbody = table.querySelector("tbody");
      tbody.innerHTML = (data.jobs || []).map(j => {
        const reportCell = j.report_path
          ? `<a href="/backtests?report=${encodeURIComponent(j.report_path)}">view</a>`
          : `<span class="subtle">pending</span>`;
        const duration = j.duration_s ? j.duration_s.toFixed(1) + "s" : "";
        const symbols = (j.symbols || []).join(", ");
        return `<tr data-job-ts="${escapeHtml(j.ts)}" data-status="${escapeHtml(j.status)}">
          <td>${escapeHtml(j.started_at_utc || "")}</td>
          <td><span class="pill status-${escapeHtml(j.status)}">${escapeHtml(j.status)}</span></td>
          <td>${escapeHtml(j.signal || "")}</td>
          <td>${escapeHtml(symbols)}</td>
          <td>${escapeHtml(j.start || "")} → ${escapeHtml(j.end || "")}</td>
          <td>${escapeHtml(j.initial_equity || "")}</td>
          <td>${escapeHtml(duration)}</td>
          <td>${reportCell}</td>
        </tr>`;
      }).join("");
    } catch (err) {
      console.warn("refresh jobs failed", err);
    }
  }

  if (document.getElementById("backtest-jobs")) {
    setInterval(refreshJobs, 3000);
  }
})();
