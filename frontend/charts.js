/**
 * charts.js — 所有 Chart.js 圖表邏輯
 *
 * 依賴：Chart.js（CDN）
 * 使用方式：在 HTML 中先引入 Chart.js，再引入本檔
 */

// ── 共用色彩（對應 CSS 變數）──────────────────
const CHART_COLORS = {
  primary:   "#1E3A5F",
  secondary: "#2E86AB",
  positive:  "#06A77D",
  negative:  "#D62839",
  muted:     "#9CA3AF",
  // 多基金比較用的顏色序列
  series: ["#2E86AB", "#06A77D", "#F59E0B", "#8B5CF6", "#D62839"],
};

// ── 共用 Chart.js 預設設定 ────────────────────
const BASE_CHART_OPTIONS = {
  responsive: true,
  maintainAspectRatio: true,
  plugins: {
    legend: {
      labels: {
        font: { family: "'Inter', 'Noto Sans TC', sans-serif", size: 12 },
        color: "#1A1A2E",
      },
    },
    tooltip: {
      backgroundColor: "#1A1A2E",
      titleFont: { size: 12 },
      bodyFont: { size: 12 },
      padding: 10,
      cornerRadius: 6,
    },
  },
  scales: {
    x: {
      grid: { color: "#EEF0F3" },
      ticks: { color: "#6B7280", maxTicksLimit: 8 },
    },
    y: {
      grid: { color: "#EEF0F3" },
      ticks: { color: "#6B7280" },
    },
  },
};

// ── NAV 走勢折線圖 ─────────────────────────────
let navChartInstance = null;

/**
 * 繪製 NAV 走勢圖（單基金）
 * @param {string} canvasId - canvas 元素的 id
 * @param {Array<{date: string, nav: number}>} navData
 *
 * TODO:
 * 1. 若 navChartInstance 存在，先 .destroy()
 * 2. 準備 labels（date）和 data（nav）
 * 3. 建立 Chart：type 'line'，單條線，填色區域
 * 4. x 軸格式化日期（月/年）
 * 5. y 軸顯示 NAV 數值，自動縮放
 * 6. hover 時顯示日期 + NAV
 */
function drawNavChart(canvasId, navData) {
  // TODO: 實作
  if (navChartInstance) navChartInstance.destroy();

  const ctx = document.getElementById(canvasId)?.getContext("2d");
  if (!ctx) return;

  // TODO: 建立 Chart
  navChartInstance = new Chart(ctx, {
    type: "line",
    data: {
      labels: [], // TODO: navData.map(d => d.date)
      datasets: [{
        label: "NAV",
        data: [],  // TODO: navData.map(d => d.nav)
        borderColor: CHART_COLORS.secondary,
        backgroundColor: "rgba(46, 134, 171, 0.08)",
        fill: true,
        tension: 0.3,
        pointRadius: 0,
        borderWidth: 2,
      }],
    },
    options: {
      ...BASE_CHART_OPTIONS,
      // TODO: 調整 y 軸、tooltip 格式
    },
  });
}

// ── 基準指數比較圖 ──────────────────────────────
let benchmarkChartInstance = null;

/**
 * 繪製基金 vs 基準指數的雙折線圖（起點標準化為 100）
 * @param {string} canvasId
 * @param {Array<{date, normalized}>} fundSeries    - 基金（已標準化）
 * @param {Array<{date, normalized}>} benchmarkSeries - 指數（已標準化）
 * @param {string} fundName
 * @param {string} benchmarkName
 *
 * TODO:
 * 1. 若 benchmarkChartInstance 存在，先 .destroy()
 * 2. 兩條線：基金（藍）、指數（灰）
 * 3. y 軸標籤：顯示相對績效（100 = 起點）
 */
function drawBenchmarkChart(canvasId, fundSeries, benchmarkSeries, fundName, benchmarkName) {
  // TODO: 實作
  if (benchmarkChartInstance) benchmarkChartInstance.destroy();

  const ctx = document.getElementById(canvasId)?.getContext("2d");
  if (!ctx) return;

  benchmarkChartInstance = new Chart(ctx, {
    type: "line",
    data: {
      labels: [], // TODO
      datasets: [
        {
          label: fundName || "基金",
          data: [],  // TODO: fundSeries.map(d => d.normalized)
          borderColor: CHART_COLORS.secondary,
          backgroundColor: "transparent",
          tension: 0.3,
          pointRadius: 0,
          borderWidth: 2,
        },
        {
          label: benchmarkName || "基準指數",
          data: [],  // TODO: benchmarkSeries.map(d => d.normalized)
          borderColor: CHART_COLORS.muted,
          backgroundColor: "transparent",
          tension: 0.3,
          pointRadius: 0,
          borderWidth: 1.5,
          borderDash: [4, 4],
        },
      ],
    },
    options: {
      ...BASE_CHART_OPTIONS,
      // TODO: 調整 tooltip
    },
  });
}

// ── 多基金走勢疊圖 ──────────────────────────────
let overlayChartInstance = null;

/**
 * 繪製多基金報酬走勢疊圖
 * @param {string} canvasId
 * @param {Array<{name: string, series: Array<{date, normalized}>}>} funds
 *
 * TODO:
 * 1. 每檔基金一條線，顏色用 CHART_COLORS.series 輪流分配
 * 2. 所有線的 labels（x 軸日期）取最長那條的日期序列
 * 3. 圖例顯示基金簡稱
 */
