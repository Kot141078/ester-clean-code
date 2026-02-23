(function(){
  // --- Helpers ---
  const E = id => document.getElementById(id);

  /**
   * Performs an asynchronous POST request.
   * Includes error handling for JSON parsing.
   * @param {string} url - The URL to post to.
   * @param {object} body - The request body.
   * @returns {Promise<object>} - The JSON response.
   */
  async function POST(url, body){
    const r = await fetch(url, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(body || {})
    });
    let j;
    try {
      j = await r.json();
    } catch(e) {
      j = {ok: false, error: 'bad json'};
    }
    return j;
  }

  // --- General Planning ---
  E('btnPlan').addEventListener('click', async () => {
    const goal = E('goal').value.trim();
    if (!goal) {
      E('planOut').textContent = 'Ukazhi tsel';
      return;
    }
    const j = await POST('/self/plan', {goal});
    E('planOut').textContent = JSON.stringify(j, null, 2);
  });

  // --- Codegen ---
  E('btnDraft').addEventListener('click', async () => {
    const name = E('modname').value.trim();
    const content = E('modcode').value;
    const j = await POST('/self/codegen/draft', {name, content});
    E('codeOut').textContent = JSON.stringify(j, null, 2);
  });

  E('btnCheck').addEventListener('click', async () => {
    const name = E('modname').value.trim();
    const j = await POST('/self/codegen/check', {name});
    E('codeOut').textContent = JSON.stringify(j, null, 2);
  });

  E('btnApply').addEventListener('click', async () => {
    const name = E('modname').value.trim();
    const j = await POST('/self/codegen/apply', {name});
    E('codeOut').textContent = JSON.stringify(j, null, 2);
  });

  // Note: This list is for codegen
  E('btnList').addEventListener('click', async () => {
    const r = await fetch('/self/codegen/list');
    const j = await r.json();
    E('codeOut').textContent = JSON.stringify(j, null, 2);
  });

  // --- Snapshots ---
  [cite_start]E('btnSnap').addEventListener('click', async () => { [cite: 1]
    [cite_start]const note = E('note').value.trim(); [cite: 1]
    [cite_start]const j = await POST('/self/pack/snapshot', {note}); [cite: 1]
    [cite_start]E('outSnap').textContent = JSON.stringify(j, null, 2); [cite: 1]
  [cite_start]}); [cite: 1]

  // Note: This list is for snapshots
  [cite_start]E('btnList').addEventListener('click', async () => { [cite: 1]
    [cite_start]const r = await fetch('/self/pack/list'); const j = await r.json(); [cite: 1]
    [cite_start]E('outSnap').textContent = JSON.stringify(j, null, 2); [cite: 1]
  [cite_start]}); [cite: 1]

  // --- Torrent ---
  [cite_start]E('btnTor').addEventListener('click', async () => { [cite: 2]
    [cite_start]const archive = E('arch').value.trim(); [cite: 2]
    [cite_start]const webseed_url = E('wseed').value.trim(); [cite: 2]
    [cite_start]const j = await POST('/self/pack/torrent', {archive, webseed_url}); [cite: 2]
    [cite_start]E('outTor').textContent = JSON.stringify(j, null, 2); [cite: 2]
  [cite_start]}); [cite: 3]

  // --- Staging & Deploy ---
  E('btnStage').addEventListener('click', async () => {
    let files = {};
    try {
      files = JSON.parse(E('files').value || '{}');
    } catch(e) {}
    const reason = E('reason').value.trim();
    const j = await POST('/self/deploy/stage', {files, reason});
    E('sid').value = j.stage_id || '';
    E('outStage').textContent = JSON.stringify(j, null, 2);
  });

  [cite_start]E('btnApprove').addEventListener('click', async () => { [cite: 4]
    [cite_start]const stage_id = E('sid').value.trim(); [cite: 4]
    [cite_start]const j = await POST('/self/deploy/approve', {stage_id, pill: false}); [cite: 4]
    [cite_start]E('outStage').textContent = JSON.stringify(j, null, 2); [cite: 4]
  [cite_start]}); [cite: 4]

  // --- Rollback ---
  [cite_start]E('btnRollback').addEventListener('click', async () => { [cite: 5]
    [cite_start]const snapshot_archive = E('snap').value.trim(); [cite: 5]
    [cite_start]const j = await POST('/self/deploy/rollback', {snapshot_archive}); [cite: 5]
    [cite_start]E('outRb').textContent = JSON.stringify(j, null, 2); [cite: 5]
  [cite_start]}); [cite: 5]

  // --- Autonomy ---
  [cite_start]let lastPlan = null; [cite: 6]
  [cite_start]E('btnPlan').addEventListener('click', async () => { [cite: 6]
    [cite_start]const j = await POST('/self/autonomy/plan', {goal: 'replicate'}); [cite: 6]
    [cite_start]lastPlan = j; [cite: 6]
    [cite_start]E('outAuto').textContent = JSON.stringify(j, null, 2); [cite: 6]
  [cite_start]}); [cite: 6]

  [cite_start]E('btnExec').addEventListener('click', async () => { [cite: 7]
    [cite_start]const j = await POST('/self/autonomy/execute', lastPlan || {plan: {}}); [cite: 7]
    [cite_start]E('outAuto').textContent = JSON.stringify(j, null, 2); [cite: 7]
  [cite_start]}); [cite: 7]

})();