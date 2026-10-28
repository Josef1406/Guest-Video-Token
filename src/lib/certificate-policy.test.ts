import { describe, it, expect } from 'vitest';
import { Pkcs10CertificateRequestGenerator, SubjectAlternativeNameExtension } from '@peculiar/x509';
import { inspectCsr, certificateDomain, encode, verifyRenewal, signatureRaw } from './certificate-policy';

async function csr(names: string[]) {
  const keys = await crypto.subtle.generateKey({ name: 'ECDSA', namedCurve: 'P-256' }, true, ['sign', 'verify']);
  const request = await Pkcs10CertificateRequestGenerator.create({ name: 'CN=' + certificateDomain, keys, signingAlgorithm: { name: 'ECDSA', hash: 'SHA-256' }, extensions: [new SubjectAlternativeNameExtension(names.map(value => ({ type: 'dns', value })))] }, crypto);
  return request.toString('pem');
}
describe('fixed video domain authorization', () => {
  it('accepts only the exact printed Cloud QR domain', async () => {
    expect((await inspectCsr(await csr(['video.gaestebuch.cloud']))).spki.length).toBeGreaterThan(50);
  });
  it('rejects extra domains or wildcard authority', async () => {
    await expect(inspectCsr(await csr(['video.gaestebuch.cloud', '*.gaestebuch.cloud']))).rejects.toThrow();
  });
  it('rejects a guest request without the enrolled Pi signature', async () => {
    const key = await crypto.subtle.generateKey({ name: 'ECDSA', namedCurve: 'P-256' }, true, ['sign', 'verify']);
    const payload = encode(new TextEncoder().encode(JSON.stringify({ version: 1, device_id: '11111111-1111-4111-8111-111111111111', request_id: '22222222-2222-4222-8222-222222222222', purpose: 'renew' })));
    await expect(verifyRenewal({ payload, signature: encode(new Uint8Array(70)) }, encode(await crypto.subtle.exportKey('spki', key.publicKey)))).rejects.toThrow();
  });
  it('rejects a malformed DER signature instead of truncating it', () => {
    expect(() => signatureRaw(new Uint8Array([48, 6, 2, 1, 1, 2, 1]))).toThrow();
  });
});