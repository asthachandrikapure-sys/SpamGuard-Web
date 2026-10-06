/**
 * script.js — Spam SMS Classifier Frontend Logic
 * ================================================
 * Handles: classification, dashboard stats, history,
 * model performance, chart rendering, navigation.
 */

"use strict";

// Auto-detect current origin when served by Flask; fallback for file:// opening
const API_BASE = window.location.origin && window.location.origin.startsWith("http")
  ? window.location.origin
  : "http://127.0.0.1:5000";

// ─────────────────────────────────────────────
// DOM REFERENCES
// ─────────────────────────────────────────────
const smsInput        = document.getElementById("sms-input");
const charCounter     = document.getElementById("char-counter");
const btnClassify     = document.getElementById("btn-classify");
const btnClear        = document.getElementById("btn-clear");
const spinner         = document.getElementById("spinner");

const resultCard      = document.getElementById("result-card");
const resultPlaceholder = document.getElementById("result-placeholder");
const resultContent   = document.getElementById("result-content");
const resultError     = document.getElementById("result-error");
const resultBadge     = document.getElementById("result-badge");
const resultLabel     = document.getElementById("result-label");
const resultVerdict   = document.getElementById("result-verdict");
const detailConfidence = document.getElementById("detail-confidence");
const detailModel     = document.getElementById("detail-model");
const detailLength    = document.getElementById("detail-length");
const confidenceBar   = document.getElementById("confidence-bar");
const confidencePct   = document.getElementById("confidence-pct");
const analyzedMsgText = document.getElementById("analyzed-msg-text");
const errorMessage    = document.getElementById("error-message");

const statTotalVal    = document.getElementById("stat-total-val");
const statSpamVal     = document.getElementById("stat-spam-val");
const statHamVal      = document.getElementById("stat-ham-val");
const statPctVal      = document.getElementById("stat-pct-val");
const chartCenterText = document.getElementById("chart-center-text");
const perfTbody       = document.getElementById("perf-tbody");

const historyTbody    = document.getElementById("history-tbody");
const historySearch   = document.getElementById("history-search");
const historyCount    = document.getElementById("history-count");
const filterBtns      = document.querySelectorAll(".filter-btn");

const systemStatusPill = document.getElementById("system-status-pill");
const statusDot        = document.getElementById("status-dot");
const statusText       = document.getElementById("status-text");

function setSystemStatus(isOnline, message) {
  if (!systemStatusPill || !statusText) return;
  if (isOnline) {
    systemStatusPill.className = "system-status-pill online";
    statusText.textContent     = message || "Backend Online (SQLite & ML Ready)";
  } else {
    systemStatusPill.className = "system-status-pill offline";
    statusText.textContent     = message || "Backend Offline";
  }
}

// ─────────────────────────────────────────────
// STATE
// ─────────────────────────────────────────────
let donutChart    = null;
let allHistory    = [];
let activeFilter  = "all";

// ─────────────────────────────────────────────
// UTILITIES
// ─────────────────────────────────────────────
function escapeHtml(str) {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function pct(val) {
  return (parseFloat(val) * 100).toFixed(1) + "%";
}

function formatDate(iso) {
  try {
    const d = new Date(iso.replace(" ", "T") + (iso.includes("T") ? "" : "Z"));
    return d.toLocaleString("en-GB", {
      day: "2-digit", month: "short", year: "numeric",
      hour: "2-digit", minute: "2-digit"
    });
  } catch {
    return iso;
  }
}

async function apiFetch(endpoint, options = {}) {
  const res = await fetch(API_BASE + endpoint, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.error || `HTTP ${res.status}`);
  }
  return res.json();
}

