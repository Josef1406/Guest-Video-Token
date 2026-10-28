import { createServerFn } from '@tanstack/react-start';
import { requireSupabaseAuth } from '@/integrations/supabase/auth-middleware';
import { enrollmentSchema, inspectCsr } from './certificate-policy';

export const approveCertificateDevice = createServerFn({ method: 'POST' })
  .middleware([requireSupabaseAuth])
  .inputValidator((value: unknown) => enrollmentSchema.parse(value))
  .handler(async ({ data, context }) => {
    const { data: operator } = await context.supabase.from('certificate_operators').select('user_id').eq('user_id', context.userId).maybeSingle();
    if (!operator) throw new Error('Dein Konto ist noch nicht als Domain-Eigentümer freigegeben.');
    const csr = await inspectCsr(data.csr);
    const { data: old } = await context.supabase.from('certificate_devices').select('spki').eq('id', data.device_id).maybeSingle();
    if (old && old.spki !== csr.spki) throw new Error('Dieser Token ist bereits mit einem anderen Schlüssel freigegeben.');
    if (!old) {
      const { error } = await context.supabase.from('certificate_devices').insert({ id: data.device_id, csr: data.csr, spki: csr.spki, approved_by: context.userId });
      if (error) throw new Error('Freigabe konnte nicht gespeichert werden.');
    }
    return { approved: true, device_id: data.device_id };
  });