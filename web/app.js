/* Google Ads Optimizer UI */
const state = {
  days: 30,
  overview: null,
  chart: null,
  models: [],
  model: null,
  history: [],
  chatBusy: false,
  chatId: null,
  chats: [],
  keywords: [],
  ads: [],
  creatives: [],
  setupGuide: null,
  gaqlLast: null,
  gaqlView: "table",
  analyticsLoadedForDays: null,
  analyticsBusy: false,
  optimizeData: null,
  optimizeBusy: false,
  currency: "PLN",
  pending: 0,
  loadLabel: "Loading data…",
  pendingAttachments: [],
  creativesFetchedAt: null,
  creativesBusy: false,
  campaigns: [],
  searchTerms: [],
  searchTermsBusy: false,
  pendingConfirmId: null,
};

const titles = {
  chat: "AI Assistant",
  overview: "Overview",
  campaigns: "Campaigns",
  wizard: "New campaign",
  keywords: "Keywords",
  searchterms: "Search terms",
  ads: "Ads",
  creatives: "Creatives",
  recommendations: "Optimize",
  analytics: "Analytics",
  gaql: "GAQL",
  playbook: "Playbook",
  setup: "Setup",
};

const money = (n) => {
  const code = (state.currency || "USD").toUpperCase();
  try {
    return new Intl.NumberFormat("pl-PL", {
      style: "currency",
      currency: code,
      maximumFractionDigits: 2,
    }).format(n || 0);
  } catch {
    return `${Number(n || 0).toFixed(2)} ${code}`;
  }
};
const num = (n) => new Intl.NumberFormat("en-US").format(n || 0);
const pct = (n) => `${((n || 0) * 100).toFixed(2)}%`;

function loaderLabelFor(path) {
  if (path.startsWith("/api/chat")) return "Agent is working…";
  if (path.startsWith("/api/analytics")) return "Loading Analytics…";
  if (path.startsWith("/api/conversion-goals")) return "Loading conversion goals…";
  if (path.startsWith("/api/gaql")) return "Running GAQL…";
  if (path.startsWith("/api/keywords")) return "Loading keywords…";
  if (path.startsWith("/api/campaigns")) return "Loading campaigns…";
  if (path.startsWith("/api/search-terms")) return "Loading search terms…";
  if (path.startsWith("/api/mutate") || path.startsWith("/api/mutations")) return "Applying mutation…";
  if (path.startsWith("/api/overview")) return "Loading overview…";
  if (path.startsWith("/api/models")) return "Loading models…";
  if (path.startsWith("/api/setup/oauth")) return "Waiting for Google sign-in…";
  if (path.startsWith("/api/setup")) return "Saving credentials…";
  return "Loading data…";
}

function updateGlobalLoader() {
  const box = document.getElementById("globalLoader");
  const text = document.getElementById("globalLoaderText");
  const refreshLabel = document.getElementById("refreshLabel");
  if (!box) return;
  const busy = state.pending > 0;
  box.hidden = !busy;
  box.setAttribute("aria-busy", busy ? "true" : "false");
  document.body.classList.toggle("is-loading", busy);
  if (text) text.textContent = state.loadLabel || "Loading data…";
  if (refreshLabel) refreshLabel.textContent = busy ? "Loading…" : "Refresh";
}

function beginLoad(label) {
  state.pending += 1;
  if (label) state.loadLabel = label;
  updateGlobalLoader();
}

function endLoad() {
  state.pending = Math.max(0, state.pending - 1);
  if (!state.pending) state.loadLabel = "Loading data…";
  updateGlobalLoader();
}

async function api(path, options = {}) {
  const { silent = false, loadLabel, ...fetchOpts } = options;
  if (!silent) beginLoad(loadLabel || loaderLabelFor(path));
  try {
    const res = await fetch(path, {
      headers: { "Content-Type": "application/json" },
      ...fetchOpts,
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      const detail = err.detail;
      const msg =
        typeof detail === "string"
          ? detail
          : (detail && JSON.stringify(detail)) || res.statusText;
      throw new Error(msg);
    }
    return res.json();
  } finally {
    if (!silent) endLoad();
  }
}

function el(html) {
  const t = document.createElement("template");
  t.innerHTML = html.trim();
  return t.content.firstElementChild;
}

function statusBadge(status) {
  const s = String(status || "").toLowerCase();
  if (s === "no_ad" || s === "missing") {
    return `<span class="badge paused">NO AD</span>`;
  }
  const cls = s.includes("enable") ? "enabled" : "paused";
  return `<span class="badge ${cls}">${status || "—"}</span>`;
}

function severityBadge(sev) {
  return `<span class="badge ${sev}">${sev}</span>`;
}

function strengthBadge(strength) {
  const s = String(strength || "UNKNOWN").toUpperCase();
  if (s === "MISSING") return `<span class="badge paused" title="Нет RSA в группе">NO AD</span>`;
  const cls = `strength-${s.toLowerCase()}`;
  const tip =
    s === "PENDING"
      ? "Ad Strength ещё считается Google (часто часы после создания/правки). Статус показа объявления — отдельное поле ENABLED/PAUSED."
      : `Ad Strength (сила объявления): ${s}`;
  const label = s;
  return `<span class="badge ${cls}" title="${escapeAttr(tip)}">${escapeHtml(label)}</span>`;
}

function strengthRank(strength) {
  const order = {
    INCOMPLETE: 0,
    POOR: 1,
    PENDING: 2,
    AVERAGE: 3,
    GOOD: 4,
    EXCELLENT: 5,
  };
  return order[String(strength || "").toUpperCase()] ?? 9;
}

function renderTable(container, columns, rows) {
  const head = columns.map((c) => `<th>${c.label}</th>`).join("");
  const body = rows
    .map((row) => {
      const cells = columns
        .map((c) => `<td>${c.render ? c.render(row) : row[c.key] ?? "—"}</td>`)
        .join("");
      return `<tr>${cells}</tr>`;
    })
    .join("");
  container.innerHTML = `<table><thead><tr>${head}</tr></thead><tbody>${body || `<tr><td colspan="${columns.length}">No data</td></tr>`}</tbody></table>`;
}

function renderKpis(totals) {
  const items = [
    { label: "Cost", value: money(totals.cost), hint: "Spend in period" },
    { label: "Conversions", value: num(totals.conversions), hint: "All conversion actions" },
    { label: "CPA", value: money(totals.cpa), hint: "Cost / conversions" },
    { label: "ROAS", value: `${(totals.roas || 0).toFixed(2)}x`, hint: "Conv. value / cost" },
  ];
  document.getElementById("kpiGrid").innerHTML = items
    .map(
      (i) => `<div class="kpi"><div class="label">${i.label}</div><div class="value">${i.value}</div><div class="delta">${i.hint}</div></div>`
    )
    .join("");
}

function renderRecs(target, items, limit = 99) {
  const list = (items || []).slice(0, limit);
  target.innerHTML = list
    .map(
      (r) => `<article class="rec">
        <div class="rec-top">${severityBadge(r.severity)}<strong>${escapeHtml(r.action_label || r.action)}</strong></div>
        <p><b>${escapeHtml(r.entity_name)}</b> — ${escapeHtml(r.reason)}</p>
      </article>`
    )
    .join("") || `<p class="muted">No recommendations.</p>`;
}

function renderOptimizeView() {
  const data = state.optimizeData;
  const note = document.getElementById("optNote");
  const kpis = document.getElementById("optKpis");
  const list = document.getElementById("recsFull");
  if (!note || !list) return;
  if (!data) {
    note.textContent = "Open this tab to run the audit.";
    return;
  }
  const summary = data.summary || {};
  const thresholds = data.thresholds || {};
  note.textContent =
    `${data.note || "Live audit"} · lookback ${data.lookback_days || state.days}d` +
    (thresholds.max_cpa != null ? ` · max CPA ${thresholds.max_cpa}` : "");

  if (kpis) {
    kpis.innerHTML = [
      { label: "Total", value: num(summary.total), hint: "Recommendations" },
      { label: "Applicable", value: num(summary.applicable), hint: "API actions" },
      { label: "High", value: num(summary.high), hint: "Severity" },
      { label: "Medium", value: num(summary.medium), hint: "Severity" },
    ]
      .map(
        (i) =>
          `<div class="kpi"><div class="label">${i.label}</div><div class="value">${i.value}</div><div class="delta">${i.hint}</div></div>`
      )
      .join("");
  }

  const filter = document.getElementById("optFilter")?.value || "all";
  let items = data.items || [];
  if (filter === "applicable") items = items.filter((r) => r.applicable);
  else if (filter === "high" || filter === "medium" || filter === "low") {
    items = items.filter((r) => r.severity === filter);
  }

  if (!items.length) {
    list.innerHTML = `<p class="muted">No recommendations for this filter. Try Re-audit or change Period.</p>`;
    return;
  }

  list.innerHTML = items
    .map((r, idx) => {
      const m = r.metrics || {};
      const camp = r.campaign_name || m.campaign_name || r.campaign_id || "";
      const status = r.campaign_status || m.campaign_status || "";
      const metricsLine = [
        m.cost != null ? `cost ${money(m.cost)}` : null,
        m.clicks != null ? `clicks ${num(m.clicks)}` : null,
        m.conversions != null ? `conv ${num(m.conversions)}` : null,
        m.cpa ? `CPA ${money(m.cpa)}` : null,
        m.ctr != null ? `CTR ${pct(m.ctr)}` : null,
      ]
        .filter(Boolean)
        .join(" · ");
      const applyBtn = r.applicable
        ? `<button type="button" class="btn btn-primary opt-apply" data-idx="${idx}">${escapeHtml(
            r.action_label || "Apply"
          )}</button>`
        : `<button type="button" class="btn btn-ghost opt-chat" data-idx="${idx}">Ask AI Assistant</button>`;
      return `<article class="opt-card" data-id="${escapeHtml(r.id || String(idx))}">
        <div class="opt-card-top">
          ${severityBadge(r.severity)}
          <span class="chip">${escapeHtml(r.action_label || r.action)}</span>
          ${status ? `<span class="chip">${escapeHtml(status)}</span>` : ""}
          ${r.applicable ? `<span class="chip">API</span>` : `<span class="chip">manual</span>`}
        </div>
        <h3 class="opt-entity">${escapeHtml(r.entity_name || r.entity_id || "—")}</h3>
        <p class="opt-reason">${escapeHtml(r.reason || "")}</p>
        <div class="opt-metrics">
          ${camp ? `<span>${escapeHtml(camp)}</span>` : ""}
          ${metricsLine ? `<span>${escapeHtml(metricsLine)}</span>` : ""}
        </div>
        <div class="opt-actions">${applyBtn}</div>
        <div class="opt-msg" hidden></div>
      </article>`;
    })
    .join("");

  // store filtered for index mapping
  list._filtered = items;

  list.querySelectorAll(".opt-apply").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const item = list._filtered[Number(btn.dataset.idx)];
      if (!item) return;
      const card = btn.closest(".opt-card");
      const msg = card?.querySelector(".opt-msg");
      if (!confirm(`Apply to Google Ads?\n\n${item.action_label}: ${item.entity_name}\n${item.reason}`)) {
        return;
      }
      btn.disabled = true;
      try {
        const res = await api("/api/recommendations/apply", {
          method: "POST",
          body: JSON.stringify({ item, confirm: true }),
        });
        if (msg) {
          msg.hidden = false;
          msg.className = `opt-msg ${res.ok ? "ok" : "err"}`;
          msg.textContent = res.message || (res.ok ? "Applied" : "Failed");
        }
        if (res.ok) card?.classList.add("is-done");
      } catch (e) {
        if (msg) {
          msg.hidden = false;
          msg.className = "opt-msg err";
          msg.textContent = String(e.message || e);
        }
      } finally {
        btn.disabled = false;
      }
    });
  });

  list.querySelectorAll(".opt-chat").forEach((btn) => {
    btn.addEventListener("click", () => {
      const item = list._filtered[Number(btn.dataset.idx)];
      if (!item) return;
      const prompt =
        `Optimize this: ${item.action} on ${item.entity_type} "${item.entity_name}". ` +
        `${item.reason} Campaign: ${item.campaign_name || item.campaign_id || "—"}. ` +
        `Propose concrete next steps and apply via tools if I confirm.`;
      askAssistant(prompt);
    });
  });
}

async function loadOptimize(force = false) {
  if (state.optimizeBusy) return;
  if (!force && state.optimizeData) {
    renderOptimizeView();
    return;
  }
  state.optimizeBusy = true;
  const note = document.getElementById("optNote");
  if (note) note.textContent = "Running live audit…";
  const btn = document.getElementById("optReloadBtn");
  if (btn) btn.disabled = true;
  try {
    const data = await api("/api/recommendations");
    state.optimizeData = data;
    renderOptimizeView();
  } catch (e) {
    if (note) note.textContent = String(e.message || e);
  } finally {
    state.optimizeBusy = false;
    if (btn) btn.disabled = false;
  }
}

function renderTrend(trend) {
  const ctx = document.getElementById("trendChart");
  const labels = trend.map((d) => d.date);
  const costs = trend.map((d) => d.cost);
  const conv = trend.map((d) => d.conversions);
  if (state.chart) state.chart.destroy();
  state.chart = new Chart(ctx, {
    type: "line",
    data: {
      labels,
      datasets: [
        {
          label: "Cost",
          data: costs,
          borderColor: "#1a73e8",
          backgroundColor: "rgba(26,115,232,.12)",
          fill: true,
          tension: 0.35,
          yAxisID: "y",
        },
        {
          label: "Conversions",
          data: conv,
          borderColor: "#34a853",
          backgroundColor: "transparent",
          tension: 0.35,
          yAxisID: "y1",
        },
      ],
    },
    options: {
      responsive: true,
      interaction: { mode: "index", intersect: false },
      plugins: { legend: { position: "bottom" } },
      scales: {
        y: { position: "left", grid: { color: "#f1f3f4" } },
        y1: { position: "right", grid: { drawOnChartArea: false } },
        x: { grid: { display: false } },
      },
    },
  });
}

const campaignCols = [
  { label: "Campaign", key: "name" },
  { label: "Status", render: (r) => statusBadge(r.status) },
  { label: "Channel", key: "channel" },
  { label: "Cost", render: (r) => money(r.cost) },
  { label: "Clicks", render: (r) => num(r.clicks) },
  { label: "Conv.", render: (r) => num(r.conversions) },
  { label: "CPA", render: (r) => money(r.cpa) },
  { label: "ROAS", render: (r) => `${(r.roas || 0).toFixed(2)}x` },
];

function campaignIdOf(r) {
  return String(r.id || r.campaign_id || "");
}

function rowActionBtns(buttons) {
  return `<div class="row-actions">${buttons.join("")}</div>`;
}

