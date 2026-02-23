/* static/js/header_utf8_safe.js */
(function (global) {
  "use strict";

  function isLatin1(value) {
    const text = String(value == null ? "" : value);
    for (const ch of text) {
      const code = ch.codePointAt(0);
      if (code != null && code > 0xff) return false;
    }
    return true;
  }

  function utf8Encode(text) {
    const s = String(text == null ? "" : text);
    if (typeof TextEncoder !== "undefined") {
      return new TextEncoder().encode(s);
    }
    const esc = unescape(encodeURIComponent(s));
    const out = new Uint8Array(esc.length);
    for (let i = 0; i < esc.length; i++) out[i] = esc.charCodeAt(i);
    return out;
  }

  function utf8Decode(bytes) {
    if (typeof TextDecoder !== "undefined") {
      return new TextDecoder().decode(bytes);
    }
    let bin = "";
    for (let i = 0; i < bytes.length; i++) bin += String.fromCharCode(bytes[i]);
    return decodeURIComponent(escape(bin));
  }

  function b64urlEncodeUtf8(value) {
    const bytes = utf8Encode(String(value == null ? "" : value));
    let bin = "";
    for (let i = 0; i < bytes.length; i++) bin += String.fromCharCode(bytes[i]);
    return btoa(bin).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/g, "");
  }

  function b64urlDecodeUtf8(value) {
    const raw = String(value == null ? "" : value).replace(/-/g, "+").replace(/_/g, "/");
    const pad = "=".repeat((4 - (raw.length % 4)) % 4);
    const bin = atob(raw + pad);
    const bytes = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
    return utf8Decode(bytes);
  }

  function toHeaderEntries(input) {
    const entries = [];
    if (!input) return entries;

    try {
      if (typeof Headers !== "undefined" && input instanceof Headers) {
        input.forEach(function (v, k) {
          entries.push([k, v]);
        });
        return entries;
      }
    } catch (_) {}

    if (Array.isArray(input)) {
      for (const pair of input) {
        if (Array.isArray(pair) && pair.length >= 2) entries.push([pair[0], pair[1]]);
      }
      return entries;
    }

    if (typeof input === "object") {
      for (const k of Object.keys(input)) entries.push([k, input[k]]);
    }
    return entries;
  }

  function setHeaderUtf8Safe(headers, name, value) {
    if (!headers || value == null) return;
    const headerName = String(name || "").trim();
    if (!headerName) return;

    const headerValue = String(value);
    if (!headerValue) return;

    const lowerName = headerName.toLowerCase();
    const explicitB64 = lowerName.endsWith("-b64");

    if (isLatin1(headerValue) || explicitB64) {
      try { headers.set(headerName, headerValue); } catch (_) {}
      return;
    }

    try { headers.delete(headerName); } catch (_) {}
    try { headers.set(headerName + "-B64", b64urlEncodeUtf8(headerValue)); } catch (_) {}
  }

  function buildHeadersSafe(input) {
    const out = new Headers();
    for (const pair of toHeaderEntries(input)) {
      setHeaderUtf8Safe(out, pair[0], pair[1]);
    }
    return out;
  }

  global.__EsterHeaderSafe = {
    isLatin1: isLatin1,
    b64urlEncodeUtf8: b64urlEncodeUtf8,
    b64urlDecodeUtf8: b64urlDecodeUtf8,
    toHeaderEntries: toHeaderEntries,
    setHeaderUtf8Safe: setHeaderUtf8Safe,
    buildHeadersSafe: buildHeadersSafe,
  };
})(window);
