    async function loadPricing(){
      const plans = await (await fetch("../static/pricing.json")).json();
      const pay = await (await fetch("./payments.json")).json().catch(()=>({}));
      const root = document.getElementById("plans-grid");
      root.innerHTML = "";
      for(const p of plans.plans){
        const link = pay[p.id] || "#";
        const one = p.one_time ? `<div class="price">€${p.one_time} razovo</div>` : "";
        const mon = p.monthly ? `<div class="price">€${p.monthly}/mes</div>` : "";
        root.insertAdjacentHTML("beforeend", `
          <div class="card">
            <h3>${p.name}</h3>
            ${one}${mon}
            <ul>${p.features.map(f=>`<li>${f}</li>`).join("")}</ul>
            <button class="buy" ${link==="#"?"disabled":""} onclick="window.open('${link}','_blank')">
              Kupit
            </button>
          </div>`);
      }
    }
    loadPricing();

    document.getElementById("lead-form").addEventListener("submit", async (e)=>{
      e.preventDefault();
      const d = new FormData(e.target);
      const body = encodeURIComponent(`Imya: ${d.get("name")}
Email: ${d.get("email")}
Soobschenie: ${d.get("msg")}`);
      window.location.href = `mailto:you@example.com?subject=Ester Lead&body=${body}`;
      document.getElementById("lead-ok").hidden = false;
      e.target.reset();
    });
