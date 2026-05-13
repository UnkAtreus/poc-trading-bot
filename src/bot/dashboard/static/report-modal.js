(function () {
  const modal = document.getElementById("report-modal");
  if (!modal) return;
  const titleEl = document.getElementById("report-modal-title");
  const bodyEl = document.getElementById("report-modal-body");
  const newTabEl = document.getElementById("report-modal-newtab");
  let lastFocus = null;

  function open() {
    lastFocus = document.activeElement;
    modal.classList.add("open");
    modal.setAttribute("aria-hidden", "false");
    document.body.classList.add("modal-open");
  }

  function close() {
    modal.classList.remove("open");
    modal.setAttribute("aria-hidden", "true");
    document.body.classList.remove("modal-open");
    if (lastFocus && typeof lastFocus.focus === "function") lastFocus.focus();
    if (location.search.includes("report=")) {
      const url = new URL(location.href);
      url.searchParams.delete("report");
      history.replaceState(null, "", url.pathname + (url.search || "") + url.hash);
    }
  }

  function escapeHtml(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  }

  function renderMarkdown(text) {
    if (typeof marked !== "undefined") {
      marked.setOptions({ gfm: true, breaks: false, headerIds: false, mangle: false });
      return marked.parse(text);
    }
    return "<pre>" + escapeHtml(text) + "</pre>";
  }

  function renderPlain(text) {
    return "<pre>" + escapeHtml(text) + "</pre>";
  }

  async function loadReport(path) {
    titleEl.textContent = path;
    bodyEl.innerHTML = '<p class="subtle">Loading…</p>';
    newTabEl.href = "/backtests?report=" + encodeURIComponent(path);
    open();
    try {
      const res = await fetch("/api/report?path=" + encodeURIComponent(path));
      if (!res.ok) {
        const detail = await res.json().catch(() => ({}));
        bodyEl.innerHTML = '<p class="severity-critical">Error: ' + escapeHtml(detail.detail || res.status) + '</p>';
        return;
      }
      const data = await res.json();
      const lower = path.toLowerCase();
      if (lower.endsWith(".md")) {
        bodyEl.innerHTML = '<div class="markdown-body">' + renderMarkdown(data.text || "") + '</div>';
      } else {
        bodyEl.innerHTML = renderPlain(data.text || "");
      }
    } catch (err) {
      bodyEl.innerHTML = '<p class="severity-critical">Error: ' + escapeHtml(String(err)) + '</p>';
    }
  }

  function isReportLink(a) {
    if (!a) return false;
    const href = a.getAttribute("href") || "";
    return href.startsWith("/backtests?report=") || href.startsWith("/alerts?report=");
  }

  document.addEventListener("click", function (e) {
    if (e.target.closest("[data-close]")) {
      close();
      return;
    }
    const a = e.target.closest("a");
    if (!a || !isReportLink(a)) return;
    if (e.metaKey || e.ctrlKey || e.shiftKey || e.button === 1) return; // let new-tab clicks pass
    const url = new URL(a.href, location.origin);
    const path = url.searchParams.get("report");
    if (!path) return;
    e.preventDefault();
    loadReport(path);
  });

  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape" && modal.classList.contains("open")) {
      close();
    }
  });

  // Deep-link: if page loaded with ?report= already set, open the modal automatically
  const initial = new URLSearchParams(location.search).get("report");
  if (initial) {
    // Remove the inline report card duplication (server still renders one); we use the modal instead.
    document.querySelectorAll(".report-card").forEach(el => el.remove());
    loadReport(initial);
  }
})();
