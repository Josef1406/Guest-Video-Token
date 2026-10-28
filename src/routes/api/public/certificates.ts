import { createFileRoute } from '@tanstack/react-router';
import { decode, requestSchema, renewalSchema, verifyRenewal } from '@/lib/certificate-policy';

export const Route = createFileRoute('/api/public/certificates')({
  server: { handlers: {
    POST: async ({ request }) => {
      try {
        const text = await request.text();
        if (text.length > 8192) return Response.json({ error: 'Anfrage zu groß.' }, { status: 413 });
        const file = renewalSchema.parse(JSON.parse(text));
        const identity = requestSchema.parse(JSON.parse(new TextDecoder().decode(decode(file.payload))));
        const { supabaseAdmin: db } = await import('@/integrations/supabase/client.server');
        // Service reads only immutable device authorization material. No writes
        // or external DNS actions occur before cryptographic caller verification.
        const { data: device } = await db.from('certificate_devices').select('spki,revoked').eq('id', identity.device_id).maybeSingle();
        if (!device || device.revoked) return Response.json({ error: 'Token noch nicht vom Domain-Eigentümer freigegeben.' }, { status: 403 });
        await verifyRenewal(file, device.spki);
        const token = process.env['HETZNER_API_TOKEN'];
        const encryption = process.env['CERTIFICATE_BROKER_ENCRYPTION_KEY'];
        if (!token || !encryption) return Response.json({ error: 'Online-Aussteller ist noch nicht konfiguriert.' }, { status: 503 });
        // Production stays opt-in after staging and real activation validation.
        const environment = process.env['CERTIFICATE_ISSUER_ENV'] === 'production' ? 'production' : 'staging';
        const { data: recent } = await db.from('certificate_orders').select('*').eq('device_id', identity.device_id).eq('environment', environment).eq('state', 'complete').gte('created_at', new Date(Date.now() - 30 * 86400000).toISOString()).order('created_at', { ascending: false }).limit(1).maybeSingle();
        if (recent?.chain) return Response.json({ state: 'complete', environment, chain: recent.chain, device_id: identity.device_id }, { headers: { 'Cache-Control': 'no-store' } });
        let { data: job } = await db.from('certificate_orders').select('*').eq('id', identity.request_id).maybeSingle();
        if (!job) {
          const { data, error } = await db.from('certificate_orders').insert({ id: identity.request_id, device_id: identity.device_id, environment }).select('*').single();
          if (error) return Response.json({ error: 'Eine andere Erneuerung läuft gerade. Bitte später erneut versuchen.' }, { status: 409 });
          job = data;
        }
        if (!job || job.device_id !== identity.device_id) return Response.json({ error: 'Anfrage gehört nicht zu diesem Token.' }, { status: 403 });
        const { advanceOrder } = await import('@/lib/certificate-issuer.server');
        await advanceOrder(job.id, { hetzner: token, encryption, environment });
        const { data: updated } = await db.from('certificate_orders').select('state,error,chain,environment').eq('id', job.id).single();
        return Response.json({ state: updated?.state, error: updated?.error, environment: updated?.environment, device_id: identity.device_id, chain: updated?.state === 'complete' ? updated.chain : undefined }, { headers: { 'Cache-Control': 'no-store' } });
      } catch {
        return Response.json({ error: 'Anfrage oder Pi-Signatur ungültig.' }, { status: 400 });
      }
    },
  } },
});