function actionBtn(cls, label, attrs) {
  const extra = Object.entries(attrs || {})
    .map(([k, v]) => `${k}="${escapeAttr(v)}"`)
    .join(" ");
  return `<button type="button" class="btn btn-ghost btn-sm ${cls}" ${extra}>${escapeHtml(label)}</button>`;
}

const campaignColsManage = [
  ...campaignCols,
  {
    label: "Bidding",
    render: (r) => escapeHtml(r.bidding_strategy_type || "—"),
  },
  {
    label: "Actions",
    render: (r) => {
      const id = campaignIdOf(r);
      const enabled = String(r.status || "").toUpperCase() === "ENABLED";
      return rowActionBtns([
        actionBtn("js-camp-toggle", enabled ? "Pause" : "Enable", {
          "data-id": id,
          "data-status": enabled ? "PAUSED" : "ENABLED",
        }),
        actionBtn("js-camp-budget", "Budget", { "data-id": id }),
        actionBtn("js-camp-bid", "Bidding", {
          "data-id": id,
          "data-bidding": r.bidding_strategy_type || "",
        }),
      ]);
    },
  },
];

const keywordCols = [
  { label: "Keyword", key: "text" },
  { label: "Match", key: "match_type" },
  { label: "Status", render: (r) => statusBadge(r.status) },
  { label: "Campaign", key: "campaign" },
  { label: "Ad group", key: "ad_group" },
  { label: "Cost", render: (r) => money(r.cost) },
  { label: "Conv.", render: (r) => num(r.conversions) },
  { label: "CPA", render: (r) => money(r.cpa) },
  { label: "CTR", render: (r) => pct(r.ctr) },
  {
    label: "Actions",
    render: (r) => {
      const enabled = String(r.status || "").toUpperCase() === "ENABLED";
      return rowActionBtns([
        actionBtn("js-kw-toggle", enabled ? "Pause" : "Enable", {
          "data-ad-group-id": r.ad_group_id || "",
          "data-criterion-id": r.criterion_id || "",
          "data-status": enabled ? "PAUSED" : "ENABLED",
          "data-text": r.text || "",
        }),
      ]);
    },
  },
];

const adCols = [
  { label: "Ad", key: "name" },
  { label: "Status", render: (r) => statusBadge(r.status) },
  { label: "Campaign", key: "campaign" },
  { label: "Ad group", key: "ad_group" },
  {
    label: "Keywords in ad group",
    render: (r) => renderKeywordTags(keywordsForRow(r), 8),
  },
  { label: "Cost", render: (r) => money(r.cost) },
  { label: "Conv.", render: (r) => num(r.conversions) },
  { label: "CTR", render: (r) => pct(r.ctr) },
  { label: "ROAS", render: (r) => `${(r.roas || 0).toFixed(2)}x` },
  {
    label: "Actions",
    render: (r) => {
      const enabled = String(r.status || "").toUpperCase() === "ENABLED";
      return rowActionBtns([
        actionBtn("js-ad-toggle", enabled ? "Pause" : "Enable", {
          "data-ad-group-id": r.ad_group_id || "",
          "data-ad-id": r.ad_id || r.id || "",
          "data-status": enabled ? "PAUSED" : "ENABLED",
        }),
      ]);
    },
  },
];

function fillCampaignSelect(selectEl, items, selected) {
  const current = selected ?? selectEl.value;
  const counts = new Map();
  for (const row of items) {
    const name = row.campaign;
    if (!name) continue;
    counts.set(name, (counts.get(name) || 0) + 1);
  }
  const campaigns = [...counts.keys()].sort((a, b) =>
    String(a).localeCompare(String(b), undefined, { sensitivity: "base" })
  );
  selectEl.innerHTML =
    `<option value="">All campaigns (${items.length})</option>` +
    campaigns
      .map(
        (c) =>
          `<option value="${escapeAttr(c)}">${escapeHtml(c)} (${counts.get(c)})</option>`
      )
      .join("");
  if (current && counts.has(current)) selectEl.value = current;
}

function fillAdGroupSelect(selectEl, items, campaignFilter, selected) {
  const current = selected ?? selectEl.value;
  const scoped = campaignFilter ? items.filter((r) => r.campaign === campaignFilter) : items;
  const counts = new Map();
  for (const row of scoped) {
    const name = row.ad_group;
    if (!name) continue;
    counts.set(name, (counts.get(name) || 0) + 1);
  }
  const groups = [...counts.keys()].sort((a, b) =>
    String(a).localeCompare(String(b), undefined, { sensitivity: "base" })
  );
  selectEl.innerHTML =
    `<option value="">All ad groups (${scoped.length})</option>` +
    groups
      .map(
        (g) =>
          `<option value="${escapeAttr(g)}">${escapeHtml(g)} (${counts.get(g)})</option>`
      )
      .join("");
  if (current && counts.has(current)) selectEl.value = current;
  else selectEl.value = "";
}

function escapeHtml(s) {
  return String(s)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function escapeAttr(s) {
  return escapeHtml(s).replaceAll("'", "&#39;");
}

function parseSort(value) {
  const idx = String(value || "").lastIndexOf("_");
  if (idx <= 0) return { key: "campaign", dir: "asc" };
  return { key: value.slice(0, idx), dir: value.slice(idx + 1) === "desc" ? "desc" : "asc" };
}

function cmpValues(a, b, dir) {
  const av = a ?? "";
  const bv = b ?? "";
  let res = 0;
  if (typeof av === "number" && typeof bv === "number") res = av - bv;
  else res = String(av).localeCompare(String(bv), undefined, { sensitivity: "base", numeric: true });
  return dir === "desc" ? -res : res;
}

function applyListControls(items, { campaign, adGroup, status, strength, search, sort, searchFields }) {
  const q = (search || "").trim().toLowerCase();
  const { key, dir } = parseSort(sort);
  let rows = items.slice();
  if (campaign) rows = rows.filter((r) => r.campaign === campaign);
  if (adGroup) rows = rows.filter((r) => r.ad_group === adGroup);
  if (status) {
    const st = status.toUpperCase();
    rows = rows.filter((r) => String(r.status || "").toUpperCase().includes(st));
  }
  if (strength) {
    const allowed = new Set(
      String(strength)
        .split(",")
        .map((s) => s.trim().toUpperCase())
        .filter(Boolean)
    );
    rows = rows.filter((r) => allowed.has(String(r.ad_strength || "").toUpperCase()));
  }
  if (q) {
    rows = rows.filter((r) =>
      searchFields.some((f) => {
        const val = r[f];
        if (Array.isArray(val)) return val.join(" ").toLowerCase().includes(q);
        return String(val ?? "").toLowerCase().includes(q);
      })
    );
  }
  rows.sort((a, b) => {
    if (key === "ad_strength") {
      const primary = strengthRank(a.ad_strength) - strengthRank(b.ad_strength);
      return dir === "desc" ? -primary : primary;
    }
    const primary = cmpValues(a[key], b[key], dir);
    if (primary !== 0) return primary;
    return cmpValues(a.campaign, b.campaign, "asc") || cmpValues(a.text || a.name, b.text || b.name, "asc");
  });
  return rows;
}

function setCountChip(el, shown, total, noun) {
  if (shown === total) {
    el.innerHTML = `${num(total)} ${noun}`;
  } else {
    el.innerHTML = `${num(shown)} <span class="muted-part">/ ${num(total)} ${noun}</span>`;
  }
}

function campaignBreakdown(items) {
  const map = new Map();
  for (const row of items) {
    const name = row.campaign || "—";
    map.set(name, (map.get(name) || 0) + 1);
  }
  return [...map.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]));
}

function keywordsForRow(row) {
  const groupId = row.ad_group_id;
  if (groupId) {
    return (state.keywords || []).filter((k) => String(k.ad_group_id) === String(groupId));
  }
  return (state.keywords || []).filter(
    (k) => k.campaign === row.campaign && k.ad_group === row.ad_group
  );
}

function renderKeywordTags(keywords, limit = 12) {
  const list = keywords || [];
  if (!list.length) {
    return `<span class="muted">нет ключей в группе</span>`;
  }
  const shown = list.slice(0, limit);
  const more = list.length - shown.length;
  const tags = shown
    .map((k) => {
      const match = String(k.match_type || "")
        .replace("EXACT", "exact")
        .replace("PHRASE", "phrase")
        .replace("BROAD", "broad");
      return `<span class="kw-tag" title="${escapeAttr(k.status || "")}">${escapeHtml(k.text || "")}<span class="match">${escapeHtml(match)}</span></span>`;
    })
    .join("");
  return `<div class="kw-tags">${tags}${
    more > 0 ? `<span class="kw-tag">+${more}</span>` : ""
  }</div>`;
}

function renderKeywordsView() {
  const items = state.keywords || [];
  const campaignSel = document.getElementById("kwCampaignFilter");
  const adGroupSel = document.getElementById("kwAdGroupFilter");
  fillCampaignSelect(campaignSel, items);
  fillAdGroupSelect(adGroupSel, items, campaignSel.value);
  const filtered = applyListControls(items, {
    campaign: campaignSel.value,
    adGroup: adGroupSel.value,
    search: document.getElementById("kwSearch").value,
    sort: document.getElementById("kwSort").value,
    searchFields: ["text", "campaign", "match_type", "ad_group", "status"],
  });
  renderTable(document.getElementById("keywordsTable"), keywordCols, filtered);
  const chip = document.getElementById("kwCount");
  const campaign = campaignSel.value;
  if (campaign) {
    chip.innerHTML = `${num(filtered.length)} <span class="muted-part">keywords in ${escapeHtml(campaign)}</span>`;
  } else {
    setCountChip(chip, filtered.length, items.length, "keywords");
    chip.title = campaignBreakdown(items).map(([n, c]) => `${n}: ${c}`).join("\n");
  }
}

function renderAdsView() {
  const items = state.ads || [];
  fillCampaignSelect(document.getElementById("adCampaignFilter"), items);
  const filtered = applyListControls(items, {
    campaign: document.getElementById("adCampaignFilter").value,
    status: document.getElementById("adStatusFilter").value,
    search: document.getElementById("adSearch").value,
    sort: document.getElementById("adSort").value,
    searchFields: ["name", "campaign", "ad_group", "status"],
  });
  renderTable(document.getElementById("adsTable"), adCols, filtered);
  setCountChip(document.getElementById("adCount"), filtered.length, items.length, "ads");
}