// ─────────────────────────────────────────────
// NAVIGATION — active link on scroll
// ─────────────────────────────────────────────
(function initNavigation() {
  const sections = document.querySelectorAll(".section");
  const links    = document.querySelectorAll(".nav-link[data-section]");
  const hamburger = document.getElementById("hamburger");
  const navLinks  = document.getElementById("nav-links");

  if (hamburger && navLinks) {
    hamburger.addEventListener("click", () => {
      navLinks.classList.toggle("open");
    });
  }

  // Close mobile menu on link click and scroll smoothly
  links.forEach(link => {
    link.addEventListener("click", (e) => {
      if (navLinks) navLinks.classList.remove("open");
      const sectionId = link.getAttribute("href")?.replace("#", "");
      const targetSec = document.getElementById(sectionId);
      if (targetSec) {
        e.preventDefault();
        targetSec.scrollIntoView({ behavior: "smooth" });
      }
    });
  });

  // "Check an SMS" Hero CTA button
  const btnCheckSms = document.getElementById("btn-check-sms");
  if (btnCheckSms) {
    btnCheckSms.addEventListener("click", (e) => {
      e.preventDefault();
      const target = document.getElementById("classifier");
      if (target) {
        target.scrollIntoView({ behavior: "smooth" });
        setTimeout(() => smsInput && smsInput.focus(), 350);
      }
    });
  }

  // "View Dashboard" Hero button
  const btnHeroDash = document.querySelector(".hero-actions .btn-ghost");
  if (btnHeroDash) {
    btnHeroDash.addEventListener("click", (e) => {
      e.preventDefault();
      document.getElementById("dashboard")?.scrollIntoView({ behavior: "smooth" });
    });
  }

  const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        links.forEach(l => l.classList.remove("active"));
        const active = document.querySelector(`.nav-link[data-section="${entry.target.id}"]`);
        if (active) active.classList.add("active");
      }
    });
  }, { rootMargin: "-40% 0px -55% 0px" });

  sections.forEach(s => observer.observe(s));
})();

// ─────────────────────────────────────────────
// CHARACTER COUNTER
// ─────────────────────────────────────────────
smsInput.addEventListener("input", () => {
  const len = smsInput.value.length;
  charCounter.textContent = `${len} / 1000`;
  charCounter.style.color = len > 900 ? "#dc2626" : "";
});

// ─────────────────────────────────────────────
// SAMPLE MESSAGES: fill & auto-classify
// ─────────────────────────────────────────────
const sampleButtonsContainer = document.getElementById("sample-buttons");
if (sampleButtonsContainer) {
  sampleButtonsContainer.addEventListener("click", async (e) => {
    const btn = e.target.closest(".sample-btn");
    if (!btn || !btn.dataset.msg) return;
    
    // Fill textarea
    smsInput.value = btn.dataset.msg;
    smsInput.dispatchEvent(new Event("input"));

    // Scroll to classifier card smoothly
    document.getElementById("classifier")?.scrollIntoView({ behavior: "smooth" });

    // Instantly trigger classification for live feedback
    await classifyMessage();
  });
}

// ─────────────────────────────────────────────
// CLEAR BUTTON
// ─────────────────────────────────────────────
btnClear.addEventListener("click", () => {
  smsInput.value = "";
  charCounter.textContent = "0 / 1000";
  charCounter.style.color = "";
  showPlaceholder();
  smsInput.focus();
});

function showPlaceholder() {
  resultPlaceholder.classList.remove("hidden");
  resultContent.classList.add("hidden");
  resultError.classList.add("hidden");
}

// ─────────────────────────────────────────────
// CLASSIFY BUTTON
// ─────────────────────────────────────────────
btnClassify.addEventListener("click", classifyMessage);
smsInput.addEventListener("keydown", (e) => {
  if (e.ctrlKey && e.key === "Enter") classifyMessage();
});

async function classifyMessage() {
  const msg = smsInput.value.trim();

  // Validate
  if (!msg) {
    showError("Please enter an SMS message before classifying.");
    return;
  }
  if (msg.length > 1000) {
    showError("Message is too long. Maximum 1000 characters.");
    return;
  }

  // Loading state
  btnClassify.disabled = true;
  spinner.classList.remove("hidden");
  resultPlaceholder.classList.remove("hidden");
  resultContent.classList.add("hidden");
  resultError.classList.add("hidden");

  try {
    const data = await apiFetch("/api/predict", {
      method: "POST",
      body:   JSON.stringify({ message: msg }),
    });
    showResult(data, msg.length, msg);

    // Refresh dashboard stats after each prediction
    loadStats();
    loadHistory();
  } catch (err) {
    showError(err.message || "Failed to connect to the server. Make sure the Flask backend is running.");
  } finally {
    btnClassify.disabled = false;
    spinner.classList.add("hidden");
  }
}

