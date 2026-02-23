// ==UserScript==
// @name         Ester Share Bridge — Capture Selection
// @namespace    https://ester.local/
// @version      1.0
// @description  Otpravka tekuschey stranitsy/vydeleniya v Ester Share Bridge (/share/capture)
// @match        *://*/*
// @grant        GM_xmlhttpRequest
// @run-at       context-menu
// ==/UserScript==

(function() {
  'use strict';

  // Nastroyka: bazovyy adres Bridge (mozhno pereopredelit v localStorage.esterBridge)
  const BRIDGE = (localStorage.getItem('esterBridge') || 'http://127.0.0.1:18081').replace(/\/+$/, '');
  const title = document.title || 'untitled';
  const url = location.href || '';
  const sel = window.getSelection ? ('' + window.getSelection()) : '';

  // Esli est vydelenie — otpravim kak text; inache poprobuem zabrat <article> ili ves body kak HTML
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
              alert('Ester Share: sokhraneno (' + (j.count || 1) + ')');
            } catch (e) {
              alert('Ester Share: sokhraneno (raw), kod ' + resp.status);
            }
          },
          onerror: function() { alert('Ester Share: ne udalos otpravit'); }
        });
      } else {
        fetch(BRIDGE + '/share/capture', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(bodyObj)
        }).then(r => r.json()).then(j => {
          alert('Ester Share: sokhraneno (' + (j.count || 1) + ')');
        }).catch(() => alert('Ester Share: ne udalos otpravit'));
      }
    } catch (e) {
      alert('Ester Share: oshibka ' + e);
    }
  };

  // Esli stranitsa ogromnaya (>5MB HTML), otpravim tolko selection/text
  const htmlSize = payload.html ? new Blob([payload.html]).size : 0;
  if (!hasSel && htmlSize > 5 * 1024 * 1024) {
    payload.html = '';
    payload.text = (document.body && document.body.innerText) ? document.body.innerText.slice(0, 50000) : '';
  }

  send(payload);
})();