function formatDisplayUrl(finalUrl, path1, path2) {
  let host = String(finalUrl || "").replace(/^https?:\/\//i, "").split("/")[0] || "example.com";
  const parts = [path1, path2].map((p) => String(p || "").trim()).filter(Boolean);
  if (parts.length) host += "/" + parts.join("/");
  return host;
}

function rsaHeadlineLen(text) {
  const t = String(text || "").trim();
  const lower = t.toLowerCase();
  if (lower.startsWith("{keyword:") && t.endsWith("}")) {
    return t.slice("{KeyWord:".length, -1).length;
  }
  return t.length;
}

function buildSerpHtml(c, { headlines, descriptions, finalUrl, path1, path2, sitelinks } = {}) {
  const hs = headlines || c.headlines || [];
  const ds = descriptions || c.descriptions || [];
  const url = finalUrl || (c.final_urls && c.final_urls[0]) || "https://example.com";
  const p1 = path1 != null ? path1 : c.path1 || "";
  const p2 = path2 != null ? path2 : c.path2 || "";
  const title = (hs.slice(0, 3).filter(Boolean).join(" | ") || c.name || "Untitled ad");
  const desc = ds.slice(0, 2).filter(Boolean).join(" ");
  const display = formatDisplayUrl(url, p1, p2);
  const letter = (display[0] || "G").toUpperCase();
  const links = (sitelinks != null ? sitelinks : c.sitelinks || []).filter((s) => !s.remove);
  let slHtml = "";
  if (links.length) {
    slHtml =
      `<div class="serp-sitelinks">` +
      links
        .slice(0, 6)
        .map((s) => {
          const d1 = s.description1 || "";
          const d2 = s.description2 || "";
          const descLine = [d1, d2].filter(Boolean).join(" · ");
          return `<div class="serp-sitelink">
            <div class="serp-sitelink-title">${escapeHtml(s.link_text || "")}</div>
            ${descLine ? `<div class="serp-sitelink-desc">${escapeHtml(descLine)}</div>` : ""}
          </div>`;
        })
        .join("") +
      `</div>`;
  } else if (!c.empty_ad_group) {
    slHtml = `<div class="serp-sitelinks-empty">No sitelinks on this campaign</div>`;
  }
  return `<div class="serp">
    <div class="serp-sponsored">Sponsored</div>
    <div class="url"><span class="serp-favicon" aria-hidden="true">${escapeHtml(letter)}</span><span>${escapeHtml(display)}</span></div>
    <div class="title">${escapeHtml(title)}</div>
    <div class="desc">${escapeHtml(desc)}</div>
    ${slHtml}
  </div>`;
}

function renderCreatives(items) {
  const grid = document.getElementById("creativesGrid");
  grid.innerHTML = (items || [])
    .map((c) => {
      if (c.empty_ad_group) {
        return `<article class="creative empty-ad-group">
          ${buildSerpHtml({ ...c, headlines: [c.ad_group || "Ad group"], descriptions: ["No RSA in this ad group — create via AI Assistant or editor."] })}
          <div class="meta">${escapeHtml(c.campaign || "")} · ${escapeHtml(c.ad_group || "")} · ${statusBadge("NO_AD")}</div>
        </article>`;
      }
      const kws = keywordsForRow(c);
      const actions = (c.action_items || [])
        .map((a) => `<li>${escapeHtml(a)}</li>`)
        .join("");
      const kwPanel =
        kws.length > 0
          ? `<details class="kw-block">
          <summary class="kw-summary">Keywords (${kws.length})</summary>
          <div class="kw-panel">${renderKeywordTags(kws, 50)}</div>
        </details>`
          : `<details class="kw-block">
          <summary class="kw-summary">Keywords (0)</summary>
          <div class="kw-panel"><span class="muted">no keywords in ad group</span></div>
        </details>`;
      const slCount = c.sitelink_count ?? (c.sitelinks || []).length;
      const policies = (c.policy_topics || [])
        .map((p) => {
          const topic = typeof p === "string" ? p : p.topic || "";
          const typ = typeof p === "string" ? "" : p.type || "";
          if (!topic) return "";
          return `<li>${escapeHtml(topic)}${typ ? ` · ${escapeHtml(typ)}` : ""}</li>`;
        })
        .filter(Boolean)
        .join("");
      return `<article class="creative" data-ad-id="${escapeAttr(c.ad_id || "")}">
        ${buildSerpHtml(c)}
        <div class="meta">${escapeHtml(c.campaign || "")} · ${escapeHtml(c.ad_group || "")} · ${statusBadge(c.status)} · ${strengthBadge(c.ad_strength)}${c.review_status ? ` · review ${escapeHtml(String(c.review_status))}` : ""}${c.approval_status ? ` · ${escapeHtml(String(c.approval_status))}` : ""} · H${c.headline_count || (c.headlines || []).length}/D${c.description_count || (c.descriptions || []).length} · SL${slCount}</div>
        ${actions ? `<ul class="action-items">${actions}</ul>` : ""}
        ${policies ? `<ul class="policy-topics">${policies}</ul>` : ""}
        <div class="creative-actions-row">
          <button type="button" class="btn btn-ghost btn-edit-rsa" data-ad-id="${escapeAttr(c.ad_id || "")}">
            <span class="material-symbols-outlined">edit</span> Edit ad
          </button>
          <button type="button" class="btn btn-ghost btn-ask-rsa" data-ad-id="${escapeAttr(c.ad_id || "")}">
            Ask AI Assistant
          </button>
        </div>
        ${kwPanel}
      </article>`;
    })
    .join("") || `<p class="muted" style="padding:16px">No creatives match filters.</p>`;

  grid.querySelectorAll(".btn-edit-rsa").forEach((btn) => {
    btn.addEventListener("click", () => openRsaEditor(btn.dataset.adId));
  });
  grid.querySelectorAll(".btn-ask-rsa").forEach((btn) => {
    btn.addEventListener("click", () => {
      const c = (state.creatives || []).find((x) => String(x.ad_id) === String(btn.dataset.adId));
      if (!c) return;
      askAssistant(
        `Improve Ad Strength for RSA ad_id=${c.ad_id} in ad group "${c.ad_group}" (campaign "${c.campaign}"). Read action_items first, then fix sitelinks and/or headlines/descriptions per rsa-ad-strength.`
      );
    });
  });
}

let rsaEditorAdId = null;
let rsaEditorCampaignId = null;

function closeRsaEditor() {
  const modal = document.getElementById("rsaEditorModal");
  if (modal) modal.hidden = true;
  rsaEditorAdId = null;
  rsaEditorCampaignId = null;
  document.body.style.overflow = "";
  renderRsaChecklist(null);
  const urlEl = document.getElementById("rsaUrlCheck");
  if (urlEl) urlEl.textContent = "";
}

function rsaEditorCollectSitelinks() {
  return [...document.querySelectorAll("#rsaSitelinkRows .rsa-sitelink-row")].map((row) => ({
    asset_id: row.dataset.assetId || null,
    campaign_asset: row.dataset.campaignAsset || null,
    link_text: row.querySelector(".sl-text")?.value.trim() || "",
    final_url: row.querySelector(".sl-url")?.value.trim() || "",
    description1: row.querySelector(".sl-d1")?.value.trim() || "",
    description2: row.querySelector(".sl-d2")?.value.trim() || "",
    remove: row.classList.contains("is-removed"),
  }));
}

function rsaEditorCollect() {
  const headlines = [...document.querySelectorAll("#rsaHeadlineLines input")]
    .map((el) => el.value.trim())
    .filter(Boolean);
  const descriptions = [...document.querySelectorAll("#rsaDescriptionLines input")]
    .map((el) => el.value.trim())
    .filter(Boolean);
  return {
    headlines,
    descriptions,
    final_url: document.getElementById("rsaEditFinalUrl")?.value.trim() || null,
    path1: document.getElementById("rsaEditPath1")?.value.trim() || null,
    path2: document.getElementById("rsaEditPath2")?.value.trim() || null,
    sitelinks: rsaEditorCollectSitelinks(),
  };
}

function refreshRsaEditorMeta() {
  const draft = rsaEditorCollect();
  const c = (state.creatives || []).find((x) => String(x.ad_id) === String(rsaEditorAdId)) || {};
  const hCount = document.getElementById("rsaHCount");
  const dCount = document.getElementById("rsaDCount");
  const slCount = document.getElementById("rsaSlCount");
  if (hCount) hCount.textContent = `(${draft.headlines.length}/15)`;
  if (dCount) dCount.textContent = `(${draft.descriptions.length}/4)`;
  const activeSl = draft.sitelinks.filter((s) => !s.remove && s.link_text);
  if (slCount) slCount.textContent = `(${activeSl.length})`;
  const preview = document.getElementById("rsaEditorLivePreview");
  if (preview) {
    preview.innerHTML = buildSerpHtml(c, {
      headlines: draft.headlines,
      descriptions: draft.descriptions,
      finalUrl: draft.final_url || (c.final_urls && c.final_urls[0]),
      path1: draft.path1 || "",
      path2: draft.path2 || "",
      sitelinks: activeSl,
    });
  }
  document.querySelectorAll("#rsaHeadlineLines input").forEach((el) => {
    const n = rsaHeadlineLen(el.value);
    el.classList.toggle("over-limit", n > 30);
    const meta = el.parentElement?.querySelector(".rsa-line-meta");
    if (meta) meta.textContent = `${n}/30`;
  });
  document.querySelectorAll("#rsaDescriptionLines input").forEach((el) => {
    const n = el.value.length;
    el.classList.toggle("over-limit", n > 90);
    const meta = el.parentElement?.querySelector(".rsa-line-meta");
    if (meta) meta.textContent = `${n}/90`;
  });
  document.querySelectorAll("#rsaSitelinkRows .sl-text").forEach((el) => {
    el.classList.toggle("over-limit", el.value.trim().length > 25);
  });
  document.querySelectorAll("#rsaSitelinkRows .sl-d1, #rsaSitelinkRows .sl-d2").forEach((el) => {
    el.classList.toggle("over-limit", el.value.trim().length > 35);
  });
  scheduleRsaEvaluate();
  scheduleRsaUrlCheck();
}

let rsaEvalTimer = null;
let rsaUrlTimer = null;

function rsaEditorKeywords() {
  const c = (state.creatives || []).find((x) => String(x.ad_id) === String(rsaEditorAdId));
  return keywordsForRow(c || {}).map((k) => k.text).filter(Boolean);
}

function renderRsaChecklist(data) {
  const box = document.getElementById("rsaChecklist");
  if (!box) return;
  if (!data) {
    box.hidden = true;
    box.innerHTML = "";
    return;
  }
  const warnings = data.warnings || [];
  const tips = data.tips || [];
  const ok = Boolean(data.ok_for_good_excellent);
  box.hidden = false;
  box.className = `rsa-checklist ${ok ? "ok" : "warn"}`;
  const stats = data.stats || {};
  box.innerHTML =
    `<strong>${ok ? "Checklist OK for Good/Excellent" : "Fix before Apply"}</strong>` +
    ` <span class="muted">H${stats.headline_count || 0}/15 · D${stats.description_count || 0}/4` +
    (stats.primary_keyword ? ` · KW ${escapeHtml(stats.primary_keyword)}` : "") +
    `</span>` +
    (warnings.length
      ? `<ul>${warnings.map((w) => `<li>${escapeHtml(w)}</li>`).join("")}</ul>`
      : "") +
    (tips.length ? `<ul class="tips">${tips.map((t) => `<li>${escapeHtml(t)}</li>`).join("")}</ul>` : "");
}

function scheduleRsaEvaluate() {
  clearTimeout(rsaEvalTimer);
  rsaEvalTimer = setTimeout(async () => {
    const draft = rsaEditorCollect();
    if (!draft.headlines.length) {
      renderRsaChecklist(null);
      return;
    }
    try {
      const data = await api("/api/creatives/evaluate", {
        method: "POST",
        silent: true,
        body: JSON.stringify({
          headlines: draft.headlines,
          descriptions: draft.descriptions,
          keywords: rsaEditorKeywords(),
        }),
      });
      renderRsaChecklist(data);
    } catch (_) {
      /* ignore live checklist errors */
    }
  }, 350);
}

function scheduleRsaUrlCheck() {
  clearTimeout(rsaUrlTimer);
  rsaUrlTimer = setTimeout(async () => {
    const el = document.getElementById("rsaUrlCheck");
    const url = document.getElementById("rsaEditFinalUrl")?.value.trim() || "";
    if (!el) return;
    if (!url) {
      el.textContent = "";
      return;
    }
    el.textContent = "checking…";
    try {
      const data = await api("/api/urls/check", {
        method: "POST",
        silent: true,
        body: JSON.stringify({ url }),
      });
      el.textContent = data.ok ? `HTTP ${data.status}` : data.error || "URL failed";
      el.classList.toggle("bad", !data.ok);
      el.classList.toggle("ok", Boolean(data.ok));
    } catch (e) {
      el.textContent = String(e.message || e);
      el.classList.add("bad");
    }
  }, 500);
}

function addRsaLine(containerId, value, maxLen) {
  const box = document.getElementById(containerId);
  if (!box) return;
  const maxItems = containerId.includes("Headline") ? 15 : 4;
  if (box.children.length >= maxItems) return;
  const row = document.createElement("div");
  row.className = "rsa-line";
  row.innerHTML = `<input type="text" value="${escapeAttr(value || "")}" maxlength="${maxLen === 30 ? 80 : 120}" /><span class="rsa-line-meta">0/${maxLen}</span>`;
  const input = row.querySelector("input");
  input.addEventListener("input", refreshRsaEditorMeta);
  box.appendChild(row);
  refreshRsaEditorMeta();
}

function addSitelinkRow(sl = {}) {
  const box = document.getElementById("rsaSitelinkRows");
  if (!box) return;
  const row = document.createElement("div");
  row.className = "rsa-sitelink-row";
  if (sl.asset_id) row.dataset.assetId = String(sl.asset_id);
  if (sl.campaign_asset) row.dataset.campaignAsset = String(sl.campaign_asset);
  row.innerHTML = `
    <input class="sl-text" type="text" maxlength="25" placeholder="Link text ≤25" value="${escapeAttr(sl.link_text || "")}" />
    <input class="sl-url" type="url" placeholder="https://…" value="${escapeAttr(sl.final_url || "")}" />
    <input class="sl-d1" type="text" maxlength="35" placeholder="Desc 1 ≤35" value="${escapeAttr(sl.description1 || "")}" />
    <input class="sl-d2" type="text" maxlength="35" placeholder="Desc 2 ≤35" value="${escapeAttr(sl.description2 || "")}" />
    <button type="button" class="rsa-sl-remove" title="Remove sitelink" aria-label="Remove">
      <span class="material-symbols-outlined">delete</span>
    </button>`;
  row.querySelectorAll("input").forEach((el) => el.addEventListener("input", refreshRsaEditorMeta));
  row.querySelector(".rsa-sl-remove").addEventListener("click", () => {
    if (row.dataset.assetId || row.dataset.campaignAsset) {
      row.classList.toggle("is-removed");
    } else {
      row.remove();
    }
    refreshRsaEditorMeta();
  });
  box.appendChild(row);
  refreshRsaEditorMeta();
}

function openRsaEditor(adId) {
  const c = (state.creatives || []).find((x) => String(x.ad_id) === String(adId));
  if (!c || c.empty_ad_group) return;
  rsaEditorAdId = String(adId);
  rsaEditorCampaignId = String(c.campaign_id || "");
  const modal = document.getElementById("rsaEditorModal");
  const sub = document.getElementById("rsaEditorSub");
  if (sub) {
    sub.textContent = `${c.campaign || ""} · ${c.ad_group || ""} · ad ${c.ad_id} · ${(c.sitelinks || []).length} sitelinks`;
  }
  document.getElementById("rsaEditFinalUrl").value = (c.final_urls && c.final_urls[0]) || "";
  document.getElementById("rsaEditPath1").value = c.path1 || "";
  document.getElementById("rsaEditPath2").value = c.path2 || "";
  const hBox = document.getElementById("rsaHeadlineLines");
  const dBox = document.getElementById("rsaDescriptionLines");
  const slBox = document.getElementById("rsaSitelinkRows");
  hBox.innerHTML = "";
  dBox.innerHTML = "";
  if (slBox) slBox.innerHTML = "";
  const headlines = (c.headlines || []).length ? c.headlines : [""];
  const descriptions = (c.descriptions || []).length ? c.descriptions : ["", ""];
  headlines.forEach((h) => addRsaLine("rsaHeadlineLines", h, 30));
  descriptions.forEach((d) => addRsaLine("rsaDescriptionLines", d, 90));
  (c.sitelinks || []).forEach((s) => addSitelinkRow(s));
  document.getElementById("rsaEditorStatus").textContent = "";
  modal.hidden = false;
  document.body.style.overflow = "hidden";
  refreshRsaEditorMeta();
}

async function applyRsaEditor() {
  const status = document.getElementById("rsaEditorStatus");
  const btn = document.getElementById("rsaEditorApply");
  const draft = rsaEditorCollect();
  if (!rsaEditorAdId) return;
  if (draft.headlines.length < 3 || draft.descriptions.length < 2) {
    status.textContent = "Need at least 3 headlines and 2 descriptions.";
    return;
  }
  for (const h of draft.headlines) {
    if (rsaHeadlineLen(h) > 30) {
      status.textContent = `Headline too long (>30): ${h}`;
      return;
    }
  }
  for (const d of draft.descriptions) {
    if (d.length > 90) {
      status.textContent = `Description too long (>90)`;
      return;
    }
  }
  const activeSl = draft.sitelinks.filter((s) => !s.remove);
  for (const s of activeSl) {
    if (!s.link_text || !s.final_url) {
      status.textContent = "Each sitelink needs link text and final URL.";
      return;
    }
    if (s.link_text.length > 25) {
      status.textContent = `Sitelink text too long (>25): ${s.link_text}`;
      return;
    }
    if ((s.description1 && !s.description2) || (!s.description1 && s.description2)) {
      status.textContent = "Sitelink descriptions must both be filled or both empty.";
      return;
    }
    if (s.description1.length > 35 || s.description2.length > 35) {
      status.textContent = "Sitelink description max 35 chars.";
      return;
    }
  }
  if (!confirm("Apply RSA + sitelinks to Google Ads?")) {
    return;
  }
  if (draft.final_url) {
    try {
      const chk = await api("/api/urls/check", {
        method: "POST",
        body: JSON.stringify({ url: draft.final_url }),
      });
      if (!chk.ok) {
        status.textContent = `Landing URL not HTTP 200: ${chk.error || chk.status || "failed"}`;
        return;
      }
    } catch (e) {
      status.textContent = `URL check failed: ${e.message || e}`;
      return;
    }
  }
  btn.disabled = true;
  status.textContent = "Applying RSA…";
  try {
    const data = await api("/api/creatives/update", {
      method: "POST",
      body: JSON.stringify({
        ad_id: rsaEditorAdId,
        headlines: draft.headlines,
        descriptions: draft.descriptions,
        final_url: draft.final_url,
        path1: draft.path1,
        path2: draft.path2,
        keywords: rsaEditorKeywords(),
        confirm: true,
      }),
    });
    if (data.needs_confirmation) {
      status.textContent = "Server returned preview only — try again.";
      return;
    }
    if (rsaEditorCampaignId && draft.sitelinks.length) {
      status.textContent = "Applying sitelinks…";
      const sl = await api("/api/creatives/sitelinks", {
        method: "POST",
        body: JSON.stringify({
          campaign_id: rsaEditorCampaignId,
          sitelinks: draft.sitelinks,
          confirm: true,
        }),
      });
      if (sl.needs_confirmation) {
        status.textContent = "Sitelinks preview only — RSA saved, sitelinks not applied.";
        await loadCreatives(true);
        return;
      }
    }
    status.textContent = "Saved. Reloading creatives…";
    await loadCreatives(true);
    closeRsaEditor();
  } catch (e) {
    status.textContent = String(e.message || e);
  } finally {
    btn.disabled = false;
  }
}

function renderCreativesView() {
  const items = state.creatives || [];
  fillCampaignSelect(document.getElementById("crCampaignFilter"), items);
  const filtered = applyListControls(items, {
    campaign: document.getElementById("crCampaignFilter").value,
    status: document.getElementById("crStatusFilter").value,
    strength: document.getElementById("crStrengthFilter").value,
    search: document.getElementById("crSearch").value,
    sort: document.getElementById("crSort").value,
    searchFields: [
      "name",
      "campaign",
      "ad_group",
      "status",
      "ad_strength",
      "headlines",
      "descriptions",
      "final_urls",
      "action_items",
    ],
  });
  renderCreatives(filtered);
  const weak = items.filter((c) =>
    ["POOR", "INCOMPLETE", "AVERAGE"].includes(String(c.ad_strength || "").toUpperCase())
  ).length;
  const chip = document.getElementById("crCount");
  setCountChip(chip, filtered.length, items.length, "creatives");
  if (weak) {
    chip.innerHTML += ` <span class="muted-part">· ${weak} need fix</span>`;
  }
  const note = document.getElementById("crFetchNote");
  if (note) {
    const when = state.creativesFetchedAt
      ? new Date(state.creativesFetchedAt).toLocaleString()
      : "—";
    note.textContent =
      `Live from Google Ads API · fetched ${when}. ` +
      `Ad Strength / Google tips can lag hours after edits (API may still return AVERAGE).`;
  }
}

async function loadCreatives(force = true) {
  if (state.creativesBusy) return;
  state.creativesBusy = true;
  const btn = document.getElementById("crReloadBtn");
  if (btn) btn.disabled = true;
  try {
    const creatives = await api("/api/creatives", {
      silent: state.pending > 0,
      cache: "no-store",
    });
    state.creatives = creatives.items || [];
    state.creativesFetchedAt = creatives.fetched_at || new Date().toISOString();
    if (document.querySelector(".nav-item.active")?.dataset?.view === "creatives" || force) {
      renderCreativesView();
    }
  } finally {
    state.creativesBusy = false;
    if (btn) btn.disabled = false;
  }
}

async function loadOverview() {
  const data = await api(`/api/overview?days=${state.days}`);
  state.overview = data;
  const account = data.account || {};
  state.currency = (account.currency_code || state.currency || "USD").toUpperCase();
  document.getElementById("accountLine").textContent =
    `${account.name || "Account"} · ${account.id || "—"} · ${state.currency}`;
  document.getElementById("modeBadge").textContent = account.demo ? "Demo mode" : "Live API";
  renderKpis(data.totals || {});
  renderTrend(data.trend || []);
  renderTable(document.getElementById("overviewCampaigns"), campaignCols, (data.campaigns || []).slice(0, 6));
  renderRecs(document.getElementById("overviewRecs"), data.recommendations || [], 4);
  normalizePlaybook(data.setup);
}

function normalizePlaybook(raw) {
  if (!raw) return;
  // New shape: { items: [...] }. Legacy: bare array.
  if (Array.isArray(raw)) {
    state.setupGuide = {
      source_label: "Static best-practice playbook",
      source_detail: "Legacy payload shape from overview.",
      guide_updated: "—",
      items: raw,
    };
  } else if (raw && Array.isArray(raw.items)) {
    state.setupGuide = raw;
  } else {
    return;
  }
  renderSetupView();
}

async function loadTables() {
  const [campaigns, keywords, ads, creatives] = await Promise.all([
    api(`/api/campaigns?days=${state.days}`),
    api(`/api/keywords?days=${state.days}`),
    api(`/api/ads?days=${state.days}`),
    api("/api/creatives", { cache: "no-store" }),
  ]);
  state.keywords = keywords.items || [];
  state.ads = ads.items || [];
  state.campaigns = campaigns.items || [];
  state.creatives = creatives.items || [];
  state.creativesFetchedAt = creatives.fetched_at || new Date().toISOString();
  renderTable(document.getElementById("campaignsTable"), campaignColsManage, state.campaigns);
  renderKeywordsView();
  renderAdsView();
  renderCreativesView();
}

async function loadAnalytics(force = false) {
  const note = document.getElementById("gaNote");
  const kpis = document.getElementById("gaKpis");
  if (!note || !kpis) return;
  if (state.analyticsBusy) return;
  if (!force && state.analyticsLoadedForDays === state.days) return;

  state.analyticsBusy = true;
  note.textContent = `Loading GA4 for last ${state.days} days…`;
  const reloadBtn = document.getElementById("gaReloadBtn");
  if (reloadBtn) reloadBtn.disabled = true;

  const emptyTable = (id, msg = "No data") => {
    const el = document.getElementById(id);
    if (el) el.innerHTML = `<p class="muted">${escapeHtml(msg)}</p>`;
  };
  const setChip = (id, text) => {
    const el = document.getElementById(id);
    if (el) el.textContent = text;
  };

  try {
    const data = await api(`/api/analytics/dashboard?days=${state.days}`);
    const st = data.status || {};
    const errs = data.errors || {};

    if (!data.ok && !st.property_id) {
      if (!st.configured) {
        note.textContent =
          "Google Ads OAuth is missing. Open Setup, sign in with Analytics scopes, then set GA4_PROPERTY_ID.";
      } else {
        note.textContent =
          "OAuth is ready, but GA4_PROPERTY_ID is not set in .env (numeric id, without properties/).";
      }
      kpis.innerHTML = "";
      const props = (data.properties && data.properties.items) || [];
      if (props.length) {
        renderTable(
          document.getElementById("gaLinks"),
          [
            { label: "Account", key: "account" },
            { label: "Property", key: "name" },
            { label: "ID", key: "property_id" },
          ],
          props
        );
        note.textContent += " Pick an ID from the Google Ads links table below.";
      }
      emptyTable("gaChannels");
      emptyTable("gaLandings");
      emptyTable("gaEvents");
      emptyTable("gaConvEvents");
      emptyTable("gaAdsGoals");
      return;
    }

    const t = data.totals || {};
    const errKeys = Object.keys(errs);
    note.textContent =
      `GA4 property ${data.property_id || st.property_id} · last ${data.days || state.days} days` +
      (errKeys.length ? ` · partial errors: ${errKeys.join(", ")}` : "");

    const fmtDur = (sec) => {
      const s = Math.round(Number(sec) || 0);
      if (s < 60) return `${s}s`;
      return `${Math.floor(s / 60)}m ${s % 60}s`;
    };

    kpis.innerHTML = [
      { label: "Sessions", value: num(t.sessions), hint: "All sessions" },
      { label: "Users", value: num(t.activeUsers), hint: "Active users" },
      { label: "Engaged", value: num(t.engagedSessions), hint: "Engaged sessions" },
      { label: "Conv. (GA4)", value: num(t.conversions), hint: "Key events counted as conversions" },
      { label: "Revenue", value: money(t.totalRevenue), hint: "totalRevenue" },
      { label: "Avg duration", value: fmtDur(t.averageSessionDuration), hint: "Average session" },
    ]
      .map(
        (i) =>
          `<div class="kpi"><div class="label">${i.label}</div><div class="value">${i.value}</div><div class="delta">${i.hint}</div></div>`
      )
      .join("");

    const channels = (data.channels && data.channels.items) || [];
    setChip("gaChannelsChip", `${channels.length}`);
    renderTable(
      document.getElementById("gaChannels"),
      [
        { label: "Channel", key: "sessionDefaultChannelGroup" },
        { label: "Sessions", render: (r) => num(r.sessions) },
        { label: "Users", render: (r) => num(r.activeUsers) },
        { label: "Engaged", render: (r) => num(r.engagedSessions) },
        { label: "Conv.", render: (r) => num(r.conversions) },
        { label: "Bounce", render: (r) => pct(r.bounceRate) },
      ],
      channels
    );

    const landings = (data.landing_pages && data.landing_pages.items) || [];
    setChip("gaLandingsChip", `${landings.length}`);
    renderTable(
      document.getElementById("gaLandings"),
      [
        { label: "Landing", key: "landingPage" },
        { label: "Sessions", render: (r) => num(r.sessions) },
        { label: "Engaged", render: (r) => num(r.engagedSessions) },
        { label: "Conv.", render: (r) => num(r.conversions) },
        { label: "Bounce", render: (r) => pct(r.bounceRate) },
      ],
      landings
    );

    const events = (data.events && data.events.items) || [];
    setChip("gaEventsChip", `${events.length}`);
    renderTable(
      document.getElementById("gaEvents"),
      [
        { label: "Event", key: "eventName" },
        { label: "Count", render: (r) => num(r.eventCount) },
        { label: "As conv.", render: (r) => num(r.conversions) },
      ],
      events
    );

    const convEvents = (data.conversion_events && data.conversion_events.items) || [];
    setChip("gaConvChip", `${convEvents.length}`);
    renderTable(
      document.getElementById("gaConvEvents"),
      [
        { label: "Key event", key: "event_name" },
        { label: "Counting", key: "counting_method" },
        { label: "Custom", render: (r) => (r.custom ? "yes" : "no") },
        { label: "Deletable", render: (r) => (r.deletable ? "yes" : "no") },
      ],
      convEvents
    );

    const links = (data.ads_links && data.ads_links.items) || [];
    renderTable(
      document.getElementById("gaLinks"),
      [
        { label: "Customer ID", render: (r) => r.customer_id || "—" },
        { label: "Name", key: "name" },
        { label: "Ads personalization", render: (r) => (r.ads_personalization_enabled == null ? "—" : String(r.ads_personalization_enabled)) },
      ],
      links.length ? links : []
    );
    if (!links.length) emptyTable("gaLinks", errs.ads_links || "No Google Ads links");

    const goals = data.ads_conversion_actions || [];
    renderTable(
      document.getElementById("gaAdsGoals"),
      [
        { label: "Action", key: "name" },
        { label: "Category", key: "category" },
        { label: "Origin", key: "origin" },
        {
          label: "Primary",
          render: (r) => (r.primary_for_goal ? "Primary" : "Secondary"),
        },
        { label: "Status", render: (r) => statusBadge(r.status) },
      ],
      goals
    );

    state.analyticsLoadedForDays = state.days;
  } catch (e) {
    note.innerHTML = `<span class="ga-error">${escapeHtml(String(e.message || e))}</span>`;
    kpis.innerHTML = "";
  } finally {
    state.analyticsBusy = false;
    if (reloadBtn) reloadBtn.disabled = false;
  }
}

function setupDoneKey() {
  return "gads_setup_done_v1";
}

function loadSetupDoneMap() {
  try {
    return JSON.parse(localStorage.getItem(setupDoneKey()) || "{}") || {};
  } catch {
    return {};
  }
}

function saveSetupDoneMap(map) {
  localStorage.setItem(setupDoneKey(), JSON.stringify(map));
}

function formatSetupWhen(iso) {
  if (!iso) return "—";
  try {
    return new Intl.DateTimeFormat("en-GB", {
      dateStyle: "medium",
      timeStyle: "short",
    }).format(new Date(iso));
  } catch {
    return String(iso).slice(0, 16).replace("T", " ");
  }
}

function renderSetupView() {
  const guide = state.setupGuide;
  const banner = document.getElementById("setupBanner");
  const list = document.getElementById("setupList");
  const progress = document.getElementById("setupProgress");
  if (!banner || !list) return;
  if (!guide || !Array.isArray(guide.items)) {
    banner.innerHTML = `<p class="muted">Loading playbook…</p>`;
    list.innerHTML = "";
    return;
  }

  const doneMap = loadSetupDoneMap();
  const items = guide.items || [];
  const doneCount = items.filter((i) => doneMap[i.id]).length;
  const filter = document.getElementById("setupFilter")?.value || "all";

  banner.innerHTML = `
    <div class="setup-banner-title">${escapeHtml(guide.source_label || "Playbook")}</div>
    <p class="setup-banner-text">${escapeHtml(guide.source_detail || "")}</p>
    <p class="setup-banner-meta">
      Guide version: <b>${escapeHtml(guide.guide_updated || "—")}</b>
      · not the same as <b>Optimize → Priority actions</b> (live account alerts)
    </p>
  `;

  if (progress) {
    progress.textContent = `Done ${doneCount} / ${items.length} (marks stored in this browser only)`;
  }

  const filtered = items.filter((item) => {
    const isDone = Boolean(doneMap[item.id]);
    if (filter === "open") return !isDone;
    if (filter === "done") return isDone;
    return true;
  });

  list.innerHTML =
    filtered
      .map((item) => {
        const done = doneMap[item.id];
        const sev =
          item.priority === "critical" ? "high" : item.priority === "high" ? "medium" : "low";
        const when = done?.at
          ? `<div class="setup-when">Marked done: ${formatSetupWhen(done.at)}</div>`
          : `<div class="setup-when muted">No event date — static checklist item, not an API alert</div>`;
        return `<article class="setup-card ${done ? "is-done" : ""}" data-id="${escapeHtml(item.id)}">
          <div class="setup-card-top">
            ${severityBadge(sev)}
            <span class="setup-area">${escapeHtml(item.area || "")}</span>
            <span class="chip">${escapeHtml(item.priority)}</span>
          </div>
          <h3 class="setup-item">${escapeHtml(item.item || "")}</h3>
          <p class="setup-why">${escapeHtml(item.why || "")}</p>
          ${when}
          <div class="setup-actions">
            <button type="button" class="btn btn-primary setup-chat-btn" data-prompt="${encodeURIComponent(
              item.chat_prompt || item.item
            )}">Ask AI Assistant</button>
            <button type="button" class="btn btn-ghost setup-toggle-btn" data-id="${escapeHtml(item.id)}">
              ${done ? "Reopen" : "Mark done"}
            </button>
          </div>
        </article>`;
      })
      .join("") || `<p class="muted">No items in this filter.</p>`;

  list.querySelectorAll(".setup-toggle-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      const id = btn.dataset.id;
      const map = loadSetupDoneMap();
      if (map[id]) delete map[id];
      else map[id] = { at: new Date().toISOString() };
      saveSetupDoneMap(map);
      renderSetupView();
    });
  });
  list.querySelectorAll(".setup-chat-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      const prompt = decodeURIComponent(btn.dataset.prompt || "");
      askAssistant(prompt);
    });
  });
}

