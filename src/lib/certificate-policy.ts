import { AsnConvert } from '@peculiar/asn1-schema';\nimport { CertificationRequest } from '@peculiar/asn1-csr';\nimport { Extensions, SubjectAlternativeName } from '@peculiar/asn1-x509';\nimport { z } from 'zod';

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
// Parsed with the low-level ASN.1 packages: @peculiar/x509 pulls in tsyringe, which crashes the published server at startup.
export async function inspectCsr(pem: string) {
  const body = pem.replace(/-----(BEGIN|END) CERTIFICATE REQUEST-----/g, '').replace(/\s+/g, '');
  if (!/^[A-Za-z0-9+/]+=*$/.test(body)) throw new Error('Pi-Anfrage ungültig.');
  const der = Uint8Array.from(atob(body), c => c.charCodeAt(0));
  const csr = AsnConvert.parse(der, CertificationRequest);
  if (csr.signatureAlgorithm.algorithm !== '1.2.840.10045.4.3.2') throw new Error('Falscher Signaturtyp.');
  const info = csr.certificationRequestInfo;
  if (info.subjectPKInfo.algorithm.algorithm !== '1.2.840.10045.2.1') throw new Error('Falscher Schlüsseltyp.');
  const spki = new Uint8Array(AsnConvert.serialize(info.subjectPKInfo));
  const key = await crypto.subtle.importKey('spki', spki, { name: 'ECDSA', namedCurve: 'P-256' }, true, ['verify']);
  const signed = new Uint8Array(AsnConvert.serialize(info));
  if (!await crypto.subtle.verify({ name: 'ECDSA', hash: 'SHA-256' }, key, signatureRaw(new Uint8Array(csr.signature)), signed)) throw new Error('Signatur der Pi-Anfrage ungültig.');
  if (info.attributes.length !== 1 || info.attributes[0].type !== '1.2.840.113549.1.9.14' || info.attributes[0].values.length !== 1) throw new Error('Zusätzliche Zertifikatsrechte sind nicht erlaubt.');
  const extensions = AsnConvert.parse(info.attributes[0].values[0], Extensions);
  if (extensions.length !== 1 || extensions[0].extnID !== '2.5.29.17') throw new Error('Zusätzliche Zertifikatsrechte sind nicht erlaubt.');
  const names = AsnConvert.parse(extensions[0].extnValue.buffer, SubjectAlternativeName);
  if (names.length !== 1 || names[0].dNSName !== certificateDomain) throw new Error('Nur die Video-Domain ist erlaubt.');
  return { spki: encode(spki), der: encode(der), key };
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