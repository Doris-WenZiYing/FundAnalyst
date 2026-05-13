/**
 * charts.js — 所有 Chart.js 圖表邏輯（深色主題）
 * 依賴：Chart.js 4（CDN），api.js（rateMetric、METRIC_DESCRIPTIONS、fmt）
 */

// ── 色彩 ───────────────────────────────────────
const CHART_COLORS = {
  gold:     "#E6B84A",
  positive: "#3DD68C",
  negative: "#FF6B6B",
  blue:     "#60A5FA",
  muted:    "#4D5566",
  grid:     "rgba(255,255,255,0.06)",
  text:     "#8B929D",
  series:   ["#60A5FA", "#3DD68C", "#E6B84A", "#A78BFA", "#FF6B6B"],
};

// ── 深色主題 Base Options ────────────────────
const BASE_OPTIONS = {
  responsive: true,
  maintainAspectRatio: true,
  animation: { duration: 500 },
  plugins: {
    legend: {
      labels: {
        font:     { family: "'IBM Plex Sans', sans-serif", size: 12 },
        color:    CHART_COLORS.text,
        boxWidth: 12,
        padding:  16,
      },
    },
    tooltip: {
      backgroundColor: "#1E2535",
      borderColor:      "rgba(255,255,255,0.1)",
      borderWidth:      1,
      titleColor:       "#E6EDF3",
      bodyColor:        "#8B929D",
      titleFont:        { size: 12, family: "'IBM Plex Sans', sans-serif" },
      bodyFont:         { size: 12, family: "'IBM Plex Mono', monospace" },
      padding:          12,
      cornerRadius:     8,
    },
  },
  scales: {
    x: {
      grid:  { color: CHART_COLORS.grid, drawBorder: false },
      ticks: {
        color:         CHART_COLORS.text,
        maxTicksLimit: 8,
        font:          { size: 11 },
        callback: function (val) {
          const d = this.getLabelForValue(val);
          return d ? d.slice(0, 7) : "";   // YYYY-MM
        },
      },
      border: { color: CHART_COLORS.grid },
    },
    y: {
      grid:  { color: CHART_COLORS.grid, drawBorder: false },
      ticks: { color: CHART_COLORS.text, font: { size: 11 } },
      border: { color: CHART_COLORS.grid },
    },
  },
};

// ─────────────────────────────────────────────────
// NAV 走勢折線圖（單 ETF）
// ─────────────────────────────────────────────────
let navChartInstance = null;

function drawNavChart(canvasId, navData) {
  if (navChartInstance) navChartInstance.destroy();
  const ctx = document.getElementById(canvasId)?.getContext("2d");
  if (!ctx || !navData?.length) return;

  navChartInstance = new Chart(ctx, {
    type: "line",
    data: {
      labels: navData.map(d => d.date),
      datasets: [{
        label:           "收盤價",
        data:            navData.map(d => d.nav),
        borderColor:     CHART_COLORS.gold,
        backgroundColor: "rgba(230,184,74,0.06)",
        fill:        true,
        tension:     0.3,
        pointRadius: 0,
        borderWidth: 2,
      }],
    },
    options: {
      ...BASE_OPTIONS,
      plugins: {
        ...BASE_OPTIONS.plugins,
        legend: { display: false },
        tooltip: {
          ...BASE_OPTIONS.plugins.tooltip,
          callbacks: {
            title: items => items[0].label,
            label: item  => ` ${Number(item.raw).toFixed(2)}`,
          },
        },
      },
      scales: {
        ...BASE_OPTIONS.scales,
        y: {
          ...BASE_OPTIONS.scales.y,
          ticks: {
            ...BASE_OPTIONS.scales.y.ticks,
            callback: v => Number(v).toFixed(0),
          },
        },
      },
    },
  });
}

// ─────────────────────────────────────────────────
// ETF vs 基準指數（雙折線，起點 = 100）
// ─────────────────────────────────────────────────
let benchmarkChartInstance = null;