async function loadSetup() {
  try {
    const data = await api("/api/playbook");
    normalizePlaybook(data);
  } catch (e1) {
    try {
      const data = await api("/api/setup");
      normalizePlaybook(data);
    } catch (e2) {
      const banner = document.getElementById("setupBanner");
      const list = document.getElementById("setupList");
      if (banner) {
        banner.innerHTML = `<p class="muted">Failed to load playbook: ${escapeHtml(
          e2.message || e1.message || e2
        )}. Restart the app server if /api/playbook is missing.</p>`;
      }
      if (list) list.innerHTML = "";
    }
  }
}

function switchView(name) {
  document.querySelectorAll(".nav-item").forEach((b) => b.classList.toggle("active", b.dataset.view === name));
  document.querySelectorAll(".view").forEach((v) => v.classList.toggle("active", v.id === `view-${name}`));
  document.getElementById("pageTitle").textContent = titles[name] || name;
  updateChatFabVisibility(name);
  if (name === "playbook") {
    if (state.setupGuide) renderSetupView();
    else loadSetup().catch(() => {});
  }
  if (name === "setup") {
    loadCredsSetup().catch(() => {});
  }
  if (name === "analytics") {
    loadAnalytics(false).catch(() => {});
  }
  if (name === "recommendations") {
    loadOptimize(false).catch(() => {});
  }
  if (name === "creatives") {
    loadCreatives(true).catch(() => {});
  }
  if (name === "searchterms") {
    loadSearchTerms(false).catch(() => {});
  }
}

