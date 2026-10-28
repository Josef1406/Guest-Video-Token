import { AcmeClient, AcmeAccount, AcmeOrder } from '@fishballpkg/acme';
import { supabaseAdmin as db } from '@/integrations/supabase/client.server';
import { certificateDomain, decode, encode, inspectCsr } from './certificate-policy';

const challengeName = '_acme-challenge.video';
const zoneName = 'gaestebuch.cloud';
type Secrets = { hetzner: string; encryption: string; environment: 'staging' | 'production' };
async function cryptKey(secret: string) {
  return crypto.subtle.importKey('raw', await crypto.subtle.digest('SHA-256', new TextEncoder().encode(secret)), 'AES-GCM', false, ['encrypt', 'decrypt']);
}
async function encrypt(value: string, secret: string) {
  const iv = crypto.getRandomValues(new Uint8Array(12));
  const data = await crypto.subtle.encrypt({ name: 'AES-GCM', iv }, await cryptKey(secret), new TextEncoder().encode(value));
  return encode(iv) + '.' + encode(data);
}
async function decrypt(value: string, secret: string) {
  const [iv, data] = value.split('.');
  if (!iv || !data) throw new Error('Ausstellerkonto nicht lesbar.');
  return new TextDecoder().decode(await crypto.subtle.decrypt({ name: 'AES-GCM', iv: decode(iv) }, await cryptKey(secret), decode(data)));
}
async function hetzner(path: string, token: string, method = 'GET', body?: object) {
  const response = await fetch('https://api.hetzner.cloud/v1' + path, { method, headers: { Authorization: 'Bearer ' + token, 'Content-Type': 'application/json' }, body: body ? JSON.stringify(body) : undefined });
  if (response.status === 404) return null;
  if (!response.ok) throw new Error('Hetzner-DNS-Anfrage fehlgeschlagen (' + response.status + ').');
  return response.json();
}
async function updateTxt(token: string, value: string, remove: boolean) {
  const zones = await hetzner('/zones?name=' + zoneName, token);
  const zone = zones?.zones?.find((item: { name: string }) => item.name === zoneName);
  if (!zone) throw new Error('DNS-Zone im Hetzner-Projekt nicht gefunden.');
  const path = '/zones/' + zone.id + '/rrsets/' + challengeName + '/TXT';
  const rrset = await hetzner(path, token);
  const record = { value: '"' + value + '"' };
  const exists = rrset?.rrset?.records?.some((item: { value: string }) => item.value === record.value);
  if ((remove && !exists) || (!remove && exists)) return;
  const result = !rrset && !remove
    ? await hetzner('/zones/' + zone.id + '/rrsets', token, 'POST', { name: challengeName, type: 'TXT', ttl: 60, records: [record] })
    : await hetzner(path + '/actions/' + (remove ? 'remove_records' : 'add_records'), token, 'POST', { records: [record] });
  // Actions are asynchronous. The next durable step reconciles the live RRset;
  // DNS visibility, not this response, gates challenge submission.
  if (result?.action?.status === 'error') throw new Error('Hetzner konnte den Prüfwert nicht setzen.');
}
async function visible(value: string) {
  const response = await fetch('https://dns.google/resolve?name=_acme-challenge.' + certificateDomain + '&type=TXT');
  if (!response.ok) return false;
  const data = await response.json();
  return data.Answer?.some((item: { data: string }) => item.data.replace(/"/g, '') === value) === true;
}
async function account(secrets: Secrets) {
  const host = secrets.environment === 'production' ? 'acme-v02.api.letsencrypt.org' : 'acme-staging-v02.api.letsencrypt.org';
  const client = await AcmeClient.init('https://' + host + '/directory');
  const { data: saved } = await db.from('certificate_accounts').select('*').eq('environment', secrets.environment).maybeSingle();
  if (saved) {
    const jwk = JSON.parse(await decrypt(saved.encrypted_key, secrets.encryption));
    const privateKey = await crypto.subtle.importKey('jwk', jwk, { name: 'ECDSA', namedCurve: 'P-256' }, true, ['sign']);
    const { d: _private, ...publicJwk } = jwk;
    const publicKey = await crypto.subtle.importKey('jwk', publicJwk, { name: 'ECDSA', namedCurve: 'P-256' }, true, ['verify']);
    return new AcmeAccount({ client, keyPair: { privateKey, publicKey }, url: saved.account_url });
  }
  const created = await client.createAccount({ emails: [] });
  const encrypted = await encrypt(JSON.stringify(await crypto.subtle.exportKey('jwk', created.keyPair.privateKey)), secrets.encryption);
  const { error } = await db.from('certificate_accounts').insert({ environment: secrets.environment, encrypted_key: encrypted, account_url: created.url });
  if (error) throw new Error('Ausstellerkonto konnte nicht gespeichert werden.');
  return created;
}

export async function advanceOrder(id: string, secrets: Secrets) {
  const { data: claimed, error: claimError } = await db.rpc('claim_certificate_order', { order_id: id });
  if (claimError || !claimed) return;
  const { data: job } = await db.from('certificate_orders').select('*').eq('id', id).single();
  if (!job) return;
  const patch = async (changes: object) => {
    const { error } = await db.from('certificate_orders').update({ ...changes, updated_at: new Date().toISOString() }).eq('id', id);
    if (error) throw new Error('Auftrag konnte nicht gespeichert werden.');
  };
  try {
    if (job.environment !== secrets.environment) throw new Error('Ausstellerumgebung wurde geändert.');
    if (job.state === 'complete' || job.state === 'failed') return;
    if (job.state === 'cleanup' || job.state === 'failed_cleanup') {
      if (job.txt_value) await updateTxt(secrets.hetzner, job.txt_value, true);
      // Release shared-name ownership only after the asynchronous removal
      // is observed by a second read on a later durable step.
      if (job.txt_value && await visible(job.txt_value)) return;
      await patch({ state: job.state === 'cleanup' ? 'complete' : 'failed' }); return;
    }
    if (Date.now() - Date.parse(job.created_at) > 3600000) throw new Error('Ausstellung abgelaufen; bitte den Admin verständigen.');
    const { data: device } = await db.from('certificate_devices').select('*').eq('id', job.device_id).single();
    if (!device || device.revoked) throw new Error('Token-Freigabe fehlt oder wurde widerrufen.');
    const acme = await account(secrets);
    if (!job.order_url) {
      // Persist intent before external write. Uncertain creation never silently
      // creates another order: operator must reconcile a creation interruption.
      if (job.state === 'creating') throw new Error('Unterbrochene Auftragsanlage: Admin-Prüfung erforderlich.');
      await patch({ state: 'creating' });
      const order = await acme.createOrder({ domains: [certificateDomain] });
      await patch({ order_url: order.url, state: 'dns' }); return;
    }
    const order = await AcmeOrder.init({ account: acme, url: job.order_url });
    const snapshot = await order.fetch();
    if (snapshot.status === 'invalid') throw new Error('Zertifikatsaussteller hat die Anfrage abgelehnt.');
    if (snapshot.status === 'valid') {
      const chain = await order.getCertificate();
      await patch({ chain, state: 'cleanup' }); return;
    }
    if (snapshot.status === 'ready') {
      const csr = await inspectCsr(device.csr);
      if (csr.spki !== device.spki) throw new Error('Geräteschlüssel wurde verändert.');
      const response = await acme.jwsFetch(snapshot.finalize, { payload: { csr: csr.der } });
      if (!response.ok) throw new Error('Zertifikatsabschluss fehlgeschlagen (' + response.status + ').');
      await patch({ state: 'issuing' }); return;
    }
    if (snapshot.status === 'processing') return;
    const authorization = order.authorizations[0];
    if (!authorization) throw new Error('Domainprüfung fehlt.');
    const challenge = authorization.findChallenge('dns-01');
    if (!challenge) throw new Error('DNS-Prüfung fehlt.');
    const value = await challenge.digestToken();
    if (!job.txt_value) { await patch({ txt_value: value }); return; }
    if (job.txt_value !== value) throw new Error('Prüfauftrag wurde verändert.');
    await updateTxt(secrets.hetzner, value, false);
    if (!await visible(value)) { await patch({ state: 'dns' }); return; }
    const state = await challenge.fetch();
    if (state.status === 'pending') await challenge.submit();
    await patch({ state: 'validating' });
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Ausstellung fehlgeschlagen.';
    if (job.state === 'cleanup' || job.state === 'failed_cleanup') {
      await patch({ error: message });
    } else {
      await patch({ state: job.txt_value ? 'failed_cleanup' : 'failed', error: message });
    }
  } finally {
    await db.from('certificate_orders').update({ lease_until: null }).eq('id', id);
  }
}