// static/auth.js
(function () {
  const btn = document.getElementById("btn-gen");
  const out = document.getElementById("out");
  const nameInput = document.getElementById("name");

  function setStatus(text, ok = true) {
    out.textContent = text;
    out.className = "out status " + (ok ? "ok" : "err");
  }

  async function mint() {
    const name = (nameInput.value || "").trim();
    if (!name) {
      setStatus("Vvedite imya (primer: Owner)", false);
      nameInput.focus();
      return;
    }
    btn.disabled = true;
    setStatus("Vypuskayu token…");

    try {
      const resp = await fetch("/auth/jwt/mint", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name })
      });
      const js = await resp.json();
      if (!resp.ok || !js.ok) {
        throw new Error(js.error || ("HTTP " + resp.status));
      }
      const token = js.token;
      localStorage.setItem("jwt", token);
      localStorage.setItem("user_name", name);
      setStatus("✅ Gotovo.\nImya: " + name + "\nRoli: " + js.roles.join(", ") + "ZhVT saved in localStorage.zhvt\n\nYou can open /portal.");
    } catch (e) {
      setStatus("❌ Oshibka vypuska tokena:" + e.message, false);
    } finally {
      btn.disabled = false;
    }
  }

  btn.addEventListener("click", mint);
  nameInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") mint();
  });
})();
