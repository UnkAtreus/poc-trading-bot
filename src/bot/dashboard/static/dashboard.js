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
        out.textContent = "# " + (data.config_dir || "config") + "\n# bot.yaml\n" + data.bot_yaml + "\n# symbols.yaml\n" + data.symbols_yaml;
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

  const secretsForm = document.getElementById("secrets-form");
  const testOutput = document.getElementById("alert-test-output");
  if (secretsForm && testOutput) {
    secretsForm.querySelectorAll("button[data-test-channel]").forEach(function (btn) {
      btn.addEventListener("click", async function () {
        const channel = btn.getAttribute("data-test-channel");
        const params = new URLSearchParams();
        params.append("channel", channel);
        const fields = ["telegram_bot_token", "telegram_chat_id", "discord_webhook_url"];
        fields.forEach(function (name) {
          const input = secretsForm.querySelector('input[name="' + name + '"]');
          if (input) params.append(name, input.value);
        });
        testOutput.hidden = false;
        testOutput.textContent = "Sending test to " + channel + "...";
        btn.disabled = true;
        try {
          const res = await fetch("/alerting/test", { method: "POST", body: params });
          let data = {};
          try { data = await res.json(); } catch (_) {}
          const ok = data.ok === true;
          const status = data.status_code === null || data.status_code === undefined ? "-" : data.status_code;
          const detail = data.detail || (ok ? "delivered" : "no detail");
          testOutput.textContent = (ok ? "OK" : "FAIL") + " [" + channel + "] status=" + status + " — " + detail;
        } catch (err) {
          testOutput.textContent = "FAIL [" + channel + "] — " + err;
        } finally {
          btn.disabled = false;
        }
      });
    });
  }

  function applyBacktestPrefill(form) {
    const PREFILL_STORAGE_KEY = "backtest_prefill";
    let prefill = null;

    // Preferred path: sessionStorage. Marker query is just ?prefill=1.
    try {
      const stored = sessionStorage.getItem(PREFILL_STORAGE_KEY);
      if (stored) {
        prefill = JSON.parse(stored);
        sessionStorage.removeItem(PREFILL_STORAGE_KEY);
      }
    } catch (err) {
      console.warn("backtest prefill (sessionStorage) failed", err);
    }

    // Backwards-compatible fallback: legacy ?prefill=<base64>.
    if (!prefill) {
      try {
        let raw = new URLSearchParams(window.location.search).get("prefill");
        if (raw && raw !== "1") {
          raw = raw.replace(/ /g, "+");
          prefill = JSON.parse(decodeURIComponent(atob(raw)));
        }
      } catch (err) {
        console.warn("backtest prefill (legacy URL) failed", err);
        return;
      }
    }
    if (!prefill || typeof prefill !== "object") return;

    const filledFields = [];

    function setField(name, value) {
      if (value === null || value === undefined || value === "") return;
      const el = form.querySelector(`[name="${name}"]`);
      if (!el) return;
      el.value = value;
      el.classList.add("prefilled");
      filledFields.push(name);
    }
    setField("start", prefill.start);
    setField("end", prefill.end);
    setField("initial_equity", prefill.initial_equity);
    setField("signal_engine", prefill.signal_engine);
    setField("signal_params", prefill.signal_params);
    setField("margin_usd", prefill.margin_usd);
    setField("leverage", prefill.leverage);
    setField("tp_offset_bps", prefill.tp_offset_bps);
    setField("max_notional_account", prefill.max_notional_account);
    setField("max_notional_per_symbol", prefill.max_notional_per_symbol);
    setField("daily_loss_limit", prefill.daily_loss_limit);

    if (Array.isArray(prefill.symbols) && prefill.symbols.length) {
      const wanted = new Set(prefill.symbols.map(s => String(s).toUpperCase()));
      const matched = new Set();
      form.querySelectorAll('input[name="symbols_picked"]').forEach(cb => {
        const isWanted = wanted.has(String(cb.value).toUpperCase());
        cb.checked = isWanted;
        const wrapper = cb.closest("label");
        if (wrapper) wrapper.classList.toggle("prefilled", isWanted);
        if (isWanted) matched.add(String(cb.value).toUpperCase());
      });
      const extra = prefill.symbols.filter(s => !matched.has(String(s).toUpperCase()));
      if (extra.length) setField("symbols_extra", extra.join(","));
      filledFields.push(`${wanted.size} symbols`);
    }

    // Sticky banner showing prefill metadata and a clear button.
    const banner = document.createElement("div");
    banner.className = "prefill-banner";
    banner.innerHTML = `
      <div class="prefill-banner-text">
        <strong>Prefilled from strategy:</strong>
        <code>${escapeHtml(prefill._strategy_label || "(unknown)")}</code>
        <span class="subtle prefill-banner-meta">${filledFields.length} fields populated · review before starting</span>
      </div>
      <button type="button" class="btn-outline" data-prefill-clear>Clear prefill</button>
    `;
    form.parentNode.insertBefore(banner, form);
    banner.querySelector("[data-prefill-clear]").addEventListener("click", () => {
      form.querySelectorAll(".prefilled").forEach(el => el.classList.remove("prefilled"));
      form.reset();
      banner.remove();
    });
  }

  // Hand-maintained guide — keep in sync with src/bot/signals/*.py.
  // Declared BEFORE the backtest-form wiring below because renderSignalGuide()
  // references it at attach time; reordering avoids a temporal-dead-zone
  // ReferenceError that silently aborted wireBacktestExtras (and thus the
  // quick-range / notional / symbol-toolbar wiring).
  const SIGNAL_GUIDE = {
    bollinger_bands: {
      summary: "Mean reversion. Long below the lower band, short above the upper band.",
      defaults: "period=20:num_std=2.0",
      params: [
        { k: "period", desc: "moving-average window length (bars)" },
        { k: "num_std", desc: "band width in standard deviations" },
      ],
    },
    zscore: {
      summary: "Mean reversion. Long when z-score < -threshold, short when > +threshold.",
      defaults: "period=50:threshold=2.0",
      params: [
        { k: "period", desc: "rolling window for the z-score" },
        { k: "threshold", desc: "absolute z-score that triggers entry" },
      ],
    },
    grid: {
      summary: "Anchored grid. Fires every grid step from an SMA anchor — bidirectional.",
      defaults: "anchor_period=200:entry_bps=50:step_bps=30",
      params: [
        { k: "anchor_period", desc: "SMA window for the anchor price" },
        { k: "entry_bps", desc: "distance from anchor for the first entry (bps)" },
        { k: "step_bps", desc: "spacing between successive grid entries (bps)" },
      ],
    },
    ema_crossover: {
      summary: "Trend follower. Long on fast > slow EMA crossover, short on the inverse. Warning: bleeds with merge-at-BEP.",
      defaults: "fast=9:slow=21",
      params: [
        { k: "fast", desc: "fast EMA length" },
        { k: "slow", desc: "slow EMA length" },
      ],
    },
    trend_filter: {
      summary: "Wraps another engine and suppresses signals in strong trends. Inner params take an inner_ prefix.",
      defaults: "inner=bollinger_bands:inner_period=20:inner_num_std=2.0:max_trend_bps=30",
      params: [
        { k: "inner", desc: "inner engine name (bollinger_bands, grid, zscore...)" },
        { k: "ema_fast", desc: "fast EMA length used to measure trend (default 30)" },
        { k: "ema_slow", desc: "slow EMA length used to measure trend (default 120)" },
        { k: "max_trend_bps", desc: "max |fast-slow| in bps before signals are suppressed" },
        { k: "inner_*", desc: "forward params to the inner engine (e.g. inner_entry_bps=50)" },
      ],
    },
    regime_gate: {
      summary: "Wraps another engine and pauses or reduces signals when benchmark EMA spread or ADX shows strong trend.",
      defaults: "inner=trend_filter:inner_inner=grid:inner_inner_anchor_period=200:inner_inner_entry_bps=50:inner_inner_step_bps=25:inner_max_trend_bps=20:max_ema_spread_bps=25:max_adx=25:unsafe_action=pause",
      params: [
        { k: "inner", desc: "inner engine name, commonly trend_filter or grid" },
        { k: "scope", desc: "benchmark (BTC gate for all symbols) or symbol" },
        { k: "benchmark_symbol", desc: "symbol used for market regime when scope=benchmark" },
        { k: "max_ema_spread_bps", desc: "max benchmark |fast-slow| EMA spread before unsafe" },
        { k: "max_adx", desc: "max rolling ADX before unsafe" },
        { k: "unsafe_action", desc: "pause, reduce, or block_new" },
        { k: "unsafe_size_scale", desc: "entry size multiplier when unsafe_action=reduce" },
        { k: "inner_*", desc: "forward params to the wrapped engine" },
      ],
    },
    placeholder_rsi: {
      summary: "Wilder-style RSI. Plumbing test only — not a real strategy.",
      defaults: "period=14:oversold=30:overbought=70",
      params: [
        { k: "period", desc: "RSI lookback period" },
        { k: "oversold", desc: "long when RSI < this" },
        { k: "overbought", desc: "short when RSI > this" },
      ],
    },
    dual_signal: {
      summary: "Combines two engines. `agree` requires both, `either` triggers on either.",
      defaults: "left=bollinger_bands:right=zscore:mode=agree:conflict=none",
      params: [
        { k: "left", desc: "first engine name" },
        { k: "right", desc: "second engine name" },
        { k: "mode", desc: "agree (both fire same side) or either" },
        { k: "conflict", desc: "none (no signal) / left / right when sides disagree" },
      ],
    },
    crash_guard: {
      summary: "Wraps another engine and blocks (or shorts-only) during BTC crashes.",
      defaults: "inner=trend_filter:btc_drop_bps=500:btc_return_bars=1440",
      params: [
        { k: "inner", desc: "inner engine name" },
        { k: "btc_symbol", desc: "ticker to watch for crash (default BTCUSDT)" },
        { k: "btc_ema_period", desc: "EMA window for BTC trend (default 200)" },
        { k: "btc_return_bars", desc: "look-back bars for return measurement (default 1440)" },
        { k: "btc_drop_bps", desc: "drop in bps that triggers the guard (default 500)" },
        { k: "block_shorts", desc: "if true, block shorts too during crash" },
      ],
    },
  };

  function renderSignalGuide(form) {
    const guide = document.getElementById("signal-guide");
    if (!guide) return;
    const engineSel = form.querySelector('select[name="signal_engine"]');
    const paramsEl = form.querySelector('input[name="signal_params"]');
    if (!engineSel) return;

    function paint() {
      const name = engineSel.value;
      if (!name) {
        guide.innerHTML = `<p class="subtle"><strong>Tip:</strong> pick an engine to see its parameters, or leave blank to use the signal from <code>config/bot.yaml</code>.</p>`;
        return;
      }
      const info = SIGNAL_GUIDE[name];
      if (!info) {
        guide.innerHTML = `<p class="subtle">No guide yet for <code>${escapeHtml(name)}</code>. See <code>src/bot/signals/${escapeHtml(name)}.py</code>.</p>`;
        return;
      }
      const params = info.params.map(p => `
        <li><code>${escapeHtml(p.k)}</code><span class="subtle"> — ${escapeHtml(p.desc)}</span></li>
      `).join("");
      guide.innerHTML = `
        <div class="signal-guide-head">
          <strong>${escapeHtml(name)}</strong>
          <span class="subtle">${escapeHtml(info.summary)}</span>
        </div>
        <ul class="signal-guide-params">${params}</ul>
        <div class="signal-guide-defaults">
          <span class="subtle">Common params:</span>
          <code>${escapeHtml(info.defaults)}</code>
          <button type="button" class="btn-outline btn-tiny" data-fill-defaults>Use these</button>
        </div>
      `;
      const fillBtn = guide.querySelector("[data-fill-defaults]");
      if (fillBtn && paramsEl) {
        fillBtn.addEventListener("click", () => {
          paramsEl.value = info.defaults;
          paramsEl.dispatchEvent(new Event("input"));
        });
      }
    }
    engineSel.addEventListener("change", paint);
    paint();
  }

  function wireBacktestExtras(form) {
    renderSignalGuide(form);

    // Quick-range buttons fill start/end relative to today.
    const quick = document.getElementById("backtest-quick-range");
    if (quick) {
      quick.addEventListener("change", () => {
        const v = quick.value;
        if (!v) return;
        const now = new Date();
        const end = now.toISOString().slice(0, 10);
        const start = new Date(now);
        if (v === "ytd") start.setTime(Date.UTC(now.getUTCFullYear(), 0, 1));
        else if (v === "3m") start.setUTCMonth(start.getUTCMonth() - 3);
        else if (v === "6m") start.setUTCMonth(start.getUTCMonth() - 6);
        else if (v === "12m") start.setUTCMonth(start.getUTCMonth() - 12);
        else if (v === "24m") start.setUTCMonth(start.getUTCMonth() - 24);
        form.querySelector('input[name="start"]').value = start.toISOString().slice(0, 10);
        form.querySelector('input[name="end"]').value = end;
      });
    }

    // Live notional preview: margin × leverage.
    const marginEl = form.querySelector('input[name="margin_usd"]');
    const leverageEl = form.querySelector('input[name="leverage"]');
    const preview = document.getElementById("notional-preview");
    function updateNotional() {
      if (!preview) return;
      const m = parseFloat(marginEl.value);
      const l = parseFloat(leverageEl.value);
      if (Number.isFinite(m) && m > 0 && Number.isFinite(l) && l > 0) {
        preview.hidden = false;
        preview.innerHTML = `<strong>Notional per order:</strong> ${(m * l).toLocaleString(undefined, { maximumFractionDigits: 2 })} USDT <span class="subtle">(${m} margin × ${l}× leverage)</span>`;
      } else {
        preview.hidden = true;
      }
    }
    if (marginEl) marginEl.addEventListener("input", updateNotional);
    if (leverageEl) leverageEl.addEventListener("input", updateNotional);
    updateNotional();

    // Signal params chip preview — parses k=v:k=v into readable list.
    const paramsEl = form.querySelector('input[name="signal_params"]');
    const paramsPreview = document.getElementById("signal-params-preview");
    function updateParams() {
      if (!paramsPreview) return;
      const text = (paramsEl.value || "").trim();
      if (!text) { paramsPreview.hidden = true; paramsPreview.innerHTML = ""; return; }
      const chips = text.split(":").map(p => {
        const [k, v] = p.split("=");
        if (!k || v === undefined) return `<span class="chip bad">${escapeHtml(p)}</span>`;
        return `<span class="chip"><strong>${escapeHtml(k.trim())}</strong>=${escapeHtml(v.trim())}</span>`;
      }).join("");
      paramsPreview.hidden = false;
      paramsPreview.innerHTML = chips;
    }
    if (paramsEl) paramsEl.addEventListener("input", updateParams);
    updateParams();

    // Symbol toolbar (select all / none + count).
    const symbolToolbar = form.querySelectorAll("[data-symbol-select]");
    const symbolCount = document.getElementById("symbol-count");
    function updateSymbolCount() {
      if (!symbolCount) return;
      const all = form.querySelectorAll('input[name="symbols_picked"]');
      const sel = form.querySelectorAll('input[name="symbols_picked"]:checked');
      symbolCount.textContent = `${sel.length}/${all.length} selected`;
    }
    symbolToolbar.forEach(btn => {
      btn.addEventListener("click", () => {
        const mode = btn.getAttribute("data-symbol-select");
        const want = mode === "all";
        form.querySelectorAll('input[name="symbols_picked"]').forEach(cb => {
          cb.checked = want;
        });
        updateSymbolCount();
      });
    });
    form.querySelectorAll('input[name="symbols_picked"]').forEach(cb => {
      cb.addEventListener("change", updateSymbolCount);
    });
    updateSymbolCount();
  }

  // Now safe to wire the backtest form — SIGNAL_GUIDE / wireBacktestExtras / renderSignalGuide
  // are all defined above this point.
  const backtestForm = document.getElementById("backtest-form");
  if (backtestForm) {
    applyBacktestPrefill(backtestForm);
    wireBacktestExtras(backtestForm);
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

  const bangkokDateTime = new Intl.DateTimeFormat("en-US", {
    timeZone: "Asia/Bangkok",
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  });

  function formatBangkokDateTime(value) {
    if (!value) return "";
    const d = new Date(value);
    if (Number.isNaN(d.getTime())) return String(value);
    return bangkokDateTime.format(d) + " ICT";
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
          <td>${escapeHtml(formatBangkokDateTime(j.started_at_utc))}</td>
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

  // Live latency widget on the overview page.
  const latencyEl = document.querySelector("[data-latency-widget]");
  if (latencyEl) {
    const restBody = latencyEl.querySelector("[data-latency-rest]");
    const wsBody = latencyEl.querySelector("[data-latency-ws]");
    const sourceEl = latencyEl.querySelector("[data-latency-source]");
    const updatedEl = latencyEl.querySelector("[data-latency-updated]");
    const cellHTML = (val) => val == null ? "—" : Number(val).toLocaleString(undefined, { maximumFractionDigits: 1 });
    const cls = (val, warn, danger) => {
      if (val == null) return "";
      if (val >= danger) return "neg";
      if (val >= warn) return "warn";
      return "pos";
    };
    const renderGroup = (tbody, data, warnP90, dangerP90) => {
      const keys = Object.keys(data || {}).sort();
      if (!keys.length) {
        tbody.innerHTML = '<tr><td colspan="6" class="subtle">no samples yet</td></tr>';
        return;
      }
      tbody.innerHTML = keys.map((key) => {
        const s = data[key] || {};
        return `<tr>
          <td><code>${key}</code></td>
          <td>${cellHTML(s.count)}</td>
          <td>${cellHTML(s.p50)}</td>
          <td class="${cls(s.p90, warnP90, dangerP90)}">${cellHTML(s.p90)}</td>
          <td>${cellHTML(s.p99)}</td>
          <td>${cellHTML(s.max)}</td>
        </tr>`;
      }).join("");
    };
    const refreshLatency = async () => {
      try {
        const res = await fetch("/api/latency?window=100", { headers: { Accept: "application/json" }});
        if (!res.ok) return;
        const data = await res.json();
        if (sourceEl) sourceEl.textContent = data.source_log || "—";
        if (updatedEl && data.updated_at) {
          const t = new Date(data.updated_at);
          updatedEl.textContent = "· updated " + t.toLocaleTimeString();
        }
        renderGroup(restBody, data.rest || {}, 200, 1000);
        renderGroup(wsBody, data.ws || {}, 500, 1000);
      } catch (err) {
        console.warn("latency refresh failed", err);
      }
    };
    refreshLatency();
    setInterval(refreshLatency, 5000);
  }

  // Live fill-slippage widget.
  const slipEl = document.querySelector("[data-slip-widget]");
  if (slipEl) {
    const sideBody = slipEl.querySelector("[data-slip-by-side]");
    const symBody = slipEl.querySelector("[data-slip-by-symbol]");
    const summaryEl = slipEl.querySelector("[data-slip-summary]");
    const updatedEl = slipEl.querySelector("[data-slip-updated]");
    const fmt = (val) => val == null ? "—" : Number(val).toLocaleString(undefined, { maximumFractionDigits: 2 });
    // Slip thresholds: positive = adverse. Sweep showed >=2 bps starts hurting, >=3 breaks the strategy.
    const clsBps = (val) => {
      if (val == null) return "";
      if (val >= 3) return "neg";
      if (val >= 1.5) return "warn";
      if (val < 0) return "pos";
      return "";
    };
    const renderRows = (tbody, data, keyLabel) => {
      const keys = Object.keys(data || {}).sort();
      if (!keys.length) {
        tbody.innerHTML = `<tr><td colspan="7" class="subtle">no fills yet</td></tr>`;
        return;
      }
      tbody.innerHTML = keys.map((k) => {
        const s = data[k] || {};
        return `<tr>
          <td><code>${k}</code></td>
          <td>${fmt(s.count)}</td>
          <td class="${clsBps(s.p50)}">${fmt(s.p50)}</td>
          <td class="${clsBps(s.p90)}">${fmt(s.p90)}</td>
          <td class="${clsBps(s.p99)}">${fmt(s.p99)}</td>
          <td class="${clsBps(s.max)}">${fmt(s.max)}</td>
          <td>${fmt(s.adverse_pct)}</td>
        </tr>`;
      }).join("");
    };
    const refreshSlip = async () => {
      try {
        const res = await fetch("/api/slip?window=200", { headers: { Accept: "application/json" }});
        if (!res.ok) return;
        const data = await res.json();
        if (updatedEl && data.updated_at) {
          const t = new Date(data.updated_at);
          updatedEl.textContent = "· updated " + t.toLocaleTimeString();
        }
        if (summaryEl && data.all && data.all.count > 0) {
          summaryEl.textContent = ` · all-fills n=${data.all.count}, p50=${fmt(data.all.p50)} bps, p90=${fmt(data.all.p90)} bps, adverse=${fmt(data.all.adverse_pct)}%`;
        } else if (summaryEl) {
          summaryEl.textContent = " · no fills observed yet";
        }
        renderRows(sideBody, data.by_side || {}, "side");
        renderRows(symBody, data.by_symbol || {}, "symbol");
      } catch (err) {
        console.warn("slip refresh failed", err);
      }
    };
    refreshSlip();
    setInterval(refreshSlip, 5000);
  }
})();
