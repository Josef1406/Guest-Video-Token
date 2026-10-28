const { test } = require('node:test');
const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const vm = require('node:vm');

async function welcome(mode, fail = false) {
  const nodes = new Map();
  const listeners = {};
  let savedMode = mode;
  const document = {
    documentElement: { dataset: {} }, visibilityState: 'visible',
    getElementById(id) {
      if (!nodes.has(id)) nodes.set(id, { hidden: true, textContent: '', classList: { add() {}, remove() {} } });
      return nodes.get(id);
    },
    addEventListener(name, fn) { listeners[name] = fn; },
  };
  vm.runInNewContext(readFileSync(__dirname + '/welcome.js', 'utf8'), {
    document, window: { addEventListener(name, fn) { listeners[name] = fn; } },
    fetch: async () => {
      if (fail) throw new Error('Offline');
      return { ok: true, json: async () => ({ mode: savedMode, certificate: savedMode === 'https' ? { message: 'Pending' } : null }) };
    },
  });
  await new Promise(resolve => setImmediate(resolve));
  return { nodes, async saved(mode) { savedMode = mode; await listeners.pageshow(); } };
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