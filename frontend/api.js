/**
 * api.js — 所有後端 API 呼叫 + localStorage 管理
 */

const API_BASE = "http://localhost:5000";

// ── 通用 fetch 包裝 ─────────────────────────────
async function apiFetch(path, options = {}) {
  const res = await fetch(`${API_BASE}${path}`, options);
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.error || `API error ${res.status}`);
  }
  return res.json();
}

// ── 基金列表 ────────────────────────────────────
async function getFunds(params = {}) {
  const query = new URLSearchParams(params).toString();
  return apiFetch(`/funds${query ? "?" + query : ""}`);
}

// ── 單一基金 ────────────────────────────────────
async function getFund(fundId) {
  return apiFetch(`/funds/${fundId}`);
}

async function getFundNav(fundId, period = "3Y") {
  return apiFetch(`/funds/${fundId}/nav?period=${period}`);
}

async function getFundMetrics(fundId, period = "3Y") {
  return apiFetch(`/funds/${fundId}/metrics?period=${period}`);
}

// ── 多基金比較 ──────────────────────────────────
async function compareFunds(fundIds, period = "3Y") {
  return apiFetch("/compare", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ fund_ids: fundIds, period }),
  });
}

// ── localStorage 比較清單 ───────────────────────
const COMPARE_KEY = "fundlens_compare";

function getCompareList() {
  try { return JSON.parse(localStorage.getItem(COMPARE_KEY)) || []; }
  catch { return []; }
}

function addToCompare(fundId, fundName) {
  const list = getCompareList();
  if (list.find(f => f.id === fundId)) return false;
  if (list.length >= 5) { alert("最多比較 5 檔基金"); return false; }
  list.push({ id: fundId, name: fundName });
  localStorage.setItem(COMPARE_KEY, JSON.stringify(list));
  return true;
}

function removeFromCompare(fundId) {
  const list = getCompareList().filter(f => f.id !== fundId);
  localStorage.setItem(COMPARE_KEY, JSON.stringify(list));
}

// ── 指標評級 ────────────────────────────────────
function rateMetric(metric, value) {
  if (value === null || value === undefined) {
    return { grade: "fair", label: "無資料", fillPct: 0 };
  }
  const rules = {
    sharpe:  [
      { min: 2,         grade: "excellent", label: "優秀", fillPct: 95 },
      { min: 1,         grade: "good",      label: "良好", fillPct: 65 },
      { min: 0,         grade: "fair",      label: "普通", fillPct: 35 },
      { min: -Infinity, grade: "poor",      label: "偏差", fillPct: 10 },
    ],
    sortino: [
      { min: 2,         grade: "excellent", label: "優秀", fillPct: 95 },
      { min: 1,         grade: "good",      label: "良好", fillPct: 65 },
      { min: 0,         grade: "fair",      label: "普通", fillPct: 35 },
      { min: -Infinity, grade: "poor",      label: "偏差", fillPct: 10 },
    ],
    calmar:  [
      { min: 1,         grade: "excellent", label: "優秀", fillPct: 95 },
      { min: 0.5,       grade: "good",      label: "良好", fillPct: 65 },
      { min: 0,         grade: "fair",      label: "普通", fillPct: 35 },
      { min: -Infinity, grade: "poor",      label: "偏差", fillPct: 10 },
    ],
    alpha:   [
      { min: 0.03,      grade: "excellent", label: "優秀", fillPct: 95 },
      { min: 0,         grade: "good",      label: "良好", fillPct: 65 },
      { min: -0.02,     grade: "fair",      label: "普通", fillPct: 35 },
      { min: -Infinity, grade: "poor",      label: "偏差", fillPct: 10 },
    ],
    mdd: [
      { max: -0.05,     grade: "excellent", label: "優秀", fillPct: 95 },
      { max: -0.15,     grade: "good",      label: "良好", fillPct: 65 },
      { max: -0.25,     grade: "fair",      label: "普通", fillPct: 35 },
      { max: -Infinity, grade: "poor",      label: "偏差", fillPct: 10 },
    ],
    beta: [
      { max: 0.6,       grade: "excellent", label: "低波動", fillPct: 90 },
      { max: 0.9,       grade: "good",      label: "穩健",   fillPct: 65 },
      { max: 1.2,       grade: "fair",      label: "同步",   fillPct: 40 },
      { max: Infinity,  grade: "poor",      label: "高波動", fillPct: 15 },
    ],
  };

  const metricRules = rules[metric];
  if (!metricRules) return { grade: "fair", label: "普通", fillPct: 50 };

  if (metric === "mdd") {
    for (const r of metricRules) {
      if (value >= r.max) return { grade: r.grade, label: r.label, fillPct: r.fillPct };
    }
  } else if (metric === "beta") {
    for (const r of metricRules) {
      if (value <= r.max) return { grade: r.grade, label: r.label, fillPct: r.fillPct };
    }
  } else {
    for (const r of metricRules) {
      if (value >= r.min) return { grade: r.grade, label: r.label, fillPct: r.fillPct };
    }
  }
  return { grade: "fair", label: "普通", fillPct: 50 };
}

// ── 指標 Tooltip 說明 ───────────────────────────
const METRIC_DESCRIPTIONS = {
  sharpe:   "每承受一單位總風險，所獲得的超額報酬。數值越高越好。",
  sortino:  "與 Sharpe 類似，但只計算下行風險（虧損波動），更適合評估防禦型基金。",
  mdd:      "歷史上最大的跌幅（從高點到谷底）。數值越接近 0% 越好。",
  beta:     "基金與大盤的連動程度。β=1 表示與大盤同步，>1 放大波動，<1 較穩定。",
  alpha:    "扣除市場風險後的超額報酬。> 0 代表基金經理人創造了額外價值。",
  calmar:   "年化報酬率除以最大回檔，同時衡量報酬與最大損失，數值越高越好。",
  annualized_return: "以年為單位換算的平均報酬率。",
  annualized_std:    "報酬率的年化波動幅度，越低代表走勢越穩定。",
};

// ── 格式化輔助 ──────────────────────────────────
function fmt(value, type) {
  if (value === null || value === undefined) return "—";
  switch (type) {
    case "pct":    return (value * 100).toFixed(1) + "%";
    case "pct2":   return (value * 100).toFixed(2) + "%";
    case "ratio":  return value.toFixed(2);
    case "nav":    return value.toFixed(4);
    case "aum":    return value.toFixed(1) + " 億";
    default:       return String(value);
  }
}

// ── 顯示錯誤訊息 ────────────────────────────────
function showError(containerId, msg) {
  const el = document.getElementById(containerId);
  if (el) el.innerHTML = `<p class="error-msg">⚠️ ${msg}</p>`;
}