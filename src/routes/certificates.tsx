import { createFileRoute } from '@tanstack/react-router';
import { useServerFn } from '@tanstack/react-start';
import { useState } from 'react';
import { ShieldCheck, Download, Upload, KeyRound } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { lovable } from '@/integrations/lovable';
import { approveCertificateDevice } from '@/lib/certificates.functions';

export const Route = createFileRoute('/certificates')({
  head: () => ({ meta: [
    { title: 'Video_GB – Zertifikat erneuern' },
    { name: 'description', content: 'Gerätegebundene Zertifikatserneuerung für deinen Video-Token.' },
    { property: 'og:title', content: 'Video_GB – Zertifikat erneuern' },
    { property: 'og:description', content: 'Zertifikat abholen und anschließend am Video-Token aktivieren.' },
    { property: 'og:type', content: 'website' }, { name: 'twitter:card', content: 'summary' },
  ] }),
  component: CertificatePage,
});

function CertificatePage() {
  const [file, setFile] = useState<unknown>();
  const [owner, setOwner] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');
  const [step, setStep] = useState(0);
  const [bundle, setBundle] = useState<string>();
  const approve = useServerFn(approveCertificateDevice);
  async function run() {
    setBusy(true); setBundle(undefined); setStep(0);
    try {
      if (owner) {
        await approve({ data: file }); setMessage('Token freigegeben. Verbinde dich wieder mit Video_GB und starte dort die Erneuerung.'); return;
      }
      const labels: Record<string, string> = { queued: 'Anfrage gespeichert', creating: 'Ausstellerauftrag anlegen', dns: 'DNS-Prüfung vorbereiten – das kann mehrere Minuten dauern', validating: 'Domain wird geprüft', issuing: 'Zertifikat wird ausgestellt', cleanup: 'Prüfeintrag entfernen', failed_cleanup: 'Aufräumen nach fehlgeschlagener Ausstellung' };
      const stages = ['queued', 'creating', 'dns', 'validating', 'issuing', 'cleanup', 'complete'];
      for (let attempt = 0; attempt < 120; attempt++) {
        const response = await fetch('/api/public/certificates', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(file) });
        const result = await response.json();
        if (!response.ok || result.state === 'failed') throw new Error(result.error || 'Erneuerung fehlgeschlagen.');
        setStep(Math.max(0, stages.indexOf(result.state)));
        setMessage(labels[result.state] || 'Ausstellung wird geprüft…');
        if (result.state === 'complete' && result.chain) {
          setBundle(JSON.stringify({ version: 1, device_id: result.device_id, environment: result.environment, chain: result.chain }));
          setMessage(result.environment === 'production' ? 'Zertifikat bereit. Herunterladen und im Token-WLAN auf der Startseite übertragen.' : 'Test-Ausstellung erfolgreich. Dieses Testzertifikat kann am Pi nicht aktiviert werden. Die echte Ausstellung ist noch gesperrt.');
          return;
        }
        await new Promise(resolve => setTimeout(resolve, 5000));
      }
      throw new Error('Prüfung dauert länger. Du kannst dieselbe Anfrage erneut auswählen und fortsetzen.');
    } catch (error) { setMessage(error instanceof Error ? error.message : 'Anfrage fehlgeschlagen.'); }
    finally { setBusy(false); }
  }
  function download() {
    if (!bundle) return;
    const url = URL.createObjectURL(new Blob([bundle], { type: 'application/json' }));
    const a = document.createElement('a'); a.href = url; a.download = 'video-token-zertifikat.json'; a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  return <main className="mx-auto max-w-xl px-6 py-12 text-foreground">
    <div className="mb-8 flex items-center gap-3 text-xl font-semibold"><ShieldCheck className="size-7 text-primary" />Video_GB</div>
    <h1 className="text-3xl font-semibold">{owner ? 'Token freigeben' : 'Zertifikat erneuern'}</h1>
    <p className="my-5 text-muted-foreground">{owner ? 'Nur der Domain-Eigentümer kann einen neuen Token freigeben.' : 'Du brauchst jetzt Internet über Mobilfunk oder dein Heim-WLAN. Nach dem Download verbindest du dich wieder mit Video_GB.'}</p>
    <div className="my-7 border-y border-border py-6">
      <label className="mb-3 block font-medium" htmlFor="certificate-file">{owner ? 'Freigabeanfrage vom Pi' : 'Erneuerungsanfrage vom Pi'}</label>
      <input id="certificate-file" type="file" accept=".json,application/json" disabled={busy} className="w-full text-sm" onChange={async event => {
        setMessage(''); setBundle(undefined); const selected = event.target.files?.[0];
        if (!selected) return;
        try { if (selected.size > 16384) throw new Error('Datei zu groß.'); setFile(JSON.parse(await selected.text())); }
        catch { setFile(undefined); setMessage('Bitte eine gültige Anfrage vom Pi auswählen.'); }
      }} />
    </div>
    {owner && <Button variant="outline" className="mb-4 w-full" onClick={async () => { const result = await lovable.auth.signInWithOAuth('lovable', { redirect_uri: window.location.origin + '/certificates' }); if (result.error) setMessage('Anmeldung fehlgeschlagen.'); }}><KeyRound />Als Eigentümer anmelden</Button>}
    <Button className="w-full" disabled={!file || busy} onClick={run}><Upload />{busy ? 'Bitte warten…' : owner ? 'Diesen Token freigeben' : 'Erneuerung starten / fortsetzen'}</Button>
    {busy && <progress className="mt-5 h-3 w-full" max={6} value={step} aria-label="Ausstellung" />}
    <p role="status" aria-live="polite" className="my-5 break-words text-sm text-muted-foreground">{message}</p>
    {bundle && <Button variant="outline" className="w-full" onClick={download}><Download />Zertifikat herunterladen</Button>}
    <div className="mt-10 border-t border-border pt-6"><Button variant="ghost" disabled={busy} onClick={() => { setOwner(!owner); setFile(undefined); setMessage(''); }}>{owner ? 'Zur Gäste-Erneuerung' : 'Eigentümer · Token-Freigabe'}</Button></div>
  </main>;
}