function drawBenchmarkChart(canvasId, fundSeries, benchmarkSeries, fundName, benchmarkName) {
  if (benchmarkChartInstance) benchmarkChartInstance.destroy();
  const ctx = document.getElementById(canvasId)?.getContext("2d");
  if (!ctx || !fundSeries?.length) return;

  benchmarkChartInstance = new Chart(ctx, {
    type: "line",
    data: {
      labels: fundSeries.map(d => d.date),
      datasets: [
        {
          label:           fundName || "ETF",
          data:            fundSeries.map(d => d.value),
          borderColor:     CHART_COLORS.gold,
          backgroundColor: "transparent",
          tension:     0.3,
          pointRadius: 0,
          borderWidth: 2,
        },
        {
          label:           benchmarkName || "0050",
          data:            (benchmarkSeries || []).map(d => d.value),
          borderColor:     CHART_COLORS.muted,
          backgroundColor: "transparent",
          tension:     0.3,
          pointRadius: 0,
          borderWidth: 1.5,
          borderDash:  [5, 4],
        },
      ],
    },
    options: {
      ...BASE_OPTIONS,
      plugins: {
        ...BASE_OPTIONS.plugins,
        tooltip: {
          ...BASE_OPTIONS.plugins.tooltip,
          callbacks: {
            label: item => ` ${item.dataset.label}：${Number(item.raw).toFixed(1)}`,
          },
        },
      },
      scales: {
        ...BASE_OPTIONS.scales,
        y: {
          ...BASE_OPTIONS.scales.y,
          ticks: {
            ...BASE_OPTIONS.scales.y.ticks,
            callback: v => Number(v).toFixed(0),
          },
        },
      },
    },
  });
}

// ─────────────────────────────────────────────────
// 多 ETF 走勢疊圖
// ─────────────────────────────────────────────────
let overlayChartInstance = null;

function drawOverlayChart(canvasId, funds) {
  if (overlayChartInstance) overlayChartInstance.destroy();
  const ctx = document.getElementById(canvasId)?.getContext("2d");
  if (!ctx || !funds?.length) return;

  const longest = funds.reduce((a, b) => a.series.length >= b.series.length ? a : b);

  overlayChartInstance = new Chart(ctx, {
    type: "line",
    data: {
      labels: longest.series.map(d => d.date),
      datasets: funds.map((fund, i) => ({
        label:           fund.name,
        data:            fund.series.map(d => d.normalized),
        borderColor:     CHART_COLORS.series[i % CHART_COLORS.series.length],
        backgroundColor: "transparent",
        tension:     0.3,
        pointRadius: 0,
        borderWidth: 2,
      })),
    },
    options: {
      ...BASE_OPTIONS,
      plugins: {
        ...BASE_OPTIONS.plugins,
        tooltip: {
          ...BASE_OPTIONS.plugins.tooltip,
          callbacks: {
            label: item => ` ${item.dataset.label}：${Number(item.raw).toFixed(1)}`,
          },
        },
      },
      scales: {
        ...BASE_OPTIONS.scales,
        y: {
          ...BASE_OPTIONS.scales.y,
          ticks: {
            ...BASE_OPTIONS.scales.y.ticks,
            callback: v => Number(v).toFixed(0),
          },
        },
      },
    },
  });
}

// ─────────────────────────────────────────────────
// 指標雷達圖
// ─────────────────────────────────────────────────
let radarChartInstance = null;

function _metricToScore(key, value) {
  if (value === null || value === undefined) return 0;
  const clamp = (v, lo, hi) => Math.min(Math.max(v, lo), hi);
  switch (key) {
    case "sharpe":  return clamp((value + 1) / 4,           0, 1);
    case "sortino": return clamp((value + 1) / 4,           0, 1);
    case "calmar":  return clamp(value / 2,                 0, 1);
    case "alpha":   return clamp((value + 0.05) / 0.15,     0, 1);
    case "beta":    return clamp(1 - value / 2,             0, 1);
    case "mdd":     return clamp(1 - Math.abs(value) / 0.5, 0, 1);
    default:        return 0;
  }
}

function drawRadarChart(canvasId, funds) {
  if (radarChartInstance) radarChartInstance.destroy();
  const ctx = document.getElementById(canvasId)?.getContext("2d");
  if (!ctx || !funds?.length) return;

  const AXIS_KEYS   = ["sharpe", "sortino", "calmar", "alpha", "beta", "mdd"];
  const AXIS_LABELS = ["Sharpe", "Sortino", "Calmar", "Alpha", "Beta 穩定性", "回檔抗性"];

  radarChartInstance = new Chart(ctx, {
    type: "radar",
    data: {
      labels: AXIS_LABELS,
      datasets: funds.map((fund, i) => ({
        label:                fund.name,
        data:                 AXIS_KEYS.map(k => _metricToScore(k, fund.metrics[k])),
        borderColor:          CHART_COLORS.series[i % CHART_COLORS.series.length],
        backgroundColor:      CHART_COLORS.series[i % CHART_COLORS.series.length] + "22",
        borderWidth:          2,
        pointRadius:          3,
        pointBackgroundColor: CHART_COLORS.series[i % CHART_COLORS.series.length],
      })),
    },
    options: {
      responsive: true,
      animation: { duration: 500 },
      plugins: {
        legend: BASE_OPTIONS.plugins.legend,
        tooltip: {
          ...BASE_OPTIONS.plugins.tooltip,
          callbacks: {
            label: item => ` ${item.dataset.label}：${(item.raw * 100).toFixed(0)} 分`,
          },
        },
      },
      scales: {
        r: {
          min:  0,
          max:  1,
          ticks: { display: false },
          grid:  { color: CHART_COLORS.grid },
          angleLines: { color: CHART_COLORS.grid },
          pointLabels: {
            font:  { size: 11, family: "'IBM Plex Sans', sans-serif" },
            color: CHART_COLORS.text,
          },
        },
      },
    },
  });
}

