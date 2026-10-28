import { createFileRoute } from '@tanstack/react-router';
import { authenticateCronRequest } from '@/integrations/supabase/cron-auth';

export const Route = createFileRoute('/api/public/certificate-recovery')({ server: { handlers: {
  POST: async ({ request }) => {
    const denied = await authenticateCronRequest(request);
    if (denied) return denied;
    const token = process.env['HETZNER_API_TOKEN'];
    const encryption = process.env['CERTIFICATE_BROKER_ENCRYPTION_KEY'];
    if (!token || !encryption) return Response.json({ error: 'Aussteller nicht konfiguriert.' }, { status: 503 });
    const environment = process.env['CERTIFICATE_ISSUER_ENV'] === 'production' ? 'production' : 'staging';
    const { supabaseAdmin: db } = await import('@/integrations/supabase/client.server');
    const { data } = await db.from('certificate_orders').select('id').not('state', 'in', '(complete,failed)').limit(1);
    const job = data?.[0];
    if (job) {
      const { advanceOrder } = await import('@/lib/certificate-issuer.server');
      await advanceOrder(job.id, { hetzner: token, encryption, environment });
    }
    return Response.json({ ok: true });
  },
} } });