function clearChatLog() {
  const main = document.getElementById("chatLog");
  const dock = document.getElementById("dockChatLog");
  if (main) main.innerHTML = "";
  if (dock) dock.innerHTML = "";
}

const ATTACH_MAX = 5;
const ATTACH_MAX_BYTES = 3_500_000;
const ATTACH_IMAGE = new Set(["image/jpeg", "image/png", "image/gif", "image/webp"]);
const ATTACH_TEXT_EXT = new Set([".txt", ".md", ".csv", ".json", ".log", ".tsv"]);

function attachExt(name) {
  const m = String(name || "").match(/(\.[a-zA-Z0-9]+)$/);
  return (m ? m[1] : "").toLowerCase();
}

function isAllowedAttachment(file) {
  const mime = (file.type || "").split(";")[0].toLowerCase();
  if (ATTACH_IMAGE.has(mime) || mime.startsWith("text/") || mime === "application/json") return true;
  return ATTACH_TEXT_EXT.has(attachExt(file.name));
}

function formatBytes(n) {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / (1024 * 1024)).toFixed(1)} MB`;
}

function readFileAsAttachment(file) {
  return new Promise((resolve, reject) => {
    if (!isAllowedAttachment(file)) {
      reject(new Error(`Unsupported file: ${file.name}`));
      return;
    }
    if (file.size > ATTACH_MAX_BYTES) {
      reject(new Error(`Too large: ${file.name} (max ${ATTACH_MAX_BYTES / 1_000_000}MB)`));
      return;
    }
    const reader = new FileReader();
    reader.onload = () => {
      const dataUrl = String(reader.result || "");
      const comma = dataUrl.indexOf(",");
      const data_base64 = comma >= 0 ? dataUrl.slice(comma + 1) : dataUrl;
      const mime = (file.type || "application/octet-stream").split(";")[0] || "application/octet-stream";
      resolve({
        id: `${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
        name: file.name,
        mime,
        data_base64,
        previewUrl: mime.startsWith("image/") ? dataUrl : null,
        size: file.size,
      });
    };
    reader.onerror = () => reject(new Error(`Failed to read ${file.name}`));
    reader.readAsDataURL(file);
  });
}

function renderAttachPreviews() {
  const items = state.pendingAttachments || [];
  for (const id of ["chatAttachPreview", "dockAttachPreview"]) {
    const el = document.getElementById(id);
    if (!el) continue;
    el.hidden = items.length === 0;
    el.innerHTML = items
      .map((a) => {
        const thumb = a.previewUrl
          ? `<img src="${a.previewUrl}" alt="">`
          : `<span class="material-symbols-outlined">draft</span>`;
        return `<div class="attach-chip" data-id="${escapeAttr(a.id)}">
          ${thumb}
          <div class="attach-chip-meta">
            <span class="attach-chip-name">${escapeHtml(a.name)}</span>
            <span class="attach-chip-size">${escapeHtml(formatBytes(a.size || 0))}</span>
          </div>
          <button type="button" class="attach-chip-remove" data-remove="${escapeAttr(a.id)}" title="Remove" aria-label="Remove">
            <span class="material-symbols-outlined">close</span>
          </button>
        </div>`;
      })
      .join("");
    el.querySelectorAll("[data-remove]").forEach((btn) => {
      btn.addEventListener("click", () => removePendingAttachment(btn.dataset.remove));
    });
  }
}

function clearPendingAttachments() {
  state.pendingAttachments = [];
  renderAttachPreviews();
}

function removePendingAttachment(id) {
  state.pendingAttachments = (state.pendingAttachments || []).filter((a) => a.id !== id);
  renderAttachPreviews();
}

async function addPendingFiles(fileList) {
  const files = [...(fileList || [])];
  if (!files.length) return;
  const status = document.getElementById("chatStatus");
  const dockStatus = document.getElementById("dockChatStatus");
  for (const file of files) {
    if ((state.pendingAttachments || []).length >= ATTACH_MAX) {
      const msg = `Max ${ATTACH_MAX} attachments`;
      if (status) status.textContent = msg;
      if (dockStatus) dockStatus.textContent = msg;
      break;
    }
    try {
      const att = await readFileAsAttachment(file);
      state.pendingAttachments.push(att);
    } catch (e) {
      const msg = String(e.message || e);
      if (status) status.textContent = msg;
      if (dockStatus) dockStatus.textContent = msg;
    }
  }
  renderAttachPreviews();
}

function contentPartsToHtml(content) {
  if (content == null || content === "") return "";
  if (typeof content === "string") {
    return `<div class="bubble-text">${escapeHtml(content)}</div>`;
  }
  if (!Array.isArray(content)) {
    return `<div class="bubble-text">${escapeHtml(String(content))}</div>`;
  }
  const media = [];
  const texts = [];
  for (const part of content) {
    if (typeof part === "string") {
      texts.push(part);
      continue;
    }
    if (!part || typeof part !== "object") continue;
    if (part.type === "image_url") {
      const url = part.image_url?.url || part.image_url || "";
      if (url) {
        media.push(`<img src="${escapeAttr(url)}" alt="attachment">`);
      }
    } else if (part.type === "text") {
      const t = String(part.text || "");
      const m = t.match(/^Attached file: ([^\n]+)\n```\n([\s\S]*)\n```$/);
      if (m) {
        media.push(
          `<span class="bubble-file"><span class="material-symbols-outlined">draft</span>${escapeHtml(m[1])}</span>`
        );
      } else if (t) {
        texts.push(t);
      }
    }
  }
  let html = "";
  if (media.length) html += `<div class="bubble-media">${media.join("")}</div>`;
  if (texts.length) html += `<div class="bubble-text">${escapeHtml(texts.join("\n"))}</div>`;
  return html || `<div class="bubble-text"></div>`;
}

function userBubbleFromPending(text, attachments) {
  const parts = [];
  for (const a of attachments || []) {
    if (a.previewUrl) {
      parts.push({ type: "image_url", image_url: { url: a.previewUrl } });
    } else {
      parts.push({ type: "text", text: `Attached file: ${a.name}\n\`\`\`\n\n\`\`\`` });
    }
  }
  if ((text || "").trim()) parts.push({ type: "text", text: text.trim() });
  if (parts.length === 1 && parts[0].type === "text" && !(attachments || []).length) {
    return parts[0].text;
  }
  return parts.length ? parts : text || "";
}

function appendBubble(role, content) {
  const make = () => {
    const div = document.createElement("div");
    div.className = `bubble ${role}`;
    if (role === "user" && (Array.isArray(content) || (typeof content === "object" && content !== null))) {
      div.innerHTML = contentPartsToHtml(content);
    } else if (role === "user" && typeof content === "string" && !content.includes("\0")) {
      // plain text user message
      div.textContent = content;
    } else if (role === "assistant" || role === "tool") {
      div.textContent = typeof content === "string" ? content : String(content ?? "");
    } else {
      div.textContent = typeof content === "string" ? content : String(content ?? "");
    }
    return div;
  };
  const main = document.getElementById("chatLog");
  if (main) {
    main.appendChild(make());
    main.scrollTop = main.scrollHeight;
  }
  const dock = document.getElementById("dockChatLog");
  if (dock) {
    dock.appendChild(make());
    dock.scrollTop = dock.scrollHeight;
  }
}

function syncDockChatLog() {
  const dock = document.getElementById("dockChatLog");
  const main = document.getElementById("chatLog");
  if (!dock || !main) return;
  dock.innerHTML = "";
  main.querySelectorAll(".bubble").forEach((node) => {
    dock.appendChild(node.cloneNode(true));
  });
  dock.scrollTop = dock.scrollHeight;
}

function isChatDockOpen() {
  return document.body.classList.contains("chat-dock-open");
}

function updateChatFabVisibility(viewName) {
  const fab = document.getElementById("chatFab");
  if (!fab) return;
  // Hide FAB on full AI Assistant page when dock is closed
  const hide = viewName === "chat" && !isChatDockOpen();
  fab.classList.toggle("is-hidden", hide);
}

function openChatDock() {
  const dock = document.getElementById("chatDock");
  const fab = document.getElementById("chatFab");
  if (!dock) return;
  dock.hidden = false;
  document.body.classList.add("chat-dock-open");
  if (fab) fab.setAttribute("aria-expanded", "true");
  syncDockChatLog();
  const status = document.getElementById("chatStatus");
  const dockStatus = document.getElementById("dockChatStatus");
  if (status && dockStatus) dockStatus.textContent = status.textContent || "Ready";
  document.getElementById("dockChatInput")?.focus();
}

function closeChatDock() {
  const dock = document.getElementById("chatDock");
  const fab = document.getElementById("chatFab");
  if (dock) dock.hidden = true;
  document.body.classList.remove("chat-dock-open");
  if (fab) fab.setAttribute("aria-expanded", "false");
  const active = document.querySelector(".nav-item.active")?.dataset?.view || "chat";
  updateChatFabVisibility(active);
}

function toggleChatDock() {
  if (isChatDockOpen()) closeChatDock();
  else openChatDock();
}

function askAssistant(prompt) {
  openChatDock();
  stopVoiceInput();
  sendChat(prompt);
}

function renderChatList() {
  const box = document.getElementById("chatList");
  const items = state.chats || [];
  if (!items.length) {
    box.innerHTML = `<p class="chat-empty">No saved conversations. Send a message or click New.</p>`;
    return;
  }
  box.innerHTML = items
    .map((c) => {
      const active = c.id === state.chatId ? "active" : "";
      const when = (c.updated_at || "").slice(0, 16).replace("T", " ");
      return `<div class="chat-item ${active}" data-id="${escapeAttr(c.id)}">
        <div class="chat-item-top">
          <div class="chat-item-title">${escapeHtml(c.title || "AI Assistant")}</div>
          <button type="button" class="chat-item-del" data-del="${escapeAttr(c.id)}" title="Delete conversation">
            <span class="material-symbols-outlined">delete</span>
          </button>
        </div>
        <div class="chat-item-meta">${escapeHtml(when)} · ${num(c.message_count || 0)} msg</div>
      </div>`;
    })
    .join("");

  box.querySelectorAll(".chat-item").forEach((el) => {
    el.addEventListener("click", (e) => {
      if (e.target.closest("[data-del]")) return;
      openChat(el.dataset.id);
    });
  });
  box.querySelectorAll("[data-del]").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      deleteChat(btn.dataset.del);
    });
  });
}

async function loadChatList() {
  const data = await api("/api/chats", { silent: state.pending > 0 || state.chatBusy });
  state.chats = data.items || [];
  renderChatList();
}

function renderStoredMessages(messages) {
  clearChatLog();
  state.history = [];
  for (const m of messages || []) {
    if (m.role === "user") {
      appendBubble("user", m.content || "");
      state.history.push({ role: "user", content: m.content || "" });
    } else if (m.role === "assistant") {
      if (m.tool_trace && m.tool_trace.length) {
        appendBubble("tool", m.tool_trace.map((t) => `▸ ${t.tool}`).join("\n"));
      }
      appendBubble("assistant", m.content || "");
      state.history.push({ role: "assistant", content: m.content || "" });
    }
  }
}

async function openChat(chatId) {
  if (!chatId || state.chatBusy) return;
  const chat = await api(`/api/chats/${chatId}`);
  state.chatId = chat.id;
  if (chat.model) {
    setSelectedModel(chat.model, { silent: true });
  }
  renderStoredMessages(chat.messages || []);
  renderChatList();
  localStorage.setItem("gads_active_chat", chat.id);
}

async function createNewChat() {
  if (state.chatBusy) return;
  const model = getSelectedModel();
  const chat = await api("/api/chats", {
    method: "POST",
    body: JSON.stringify({ model }),
  });
  state.chatId = chat.id;
  state.history = [];
  clearChatLog();
  localStorage.setItem("gads_active_chat", chat.id);
  await loadChatList();
}

async function deleteChat(chatId) {
  if (!chatId || state.chatBusy) return;
  const title = (state.chats.find((c) => c.id === chatId) || {}).title || "this conversation";
  if (!confirm(`Delete conversation “${title}”?`)) return;
  await api(`/api/chats/${chatId}`, { method: "DELETE" });
  if (state.chatId === chatId) {
    state.chatId = null;
    state.history = [];
    clearChatLog();
    localStorage.removeItem("gads_active_chat");
  }
  await loadChatList();
  if (!state.chatId && state.chats.length) {
    await openChat(state.chats[0].id);
  }
}

