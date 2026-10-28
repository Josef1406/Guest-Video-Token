CREATE TABLE public.certificate_operators (user_id uuid PRIMARY KEY, created_at timestamptz NOT NULL DEFAULT now());
GRANT SELECT ON public.certificate_operators TO authenticated;
GRANT ALL ON public.certificate_operators TO service_role;
ALTER TABLE public.certificate_operators ENABLE ROW LEVEL SECURITY;
CREATE POLICY operator_self_read ON public.certificate_operators FOR SELECT TO authenticated USING (auth.uid() = user_id);
CREATE TABLE public.certificate_devices (id uuid PRIMARY KEY, csr text NOT NULL, spki text NOT NULL, approved_by uuid NOT NULL, revoked boolean NOT NULL DEFAULT false, created_at timestamptz NOT NULL DEFAULT now());
GRANT SELECT, INSERT, UPDATE ON public.certificate_devices TO authenticated;
GRANT ALL ON public.certificate_devices TO service_role;
ALTER TABLE public.certificate_devices ENABLE ROW LEVEL SECURITY;
CREATE POLICY operator_devices ON public.certificate_devices FOR ALL TO authenticated USING (EXISTS (SELECT 1 FROM public.certificate_operators WHERE user_id = auth.uid())) WITH CHECK (EXISTS (SELECT 1 FROM public.certificate_operators WHERE user_id = auth.uid()));
CREATE TABLE public.certificate_accounts (environment text PRIMARY KEY, encrypted_key text NOT NULL, account_url text NOT NULL);
GRANT ALL ON public.certificate_accounts TO service_role;
ALTER TABLE public.certificate_accounts ENABLE ROW LEVEL SECURITY;
CREATE TABLE public.certificate_orders (id uuid PRIMARY KEY, device_id uuid NOT NULL REFERENCES public.certificate_devices(id), environment text NOT NULL, state text NOT NULL DEFAULT 'queued', order_url text, txt_value text, chain text, error text, lease_until timestamptz, created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now());
GRANT ALL ON public.certificate_orders TO service_role;
ALTER TABLE public.certificate_orders ENABLE ROW LEVEL SECURITY;
CREATE UNIQUE INDEX certificate_active_order ON public.certificate_orders ((1)) WHERE state NOT IN ('complete','failed');
CREATE FUNCTION public.claim_certificate_order(order_id uuid) RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
BEGIN
 UPDATE public.certificate_orders SET lease_until = now() + interval '90 seconds' WHERE id = order_id AND (lease_until IS NULL OR lease_until < now());
 RETURN FOUND;
END; $$;
REVOKE ALL ON FUNCTION public.claim_certificate_order(uuid) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.claim_certificate_order(uuid) TO service_role;