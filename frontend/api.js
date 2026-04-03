/**
 * api.js — 所有後端 API 呼叫集中在此
 */

const API_BASE = "http://localhost:5000";

// ── 通用 fetch 包裝 ─────────────────────────────
async function apiFetch(path, options = {}) {
  // TODO:
  // - 加上統一的 error handling
  // - 若 response 不是 2xx，throw 帶有訊息的 Error
  // - 可加 loading 狀態管理
  const res = await fetch(`${API_BASE}${path}`, options);
  if (!res.ok) throw new Error(`API error: ${res.status} ${path}`);
  return res.json();
}

// ── 基金列表 ────────────────────────────────────
/**
 * 取得基金列表
 * @param {Object} params - { q, type, sort, limit }
 * @returns {Promise<Array>}
 *
 * TODO:
 * - 將 params 轉為 URLSearchParams 附到 /funds
 */
async function getFunds(params = {}) {
  // TODO: 實作
  const query = new URLSearchParams(params).toString();
  return apiFetch(`/funds${query ? "?" + query : ""}`);
}

// ── 單一基金 ────────────────────────────────────
/**
 * 取得單一基金基本資訊
 * @param {string} fundId
 */
async function getFund(fundId) {
  // TODO: 實作
  return apiFetch(`/funds/${fundId}`);
}

/**
 * 取得基金歷史 NAV
 * @param {string} fundId
 * @param {string} period - '1Y' | '3Y' | '5Y'
 */
async function getFundNav(fundId, period = "3Y") {
  // TODO: 實作
  return apiFetch(`/funds/${fundId}/nav?period=${period}`);
}

/**
 * 取得基金風險指標
 * @param {string} fundId
 * @param {string} period - '1Y' | '3Y' | '5Y'
 */
async function getFundMetrics(fundId, period = "3Y") {
  // TODO: 實作
  return apiFetch(`/funds/${fundId}/metrics?period=${period}`);
}

// ── 多基金比較 ──────────────────────────────────
/**
 * 多基金比較
 * @param {string[]} fundIds - 2–5 個基金 id
 * @param {string} period
 */
async function compareFunds(fundIds, period = "3Y") {
  // TODO: 實作
  return apiFetch("/compare", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ fund_ids: fundIds, period }),
  });
}

// ── localStorage 比較清單管理 ───────────────────
const COMPARE_KEY = "fundlens_compare";

function getCompareList() {
  // TODO: 從 localStorage 讀取，回傳 fund_id 陣列
  try {
    return JSON.parse(localStorage.getItem(COMPARE_KEY)) || [];
  } catch {
    return [];
  }
}

function addToCompare(fundId) {
  // TODO:
  // - 讀取現有清單
  // - 若已存在則不重複加入
  // - 若超過 5 檔，提示使用者
  // - 寫回 localStorage
  const list = getCompareList();
  if (list.includes(fundId)) return false;
  if (list.length >= 5) {
    alert("最多比較 5 檔基金");
    return false;
  }
  list.push(fundId);
  localStorage.setItem(COMPARE_KEY, JSON.stringify(list));
  return true;
}

function removeFromCompare(fundId) {
  // TODO: 移除指定 id，寫回 localStorage
  const list = getCompareList().filter(id => id !== fundId);
  localStorage.setItem(COMPARE_KEY, JSON.stringify(list));
}

// ── 指標評級輔助 ────────────────────────────────
/**
 * 計算指標評級（供指標卡用）
 * @param {string} metric - 指標名稱
 * @param {number} value
 * @returns {{ grade: 'excellent'|'good'|'fair'|'poor', label: string, fillPct: number }}
 *
 * TODO: 依照 spec 6.3 的評級對照表實作各指標邏輯
 * Sharpe：> 2 優秀 / 1-2 良好 / 0-1 普通 / <0 偏差
 * Sortino：TODO 定義門檻
 * MDD：TODO 定義門檻（值為負，越接近 0 越好）
 * Beta：TODO 定義門檻
 * Alpha：TODO 定義門檻
 * Calmar：TODO 定義門檻
 */
function rateMetric(metric, value) {
  // TODO: 實作各指標評級邏輯
  return { grade: "fair", label: "普通", fillPct: 50 };
}

/**
 * 指標的 Tooltip 說明文字
 * TODO: 補上所有指標的中文說明
 */
const METRIC_DESCRIPTIONS = {
  sharpe:   "每承受一單位總風險，所獲得的超額報酬。數值越高越好。",
  sortino:  "與 Sharpe 類似，但只計算下行風險（虧損波動），更適合評估防禦型基金。",
  mdd:      "歷史上最大的跌幅（從高點到谷底）。數值越接近 0% 越好。",
  beta:     "基金與大盤的連動程度。β=1 表示與大盤同步，>1 放大波動，<1 較穩定。",
  alpha:    "扣除市場風險後的超額報酬。> 0 代表基金經理人創造了額外價值。",
  calmar:   "年化報酬率除以最大回檔，同時衡量報酬與最大損失，數值越高越好。",
  // TODO: 補充其他指標
};