async function ensureChatId() {
  if (state.chatId) return state.chatId;
  const model = getSelectedModel();
  const chat = await api("/api/chats", {
    method: "POST",
    body: JSON.stringify({ model }),
  });
  state.chatId = chat.id;
  localStorage.setItem("gads_active_chat", chat.id);
  await loadChatList();
  return state.chatId;
}

function modelSelectEls() {
  return [...document.querySelectorAll("[data-model-select]")];
}

function getSelectedModel() {
  const el = document.getElementById("modelSelect") || modelSelectEls()[0];
  return (el && el.value) || state.model || "";
}

function setSelectedModel(modelId, { silent } = {}) {
  if (!modelId) return;
  state.model = modelId;
  for (const el of modelSelectEls()) {
    if ([...el.options].some((o) => o.value === modelId)) {
      el.value = modelId;
    }
  }
  if (!silent) {
    /* callers handle persist */
  }
}

function shortModelLabel(id, name) {
  const raw = String(name || id || "");
  // Prefer readable short names for the compact composer dropdown
  const cleaned = raw
    .replace(/^anthropic\//i, "")
    .replace(/^openai\//i, "")
    .replace(/^google\//i, "")
    .replace(/^meta-llama\//i, "")
    .replace(/:free$/i, "");
  if (cleaned.length <= 28) return cleaned;
  return cleaned.slice(0, 27) + "…";
}

async function loadModels() {
  const status = document.getElementById("chatStatus");
  const selects = modelSelectEls();
  try {
    const data = await api("/api/models");
    state.models = data.items || [];
    const optionsHtml = state.models
      .map(
        (m) =>
          `<option value="${escapeAttr(m.id)}">${escapeHtml(shortModelLabel(m.id, m.name))}</option>`
      )
      .join("");
    for (const select of selects) {
      select.innerHTML = optionsHtml;
    }
    const preferred = data.default_model || state.model;
    if (preferred && state.models.some((m) => m.id === preferred)) {
      setSelectedModel(preferred, { silent: true });
    } else if (selects[0]) {
      state.model = selects[0].value;
    }
    if (data.configured) {
      status.classList.remove("warn");
      status.textContent = `OpenRouter ready · top-${state.models.length} · history saved`;
    } else {
      status.classList.add("warn");
      status.textContent = "Add OPENROUTER_API_KEY to .env — AI Assistant drives the whole system";
    }
    const dockStatus = document.getElementById("dockChatStatus");
    if (dockStatus) dockStatus.textContent = status.textContent;
  } catch (e) {
    status.classList.add("warn");
    status.textContent = String(e.message || e);
  }
}

async function sendChat(text, attachments) {
  const atts = attachments != null ? attachments : [...(state.pendingAttachments || [])];
  const message = (text || "").trim();
  if ((!message && !atts.length) || state.chatBusy) return;
  if (attachments == null) clearPendingAttachments();

  state.chatBusy = true;
  const sendBtn = document.getElementById("chatSend");
  const dockSend = document.getElementById("dockChatSend");
  if (sendBtn) sendBtn.disabled = true;
  if (dockSend) dockSend.disabled = true;

  const displayContent = userBubbleFromPending(message, atts);
  appendBubble("user", displayContent);
  state.history.push({ role: "user", content: message || "[attachment]" });

  appendBubble("assistant", "");
  const thinkers = [];
  for (const id of ["chatLog", "dockChatLog"]) {
    const el = document.getElementById(id)?.lastElementChild;
    if (!el) continue;
    el.classList.add("thinking");
    el.innerHTML =
      '<span class="thinking-dots" aria-hidden="true"><i></i><i></i><i></i></span>' +
      "<span>Thinking and calling tools…</span>";
    thinkers.push(el);
  }
  const dockStatus = document.getElementById("dockChatStatus");
  if (dockStatus) dockStatus.textContent = "Working…";
  try {
    const chatId = await ensureChatId();
    const model = getSelectedModel();
    const data = await api("/api/chat", {
      method: "POST",
      body: JSON.stringify({
        message,
        model,
        chat_id: chatId,
        history: state.history.slice(0, -1),
        attachments: atts.map((a) => ({
          name: a.name,
          mime: a.mime,
          data_base64: a.data_base64,
        })),
      }),
    });
    if (data.chat_id) {
      state.chatId = data.chat_id;
      localStorage.setItem("gads_active_chat", data.chat_id);
    }
    thinkers.forEach((t) => t.remove());
    if (data.tool_trace && data.tool_trace.length) {
      const tools = data.tool_trace.map((t) => `▸ ${t.tool}`).join("\n");
      appendBubble("tool", tools);
    }
    const reply = data.message || "(empty reply)";
    appendBubble("assistant", reply);
    state.history.push({ role: "assistant", content: reply });
    if (data.pending_mutation) {
      openConfirmModal(data.pending_mutation);
    }
    await loadChatList();
    if (dockStatus) dockStatus.textContent = "Ready";
  } catch (e) {
    thinkers.forEach((t) => t.remove());
    appendBubble("assistant", `Error: ${e.message || e}`);
    if (state.history.length && state.history[state.history.length - 1].role === "user") {
      state.history.pop();
    }
    if (dockStatus) dockStatus.textContent = "Error";
  } finally {
    state.chatBusy = false;
    if (sendBtn) sendBtn.disabled = false;
    if (dockSend) dockSend.disabled = false;
  }
}

async function refresh() {
  state.days = Number(document.getElementById("daysSelect").value);
  state.loadLabel = "Refreshing account data…";
  // Force GA reload next time Analytics is opened if period changed
  if (state.analyticsLoadedForDays !== state.days) {
    state.analyticsLoadedForDays = null;
  }
  await loadOverview();
  await loadAccounts();
  await loadTables();
  await loadSetup();
  const active = document.querySelector(".nav-item.active")?.dataset?.view;
  if (active === "analytics") {
    await loadAnalytics(true);
  }
  if (active === "recommendations") {
    state.optimizeData = null;
    await loadOptimize(true);
  }
  if (active === "searchterms") {
    await loadSearchTerms(true);
  }
}

async function mutateAction(action, payload, promptText) {
  if (promptText && !window.confirm(promptText)) return null;
  const data = await api("/api/mutate", {
    method: "POST",
    body: JSON.stringify({ action, payload, confirm: true }),
  });
  if (data.needs_confirmation) {
    openConfirmModal({
      id: data.pending_id,
      action,
      preview: data.preview || data,
    });
    return data;
  }
  return data;
}

function openConfirmModal(item) {
  const modal = document.getElementById("confirmModal");
  if (!modal || !item) return;
  state.pendingConfirmId = item.id || item.pending_id || null;
  const title = document.getElementById("confirmModalTitle");
  const sub = document.getElementById("confirmModalSub");
  const preview = document.getElementById("confirmModalPreview");
  const status = document.getElementById("confirmModalStatus");
  if (title) title.textContent = `Confirm: ${item.action || "mutation"}`;
  if (sub) sub.textContent = state.pendingConfirmId ? `pending_id ${state.pendingConfirmId}` : "Review preview";
  if (preview) preview.textContent = JSON.stringify(item.preview || item, null, 2);
  if (status) status.textContent = "";
  modal.hidden = false;
}

function closeConfirmModal() {
  const modal = document.getElementById("confirmModal");
  if (modal) modal.hidden = true;
  state.pendingConfirmId = null;
}

async function applyConfirmModal() {
  const status = document.getElementById("confirmModalStatus");
  const btn = document.getElementById("confirmModalApply");
  if (!state.pendingConfirmId) {
    if (status) status.textContent = "No pending mutation.";
    return;
  }
  if (btn) btn.disabled = true;
  if (status) status.textContent = "Applying…";
  try {
    const data = await api("/api/mutations/confirm", {
      method: "POST",
      body: JSON.stringify({ pending_id: state.pendingConfirmId }),
    });
    if (status) status.textContent = data.ok ? "Applied." : data.error || JSON.stringify(data);
    if (data.ok) {
      closeConfirmModal();
      await refresh();
    }
  } catch (e) {
    if (status) status.textContent = String(e.message || e);
  } finally {
    if (btn) btn.disabled = false;
  }
}

async function loadAccounts() {
  const sel = document.getElementById("accountSelect");
  if (!sel) return;
  try {
    const data = await api("/api/accounts", { silent: true });
    const items = data.accounts || [];
    const current = String(
      (state.overview && state.overview.account && state.overview.account.id) || sel.value || ""
    );
    sel.innerHTML =
      items
        .map((a) => {
          const id = String(a.id || "");
          const label = a.name ? `${a.name} · ${id}` : id;
          return `<option value="${escapeAttr(id)}">${escapeHtml(label)}</option>`;
        })
        .join("") || `<option value="">—</option>`;
    if (current && [...sel.options].some((o) => o.value === current)) sel.value = current;
  } catch (_) {
    /* keep current */
  }
}

async function switchAccount(customerId) {
  if (!customerId) return;
  await api("/api/account/switch", {
    method: "POST",
    body: JSON.stringify({ customer_id: customerId }),
  });
  state.searchTerms = [];
  await refresh();
}

async function loadSearchTerms(force = false) {
  if (state.searchTermsBusy) return;
  if (!force && state.searchTerms.length) {
    renderSearchTermsView();
    return;
  }
  state.searchTermsBusy = true;
  try {
    const data = await api(`/api/search-terms?days=${state.days}`);
    state.searchTerms = (data.items || []).map((r) => ({
      ...r,
      campaign: r.campaign || r.campaign_name,
      ad_group: r.ad_group || r.ad_group_name,
    }));
    renderSearchTermsView();
  } finally {
    state.searchTermsBusy = false;
  }
}

function renderSearchTermsView() {
  const box = document.getElementById("searchTermsTable");
  if (!box) return;
  const all = state.searchTerms || [];
  const campaignSel = document.getElementById("stCampaignFilter");
  if (campaignSel) fillCampaignSelect(campaignSel, all);
  const filtered = applyListControls(all, {
    campaign: campaignSel?.value || "",
    search: document.getElementById("stSearch")?.value || "",
    sort: document.getElementById("stSort")?.value || "cost_desc",
    searchFields: ["search_term", "campaign", "campaign_name", "ad_group", "ad_group_name", "status"],
  });
  const cols = [
    { label: "Search term", key: "search_term" },
    { label: "Campaign", key: "campaign_name" },
    { label: "Ad group", key: "ad_group_name" },
    { label: "Status", render: (r) => statusBadge(r.status) },
    { label: "Cost", render: (r) => money(r.cost) },
    { label: "Clicks", render: (r) => num(r.clicks) },
    { label: "Conv.", render: (r) => num(r.conversions) },
    {
      label: "Actions",
      render: (r) =>
        rowActionBtns([
          actionBtn("js-st-neg", "Add negative", {
            "data-campaign-id": r.campaign_id || "",
            "data-term": r.search_term || "",
          }),
        ]),
    },
  ];
  renderTable(box, cols, filtered);
  const chip = document.getElementById("stCount");
  if (chip) {
    const campaign = campaignSel?.value || "";
    if (campaign) {
      chip.innerHTML = `${num(filtered.length)} <span class="muted-part">terms in ${escapeHtml(campaign)}</span>`;
    } else {
      setCountChip(chip, filtered.length, all.length, "terms");
    }
  }
}

function parseKeywordLines(text) {
  return String(text || "")
    .split(/\n/)
    .map((l) => l.trim())
    .filter(Boolean)
    .map((line) => {
      const m = line.match(/^(exact|phrase|broad)\s+(.+)$/i);
      if (m) return { text: m[2].trim(), match_type: m[1].toUpperCase() };
      return { text: line, match_type: "PHRASE" };
    });
}

function parseSitelinkLines(text) {
  return String(text || "")
    .split(/\n/)
    .map((l) => l.trim())
    .filter(Boolean)
    .map((line) => {
      const p = line.split("|").map((s) => s.trim());
      return {
        link_text: p[0] || "",
        final_url: p[1] || "",
        description1: p[2] || "",
        description2: p[3] || "",
      };
    })
    .filter((s) => s.link_text && s.final_url);
}

function collectWizardPayload() {
  const form = document.getElementById("wizardForm");
  if (!form) return null;
  const fd = new FormData(form);
  const headlines = String(fd.get("headlines") || "")
    .split(/\n/)
    .map((s) => s.trim())
    .filter(Boolean);
  const descriptions = String(fd.get("descriptions") || "")
    .split(/\n/)
    .map((s) => s.trim())
    .filter(Boolean);
  const targetCpa = Number(fd.get("target_cpa") || 0);
  return {
    campaign_name: String(fd.get("campaign_name") || "").trim(),
    daily_budget: Number(fd.get("daily_budget") || 0),
    bidding: String(fd.get("bidding") || "maximize_clicks"),
    ad_group_name: String(fd.get("ad_group_name") || "").trim(),
    final_url: String(fd.get("final_url") || "").trim(),
    cpc_bid: Number(fd.get("cpc_bid") || 1),
    target_cpa: targetCpa > 0 ? targetCpa : null,
    headlines,
    descriptions,
    keywords: parseKeywordLines(fd.get("keywords")),
    sitelinks: parseSitelinkLines(fd.get("sitelinks")),
    start_paused: true,
  };
}

function showWizardStatus(msg, previewObj) {
  const status = document.getElementById("wizardStatus");
  const preview = document.getElementById("wizardPreview");
  if (status) status.textContent = msg || "";
  if (preview) {
    if (previewObj) {
      preview.hidden = false;
      preview.textContent = typeof previewObj === "string" ? previewObj : JSON.stringify(previewObj, null, 2);
    }
  }
}

async function wizardPreview() {
  const payload = collectWizardPayload();
  if (!payload) return;
  showWizardStatus("Preview…");
  try {
    const data = await api("/api/campaigns/create", {
      method: "POST",
      body: JSON.stringify({ ...payload, confirm: false }),
    });
    showWizardStatus(data.needs_confirmation ? "Preview only — confirm to create (paused)." : "Preview");
    const box = document.getElementById("wizardPreview");
    if (box) {
      box.hidden = false;
      box.textContent = JSON.stringify(data.preview || data, null, 2);
    }
  } catch (e) {
    showWizardStatus(String(e.message || e));
  }
}

async function wizardCreate(e) {
  e.preventDefault();
  const payload = collectWizardPayload();
  if (!payload) return;
  if (!window.confirm("Create Search campaign as PAUSED in Google Ads?")) return;
  showWizardStatus("Creating…");
  try {
    const data = await api("/api/campaigns/create", {
      method: "POST",
      body: JSON.stringify({ ...payload, confirm: true }),
    });
    if (data.needs_confirmation) {
      openConfirmModal({
        id: data.pending_id,
        action: "create_full_search_setup",
        preview: data.preview || data,
      });
      showWizardStatus("Needs confirmation.");
      return;
    }
    const box = document.getElementById("wizardPreview");
    if (box) {
      box.hidden = false;
      box.textContent = JSON.stringify(data, null, 2);
    }
    showWizardStatus(data.ok ? `Created campaign ${data.campaign_id || ""} (paused).` : data.error || "Failed");
    if (data.ok) await refresh();
  } catch (e) {
    showWizardStatus(String(e.message || e));
  }
}

async function onCampaignTableClick(e) {
  const btn = e.target.closest("button");
  if (!btn) return;
  const id = btn.dataset.id;
  try {
    if (btn.classList.contains("js-camp-toggle")) {
      await mutateAction(
        "set_campaign_status",
        { campaign_id: id, status: btn.dataset.status },
        `${btn.dataset.status} campaign ${id}?`
      );
      await loadTables();
    } else if (btn.classList.contains("js-camp-budget")) {
      const raw = window.prompt("Daily budget", "50");
      if (!raw) return;
      await mutateAction(
        "update_campaign_budget",
        { campaign_id: id, daily_budget: Number(raw) },
        `Set daily budget ${raw} on ${id}?`
      );
      await loadTables();
    } else if (btn.classList.contains("js-camp-bid")) {
      const bidding = window.prompt(
        "Bidding: maximize_clicks | maximize_conversions | target_cpa | manual_cpc",
        "maximize_clicks"
      );
      if (!bidding) return;
      const payload = { campaign_id: id, bidding: bidding.trim() };
      if (payload.bidding === "target_cpa") {
        const cpa = window.prompt("Target CPA", "20");
        payload.target_cpa = Number(cpa);
      }
      await mutateAction("update_campaign_bidding", payload, `Change bidding on ${id}?`);
      await loadTables();
    }
  } catch (err) {
    window.alert(String(err.message || err));
  }
}

async function onKeywordTableClick(e) {
  const btn = e.target.closest(".js-kw-toggle");
  if (!btn) return;
  try {
    await mutateAction(
      "set_keyword_status",
      {
        status: btn.dataset.status,
        keywords: [
          {
            ad_group_id: btn.dataset.adGroupId,
            criterion_id: btn.dataset.criterionId,
            text: btn.dataset.text || "",
          },
        ],
      },
      `${btn.dataset.status} keyword?`
    );
    await loadTables();
  } catch (err) {
    window.alert(String(err.message || err));
  }
}

async function onAdsTableClick(e) {
  const btn = e.target.closest(".js-ad-toggle");
  if (!btn) return;
  try {
    await mutateAction(
      "set_ad_status",
      {
        status: btn.dataset.status,
        ads: [{ ad_group_id: btn.dataset.adGroupId, ad_id: btn.dataset.adId }],
      },
      `${btn.dataset.status} ad?`
    );
    await loadTables();
  } catch (err) {
    window.alert(String(err.message || err));
  }
}

async function onSearchTermsClick(e) {
  const btn = e.target.closest(".js-st-neg");
  if (!btn) return;
  const term = btn.dataset.term;
  const campaignId = btn.dataset.campaignId;
  try {
    await mutateAction(
      "add_negative_keywords",
      {
        campaign_id: campaignId,
        negatives: [{ text: term, match_type: "EXACT" }],
      },
      `Add EXACT negative "${term}" to campaign ${campaignId}?`
    );
    await loadSearchTerms(true);
  } catch (err) {
    window.alert(String(err.message || err));
  }
}

function renderCredsGuide(guide) {
  const box = document.getElementById("credsGuide");
  if (!box) return;
  box.innerHTML = (guide || []).map((block) => {
    const steps = (block.steps || []).map((s) => `<li>${escapeHtml(s)}</li>`).join("");
    const links = (block.links || []).map((l) => (
      `<a href="${escapeHtml(l.url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(l.label)}</a>`
    )).join("");
    return `<article class="creds-card">
      <h3>${escapeHtml(block.title || "")}</h3>
      <p class="muted">${escapeHtml(block.summary || "")}</p>
      <ol>${steps}</ol>
      <div class="creds-links">${links}</div>
    </article>`;
  }).join("");
}

function renderCredsStatus(data) {
  const el = document.getElementById("credsStatus");
  if (!el) return;
  el.classList.toggle("ready", Boolean(data.ready));
  el.classList.toggle("demo", !data.ready);
  if (data.ready) {
    el.textContent = `Live credentials in .env${data.source ? ` (${data.source})` : ""}`;
  } else {
    el.textContent = "Demo mode — add a developer token, Desktop OAuth client, then sign in";
  }
  const form = document.getElementById("credsForm");
  if (form) {
    if (data.customer_id) form.customer_id.placeholder = data.customer_id;
    if (data.login_customer_id) form.login_customer_id.placeholder = data.login_customer_id;
    if (data.ga4_property_id) form.ga4_property_id.placeholder = data.ga4_property_id;
    if (data.has_developer_token) form.developer_token.placeholder = data.developer_token || "saved";
    if (data.has_client_id) form.client_id.placeholder = data.client_id || "saved";
    if (data.has_client_secret) form.client_secret.placeholder = "saved ••••";
  }
  const accounts = document.getElementById("credsAccounts");
  if (accounts && Array.isArray(data.accounts) && data.accounts.length) {
    accounts.className = "creds-accounts";
    accounts.innerHTML = `<p>Accessible accounts: ${data.accounts.map((a) => escapeHtml(a.name || a.id)).join(", ")}</p>`;
  }
}

async function loadCredsSetup() {
  const data = await api("/api/setup/status");
  renderCredsGuide(data.guide || []);
  renderCredsStatus(data);
  return data;
}

function credsFormPayload() {
  const form = document.getElementById("credsForm");
  const body = {};
  if (!form) return body;
  new FormData(form).forEach((value, key) => {
    const text = String(value || "").trim();
    if (text) body[key] = text;
  });
  return body;
}

async function saveCredsSetup() {
  const msg = document.getElementById("credsMsg");
  const data = await api("/api/setup/save", {
    method: "POST",
    body: JSON.stringify(credsFormPayload()),
  });
  renderCredsStatus(data);
  if (msg) msg.textContent = data.ready ? "Saved. Sign in if the refresh token is still missing." : "Saved to .env. Sign in with Google to finish.";
  return data;
}

async function oauthCredsSetup() {
  const msg = document.getElementById("credsMsg");
  if (msg) msg.textContent = "Saving keys, then opening Google sign-in…";
  await saveCredsSetup();
  const withAnalytics = Boolean(document.getElementById("credsAnalytics")?.checked);
  const data = await api("/api/setup/oauth", {
    method: "POST",
    body: JSON.stringify({
      with_analytics: withAnalytics,
      ...credsFormPayload(),
    }),
  });
  renderCredsStatus(data);
  if (msg) {
    msg.textContent = data.refresh_token_saved
      ? (data.account_error ? `Signed in. Account list failed: ${data.account_error}` : "Signed in. Credentials are in .env.")
      : "Google did not return a refresh token.";
  }
  if (data.ready) {
    await refresh();
  }
}

async function bootstrapChats() {
  await loadChatList();
  const saved = localStorage.getItem("gads_active_chat");
  if (saved && state.chats.some((c) => c.id === saved)) {
    await openChat(saved);
  } else if (state.chats.length) {
    await openChat(state.chats[0].id);
  }
}

document.querySelectorAll(".nav-item").forEach((btn) => {
  btn.addEventListener("click", () => switchView(btn.dataset.view));
});
document.getElementById("credsForm")?.addEventListener("submit", (e) => {
  e.preventDefault();
  saveCredsSetup().catch((err) => {
    const msg = document.getElementById("credsMsg");
    if (msg) msg.textContent = String(err.message || err);
  });
});
document.getElementById("credsOAuthBtn")?.addEventListener("click", () => {
  oauthCredsSetup().catch((err) => {
    const msg = document.getElementById("credsMsg");
    if (msg) msg.textContent = String(err.message || err);
  });
});
document.getElementById("refreshBtn").addEventListener("click", () => refresh());
document.getElementById("daysSelect").addEventListener("change", () => refresh());
modelSelectEls().forEach((el) => {
  el.addEventListener("change", async (e) => {
    setSelectedModel(e.target.value, { silent: true });
    if (!state.chatId) return;
    try {
      await api(`/api/chats/${state.chatId}`, {
        method: "PATCH",
        body: JSON.stringify({ model: state.model }),
      });
      await loadChatList();
    } catch (_) {
      /* ignore */
    }
  });
});
document.getElementById("newChatBtn").addEventListener("click", () => createNewChat());

["kwCampaignFilter", "kwAdGroupFilter", "kwSort"].forEach((id) => {
  document.getElementById(id).addEventListener("change", () => {
    if (id === "kwCampaignFilter") {
      document.getElementById("kwAdGroupFilter").value = "";
    }
    renderKeywordsView();
  });
});
document.getElementById("kwSearch").addEventListener("input", () => renderKeywordsView());

["adCampaignFilter", "adStatusFilter", "adSort"].forEach((id) => {
  document.getElementById(id).addEventListener("change", () => renderAdsView());
});
document.getElementById("adSearch").addEventListener("input", () => renderAdsView());

["crCampaignFilter", "crStatusFilter", "crStrengthFilter", "crSort"].forEach((id) => {
  document.getElementById(id).addEventListener("change", () => renderCreativesView());
});
document.getElementById("crSearch").addEventListener("input", () => renderCreativesView());
document.getElementById("crReloadBtn")?.addEventListener("click", () => loadCreatives(true));

document.getElementById("rsaEditorClose")?.addEventListener("click", () => closeRsaEditor());
document.getElementById("rsaEditorCancel")?.addEventListener("click", () => closeRsaEditor());
document.getElementById("rsaEditorApply")?.addEventListener("click", () => applyRsaEditor());
document.getElementById("rsaAddHeadline")?.addEventListener("click", () => addRsaLine("rsaHeadlineLines", "", 30));
document.getElementById("rsaAddDescription")?.addEventListener("click", () => addRsaLine("rsaDescriptionLines", "", 90));
document.getElementById("rsaAddSitelink")?.addEventListener("click", () => addSitelinkRow());
["rsaEditFinalUrl", "rsaEditPath1", "rsaEditPath2"].forEach((id) => {
  document.getElementById(id)?.addEventListener("input", () => refreshRsaEditorMeta());
});
document.getElementById("rsaEditorModal")?.addEventListener("click", (e) => {
  if (e.target?.id === "rsaEditorModal") closeRsaEditor();
});
document.addEventListener("keydown", (e) => {
  if (e.key !== "Escape") return;
  const confirmEl = document.getElementById("confirmModal");
  if (confirmEl && !confirmEl.hidden) {
    closeConfirmModal();
    return;
  }
  if (document.getElementById("rsaEditorModal") && !document.getElementById("rsaEditorModal").hidden) {
    closeRsaEditor();
  }
});

document.getElementById("campaignsTable")?.addEventListener("click", (e) => onCampaignTableClick(e));
document.getElementById("keywordsTable")?.addEventListener("click", (e) => onKeywordTableClick(e));
document.getElementById("adsTable")?.addEventListener("click", (e) => onAdsTableClick(e));
document.getElementById("searchTermsTable")?.addEventListener("click", (e) => onSearchTermsClick(e));
["stCampaignFilter", "stSort"].forEach((id) => {
  document.getElementById(id)?.addEventListener("change", () => renderSearchTermsView());
});
document.getElementById("stSearch")?.addEventListener("input", () => renderSearchTermsView());
document.getElementById("openWizardBtn")?.addEventListener("click", () => switchView("wizard"));
document.getElementById("wizardPreviewBtn")?.addEventListener("click", () => wizardPreview());
document.getElementById("wizardForm")?.addEventListener("submit", (e) => wizardCreate(e));
document.getElementById("accountSelect")?.addEventListener("change", (e) => switchAccount(e.target.value));
document.getElementById("confirmModalClose")?.addEventListener("click", () => closeConfirmModal());
document.getElementById("confirmModalCancel")?.addEventListener("click", () => closeConfirmModal());
document.getElementById("confirmModalApply")?.addEventListener("click", () => applyConfirmModal());
document.getElementById("confirmModal")?.addEventListener("click", (e) => {
  if (e.target?.id === "confirmModal") closeConfirmModal();
});

document.getElementById("setupFilter")?.addEventListener("change", () => renderSetupView());
document.getElementById("setupResetDone")?.addEventListener("click", () => {
  if (confirm("Clear all Playbook done marks?")) {
    saveSetupDoneMap({});
    renderSetupView();
  }
});
document.getElementById("gaReloadBtn")?.addEventListener("click", () => loadAnalytics(true));
document.getElementById("optReloadBtn")?.addEventListener("click", () => {
  state.optimizeData = null;
  loadOptimize(true);
});
document.getElementById("optFilter")?.addEventListener("change", () => renderOptimizeView());

document.getElementById("chatForm").addEventListener("submit", (e) => {
  e.preventDefault();
  stopVoiceInput();
  const input = document.getElementById("chatInput");
  const text = input.value.trim();
  input.value = "";
  sendChat(text);
});
document.getElementById("dockChatForm")?.addEventListener("submit", (e) => {
  e.preventDefault();
  stopVoiceInput();
  const input = document.getElementById("dockChatInput");
  const text = input.value.trim();
  input.value = "";
  sendChat(text);
});

function wireAttachControls(btnId, inputId) {
  const btn = document.getElementById(btnId);
  const input = document.getElementById(inputId);
  if (!btn || !input) return;
  btn.addEventListener("click", () => input.click());
  input.addEventListener("change", async () => {
    await addPendingFiles(input.files);
    input.value = "";
  });
}
wireAttachControls("chatAttachBtn", "chatFileInput");
wireAttachControls("dockAttachBtn", "dockFileInput");

function wireComposerDrop(formId) {
  const form = document.getElementById(formId);
  if (!form) return;
  const box = form.querySelector(".composer-box") || form;
  ["dragenter", "dragover"].forEach((ev) => {
    box.addEventListener(ev, (e) => {
      e.preventDefault();
      e.stopPropagation();
      box.classList.add("drag-over");
    });
  });
  ["dragleave", "drop"].forEach((ev) => {
    box.addEventListener(ev, (e) => {
      e.preventDefault();
      e.stopPropagation();
      if (ev === "drop") addPendingFiles(e.dataTransfer?.files);
      box.classList.remove("drag-over");
    });
  });
}
wireComposerDrop("chatForm");
wireComposerDrop("dockChatForm");

function wirePasteAttach(textareaId) {
  const ta = document.getElementById(textareaId);
  if (!ta) return;
  ta.addEventListener("paste", async (e) => {
    const items = [...(e.clipboardData?.items || [])];
    const files = items
      .filter((it) => it.kind === "file")
      .map((it) => it.getAsFile())
      .filter(Boolean);
    if (!files.length) return;
    e.preventDefault();
    await addPendingFiles(files);
  });
}
wirePasteAttach("chatInput");
wirePasteAttach("dockChatInput");

function wireEnterToSend(textareaId, formId) {
  const ta = document.getElementById(textareaId);
  const form = document.getElementById(formId);
  if (!ta || !form) return;
  ta.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      form.requestSubmit();
    }
  });
}
wireEnterToSend("chatInput", "chatForm");
wireEnterToSend("dockChatInput", "dockChatForm");

document.getElementById("chatFab")?.addEventListener("click", () => openChatDock());
document.getElementById("dockCloseBtn")?.addEventListener("click", () => closeChatDock());
document.getElementById("dockOpenFullBtn")?.addEventListener("click", () => {
  closeChatDock();
  switchView("chat");
});
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && isChatDockOpen()) closeChatDock();
});
document.querySelectorAll(".prompt-chip").forEach((btn) => {
  btn.addEventListener("click", () => {
    stopVoiceInput();
    sendChat(btn.dataset.prompt);
  });
});