function showResult(data, msgLen, rawMsg) {
  const isSpam = data.prediction === "spam";
  const conf   = parseFloat(data.confidence);
  const confPct = Math.round(conf * 100);

  // Badge
  resultBadge.className = "result-badge " + (isSpam ? "spam-badge" : "ham-badge");
  resultLabel.textContent = isSpam ? "SPAM MESSAGE" : "HAM MESSAGE";

  // Verdict (Exact text requested in prompt)
  resultVerdict.textContent = isSpam
    ? "⚠ This message may be suspicious."
    : "✓ This message appears to be legitimate.";

  // Details
  detailConfidence.textContent = confPct + "%";
  detailModel.textContent      = data.model || "–";
  detailLength.textContent     = msgLen + " characters";

  // Message Analyzed
  if (analyzedMsgText) {
    analyzedMsgText.textContent = `"${data.message || rawMsg}"`;
  }

  // Confidence bar
  confidenceBar.style.width = confPct + "%";
  confidenceBar.className   = "confidence-bar-fill " + (isSpam ? "spam-fill" : "ham-fill");
  confidencePct.textContent = confPct + "%";

  resultPlaceholder.classList.add("hidden");
  resultError.classList.add("hidden");
  resultContent.classList.remove("hidden");
}

function showError(msg) {
  errorMessage.textContent = msg;
  resultPlaceholder.classList.add("hidden");
  resultContent.classList.add("hidden");
  resultError.classList.remove("hidden");
}

// ─────────────────────────────────────────────
// DASHBOARD — STATS
// ─────────────────────────────────────────────
async function loadStats() {
  try {
    const data = await apiFetch("/api/stats");
    statTotalVal.textContent = data.total    ?? "0";
    statSpamVal.textContent  = data.spam     ?? "0";
    statHamVal.textContent   = data.ham      ?? "0";
    statPctVal.textContent   = (data.spam_percent ?? "0") + "%";
    chartCenterText.textContent = data.total ?? "0";
    setSystemStatus(true, "Backend Online · SQLite Connected");
    try {
      renderDonutChart(data.spam ?? 0, data.ham ?? 0);
    } catch (chartErr) {
      console.warn("Chart rendering notice:", chartErr);
    }
  } catch (err) {
    console.warn("Stats load failed:", err.message);
    setSystemStatus(false, "Backend Disconnected");
    statTotalVal.textContent = "–";
    statSpamVal.textContent  = "–";
    statHamVal.textContent   = "–";
    statPctVal.textContent   = "–";
  }
}

function renderDonutChart(spam, ham) {
  if (typeof Chart === "undefined") {
    console.warn("Chart.js not loaded");
    return;
  }
  const canvas = document.getElementById("donut-chart");
  if (!canvas) return;

  const ctx  = canvas.getContext("2d");
  const data = (spam === 0 && ham === 0) ? [1, 0] : [spam, ham];
  const colors = ["#dc2626", "#16a34a"];

  if (donutChart) {
    donutChart.data.datasets[0].data = data;
    donutChart.update();
    return;
  }

  donutChart = new Chart(ctx, {
    type: "doughnut",
    data: {
      labels: ["Spam", "Ham"],
      datasets: [{
        data:            data,
        backgroundColor: colors,
        borderColor:     ["#fff", "#fff"],
        borderWidth:     3,
        hoverOffset:     6,
      }],
    },
    options: {
      cutout:     "72%",
      responsive: true,
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: ctx => ` ${ctx.label}: ${ctx.parsed}`,
          },
        },
      },
    },
  });
}

// ─────────────────────────────────────────────
// DASHBOARD — MODEL PERFORMANCE
// ─────────────────────────────────────────────
async function loadModelPerformance() {
  try {
    const data = await apiFetch("/api/model-performance");
    renderPerfTable(data);
  } catch (err) {
    perfTbody.innerHTML = `<tr><td colspan="5" class="table-loading">⚠ ${escapeHtml(err.message)}</td></tr>`;
  }
}

function renderPerfTable(models) {
  if (!models || models.length === 0) {
    perfTbody.innerHTML = `<tr><td colspan="5" class="table-loading">No performance data available. Train the model first.</td></tr>`;
    return;
  }

  const rows = models.map(m => {
    const bestTag = m.is_best ? `<span class="best-badge">BEST</span>` : "";
    return `
      <tr class="${m.is_best ? "best-row" : ""}">
        <td>${escapeHtml(m.model_name)}${bestTag}</td>
        <td>${pct(m.accuracy)}</td>
        <td>${pct(m.precision)}</td>
        <td>${pct(m.recall)}</td>
        <td>${pct(m.f1_score)}</td>
      </tr>`;
  });

  perfTbody.innerHTML = rows.join("");
}

