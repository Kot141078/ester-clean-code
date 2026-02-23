(function(){
  const E = id => document.getElementById(id);
  async function POST(url, body){
    const r = await fetch(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body||{})});
    let j; try{ j = await r.json(); }catch(e){ j = {ok:false,error:'bad json'} }
    return j;
  }
  // add peer
  E('btnAdd').addEventListener('click', async ()=>{
    const j = await POST('/trust/peers/add',{id:E('pid').value.trim(), name:E('pname').value.trim(), alg:E('alg').value.trim(), pubkey:E('pub').value.trim()});
    const lst = await (await fetch('/trust/peers')).json();
    E('outPeers').textContent = JSON.stringify({add:j, list:lst}, null, 2);
  });
  // invite
  E('btnIssue').addEventListener('click', async ()=>{
    const d = {sub:E('sub').value.trim(), scope:E('scope').value.trim(), ttl_sec:parseInt(E('ttl').value||'600',10),
               archive_sha:E('archsha').value.trim()||null, aud:E('aud').value.trim()};
    const j = await POST('/trust/invite/issue', d);
    E('outInv').textContent = JSON.stringify(j,null,2);
  });
  E('btnVerify').addEventListener('click', async ()=>{
    let tok = {};
    try{ tok = JSON.parse(E('outInv').textContent).token; }catch(e){}
    const j = await POST('/trust/invite/verify',{token:tok});
    E('outInv').textContent = JSON.stringify(j,null,2);
  });
  // signing
  E('btnSign').addEventListener('click', async ()=>{
    const j = await POST('/self/pack/sign',{archive:E('arch').value.trim()});
    E('outSig').textContent = JSON.stringify(j,null,2);
  });
  E('btnCheck').addEventListener('click', async ()=>{
    const j = await POST('/self/pack/verify',{archive:E('arch').value.trim()});
    E('outSig').textContent = JSON.stringify(j,null,2);
  });
})();
// c=a+b
