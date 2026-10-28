import { Pkcs10CertificateRequest, SubjectAlternativeNameExtension } from '@peculiar/x509';
import { z } from 'zod';

export const certificateDomain = 'video.gaestebuch.cloud';
export const enrollmentSchema = z.object({ version: z.literal(1), device_id: z.string().uuid(), csr: z.string().min(100).max(8192) }).strict();
export const renewalSchema = z.object({ payload: z.string().min(20).max(2048), signature: z.string().min(20).max(512) }).strict();
export const requestSchema = z.object({ version: z.literal(1), device_id: z.string().uuid(), request_id: z.string().uuid(), purpose: z.literal('renew') }).strict();

export function encode(data: ArrayBuffer | Uint8Array): string {
  return btoa(String.fromCharCode(...new Uint8Array(data))).replace(/=/g, '').replace(/\+/g, '-').replace(/\//g, '_');
}
export function decode(data: string): Uint8Array<ArrayBuffer> {
  return Uint8Array.from(atob(data.replace(/-/g, '+').replace(/_/g, '/')), c => c.charCodeAt(0));
}
export async function inspectCsr(pem: string) {
  const csr = new Pkcs10CertificateRequest(pem);
  if (!await csr.verify(crypto)) throw new Error('Signatur der Pi-Anfrage ungültig.');
  const san = csr.getExtension('2.5.29.17');
  if (!(san instanceof SubjectAlternativeNameExtension)) throw new Error('Domain fehlt.');
  const names = san.names.items;
  if (names.length !== 1 || names[0]?.type !== 'dns' || names[0]?.value !== certificateDomain) throw new Error('Nur die Video-Domain ist erlaubt.');
  if (csr.extensions.length !== 1) throw new Error('Zusätzliche Zertifikatsrechte sind nicht erlaubt.');
  const key = await csr.publicKey.export({ name: 'ECDSA', namedCurve: 'P-256' }, ['verify'], crypto);
  if ((key.algorithm as EcKeyAlgorithm).namedCurve !== 'P-256') throw new Error('Falscher Schlüsseltyp.');
  return { spki: encode(csr.publicKey.rawData), der: encode(csr.rawData), key };
}

// OpenSSL produces DER ECDSA signatures; WebCrypto expects fixed-width r||s.
export function signatureRaw(input: Uint8Array): Uint8Array<ArrayBuffer> {
  if (input[0] !== 48 || input.length > 72) throw new Error('Signaturformat ungültig.');
  let offset = 2;
  const output = new Uint8Array(64);
  for (let part = 0; part < 2; part++) {
    if (input[offset++] !== 2) throw new Error('Signaturformat ungültig.');
    const size = input[offset++];
    if (!size || size > 33 || offset + size > input.length) throw new Error('Signaturformat ungültig.');
    let number = input.slice(offset, offset + size); offset += size;
    if (number.length === 33 && number[0] === 0) number = number.slice(1);
    if (number.length > 32) throw new Error('Signaturformat ungültig.');
    output.set(number, part * 32 + 32 - number.length);
  }
  if (offset !== input.length || input[1] !== input.length - 2) throw new Error('Signaturformat ungültig.');
  return output;
}
export async function verifyRenewal(file: unknown, spki: string) {
  const request = renewalSchema.parse(file);
  const bytes = decode(request.payload);
  const payload = requestSchema.parse(JSON.parse(new TextDecoder().decode(bytes)));
  const key = await crypto.subtle.importKey('spki', decode(spki), { name: 'ECDSA', namedCurve: 'P-256' }, false, ['verify']);
  if (!await crypto.subtle.verify({ name: 'ECDSA', hash: 'SHA-256' }, key, signatureRaw(decode(request.signature)), bytes)) throw new Error('Pi-Signatur ungültig.');
  return payload;
}