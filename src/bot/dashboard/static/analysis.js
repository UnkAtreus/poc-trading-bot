(function () {
  if (typeof Chart === "undefined") return;
  const primaryCanvas = document.getElementById("analysis-primary");
  if (!primaryCanvas) return; // not on the analysis page

  const riskReturnCanvas = document.getElementById("analysis-risk-return");
  const xMetricSel = document.getElementById("chart-x-metric");
  const yMetricSel = document.getElementById("chart-y-metric");
  const chartTypeSel = document.getElementById("chart-type");
  const summaryTbody = document.querySelector("#analysis-summary tbody");
  const rowsTbody = document.querySelector("#analysis-rows tbody");
  const rowCount = document.getElementById("analysis-row-count");
  const form = document.getElementById("analysis-filters");
  const applyBtn = document.getElementById("analysis-apply");
  const resetBtn = document.getElementById("analysis-reset");
  const activeCount = document.getElementById("analysis-active-count");

  const detailPanel = document.getElementById("analysis-detail-panel");
  const detailTitle = document.getElementById("analysis-detail-title");
  const detailMetrics = document.getElementById("analysis-detail-metrics");
  const detailWindow = document.getElementById("analysis-detail-window");
  const detailPrefill = document.getElementById("analysis-detail-prefill");
  const detailClose = document.getElementById("analysis-detail-close");
  const strategySearch = document.querySelector("[data-strategy-filter-search]");
  const strategyCount = document.getElementById("strategy-count");
  const adjustReset = document.getElementById("analysis-adjust-reset");
  const adjustFields = {
    symbols: document.getElementById("analysis-adjust-symbols"),
    signalEngine: document.getElementById("analysis-adjust-signal-engine"),
    signalParams: document.getElementById("analysis-adjust-signal-params"),
    initialEquity: document.getElementById("analysis-adjust-initial-equity"),
    margin: document.getElementById("analysis-adjust-margin"),
    leverage: document.getElementById("analysis-adjust-leverage"),
    tp: document.getElementById("analysis-adjust-tp"),
    accountCap: document.getElementById("analysis-adjust-account-cap"),
    symbolCap: document.getElementById("analysis-adjust-symbol-cap"),
    dailyLoss: document.getElementById("analysis-adjust-daily-loss"),
  };

  let currentStrategy = null;

  function color(name, fallback) {
    const v = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
    if (!v) return fallback;
    if (v.startsWith("#") || v.startsWith("rgb") || v.startsWith("hsl") || v.startsWith("oklch")) return v;
    return `hsl(${v})`;
  }

  function palette() {
    return [
      color("--chart-1", "#2563eb"),
      color("--chart-2", "#10b981"),
      color("--chart-3", "#ef4444"),
      color("--chart-4", "#f59e0b"),
      color("--chart-5", "#8b5cf6"),
      color("--chart-6", "#06b6d4"),
      color("--chart-7", "#ec4899"),
      color("--chart-8", "#14b8a6"),
    ];
  }

  function fmt(v, digits) {
    if (v === null || v === undefined || Number.isNaN(v)) return "—";
    const n = Number(v);
    if (!Number.isFinite(n)) return "—";
    return n.toFixed(digits == null ? 2 : digits);
  }

  function escapeHtml(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  // Strategy names from the research index can be full signal specs with a
  // ` / <discriminator>` suffix. Show just the suffix when present so the
  // visible label stays compact — full name kept in the title tooltip.
  function prettifyStrategy(name) {
    const s = String(name == null ? "" : name);
    const idx = s.lastIndexOf(" / ");
    if (idx >= 0) {
      const tail = s.slice(idx + 3).trim();
      if (tail) return tail;
    }
    return s;
  }

  function getCheckedValues(groupName) {
    return Array.from(form.querySelectorAll(`[data-filter-group="${groupName}"] input[type="checkbox"]:checked`))
      .map(cb => cb.value);
  }

  function strategyLabels() {
    return Array.from(form.querySelectorAll('[data-filter-group="strategies"] label.check'));
  }

  function updateStrategyCount() {
    if (!strategyCount) return;
    const labels = strategyLabels();
    const visible = labels.filter(label => label.style.display !== "none");
    const checked = labels.filter(label => label.querySelector('input[type="checkbox"]')?.checked);
    strategyCount.textContent = `${checked.length} selected · ${visible.length}/${labels.length} visible`;
  }

  function filterStrategyList() {
    const q = String(strategySearch ? strategySearch.value : "").trim().toLowerCase();
    for (const label of strategyLabels()) {
      const text = `${label.textContent || ""} ${label.title || ""}`.toLowerCase();
      label.style.display = !q || text.includes(q) ? "" : "none";
    }
    updateStrategyCount();
  }

  function applyQuickRange(value) {
    const startEl = form.querySelector('input[name="start"]');
    const endEl = form.querySelector('input[name="end"]');
    if (!startEl || !endEl) return;
    if (!value) return;
    if (value === "all") {
      startEl.value = "";
      endEl.value = "";
      return;
    }
    const now = new Date();
    const endStr = now.toISOString().slice(0, 10);
    let start = new Date(now);
    if (value === "ytd") {
      start = new Date(Date.UTC(now.getUTCFullYear(), 0, 1));
    } else if (value === "6m") {
      start.setUTCMonth(start.getUTCMonth() - 6);
    } else if (value === "12m") {
      start.setUTCMonth(start.getUTCMonth() - 12);
    } else if (value === "24m") {
      start.setUTCMonth(start.getUTCMonth() - 24);
    }
    startEl.value = start.toISOString().slice(0, 10);
    endEl.value = endStr;
  }

  function queryString() {
    const params = new URLSearchParams();
    const strategies = getCheckedValues("strategies");
    const symbols = getCheckedValues("symbols");
    if (strategies.length) params.set("strategies", strategies.join(","));
    if (symbols.length) params.set("symbols", symbols.join(","));
    const start = form.querySelector('input[name="start"]').value;
    const end = form.querySelector('input[name="end"]').value;
    const minTrades = form.querySelector('input[name="min_trades"]').value;
    const minWin = form.querySelector('input[name="min_win_rate_pct"]').value;
    const hideZero = form.querySelector('input[name="hide_zero_trades"]');
    if (start) params.set("start", start);
    if (end) params.set("end", end);
    if (Number(minTrades) > 0) params.set("min_trades", minTrades);
    if (Number(minWin) > 0) params.set("min_win_rate_pct", minWin);
    params.set("hide_zero_trades", hideZero && hideZero.checked ? "true" : "false");
    return params.toString();
  }

  function updateActiveCount() {
    if (!activeCount) return;
    updateStrategyCount();
    const parts = [];
    const strategies = getCheckedValues("strategies");
    const symbols = getCheckedValues("symbols");
    if (strategies.length) parts.push(`${strategies.length} strat`);
    if (symbols.length) parts.push(`${symbols.length} sym`);
    const start = form.querySelector('input[name="start"]').value;
    const end = form.querySelector('input[name="end"]').value;
    if (start || end) parts.push(`window`);
    const minT = Number(form.querySelector('input[name="min_trades"]').value);
    const minW = Number(form.querySelector('input[name="min_win_rate_pct"]').value);
    const hideZero = form.querySelector('input[name="hide_zero_trades"]');
    if (minT > 0) parts.push(`≥${minT} trades`);
    if (minW > 0) parts.push(`≥${minW}% win`);
    if (hideZero && hideZero.checked) parts.push("hide zero-trade");
    activeCount.textContent = parts.length ? `Active filters: ${parts.join(" · ")}` : "No filters applied";
  }

  function groupByStrategy(rows) {
    const map = new Map();
    for (const row of rows) {
      const key = row.strategy || "unknown";
      if (!map.has(key)) map.set(key, []);
      map.get(key).push(row);
    }
    return map;
  }

  function toTimestamp(dateStr) {
    if (!dateStr) return null;
    const d = new Date(dateStr + "T00:00:00Z");
    const t = d.getTime();
    return Number.isFinite(t) ? t : null;
  }

  const METRIC_LABELS = {
    net_pnl: "Net PnL (USDT)",
    roi_pct: "ROI %",
    max_drawdown_pct: "Max DD %",
    win_rate_pct: "Win rate %",
    trades: "Trades",
    stability_score: "Stability score",
    avg_monthly_roi_pct: "Avg monthly ROI %",
    worst_monthly_dd_pct: "Worst monthly DD %",
    start: "Window start",
  };

  function metricLabel(key) {
    return METRIC_LABELS[key] || key;
  }

  function metricValue(row, key) {
    if (key === "start") return toTimestamp(row.start);
    const v = row[key];
    if (v === null || v === undefined) return null;
    const n = Number(v);
    return Number.isFinite(n) ? n : null;
  }

  function formatMonth(ts) {
    if (ts == null) return "";
    const d = new Date(ts);
    if (Number.isNaN(d.getTime())) return "";
    const months = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
    return `${months[d.getUTCMonth()]} ${d.getUTCFullYear()}`;
  }

  function tooltipBody(row) {
    return [
      `window: ${row.start} → ${row.end}`,
      `ROI: ${fmt(row.roi_pct)}%`,
      `net: ${fmt(row.net_pnl)}`,
      `max DD: ${fmt(row.max_drawdown_pct)}%`,
      `trades: ${row.trades || 0} (win ${fmt(row.win_rate_pct)}%)`,
    ];
  }

  function buildScatterDatasets(rows, xMetric, yMetric) {
    const groups = groupByStrategy(rows);
    const colors = palette();
    let i = 0;
    const datasets = [];
    for (const [strategy, items] of groups) {
      const data = items
        .map(r => {
          const x = metricValue(r, xMetric);
          const y = metricValue(r, yMetric);
          if (x === null || y === null) return null;
          return { x, y, _row: r };
        })
        .filter(p => p !== null);
      if (xMetric === "start") data.sort((a, b) => a.x - b.x);
      if (!data.length) continue;
      const c = colors[i % colors.length];
      i += 1;
      datasets.push({
        label: prettifyStrategy(strategy),
        _strategyFull: strategy,
        data,
        backgroundColor: c,
        borderColor: c,
        pointRadius: 5,
        pointHoverRadius: 7,
        showLine: xMetric === "start",
        tension: 0.2,
        borderWidth: 1.5,
      });
    }
    return datasets;
  }

  function buildBarDatasets(rows, yMetric) {
    const groups = groupByStrategy(rows);
    const labels = [];
    const values = [];
    const colors = palette();
    const bg = [];
    let i = 0;
    for (const [strategy, items] of groups) {
      const numeric = items.map(r => metricValue(r, yMetric)).filter(v => v !== null);
      if (!numeric.length) continue;
      // For monotonic metrics use sum; for averageable ones use mean.
      let value;
      if (yMetric === "trades" || yMetric === "net_pnl") {
        value = numeric.reduce((a, b) => a + b, 0);
      } else {
        value = numeric.reduce((a, b) => a + b, 0) / numeric.length;
      }
      labels.push(prettifyStrategy(strategy));
      values.push(value);
      bg.push(colors[i % colors.length]);
      i += 1;
    }
    return { labels, values, bg };
  }

  function renderPrimaryChart(rows) {
    const xMetric = xMetricSel.value || "start";
    const yMetric = yMetricSel.value || "net_pnl";
    const chartType = chartTypeSel.value || "scatter";

    if (primaryCanvas._chart) primaryCanvas._chart.destroy();

    if (chartType === "bar") {
      const { labels, values, bg } = buildBarDatasets(rows, yMetric);
      const aggLabel = (yMetric === "trades" || yMetric === "net_pnl") ? "total" : "avg";
      primaryCanvas._chart = new Chart(primaryCanvas, {
        type: "bar",
        data: {
          labels,
          datasets: [{ label: `${aggLabel} ${metricLabel(yMetric)}`, data: values, backgroundColor: bg }],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: { legend: { display: false } },
          scales: {
            x: { title: { display: true, text: "Strategy" } },
            y: { title: { display: true, text: `${aggLabel} ${metricLabel(yMetric)}` } },
          },
        },
      });
      return;
    }

    const datasets = buildScatterDatasets(rows, xMetric, yMetric);
    const xIsTime = xMetric === "start";
    primaryCanvas._chart = new Chart(primaryCanvas, {
      type: "scatter",
      data: { datasets },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: "nearest", intersect: true },
        plugins: {
          legend: { position: "bottom" },
          tooltip: {
            callbacks: {
              label: ctx => {
                const r = ctx.raw && ctx.raw._row;
                if (!r) return `${ctx.dataset.label}: ${ctx.parsed.y}`;
                return [ctx.dataset.label, ...tooltipBody(r)];
              },
            },
          },
        },
        scales: {
          x: {
            type: "linear",
            title: { display: true, text: metricLabel(xMetric) },
            ticks: xIsTime
              ? { maxTicksLimit: 8, callback: v => formatMonth(v) }
              : { maxTicksLimit: 8 },
          },
          y: { title: { display: true, text: metricLabel(yMetric) } },
        },
      },
    });
  }

  function renderRiskReturnChart(rows) {
    if (!riskReturnCanvas) return;
    const datasets = buildScatterDatasets(rows, "max_drawdown_pct", "roi_pct").map(ds => ({
      ...ds,
      showLine: false,
    }));
    if (riskReturnCanvas._chart) riskReturnCanvas._chart.destroy();
    riskReturnCanvas._chart = new Chart(riskReturnCanvas, {
      type: "scatter",
      data: { datasets },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { position: "bottom" },
          tooltip: {
            callbacks: {
              label: ctx => {
                const r = ctx.raw && ctx.raw._row;
                if (!r) return `${ctx.dataset.label}`;
                return [ctx.dataset.label, ...tooltipBody(r)];
              },
            },
          },
        },
        scales: {
          x: { title: { display: true, text: "Max DD %" }, beginAtZero: true },
          y: { title: { display: true, text: "ROI %" } },
        },
      },
    });
  }

  const PREFILL_STORAGE_KEY = "backtest_prefill";

  function cleanInputValue(el) {
    if (!el) return null;
    const value = String(el.value == null ? "" : el.value).trim();
    return value === "" ? null : value;
  }

  function cleanNumberValue(el) {
    const value = cleanInputValue(el);
    if (value === null) return null;
    const n = Number(value);
    return Number.isFinite(n) ? n : null;
  }

  function setAdjustField(el, value) {
    if (!el) return;
    el.value = value === null || value === undefined ? "" : String(value);
  }

  function ensureSelectOption(select, value) {
    if (!select || !value) return;
    const exists = Array.from(select.options).some(opt => opt.value === value);
    if (!exists) {
      const opt = document.createElement("option");
      opt.value = value;
      opt.textContent = value;
      select.appendChild(opt);
    }
  }

  function splitSymbols(value) {
    return String(value || "")
      .split(",")
      .map(s => s.trim().toUpperCase())
      .filter(Boolean);
  }

  function populateAdjustForm(strategyRow) {
    const cfg = (strategyRow && strategyRow.config) || {};
    ensureSelectOption(adjustFields.signalEngine, cfg.signal_engine || "");
    setAdjustField(adjustFields.symbols, (strategyRow.symbols || []).join(","));
    setAdjustField(adjustFields.signalEngine, cfg.signal_engine || "");
    setAdjustField(adjustFields.signalParams, cfg.signal_params_str || "");
    setAdjustField(adjustFields.initialEquity, "");
    setAdjustField(adjustFields.margin, cfg.margin_usd);
    setAdjustField(adjustFields.leverage, cfg.leverage);
    setAdjustField(adjustFields.tp, cfg.tp_offset_bps);
    setAdjustField(adjustFields.accountCap, cfg.account_cap);
    setAdjustField(adjustFields.symbolCap, cfg.symbol_cap);
    setAdjustField(adjustFields.dailyLoss, cfg.daily_loss_limit);
  }

  function buildPrefillPayload(strategyRow, picked) {
    const win = picked || {};
    const symbols = splitSymbols(cleanInputValue(adjustFields.symbols) || "");
    return {
      _strategy_label: strategyRow.strategy,
      _saved_at: new Date().toISOString(),
      start: win.start || null,
      end: win.end || null,
      signal_engine: cleanInputValue(adjustFields.signalEngine),
      signal_params: cleanInputValue(adjustFields.signalParams),
      initial_equity: cleanNumberValue(adjustFields.initialEquity),
      margin_usd: cleanNumberValue(adjustFields.margin),
      leverage: cleanNumberValue(adjustFields.leverage),
      tp_offset_bps: cleanNumberValue(adjustFields.tp),
      max_notional_account: cleanNumberValue(adjustFields.accountCap),
      max_notional_per_symbol: cleanNumberValue(adjustFields.symbolCap),
      daily_loss_limit: cleanNumberValue(adjustFields.dailyLoss),
      symbols: symbols.length ? symbols : (strategyRow.symbols || []),
    };
  }

  function stashPrefillAndGo(strategyRow, picked) {
    const payload = buildPrefillPayload(strategyRow, picked);
    try {
      sessionStorage.setItem(PREFILL_STORAGE_KEY, JSON.stringify(payload));
    } catch (err) {
      console.warn("could not stash prefill in sessionStorage", err);
      // Fall back to URL encoding so the user still ends up on /backtests.
      const encoded = btoa(encodeURIComponent(JSON.stringify(payload)));
      window.location.href = "/backtests?prefill=" + encodeURIComponent(encoded);
      return;
    }
    window.location.href = "/backtests?prefill=1";
  }

  function showStrategyDetails(strategyRow) {
    if (!detailPanel) return;
    currentStrategy = strategyRow;
    detailPanel.hidden = false;
    detailTitle.textContent = `Strategy: ${prettifyStrategy(strategyRow.strategy)}`;
    detailTitle.title = strategyRow.strategy;

    const cfg = strategyRow.config || {};
    populateAdjustForm(strategyRow);
    const inferredKeys = new Set(cfg.inferred_keys || []);
    const signalParts = [];
    if (cfg.signal_engine) {
      const params = cfg.signal_params || {};
      const paramStr = Object.keys(params).map(k => {
        const v = params[k];
        const marked = inferredKeys.has(k) ? `<mark title="Inferred from candidate name '${escapeHtml(cfg.candidate_name || "")}' — exact value not in the research index">${escapeHtml(k)}=${escapeHtml(String(v))}</mark>` : `${escapeHtml(k)}=${escapeHtml(String(v))}`;
        return marked;
      }).join(":");
      signalParts.push(escapeHtml(cfg.signal_engine) + (paramStr ? ":" + paramStr : ""));
    } else {
      signalParts.push("(use config/bot.yaml)");
    }
    const signalLineHtml = signalParts.join("");
    const symbols = (strategyRow.symbols || []).join(", ") || "(none)";
    const reportLink = strategyRow.report_path
      ? ` · <a href="/backtests?report=${encodeURIComponent(strategyRow.report_path)}">view source report</a>`
      : "";
    const inferredNote = inferredKeys.size
      ? `<div class="subtle" style="margin-top:6px;color:hsl(var(--warning));">
           Highlighted params were inferred from the candidate name. The research index doesn't store true per-candidate signal params; check the source report for exact values.
         </div>`
      : "";

    detailMetrics.innerHTML = `
      <div class="metric">
        <div class="metric-label">Margin / order</div>
        <div class="metric-value">${fmt(cfg.margin_usd)}<span class="subtle" style="font-size:12px;margin-left:4px">USDT</span></div>
      </div>
      <div class="metric">
        <div class="metric-label">Leverage</div>
        <div class="metric-value">${cfg.leverage ?? "—"}<span class="subtle" style="font-size:12px;margin-left:4px">x</span></div>
      </div>
      <div class="metric">
        <div class="metric-label">Account cap</div>
        <div class="metric-value">${fmt(cfg.account_cap)}<span class="subtle" style="font-size:12px;margin-left:4px">USDT</span></div>
      </div>
      <div class="metric">
        <div class="metric-label">Per-symbol cap</div>
        <div class="metric-value">${fmt(cfg.symbol_cap)}<span class="subtle" style="font-size:12px;margin-left:4px">USDT</span></div>
      </div>
      <div class="metric">
        <div class="metric-label">TP offset</div>
        <div class="metric-value">${fmt(cfg.tp_offset_bps)}<span class="subtle" style="font-size:12px;margin-left:4px">bps</span></div>
      </div>
      <div class="metric">
        <div class="metric-label">Daily loss limit</div>
        <div class="metric-value">${fmt(cfg.daily_loss_limit)}<span class="subtle" style="font-size:12px;margin-left:4px">USDT</span></div>
      </div>
      <div class="metric">
        <div class="metric-label">Runs · win rate</div>
        <div class="metric-value">${strategyRow.runs}<span class="subtle" style="font-size:12px;margin-left:6px">${fmt(strategyRow.win_rate_pct)}%</span></div>
      </div>
      <div class="metric" style="grid-column: 1 / -1;">
        <div class="metric-label">Signal <span class="subtle" style="font-weight:400;">· candidate <code>${escapeHtml(cfg.candidate_name || strategyRow.strategy)}</code></span></div>
        <div class="metric-value" style="font-size:14px;font-weight:500;word-break:break-all;"><code>${signalLineHtml}</code></div>
        ${inferredNote}
        <div class="subtle" style="margin-top:6px;">Symbols: ${escapeHtml(symbols)}${reportLink}</div>
      </div>
    `;

    const windows = (strategyRow.windows || []).slice().sort((a, b) => (a.start || "").localeCompare(b.start || ""));
    detailWindow.innerHTML = windows.map((w, i) => {
      const label = `${w.start} → ${w.end}  ·  ROI ${fmt(w.roi_pct)}%  ·  ${w.trades || 0} trades`;
      return `<option value="${i}">${escapeHtml(label)}</option>`;
    }).join("");

    // Replace anchor navigation with a click handler that stashes the payload
    // into sessionStorage. Far more robust than URL-encoded base64.
    detailPrefill.onclick = (e) => {
      e.preventDefault();
      const idx = Number(detailWindow.value || 0);
      stashPrefillAndGo(strategyRow, windows[idx] || windows[0] || {});
    };
    detailPrefill.setAttribute("href", "/backtests?prefill=1");

    detailPanel.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }

  function hideStrategyDetails() {
    if (!detailPanel) return;
    detailPanel.hidden = true;
    currentStrategy = null;
  }

  if (detailClose) detailClose.addEventListener("click", hideStrategyDetails);
  if (adjustReset) {
    adjustReset.addEventListener("click", () => {
      if (currentStrategy) populateAdjustForm(currentStrategy);
    });
  }

  function renderSummary(perStrategy) {
    summaryTbody.innerHTML = "";
    for (const r of perStrategy || []) {
      const tr = document.createElement("tr");
      tr.className = "analysis-summary-row";
      tr.style.cursor = "pointer";
      tr.dataset.strategy = r.strategy;
      tr.title = r.strategy;
      tr.innerHTML = `
        <td><strong>${escapeHtml(prettifyStrategy(r.strategy))}</strong></td>
        <td>${r.runs}</td>
        <td class="${(r.net_pnl_total || 0) >= 0 ? "pos" : "neg"}">${fmt(r.net_pnl_total)}</td>
        <td>${fmt(r.avg_roi_pct)}</td>
        <td>${fmt(r.best_roi_pct)}</td>
        <td>${fmt(r.worst_roi_pct)}</td>
        <td>${fmt(r.max_drawdown_pct)}</td>
        <td>${r.trades_total || 0}</td>
        <td>${fmt(r.win_rate_pct)}</td>
      `;
      tr.addEventListener("click", () => showStrategyDetails(r));
      summaryTbody.appendChild(tr);
    }
  }

  function renderRows(rows) {
    rowsTbody.innerHTML = "";
    if (rowCount) rowCount.textContent = `(${(rows || []).length} runs)`;
    for (const r of rows || []) {
      const tr = document.createElement("tr");
      const launch = r.launch_pass === true ? "✓"
        : r.launch_pass === false ? "✗" : "";
      const reportLink = r.report_path
        ? `<a href="/backtests?report=${encodeURIComponent(r.report_path)}">view</a>`
        : `<span class="subtle">–</span>`;
      tr.title = r.strategy;
      tr.innerHTML = `
        <td>${escapeHtml(prettifyStrategy(r.strategy))}</td>
        <td>${escapeHtml(r.start || "")} → ${escapeHtml(r.end || "")}</td>
        <td>${r.months ?? ""}</td>
        <td>${r.trades ?? 0}</td>
        <td>${fmt(r.win_rate_pct)}</td>
        <td>${fmt(r.roi_pct)}</td>
        <td class="${(r.net_pnl || 0) >= 0 ? "pos" : "neg"}">${fmt(r.net_pnl)}</td>
        <td>${fmt(r.max_drawdown_pct)}</td>
        <td>${launch}</td>
        <td><span class="subtle">${escapeHtml((r.symbols || []).join(", "))}</span></td>
        <td>${reportLink}</td>
      `;
      rowsTbody.appendChild(tr);
    }
  }

  let lastRows = [];

  function render(data) {
    const rows = (data && data.rows) || [];
    lastRows = rows;
    renderPrimaryChart(rows);
    renderRiskReturnChart(rows);
    renderSummary((data && data.per_strategy) || []);
    renderRows(rows);
    updateActiveCount();

    // If a strategy was open, re-show it from the new dataset (refreshed config/windows).
    if (currentStrategy) {
      const next = (data && data.per_strategy || []).find(s => s.strategy === currentStrategy.strategy);
      if (next) showStrategyDetails(next);
      else hideStrategyDetails();
    }
  }

  async function refetch() {
    const qs = queryString();
    const url = "/api/backtest-analysis" + (qs ? "?" + qs : "");
    try {
      const res = await fetch(url, { headers: { Accept: "application/json" }, credentials: "same-origin" });
      if (!res.ok) throw new Error("status " + res.status);
      const data = await res.json();
      render(data);
    } catch (err) {
      console.warn("analysis fetch failed", err);
    }
  }

  applyBtn.addEventListener("click", refetch);
  resetBtn.addEventListener("click", function () {
    form.querySelectorAll('input[type="checkbox"]').forEach(cb => { cb.checked = false; });
    form.querySelector('input[name="start"]').value = "";
    form.querySelector('input[name="end"]').value = "";
    form.querySelector('input[name="min_trades"]').value = "0";
    form.querySelector('input[name="min_win_rate_pct"]').value = "0";
    form.querySelector('input[name="hide_zero_trades"]').checked = true;
    form.querySelector('select[name="quick_range"]').value = "";
    if (strategySearch) strategySearch.value = "";
    filterStrategyList();
    refetch();
  });

  if (strategySearch) strategySearch.addEventListener("input", filterStrategyList);
  document.querySelectorAll("[data-strategy-select]").forEach(btn => {
    btn.addEventListener("click", () => {
      const mode = btn.getAttribute("data-strategy-select");
      for (const label of strategyLabels()) {
        const cb = label.querySelector('input[type="checkbox"]');
        if (!cb) continue;
        if (mode === "none") cb.checked = false;
        if (mode === "visible" && label.style.display !== "none") cb.checked = true;
      }
      updateActiveCount();
    });
  });

  const quickRange = form.querySelector('select[name="quick_range"]');
  if (quickRange) {
    quickRange.addEventListener("change", () => {
      applyQuickRange(quickRange.value);
      updateActiveCount();
    });
  }

  // Live-update the "active filters" counter as user clicks pills / edits inputs.
  form.addEventListener("change", updateActiveCount);
  form.addEventListener("input", updateActiveCount);

  // Chart picker changes redraw the primary chart without refetching.
  [xMetricSel, yMetricSel, chartTypeSel].forEach(sel => {
    if (sel) sel.addEventListener("change", () => renderPrimaryChart(lastRows));
  });

  // Initial render uses the server-provided dataset to avoid an extra round trip.
  render(window.__analysisInitial || {});
})();
