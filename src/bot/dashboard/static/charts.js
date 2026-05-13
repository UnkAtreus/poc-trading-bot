(function () {
  if (typeof Chart === "undefined") return;

  function color(name, fallback) {
    const v = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
    if (!v) return fallback;
    if (v.startsWith("#") || v.startsWith("rgb") || v.startsWith("hsl") || v.startsWith("oklch")) return v;
    return `hsl(${v})`;
  }

  function colorAlpha(name, alpha, fallback) {
    const v = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
    if (!v) return fallback;
    if (v.startsWith("#") || v.startsWith("rgb") || v.startsWith("hsl") || v.startsWith("oklch")) return v;
    return `hsl(${v} / ${alpha})`;
  }

  function applyChartDefaults() {
    Chart.defaults.color = color("--chart-text", "#6b7280");
    Chart.defaults.borderColor = color("--chart-grid", "#e5e7eb");
    Chart.defaults.font.family = "ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto";
    Chart.defaults.font.size = 11;
  }
  applyChartDefaults();

  async function fetchJson(url) {
    const res = await fetch(url, { headers: { Accept: "application/json" } });
    if (!res.ok) throw new Error("fetch " + url + " -> " + res.status);
    return res.json();
  }

  function buildEquityChart(canvas, data) {
    const rows = (data && data.history) || [];
    const labels = rows.map(r => (r.ts || "").replace("T", " ").slice(0, 19));
    const equity = rows.map(r => r.total_equity);
    return new Chart(canvas, {
      type: "line",
      data: {
        labels,
        datasets: [
          {
            label: "Total equity",
            data: equity,
            borderColor: color("--chart-1", "#2563eb"),
            backgroundColor: colorAlpha("--chart-1", 0.12, "rgba(37,99,235,0.12)"),
            tension: 0.2,
            spanGaps: true,
            pointRadius: 0,
            fill: true,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: { x: { ticks: { maxTicksLimit: 8 } } },
        plugins: { legend: { display: true } },
      },
    });
  }

  function buildDailyPnlChart(canvas, data) {
    const rows = (data && data.history) || [];
    const labels = rows.map(r => (r.ts || "").slice(0, 10));
    const values = rows.map(r => r.daily_closed_pnl || 0);
    const bg = values.map(v => (v >= 0 ? color("--success", "#15803d") : color("--destructive", "#b91c1c")));
    return new Chart(canvas, {
      type: "bar",
      data: { labels, datasets: [{ label: "Daily closed PnL", data: values, backgroundColor: bg }] },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: { x: { ticks: { maxTicksLimit: 12 } } },
      },
    });
  }

  function chartPalette() {
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

  function buildPositionsPie(canvas, data) {
    const rows = (data && data.breakdown) || [];
    const labels = rows.map(r => r.symbol);
    const values = rows.map(r => r.notional);
    const palette = chartPalette();
    const bg = labels.map((_, i) => palette[i % palette.length]);
    return new Chart(canvas, {
      type: "doughnut",
      data: { labels, datasets: [{ data: values, backgroundColor: bg, borderColor: color("--card", "#fff"), borderWidth: 2 }] },
      options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: "bottom" } } },
    });
  }

  function buildBacktestSeries(canvas, data) {
    const rows = (data && data.rows) || [];
    const headers = (data && data.headers) || [];
    const labels = rows.map(r => r.period || r.month || r.ts || r.date || "");
    const datasets = [];
    const numericFields = headers.filter(h => /pnl|equity|roi|dd/i.test(h));
    const palette = chartPalette();
    numericFields.slice(0, 5).forEach((field, idx) => {
      datasets.push({
        label: field,
        data: rows.map(r => parseFloat(r[field])).map(v => (isFinite(v) ? v : null)),
        borderColor: palette[idx % palette.length],
        backgroundColor: "transparent",
        tension: 0.2,
        spanGaps: true,
        pointRadius: 0,
      });
    });
    return new Chart(canvas, {
      type: "line",
      data: { labels, datasets },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: { x: { ticks: { maxTicksLimit: 12 } } },
      },
    });
  }

  function buildEquityDrawdown(canvas, data) {
    const rows = (data && data.history) || [];
    const labels = rows.map(r => (r.ts || "").replace("T", " ").slice(0, 16));
    const equity = rows.map(r => r.total_equity || null);
    let peak = 0;
    const drawdown = rows.map(r => {
      const eq = r.total_equity || 0;
      if (eq > peak) peak = eq;
      return peak > 0 ? -(peak - eq) : 0;
    });
    return new Chart(canvas, {
      type: "line",
      data: {
        labels,
        datasets: [
          {
            label: "Equity",
            data: equity,
            borderColor: color("--chart-1", "#2563eb"),
            backgroundColor: colorAlpha("--chart-1", 0.10, "rgba(37,99,235,0.10)"),
            tension: 0.2,
            spanGaps: true,
            pointRadius: 0,
            yAxisID: "y",
            fill: true,
          },
          {
            label: "Drawdown",
            data: drawdown,
            borderColor: color("--chart-3", "#b91c1c"),
            backgroundColor: colorAlpha("--chart-3", 0.18, "rgba(185,28,28,0.18)"),
            tension: 0.2,
            spanGaps: true,
            pointRadius: 0,
            fill: true,
            yAxisID: "y1",
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: "index", intersect: false },
        scales: {
          x: { ticks: { maxTicksLimit: 8 } },
          y: { position: "left", title: { display: true, text: "Equity" } },
          y1: { position: "right", grid: { drawOnChartArea: false }, title: { display: true, text: "Drawdown" } },
        },
      },
    });
  }

  function buildDailyRealizedBar(canvas, data) {
    const rows = (data && data.daily_pnl) || [];
    const labels = rows.map(r => r.day);
    const values = rows.map(r => r.realised_delta || r.daily_closed_pnl || 0);
    const bg = values.map(v => (v >= 0 ? color("--chart-2", "#15803d") : color("--chart-3", "#b91c1c")));
    return new Chart(canvas, {
      type: "bar",
      data: { labels, datasets: [{ label: "Realised PnL", data: values, backgroundColor: bg }] },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: { x: { ticks: { maxTicksLimit: 10 } } },
      },
    });
  }

  function buildMarginUtil(canvas, data) {
    const rows = (data && data.history) || [];
    const labels = rows.map(r => (r.ts || "").replace("T", " ").slice(0, 16));
    const util = rows.map(r => {
      const eq = r.total_equity || 0;
      const av = r.total_available_balance;
      if (eq <= 0 || av == null) return null;
      return Math.max(0, ((eq - av) / eq) * 100);
    });
    return new Chart(canvas, {
      type: "line",
      data: {
        labels,
        datasets: [{
          label: "Margin utilization %",
          data: util,
          borderColor: color("--chart-4", "#f59e0b"),
          backgroundColor: colorAlpha("--chart-4", 0.18, "rgba(245,158,11,0.18)"),
          tension: 0.2,
          spanGaps: true,
          pointRadius: 0,
          fill: true,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: { x: { ticks: { maxTicksLimit: 8 } }, y: { beginAtZero: true, suggestedMax: 100 } },
      },
    });
  }

  function buildEventTimeline(canvas, data) {
    const rows = (data && data.timeline) || [];
    const labels = rows.map(r => (r.bucket || "").replace("T", " ").slice(5, 16));
    return new Chart(canvas, {
      type: "bar",
      data: {
        labels,
        datasets: [
          { label: "Critical", data: rows.map(r => r.critical || 0), backgroundColor: color("--chart-3", "#b91c1c") },
          { label: "Warning", data: rows.map(r => r.warning || 0), backgroundColor: color("--chart-4", "#f59e0b") },
          {
            label: "Other",
            data: rows.map(r => Math.max(0, (r.total || 0) - (r.critical || 0) - (r.warning || 0))),
            backgroundColor: color("--chart-text", "#6b7280"),
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { position: "bottom" } },
        scales: {
          x: { stacked: true, ticks: { maxTicksLimit: 12 } },
          y: { stacked: true, beginAtZero: true },
        },
      },
    });
  }

  function buildSeverityPie(canvas, data) {
    const labels = ["Critical", "Warning", "Info"];
    const values = [data.critical || 0, data.warning || 0, data.info || 0];
    return new Chart(canvas, {
      type: "doughnut",
      data: {
        labels,
        datasets: [{
          data: values,
          backgroundColor: [
            color("--chart-3", "#b91c1c"),
            color("--chart-4", "#f59e0b"),
            color("--chart-text", "#6b7280"),
          ],
          borderColor: color("--card", "#fff"),
          borderWidth: 2,
        }],
      },
      options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: "bottom" } } },
    });
  }

  function buildPnlBar(canvas, data) {
    const rows = (data && data.pnl_by_symbol) || [];
    const labels = rows.map(r => r.symbol);
    const values = rows.map(r => r.unrealised_pnl || 0);
    const bg = values.map(v => (v >= 0 ? color("--chart-2", "#15803d") : color("--chart-3", "#b91c1c")));
    return new Chart(canvas, {
      type: "bar",
      data: { labels, datasets: [{ label: "Unrealised PnL", data: values, backgroundColor: bg }] },
      options: {
        indexAxis: "y",
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
      },
    });
  }

  const builders = {
    "equity-line": buildEquityChart,
    "daily-pnl": buildDailyPnlChart,
    "positions-pie": buildPositionsPie,
    "backtest-series": buildBacktestSeries,
    "pnl-bar": buildPnlBar,
    "event-timeline": buildEventTimeline,
    "severity-pie": buildSeverityPie,
    "equity-drawdown": buildEquityDrawdown,
    "daily-realized-bar": buildDailyRealizedBar,
    "margin-util": buildMarginUtil,
  };

  async function renderChart(canvas) {
    const kind = canvas.getAttribute("data-chart");
    const endpoint = canvas.getAttribute("data-endpoint");
    const build = builders[kind];
    if (!build || !endpoint) return;
    try {
      const data = await fetchJson(endpoint);
      if (canvas._chart) canvas._chart.destroy();
      canvas._chart = build(canvas, data);
    } catch (err) {
      console.warn("chart failed", kind, err);
    }
  }

  function init() {
    document.querySelectorAll("canvas[data-chart]").forEach(renderChart);
  }

  document.addEventListener("DOMContentLoaded", init);
  window.addEventListener("dashboard:themechange", function () {
    applyChartDefaults();
    init();
  });
  window.dashboardCharts = { renderAll: init, render: renderChart };
})();