/* —— Voice input (Web Speech API) —— */
let voiceRecognition = null;
let voiceBaseText = "";
let voiceListening = false;
let voiceTargetInputId = "chatInput";

function speechRecognitionCtor() {
  return window.SpeechRecognition || window.webkitSpeechRecognition || null;
}

function voiceButtons() {
  return [...document.querySelectorAll("[data-voice-btn]")];
}

function activeVoiceInput() {
  return (
    document.getElementById(voiceTargetInputId) ||
    document.getElementById("chatInput") ||
    document.getElementById("dockChatInput")
  );
}

function setVoiceUi(listening, note) {
  const input = activeVoiceInput();
  const status = document.getElementById("chatStatus");
  const dockStatus = document.getElementById("dockChatStatus");
  voiceListening = listening;
  for (const btn of voiceButtons()) {
    const icon = btn.querySelector("[data-voice-icon]");
    btn.classList.toggle("listening", listening);
    btn.setAttribute("aria-pressed", listening ? "true" : "false");
    if (icon) icon.textContent = listening ? "mic_off" : "mic";
    btn.title = listening ? "Stop recording" : "Voice input";
  }
  if (input) input.classList.toggle("dictating", listening);
  document.querySelectorAll(".composer-box").forEach((box) => {
    box.classList.toggle("dictating", listening);
  });
  if (typeof note === "string") {
    if (status) status.textContent = note;
    if (dockStatus) dockStatus.textContent = note || (listening ? "Listening…" : "Ready");
  }
}

