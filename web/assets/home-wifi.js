(function () {
  if (document.documentElement.dataset.preview === 'true') return;
  const $ = id => document.getElementById(id);
  const form = $('home-wifi-form'), saved = $('home-wifi-saved'), bar = $('home-progress'), msg = $('home-message');
  if (!form) return;
  let timer = null;
  async function call(path, body) {
    const r = await fetch(path, { method: body === undefined ? 'GET' : 'POST', cache: 'no-store',
      headers: { 'Content-Type': 'application/json' }, body: body === undefined ? undefined : JSON.stringify(body) });
    const data = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(data.error || 'Token antwortet nicht.');
    return data;
  }
  function show(s) {
    form.hidden = s.configured && !form.dataset.edit;
    saved.hidden = !s.configured || !!form.dataset.edit;
    $('home-wifi-name').textContent = s.ssid || '';
    $('home-connect').disabled = $('home-retry').disabled = s.busy;
    bar.hidden = !s.busy && s.phase !== 'done';
    bar.value = s.progress || 0;
    msg.textContent = s.message || '';
    if (s.phase === 'done') window.dispatchEvent(new Event('pageshow'));
    clearTimeout(timer);
    if (s.busy) timer = setTimeout(refresh, 2000);
  }
  async function refresh() { try { show(await call('/api/public/home-wifi')); } catch (e) { msg.textContent = e.message; } }
  form.addEventListener('submit', async e => {
    e.preventDefault();
    try {
      delete form.dataset.edit;
      show(await call('/api/public/home-wifi', { ssid: $('home-ssid').value.trim(), psk: $('home-psk').value }));
      $('home-psk').value = '';
    } catch (err) { msg.textContent = err.message; }
  });
  $('home-retry').addEventListener('click', async () => { try { show(await call('/api/public/home-wifi/renew', {})); } catch (e) { msg.textContent = e.message; } });
  $('home-change').addEventListener('click', () => { form.dataset.edit = '1'; form.hidden = false; saved.hidden = true; });
  $('home-scan').addEventListener('click', async () => {
    msg.textContent = 'Suche WLANs…';
    try {
      const { networks } = await call('/api/public/home-wifi/scan', {});
      $('home-ssid-list').replaceChildren(...networks.map(n => Object.assign(document.createElement('option'), { value: n })));
      msg.textContent = networks.length ? networks.length + ' WLANs gefunden – Feld antippen zum Auswählen.' : 'Keine WLANs gefunden. Name bitte eintippen.';
    } catch (e) { msg.textContent = e.message; }
  });
  refresh();
})();
