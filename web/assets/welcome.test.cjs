const { test } = require('node:test');
const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const vm = require('node:vm');

async function welcome(mode, fail = false, certificate = { state: 'setup_required', ready: false, message: 'Pending' }) {
  const nodes = new Map();
  const listeners = {};
  let savedMode = mode;
  let savedCertificate = certificate;
  const document = {
    documentElement: { dataset: {} }, visibilityState: 'visible',
    getElementById(id) {
      if (!nodes.has(id)) nodes.set(id, { hidden: true, textContent: '', classList: { add() {}, remove() {} } });
      return nodes.get(id);
    },
    addEventListener(name, fn) { listeners[name] = fn; },
  };
  vm.runInNewContext(readFileSync(__dirname + '/welcome.js', 'utf8'), {
    document, window: { addEventListener(name, fn) { listeners[name] = fn; }, setInterval(fn) { listeners.poll = fn; } },
    fetch: async () => {
      if (fail) throw new Error('Offline');
      return { ok: true, json: async () => ({ mode: savedMode, certificate: savedMode === 'https' ? savedCertificate : null }) };
    },
  });
  await new Promise(resolve => setImmediate(resolve));
  return { nodes, async saved(mode) { savedMode = mode; await listeners.pageshow(); }, async activated(cert) { savedCertificate = cert; listeners.poll(); await new Promise(resolve => setImmediate(resolve)); } };
}

test('Direct mode shows only the direct workflow, without certificates', async () => {
  const { nodes } = await welcome('normal');
  assert.equal(nodes.get('normal-mode').hidden, false);
  assert.equal(nodes.get('https-mode').hidden, true);
  assert.equal(nodes.get('video-instructions').hidden, false);
});

test('Certificate mode shows only the certificate workflow', async () => {
  const { nodes } = await welcome('https');
  assert.equal(nodes.get('normal-mode').hidden, true);
  assert.equal(nodes.get('https-mode').hidden, false);
  assert.equal(nodes.get('video-instructions').hidden, true);
});

test('Verified valid HTTPS activation automatically reveals camera scan without changing mode', async () => {
  const view = await welcome('https');
  await view.activated({ ready: true, expires_at: new Date(Date.now() + 86400000).toISOString() });
  assert.equal(view.nodes.get('https-mode').hidden, true);
  assert.equal(view.nodes.get('local-mode').hidden, false);
  assert.equal(view.nodes.get('video-instructions').hidden, false);
});

test('Expired certificates cannot reveal the HTTPS camera workflow', async () => {
  const { nodes } = await welcome('https', false, { ready: true, expires_at: '2020-01-01T00:00:00Z' });
  assert.equal(nodes.get('video-instructions').hidden, true);
  assert.equal(nodes.get('https-mode').hidden, false);
});

test('An unverified certificate cannot reveal the HTTPS camera workflow', async () => {
  const { nodes } = await welcome('https', false, { ready: false, expires_at: new Date(Date.now() + 86400000).toISOString() });
  assert.equal(nodes.get('video-instructions').hidden, true);
});

test('Missing expiry cannot reveal the HTTPS camera workflow', async () => {
  const { nodes } = await welcome('https', false, { ready: true });
  assert.equal(nodes.get('video-instructions').hidden, true);
});

test('Returning to the page reads the saved Admin mode instead of retaining the old selection', async () => {
  const view = await welcome('normal');
  await view.saved('https');
  assert.equal(view.nodes.get('normal-mode').hidden, true);
  assert.equal(view.nodes.get('https-mode').hidden, false);
  await view.saved('normal');
  assert.equal(view.nodes.get('normal-mode').hidden, false);
  assert.equal(view.nodes.get('https-mode').hidden, true);
});

test('Unavailable settings do not assume a guest mode', async () => {
  const { nodes } = await welcome('normal', true);
  assert.equal(nodes.get('normal-mode').hidden, true);
  assert.equal(nodes.get('https-mode').hidden, true);
  assert.equal(nodes.get('video-instructions').hidden, true);
});

test('Unknown settings cannot enable either workflow', async () => {
  const { nodes } = await welcome('client');
  assert.equal(nodes.get('normal-mode').hidden, true);
  assert.equal(nodes.get('https-mode').hidden, true);
});

test('Guests can renew only when the Pi reports an available local identity', async () => {
  const view = await welcome('https', false, { ready: false, renewal_available: false });
  assert.equal(view.nodes.get('renew-certificate').disabled, true);
  await view.activated({ ready: false, renewal_available: true });
  assert.equal(view.nodes.get('renew-certificate').disabled, false);
});
for (const [mode, shown] of [['normal', 'normal-mode'], ['cloud', 'cloud-mode'], ['local', 'local-mode']]) {
  test(`Admin mode ${mode} shows only its own guest workflow`, async () => {
    const { nodes } = await welcome(mode);
    for (const id of ['normal-mode', 'cloud-mode', 'local-mode', 'https-mode']) {
      assert.equal(nodes.get(id).hidden, id !== shown, id);
    }
  });
}
