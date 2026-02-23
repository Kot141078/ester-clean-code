/* static/js/headers_latin_guard.js */
(function () {
  function isLatin1(s) {
    if (s == null) return true;
    s = String(s);
    for (let i = 0; i < s.length; i++) if (s.charCodeAt(i) > 255) return false;
    return true;
  }
  function toHeaders(h) {
    try { if (h instanceof Headers) return new Headers(h); } catch(e) {}
    const out = new Headers();
    if (!h) return out;
    if (Array.isArray(h)) for (const [k,v] of h) out.append(k, v);
    else if (typeof h === "object") for (const k of Object.keys(h)) out.append(k, h[k]);
    return out;
  }
  const allowed = new Set(["accept","content-type","authorization"]);
  const nativeFetch = window.fetch;
  if (typeof nativeFetch === "function") {
    window.fetch = function(input, init) {
      init = init || {};
      let clean;
      try {
        const hdrs = toHeaders(init.headers);
        clean = new Headers();
        hdrs.forEach((v,k) => {
          const lk = String(k).toLowerCase();
          if (!allowed.has(lk) && !lk.startsWith("x-")) return;
          const sv = String(v);
          clean.set(k, isLatin1(sv) ? sv : encodeURIComponent(sv));
        });
      } catch (e) { console.warn("[headers_latin_guard] headers build error:", e); }
      const safeInit = Object.assign({}, init);
      if (clean) safeInit.headers = clean;
      try { return nativeFetch(input, safeInit); }
      catch (e) {
        console.warn("[headers_latin_guard] fetch retry without headers:", e);
        const fallbackInit = Object.assign({}, safeInit); delete fallbackInit.headers;
        return nativeFetch(input, fallbackInit);
      }
    };
  }
  if (window.XMLHttpRequest) {
    const proto = XMLHttpRequest.prototype;
    const nativeSet = proto.setRequestHeader;
    proto.setRequestHeader = function(k, v) {
      const sv = String(v);
      return nativeSet.call(this, k, isLatin1(sv) ? sv : encodeURIComponent(sv));
    };
  }
  console.log("[headers_latin_guard] active");
})();