function stopVoiceInput() {
  if (voiceRecognition && voiceListening) {
    try {
      voiceRecognition.stop();
    } catch (_) {
      /* ignore */
    }
  }
  setVoiceUi(false);
}

function startVoiceInput(inputId) {
  const Ctor = speechRecognitionCtor();
  const status = document.getElementById("chatStatus");
  const dockStatus = document.getElementById("dockChatStatus");
  voiceTargetInputId =
    inputId || (isChatDockOpen() ? "dockChatInput" : "chatInput");
  const input = activeVoiceInput();
  if (!Ctor) {
    const msg = "Voice input needs Chrome / Edge.";
    if (status) status.textContent = msg;
    if (dockStatus) dockStatus.textContent = msg;
    return;
  }
  if (!input || state.chatBusy) return;

  voiceBaseText = (input.value || "").trim();
  if (!voiceRecognition) {
    voiceRecognition = new Ctor();
    voiceRecognition.lang = "ru-RU";
    voiceRecognition.interimResults = true;
    voiceRecognition.continuous = true;
    voiceRecognition.maxAlternatives = 1;

    voiceRecognition.onstart = () => {
      setVoiceUi(true, "Listening… tap mic again to stop");
    };
    voiceRecognition.onerror = (ev) => {
      const err = ev.error || "error";
      let msg = `Voice input: ${err}`;
      if (err === "not-allowed") msg = "Microphone blocked — allow access in the browser.";
      else if (err === "no-speech") msg = "No speech detected — try again.";
      else if (err === "aborted") msg = "";
      if (msg) {
        if (status) status.textContent = msg;
        if (dockStatus) dockStatus.textContent = msg;
      }
      setVoiceUi(false);
    };
    voiceRecognition.onend = () => {
      setVoiceUi(false);
    };
    voiceRecognition.onresult = (event) => {
      const target = activeVoiceInput();
      if (!target) return;
      let interim = "";
      let finalChunk = "";
      for (let i = event.resultIndex; i < event.results.length; i += 1) {
        const res = event.results[i];
        const text = res[0]?.transcript || "";
        if (res.isFinal) finalChunk += text;
        else interim += text;
      }
      if (finalChunk) {
        voiceBaseText = `${voiceBaseText} ${finalChunk}`.replace(/\s+/g, " ").trim();
      }
      target.value = `${voiceBaseText}${interim ? ` ${interim}` : ""}`.replace(/\s+/g, " ").trim();
      target.focus();
    };
  }

  try {
    voiceRecognition.start();
  } catch (_) {
    stopVoiceInput();
  }
}

function toggleVoiceInput(inputId) {
  if (voiceListening) stopVoiceInput();
  else startVoiceInput(inputId);
}

(() => {
  const supported = !!speechRecognitionCtor();
  for (const btn of voiceButtons()) {
    if (!supported) {
      btn.disabled = true;
      btn.title = "Voice input needs Chrome / Edge";
      continue;
    }
    btn.addEventListener("click", () => toggleVoiceInput(btn.dataset.voiceInput));
  }
})();
document.getElementById("runGaqlBtn").addEventListener("click", () => runGaql());
document.getElementById("gaqlFormatBtn")?.addEventListener("click", () => {
  const el = document.getElementById("gaqlQuery");
  el.value = el.value.replace(/\n{3,}/g, "\n\n").trim() + "\n";
});
document.getElementById("gaqlCopyBtn")?.addEventListener("click", async () => {
  const q = document.getElementById("gaqlQuery").value;
    try {
      await navigator.clipboard.writeText(q);
      setGaqlChip("copied");
    } catch {
      setGaqlChip("copy failed");
    }
  });
  document.getElementById("gaqlViewTable")?.addEventListener("click", () => setGaqlView("table"));
  document.getElementById("gaqlViewJson")?.addEventListener("click", () => setGaqlView("json"));
  document.getElementById("gaqlQuery")?.addEventListener("keydown", (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
      e.preventDefault();
      runGaql();
    }
  });

const GAQL_PRESETS = [
  {
    id: "campaigns",
    label: "Campaigns 7d",
    query: `SELECT
  campaign.id,
  campaign.name,
  campaign.status,
  campaign.bidding_strategy_type,
  metrics.impressions,
  metrics.clicks,
  metrics.cost_micros,
  metrics.conversions
FROM campaign
WHERE segments.date DURING LAST_7_DAYS
  AND campaign.status != 'REMOVED'
ORDER BY metrics.cost_micros DESC
LIMIT 30`,
  },
  {
    id: "keywords",
    label: "Keywords by spend",
    query: `SELECT
  campaign.name,
  ad_group.name,
  ad_group_criterion.keyword.text,
  ad_group_criterion.keyword.match_type,
  ad_group_criterion.status,
  metrics.clicks,
  metrics.cost_micros,
  metrics.conversions
FROM keyword_view
WHERE segments.date DURING LAST_30_DAYS
  AND campaign.status != 'REMOVED'
  AND ad_group_criterion.status != 'REMOVED'
ORDER BY metrics.cost_micros DESC
LIMIT 40`,
  },
  {
    id: "search_terms",
    label: "Search terms",
    query: `SELECT
  campaign.name,
  ad_group.name,
  search_term_view.search_term,
  metrics.clicks,
  metrics.cost_micros,
  metrics.conversions
FROM search_term_view
WHERE segments.date DURING LAST_30_DAYS
  AND campaign.status != 'REMOVED'
ORDER BY metrics.cost_micros DESC
LIMIT 40`,
  },
  {
    id: "ads_strength",
    label: "RSA + strength",
    query: `SELECT
  campaign.name,
  ad_group.name,
  ad_group_ad.ad.id,
  ad_group_ad.status,
  ad_group_ad.ad_strength,
  metrics.impressions,
  metrics.clicks,
  metrics.conversions
FROM ad_group_ad
WHERE segments.date DURING LAST_30_DAYS
  AND campaign.status != 'REMOVED'
  AND ad_group_ad.status != 'REMOVED'
ORDER BY metrics.impressions DESC
LIMIT 40`,
  },
  {
    id: "conversions",
    label: "Conversion actions",
    query: `SELECT
  conversion_action.id,
  conversion_action.name,
  conversion_action.status,
  conversion_action.category,
  conversion_action.origin,
  conversion_action.primary_for_goal,
  conversion_action.include_in_conversions_metric
FROM conversion_action
WHERE conversion_action.status != 'REMOVED'
ORDER BY conversion_action.name`,
  },
  {
    id: "account",
    label: "Account",
    query: `SELECT
  customer.id,
  customer.descriptive_name,
  customer.currency_code,
  customer.time_zone,
  customer.auto_tagging_enabled
FROM customer
LIMIT 1`,
  },
];

function setGaqlChip(text) {
  const chip = document.getElementById("gaqlStatusChip");
  if (chip) chip.textContent = text;
}

function setGaqlView(mode) {
  state.gaqlView = mode === "json" ? "json" : "table";
  document.getElementById("gaqlViewTable")?.classList.toggle("active", state.gaqlView === "table");
  document.getElementById("gaqlViewJson")?.classList.toggle("active", state.gaqlView === "json");
  renderGaqlResult();
}

function flattenGaqlRow(row, prefix = "") {
  const out = {};
  if (row == null || typeof row !== "object" || Array.isArray(row)) {
    out[prefix || "value"] = row;
    return out;
  }
  for (const [k, v] of Object.entries(row)) {
    const key = prefix ? `${prefix}.${k}` : k;
    if (v != null && typeof v === "object" && !Array.isArray(v)) {
      Object.assign(out, flattenGaqlRow(v, key));
    } else {
      out[key] = Array.isArray(v) ? JSON.stringify(v) : v;
    }
  }
  return out;
}

function renderGaqlResult() {
  const meta = document.getElementById("gaqlMeta");
  const tableWrap = document.getElementById("gaqlTableWrap");
  const tableHost = document.getElementById("gaqlTable");
  const pre = document.getElementById("gaqlResult");
  const data = state.gaqlLast;
  if (!data) {
    if (meta) meta.textContent = "Click Run or pick a preset.";
    if (tableWrap) tableWrap.hidden = true;
    if (pre) {
      pre.hidden = true;
      pre.classList.remove("is-error");
    }
    return;
  }
  if (data.error) {
    if (meta) meta.textContent = "Query error";
    if (tableWrap) tableWrap.hidden = true;
    if (pre) {
      pre.hidden = false;
      pre.classList.add("is-error");
      pre.textContent = data.error;
    }
    return;
  }

  const rows = Array.isArray(data.rows) ? data.rows : [];
  const flat = rows.map((r) => flattenGaqlRow(r));
  const cols = [];
  const seen = new Set();
  for (const r of flat) {
    for (const k of Object.keys(r)) {
      if (!seen.has(k)) {
        seen.add(k);
        cols.push(k);
      }
    }
  }

  if (meta) {
    const mode = data.demo ? "demo" : "live";
    meta.textContent = `${rows.length} rows · ${mode} · customer ${data.customer_id || "—"}`;
  }

  if (state.gaqlView === "json") {
    if (tableWrap) tableWrap.hidden = true;
    if (pre) {
      pre.hidden = false;
      pre.classList.remove("is-error");
      pre.textContent = JSON.stringify(data, null, 2);
    }
    return;
  }

  if (pre) pre.hidden = true;
  if (tableWrap) tableWrap.hidden = false;
  if (!cols.length) {
    tableHost.innerHTML = `<p class="muted">0 rows — query succeeded, no data.</p>`;
    return;
  }
  renderTable(
    tableHost,
    cols.map((c) => ({
      label: c,
      render: (row) => {
        const v = row[c];
        if (v == null) return "—";
        if (typeof v === "number" && /micros$/i.test(c)) {
          return `${v} (${(v / 1_000_000).toFixed(2)})`;
        }
        return String(v);
      },
    })),
    flat
  );
}

function initGaqlPresets() {
  const box = document.getElementById("gaqlPresets");
  const textarea = document.getElementById("gaqlQuery");
  if (!box || !textarea) return;
  if (!textarea.value.trim()) {
    textarea.value = GAQL_PRESETS[0].query;
  }
  box.innerHTML = GAQL_PRESETS.map(
    (p) =>
      `<button type="button" class="gaql-preset" data-id="${p.id}" title="Load example">${escapeHtml(
        p.label
      )}</button>`
  ).join("");
  box.querySelectorAll(".gaql-preset").forEach((btn) => {
    btn.addEventListener("click", () => {
      const preset = GAQL_PRESETS.find((p) => p.id === btn.dataset.id);
      if (!preset) return;
      box.querySelectorAll(".gaql-preset").forEach((b) => b.classList.toggle("active", b === btn));
      textarea.value = preset.query;
      setGaqlChip(`preset: ${preset.label}`);
    });
  });
}

async function runGaql() {
  const query = document.getElementById("gaqlQuery").value;
  const btn = document.getElementById("runGaqlBtn");
  setGaqlChip("running…");
  if (btn) btn.disabled = true;
  try {
    const data = await api("/api/gaql", { method: "POST", body: JSON.stringify({ query }) });
    state.gaqlLast = data;
    setGaqlChip("ok");
    renderGaqlResult();
  } catch (e) {
    state.gaqlLast = { error: String(e.message || e) };
    setGaqlChip("error");
    setGaqlView("json");
    renderGaqlResult();
  } finally {
    if (btn) btn.disabled = false;
  }
}

Promise.all([loadModels(), refresh(), bootstrapChats()]).then(() => {
  initGaqlPresets();
  updateChatFabVisibility(document.querySelector(".nav-item.active")?.dataset?.view || "chat");
  const st = state.overview && state.overview.status;
  if (st && st.switched_from_manager) {
    const badge = document.getElementById("modeBadge");
    badge.textContent = `${badge.textContent} · client ${st.customer_id}`;
  }
  if (st && st.mode === "demo" && !sessionStorage.getItem("gads_setup_opened")) {
    sessionStorage.setItem("gads_setup_opened", "1");
    switchView("setup");
  }
}).catch((e) => {
  document.getElementById("modeBadge").textContent = "Partial error";
  document.getElementById("accountLine").textContent = String(e.message || e);
  initGaqlPresets();
  updateChatFabVisibility("chat");
});