function drawOverlayChart(canvasId, funds) {
  // TODO: 實作
  if (overlayChartInstance) overlayChartInstance.destroy();

  const ctx = document.getElementById(canvasId)?.getContext("2d");
  if (!ctx) return;

  overlayChartInstance = new Chart(ctx, {
    type: "line",
    data: {
      labels: [], // TODO
      datasets: funds.map((fund, i) => ({
        label: fund.name,
        data: [],  // TODO: fund.series.map(d => d.normalized)
        borderColor: CHART_COLORS.series[i],
        backgroundColor: "transparent",
        tension: 0.3,
        pointRadius: 0,
        borderWidth: 2,
      })),
    },
    options: { ...BASE_CHART_OPTIONS },
  });
}

// ── 指標雷達圖 ─────────────────────────────────
let radarChartInstance = null;

/**
 * 繪製指標雷達圖
 * @param {string} canvasId
 * @param {Array<{name: string, metrics: Object}>} funds
 *
 * TODO:
 * 1. 各軸：Sharpe / Sortino / Calmar / Alpha / (1-|Beta-1|) / (1-|MDD|)
 * 2. 注意 Beta 和 MDD 是「越接近某值越好」，需轉換方向
 * 3. 各軸數值需先正規化到 0–1 範圍（避免不同量綱影響圖形）
 * 4. 每檔基金一個多邊形，顏色用 CHART_COLORS.series
 * 5. 填色透明度 0.15，邊框寬度 2
 */
function drawRadarChart(canvasId, funds) {
  // TODO: 實作
  if (radarChartInstance) radarChartInstance.destroy();

  const ctx = document.getElementById(canvasId)?.getContext("2d");
  if (!ctx) return;

  const AXES = ["Sharpe", "Sortino", "Calmar", "Alpha", "Beta 穩定性", "回檔抗性"];

  radarChartInstance = new Chart(ctx, {
    type: "radar",
    data: {
      labels: AXES,
      datasets: funds.map((fund, i) => ({
        label: fund.name,
        data: [], // TODO: 正規化後的各軸數值
        borderColor: CHART_COLORS.series[i],
        backgroundColor: CHART_COLORS.series[i] + "26", // 15% 透明
        borderWidth: 2,
        pointRadius: 3,
      })),
    },
    options: {
      responsive: true,
      plugins: {
        legend: BASE_CHART_OPTIONS.plugins.legend,
      },
      scales: {
        r: {
          min: 0,
          max: 1,
          ticks: { display: false },
          grid: { color: "#DDE1E7" },
          pointLabels: {
            font: { size: 12 },
            color: "#1A1A2E",
          },
        },
      },
    },
  });
}

// ── 輔助：渲染指標卡 ──────────────────────────
/**
 * 動態渲染指標卡到容器
 * @param {string} containerId - .metrics-grid 的 id
 * @param {Object} metrics - 指標物件（sharpe, sortino, mdd, beta, alpha, calmar）
 *
 * TODO:
 * 1. 定義指標清單（label, key, format）
 * 2. 對每個指標呼叫 rateMetric() 取得評級
 * 3. 建立 .metric-card HTML 結構，插入容器
 * 4. 綁定 ⓘ 按鈕的 Tooltip 顯示邏輯
 */
function renderMetricCards(containerId, metrics) {
  const container = document.getElementById(containerId);
  if (!container) return;

  const METRIC_DEFS = [
    { key: "sharpe",  label: "Sharpe Ratio", format: v => v?.toFixed(2) ?? "—" },
    { key: "sortino", label: "Sortino Ratio", format: v => v?.toFixed(2) ?? "—" },
    { key: "mdd",     label: "MDD",           format: v => v != null ? (v * 100).toFixed(1) + "%" : "—" },
    { key: "beta",    label: "Beta",           format: v => v?.toFixed(2) ?? "—" },
    { key: "alpha",   label: "Alpha",          format: v => v != null ? (v * 100).toFixed(2) + "%" : "—" },
    { key: "calmar",  label: "Calmar Ratio",   format: v => v?.toFixed(2) ?? "—" },
  ];

  container.innerHTML = "";

  METRIC_DEFS.forEach(({ key, label, format }) => {
    const value = metrics[key];
    const { grade, label: gradeLabel, fillPct } = rateMetric(key, value);

    // TODO: 建立完整的指標卡 HTML
    const card = document.createElement("div");
    card.className = `metric-card grade-${grade}`;
    card.innerHTML = `
      <span class="metric-label">${label}</span>
      <button class="metric-info-btn" data-metric="${key}">ⓘ</button>
      <div class="metric-value">${format(value)}</div>
      <div class="metric-grade-bar">
        <div class="metric-grade-fill" style="width: ${fillPct}%"></div>
      </div>
      <span class="metric-grade-label">${gradeLabel}</span>
      <!-- TODO: 同類均值（需後端提供） -->
    `;

    // TODO: 綁定 ⓘ 按鈕事件（顯示 Tooltip 或 Modal）

    container.appendChild(card);
  });
}