// ─────────────────────────────────────────────
// HISTORY
// ─────────────────────────────────────────────
async function loadHistory() {
  try {
    allHistory = await apiFetch("/api/history");
    applyHistoryFilters();
  } catch (err) {
    historyTbody.innerHTML = `<tr><td colspan="6" class="table-loading">⚠ ${escapeHtml(err.message)}</td></tr>`;
  }
}

function applyHistoryFilters() {
  const query = historySearch.value.trim().toLowerCase();
  let rows = allHistory;

  if (activeFilter !== "all") {
    rows = rows.filter(r => (r.prediction || "").toLowerCase() === activeFilter.toLowerCase());
  }
  if (query) {
    rows = rows.filter(r => 
      (r.message || "").toLowerCase().includes(query) ||
      (r.model || "").toLowerCase().includes(query) ||
      (r.prediction || "").toLowerCase().includes(query)
    );
  }

  renderHistoryTable(rows);
}

function renderHistoryTable(records) {
  historyCount.textContent = `Showing ${records.length} record${records.length !== 1 ? "s" : ""}`;

  if (records.length === 0) {
    historyTbody.innerHTML = `<tr><td colspan="6" class="table-loading">No records found.</td></tr>`;
    return;
  }

  const rows = records.map((r) => {
    const isSpam   = (r.prediction || "").toLowerCase() === "spam";
    const badge    = isSpam
      ? `<span class="badge-spam">Spam</span>`
      : `<span class="badge-ham">Ham</span>`;
    const confPct  = Math.round(parseFloat(r.confidence) * 100) + "%";
    const msgShort = r.message.length > 60
      ? escapeHtml(r.message.slice(0, 60)) + "…"
      : escapeHtml(r.message);

    return `
      <tr>
        <td>${r.id}</td>
        <td class="msg-cell" title="${escapeHtml(r.message)}">${msgShort}</td>
        <td>${badge}</td>
        <td>${confPct}</td>
        <td>${escapeHtml(r.model)}</td>
        <td>${formatDate(r.created_at)}</td>
      </tr>`;
  });

  historyTbody.innerHTML = rows.join("");
}

// Filter buttons
filterBtns.forEach(btn => {
  btn.addEventListener("click", () => {
    filterBtns.forEach(b => b.classList.remove("active"));
    btn.classList.add("active");
    activeFilter = btn.dataset.filter;
    applyHistoryFilters();
  });
});

historySearch.addEventListener("input", applyHistoryFilters);

// Refresh buttons with visual feedback
const btnRefreshStats = document.getElementById("btn-refresh-stats");
if (btnRefreshStats) {
  btnRefreshStats.addEventListener("click", async () => {
    btnRefreshStats.disabled = true;
    const origHtml = btnRefreshStats.innerHTML;
    btnRefreshStats.innerHTML = `<span class="btn-spinner">⟳</span> Refreshing...`;
    try {
      await Promise.all([loadStats(), loadModelPerformance()]);
      btnRefreshStats.innerHTML = `✓ Refreshed!`;
    } catch {
      btnRefreshStats.innerHTML = `⚠ Failed`;
    } finally {
      setTimeout(() => {
        btnRefreshStats.innerHTML = origHtml;
        btnRefreshStats.disabled = false;
      }, 700);
    }
  });
}

const btnRefreshHistory = document.getElementById("btn-refresh-history");
if (btnRefreshHistory) {
  btnRefreshHistory.addEventListener("click", async () => {
    btnRefreshHistory.disabled = true;
    const origHtml = btnRefreshHistory.innerHTML;
    btnRefreshHistory.innerHTML = `<span class="btn-spinner">⟳</span> Refreshing...`;
    try {
      await loadHistory();
      btnRefreshHistory.innerHTML = `✓ Refreshed!`;
    } catch {
      btnRefreshHistory.innerHTML = `⚠ Failed`;
    } finally {
      setTimeout(() => {
        btnRefreshHistory.innerHTML = origHtml;
        btnRefreshHistory.disabled = false;
      }, 700);
    }
  });
}

// ─────────────────────────────────────────────
// INIT
// ─────────────────────────────────────────────
(function init() {
  loadStats();
  loadModelPerformance();
  loadHistory();
})();
