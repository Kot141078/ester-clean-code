// ==UserScript==
// @name         Ester Share Bridge — Capture Selection
// @namespace    https://ester.local/
// @version      1.0
// @description Send current page/selection to Esther Shar Bridge (/ball/capture)
// @match        *://*/*
// @grant        GM_xmlhttpRequest
// @run-at       context-menu
// ==/UserScript==

(function() {
  'use strict';

  // Setting: Bridge base address (can be overridden in localStorage.esterbridge)
  const BRIDGE = (localStorage.getItem('esterBridge') || 'http://127.0.0.1:18081').replace(/\/+$/, '');
  const title = document.title || 'untitled';
  const url = location.href || '';
  const sel = window.getSelection ? ('' + window.getSelection()) : '';

  // If there is a selection, we will send it as text; otherwise it will try to pick up <article> or the weight of water as HTML
  const hasSel = sel && sel.trim().length > 0;
  let payload = {
    url, title,
    html: hasSel ? '' : document.documentElement.outerHTML,
    text: hasSel ? sel.trim() : '',
    selection: hasSel ? sel.trim() : '',
    tags: [],
    note: null
  };

  const send = (bodyObj) => {
    try {
      if (typeof GM_xmlhttpRequest === 'function') {
        GM_xmlhttpRequest({
          method: 'POST',
          url: BRIDGE + '/share/capture',
          headers: { 'Content-Type': 'application/json' },
          data: JSON.stringify(bodyObj),
          onload: function(resp) {
            try {
              const j = JSON.parse(resp.responseText || '{}');
              alert('Esther Share: saved (' + (j.count || 1) + ')');
            } catch (e) {
              alert('Esther Share: saved (rav), code' + resp.status);
            }
          },
          onerror: function() { alert('Esther Share: failed to send'); }
        });
      } else {
        fetch(BRIDGE + '/share/capture', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(bodyObj)
        }).then(r => r.json()).then(j => {
          alert('Esther Share: saved (' + (j.count || 1) + ')');
        }).catch(() => alert('Esther Share: failed to send'));
      }
    } catch (e) {
      alert('Esther Share: mistake' + e);
    }
  };

  // If the page is huge (>5MB HTML), send only selection/text
  const htmlSize = payload.html ? new Blob([payload.html]).size : 0;
  if (!hasSel && htmlSize > 5 * 1024 * 1024) {
    payload.html = '';
    payload.text = (document.body && document.body.innerText) ? document.body.innerText.slice(0, 50000) : '';
  }

  send(payload);
})();