// ─────────────────────────────────────────────────
// 指標卡渲染
// ─────────────────────────────────────────────────
let _tooltipEl = null;

function _getTooltipEl() {
  if (_tooltipEl) return _tooltipEl;
  _tooltipEl = document.createElement("div");
  _tooltipEl.style.cssText = [
    "position:fixed",
    "background:#1E2535",
    "color:#E6EDF3",
    "border:1px solid rgba(255,255,255,0.1)",
    "padding:10px 14px",
    "border-radius:8px",
    "font-size:0.78rem",
    "font-family:'IBM Plex Sans',sans-serif",
    "max-width:220px",
    "line-height:1.6",
    "z-index:9999",
    "pointer-events:none",
    "opacity:0",
    "transition:opacity 0.15s",
    "box-shadow:0 8px 24px rgba(0,0,0,0.5)",
  ].join(";");
  document.body.appendChild(_tooltipEl);
  return _tooltipEl;
}

function renderMetricCards(containerId, metrics) {
  const container = document.getElementById(containerId);
  if (!container) return;

  const DEFS = [
    { key: "sharpe",            label: "Sharpe Ratio",  fmt: v => v?.toFixed(2) ?? "—" },
    { key: "sortino",           label: "Sortino Ratio", fmt: v => v?.toFixed(2) ?? "—" },
    { key: "mdd",               label: "MDD",           fmt: v => v != null ? (v * 100).toFixed(1) + "%" : "—" },
    { key: "beta",              label: "Beta",          fmt: v => v?.toFixed(2) ?? "—" },
    { key: "alpha",             label: "Alpha",         fmt: v => v != null ? (v * 100).toFixed(2) + "%" : "—" },
    { key: "calmar",            label: "Calmar Ratio",  fmt: v => v?.toFixed(2) ?? "—" },
    { key: "annualized_return", label: "年化報酬",      fmt: v => v != null ? (v * 100).toFixed(1) + "%" : "—" },
    { key: "annualized_std",    label: "年化波動率",    fmt: v => v != null ? (v * 100).toFixed(1) + "%" : "—" },
  ];

  const GRADE_COLORS = {
    excellent: "#3DD68C",
    good:      "#60A5FA",
    fair:      "#4D5566",
    poor:      "#FF6B6B",
  };

  container.innerHTML = "";
  const tip = _getTooltipEl();

  DEFS.forEach(({ key, label, fmt }) => {
    const value      = metrics[key];
    const { grade, label: gradeLabel, fillPct } = rateMetric(key, value);
    const gradeColor = GRADE_COLORS[grade] || "#4D5566";

    const card = document.createElement("div");
    card.className = `metric-card grade-${grade}`;
    card.innerHTML = `
      <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:2px">
        <span class="metric-label">${label}</span>
        <button class="metric-info-btn" aria-label="${label} 說明">ⓘ</button>
      </div>
      <div class="metric-value">${fmt(value)}</div>
      <div class="metric-grade-bar">
        <div class="metric-grade-fill" style="width:${fillPct}%;background:${gradeColor}"></div>
      </div>
      <span class="metric-grade-label" style="color:${gradeColor}">${gradeLabel}</span>
    `;

    const btn = card.querySelector(".metric-info-btn");
    btn.addEventListener("mouseenter", () => {
      tip.textContent  = METRIC_DESCRIPTIONS[key] || "";
      tip.style.opacity = "1";
    });
    btn.addEventListener("mousemove", e => {
      tip.style.left = (e.clientX + 14) + "px";
      tip.style.top  = (e.clientY - 8)  + "px";
    });
    btn.addEventListener("mouseleave", () => {
      tip.style.opacity = "0";
    });

    container.appendChild(card);
  });
}