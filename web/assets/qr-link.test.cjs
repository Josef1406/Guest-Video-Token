const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const sandbox = { URL, module: { exports: {} } };
vm.runInNewContext(fs.readFileSync(__dirname + '/qr-link.js', 'utf8'), sandbox);
const { localVideoLink } = sandbox.module.exports;
const file = 'Hochzeit_11_07_2026_16_12_32_3YGYWD.mp4';
test('Cloud-QR preserves event and filename and returns only local HTTP-compatible paths', () => {
  assert.deepEqual({ ...localVideoLink(`https://video.gaestebuch.cloud/v/Hochzeit/${file}`) }, {
    player: `/v/Hochzeit/${file}`, media: `/media/Hochzeit/${file}`,
  });
});
test('existing Token QR continues to work', () => {
  assert.equal(localVideoLink(`http://192.168.4.1/v/Hochzeit/${file}`).player, `/v/Hochzeit/${file}`);
});
test('encoded names preserve case and spaces without changing file', () => {
  assert.equal(localVideoLink('https://video.gaestebuch.cloud/v/Helga%20Bernd/Take%2001.mp4').media, '/media/Helga%20Bernd/Take%2001.mp4');
});
test('unrelated origins, executable schemes and credential-bearing links are rejected', () => {
  for (const value of ['https://evil.example/v/E/a.mp4', 'javascript:alert(1)', 'https://video.gaestebuch.cloud.evil.example/v/E/a.mp4', 'https://user@video.gaestebuch.cloud/v/E/a.mp4']) {
    assert.throws(() => localVideoLink(value));
  }
});
test('path traversal, malformed encodings and non-video QR codes are rejected', () => {
  for (const path of ['/v/E/%2Fbad.mp4', '/v/E/%5Cbad.mp4', '/v/%00/a.mp4', '/v/%ZZ/a.mp4', '/v/E/a.pdf', '/v/unknown-id']) {
    assert.throws(() => localVideoLink('https://video.gaestebuch.cloud' + path));
  }
});