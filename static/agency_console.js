(function(){
  const E = id => document.getElementById(id);

  async function POST(url, body){
    const r = await fetch(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body||{})});
    let j; try{ j = await r.json(); }catch(e){ j = {ok:false,error:'bad json'} }
    return j;
  }

  // Plan
  E('btnPlan').addEventListener('click', async ()=>{
    const need = E('need').value.trim();
    const budget_eur = parseFloat(E('budget').value||'0');
    const j = await POST('/agency/procure/plan',{need, budget_eur});
    E('outPlan').textContent = JSON.stringify(j,null,2);
  });
  E('btnExec').addEventListener('click', async ()=>{
    try{
      const jPlan = JSON.parse(E('outPlan').textContent);
      const j = await POST('/agency/procure/execute',{plan:jPlan});
      E('outPlan').textContent = JSON.stringify(j,null,2);
    }catch(e){
      E('outPlan').textContent = 'Snachala sformiruy plan';
    }
  });

  // Ledzher
  E('btnIncome').addEventListener('click', async ()=>{
    const amount = parseFloat(E('incAmt').value||'0');
    const source = E('incSrc').value.trim()||'unknown';
    const j = await POST('/agency/ledger/income',{amount, currency:'EUR', source});
    E('outLedger').textContent = JSON.stringify(j,null,2);
  });
  E('btnExpense').addEventListener('click', async ()=>{
    const amount = parseFloat(E('expAmt').value||'0');
    const purpose = E('expPurp').value.trim()||'test';
    const j = await POST('/agency/ledger/expense',{amount, currency:'EUR', purpose});
    E('outLedger').textContent = JSON.stringify(j,null,2);
  });

  // Naym
  E('btnHDraft').addEventListener('click', async ()=>{
    const title = E('hTitle').value.trim();
    const skills = (E('hSkills').value||'').split(',').map(s=>s.trim()).filter(Boolean);
    const budget_eur = parseFloat(E('hBudget').value||'0');
    const duration = E('hDur').value.trim();
    const description = E('hDesc').value;
    const j = await POST('/agency/hiring/draft',{title,skills,budget_eur,duration,description});
    E('outHire').textContent = JSON.stringify(j,null,2);
  });
  E('btnHList').addEventListener('click', async ()=>{
    const r = await fetch('/agency/hiring/list'); const j = await r.json();
    E('outHire').textContent = JSON.stringify(j,null,2);
  });

  // Semya
  E('btnFPrep').addEventListener('click', async ()=>{
    const amount = parseFloat(E('fAmt').value||'0');
    const beneficiary_name = E('fName').value.trim();
    const purpose = E('fPurpose').value.trim();
    const beneficiary_iban = E('fIBAN').value.trim()||'<FILL_MANUALLY>';
    const j = await POST('/agency/family/prepare_transfer',{amount,beneficiary_name,purpose,beneficiary_iban});
    E('outFamily').textContent = JSON.stringify(j,null,2);
  });
  E('btnFList').addEventListener('click', async ()=>{
    const r = await fetch('/agency/family/list'); const j = await r.json();
    E('outFamily').textContent = JSON.stringify(j,null,2);
  });
})();

// c=a+b
