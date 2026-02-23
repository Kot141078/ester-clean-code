/* -*- coding: utf-8 -*-
 * app.js — legkaya frontovaya logika:
 * - mini-panel statusov provayderov (v Trace)
 * - tultip/leybl "cached_until" dlya vidzhetov
 * - myagkie oshibki i degradatsiya: esli API nedostupny/net JWT — UI ne padaet
 *
 * Ozhidaetsya, chto JWT kladetsya libo v window.JWT, libo v localStorage["jwt"].
 * Esli nichego net — zaprosy uydut bez avtorizatsii i vernut 401 (UI pokazhet plashku).
 */

(function () {
  "use strict";

  const $ = (sel, root) => (root || document).querySelector(sel);
  const $$ = (sel, root) => Array.from((root || document).querySelectorAll(sel));

  function bearer() {
    try {
      return window.JWT || localStorage.getItem("jwt") || "";
    } catch (e) {
      return "";
    }
  }

  function buildHeadersSafe(input) {
    const hs = (window.__EsterHeaderSafe || {});
    if (typeof hs.buildHeadersSafe === "function") {
      return hs.buildHeadersSafe(input);
    }
    const out = new Headers();
    const entries = [];
    if (input instanceof Headers) {
      input.forEach((v, k) => entries.push([k, v]));
    } else if (Array.isArray(input)) {
      for (const pair of input) entries.push(pair);
    } else if (input && typeof input === "object") {
      for (const k of Object.keys(input)) entries.push([k, input[k]]);
    }
    for (const [k, v] of entries) {
      try { out.set(String(k), String(v)); } catch (_) {}
    }
    return out;
  }

  function setHeaderSafe(headers, name, value) {
    const hs = (window.__EsterHeaderSafe || {});
    if (typeof hs.setHeaderUtf8Safe === "function") {
      hs.setHeaderUtf8Safe(headers, name, value);
      return;
    }
    if (value == null) return;
    try { headers.set(String(name), String(value)); } catch (_) {}
  }

  async function fetchJSON(url, opts = {}) {
    const headers = buildHeadersSafe(opts.headers || {});
    setHeaderSafe(headers, "Content-Type", "application/json");
    const token = bearer();
    if (token) setHeaderSafe(headers, "Authorization", `Bearer ${token}`);
    const res = await fetch(url, Object.assign({}, opts, { headers }));
    let data = null;
    try {
      data = await res.json();
    } catch (e) {
      data = null;
    }
    if (!res.ok) {
      const msg = (data && (data.error || data.message)) || res.statusText;
      throw new Error(`${res.status} ${msg}`);
    }
    return data;
  }

  function nowTs() {
    return Math.floor(Date.now() / 1000);
  }

  function formatTime(tsSec) {
    try {
      const d = new Date(tsSec * 1000);
      return d.toLocaleString();
    } catch (e) {
      return String(tsSec);
    }
  }

  function setCachedUntil(el, secondsFromNow) {
    if (!el) return;
    const untilTs = nowTs() + (secondsFromNow || 60);
    el.dataset.cachedUntil = String(untilTs);
    el.textContent = "do " + formatTime(untilTs);
    el.title = "Dannye deystvitelny do ukazannogo vremeni";
  }

  function refreshCachedUntilBadges() {
    const nodes = $$("[data-cached-until]");
    const now = nowTs();
    nodes.forEach((el) => {
      const ts = parseInt(el.dataset.cachedUntil || "0", 10);
      const overdue = ts && ts < now;
      el.classList.toggle("text-red-600", overdue);
      el.classList.toggle("text-gray-500", !overdue);
    });
  }

  async function refreshProvidersBlock() {
    const box = $("#providers-status");
    const warn = $("#providers-warning");
    if (!box) return;

    try {
      const st = await fetchJSON("/providers/status");
      const rows = [];
      const keys = Object.keys(st).filter(
        (k) => !["active", "default_cloud"].includes(k)
      );
      keys.sort();
      keys.forEach((name) => {
        const s = st[name] || {};
        const ok = !!s.ok;
        const lat = s.latency_ms != null ? `${s.latency_ms} ms` : "—";
        const model = s.model || "—";
        const kind = s.kind || "—";
        rows.push(
          `<tr class="border-b">
             <td class="px-2 py-1 font-mono">${name}</td>
             <td class="px-2 py-1">${ok ? "OK" : "ERR"}</td>
             <td class="px-2 py-1">${lat}</td>
             <td class="px-2 py-1">${kind}</td>
             <td class="px-2 py-1">${model}</td>
           </tr>`
        );
      });
      box.innerHTML = `
        <div class="flex items-center justify-between mb-1">
          <div class="text-sm text-gray-600">Aktivnyy: <span class="font-semibold">${st.active}</span>, sudya po umolchaniyu: <span class="font-semibold">${st.default_cloud}</span></div>
          <div class="text-xs text-gray-500">cached_until: <span id="providers-cached" class="align-middle px-1 rounded bg-gray-100"></span></div>
        </div>
        <table class="w-full text-sm">
          <thead>
            <tr class="border-b bg-gray-50">
              <th class="px-2 py-1 text-left">provider</th>
              <th class="px-2 py-1 text-left">state</th>
              <th class="px-2 py-1 text-left">latency</th>
              <th class="px-2 py-1 text-left">kind</th>
              <th class="px-2 py-1 text-left">model</th>
            </tr>
          </thead>
          <tbody>${rows.join("")}</tbody>
        </table>
      `;
      const badge = $("#providers-cached");
      setCachedUntil(badge, 60);
      if (warn) warn.classList.add("hidden");
    } catch (e) {
      if (warn) {
        warn.textContent = `Provaydery: ${e.message}. Vozmozhno, net JWT ili server nedostupen.`;
        warn.classList.remove("hidden");
      }
    }
  }

  async function refreshTraceStats() {
    const root = $("#trace-mini-stats");
    if (!root) return;
    try {
      const st = await fetchJSON("/trace/status");
      const count = st.count != null ? st.count : (st.stats && st.stats.total) || "—";
      root.innerHTML = `
        <div class="text-sm text-gray-700">Trace zapisey: <span class="font-semibold">${count}</span></div>
      `;
    } catch (e) {
      root.innerHTML = `<div class="text-xs text-gray-500">Trace nedostupen: ${e.message}</div>`;
    }
  }

  function bindActions() {
    const btn = $("#btn-refresh-providers");
    if (btn) btn.addEventListener("click", () => refreshProvidersBlock());

    // avto-obnovlenie kazhdye 60s dlya statusov provayderov
    setInterval(refreshProvidersBlock, 60000);
    // apdeyt tsveta beydzhey cached_until raz v 2s
    setInterval(refreshCachedUntilBadges, 2000);
  }

  document.addEventListener("DOMContentLoaded", () => {
    refreshProvidersBlock();
    refreshTraceStats();
    refreshCachedUntilBadges();
    bindActions();
  });
})();
