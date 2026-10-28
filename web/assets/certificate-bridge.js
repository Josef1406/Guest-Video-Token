(function () {
  if (document.documentElement.dataset.preview === 'true') return;
  const renew = document.getElementById('renew-certificate');
  const upload = document.getElementById('certificate-file');
  const message = document.getElementById('renewal-message');
  const progress = document.getElementById('renewal-progress');
  if (!renew || !upload || !message || !progress) return;
  function download(value, name) {
    const url = URL.createObjectURL(new Blob([JSON.stringify(value)], { type: 'application/json' }));
    const a = document.createElement('a'); a.href = url; a.download = name; a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  renew.addEventListener('click', async () => {
    renew.disabled = true; progress.hidden = false; progress.removeAttribute('value');
    message.textContent = 'Erneuerungsanfrage auf dem Pi vorbereiten…';
    try {
      const response = await fetch('/api/public/certificate/request', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'Anfrage fehlgeschlagen.');
      download(data, 'video-token-anfrage.json');
      document.getElementById('renewal-online').hidden = false;
      progress.value = 1;
      message.textContent = 'Anfrage gespeichert. WLAN kurz ausschalten, Online-Seite in Safari öffnen und diese Datei auswählen. Danach wieder mit Video_GB verbinden.';
    } catch (error) { message.textContent = error.message; progress.hidden = true; }
    finally { renew.disabled = false; }
  });
  upload.addEventListener('change', async () => {
    const file = upload.files?.[0]; if (!file) return;
    upload.disabled = true; progress.hidden = false; progress.removeAttribute('value');
    message.textContent = 'Zertifikat auf dem Pi prüfen und HTTPS aktivieren…';
    try {
      if (file.size > 40000) throw new Error('Zertifikatsdatei zu groß.');
      const data = JSON.parse(await file.text());
      const response = await fetch('/api/public/certificate/import', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) });
      const result = await response.json();
      if (!response.ok || !result.ready) throw new Error(result.error || 'HTTPS konnte nicht aktiviert werden.');
      progress.value = 1; message.textContent = 'Zertifikat geprüft und aktiviert. Du kannst jetzt den QR-Code mit der normalen Kamera scannen.';
      window.dispatchEvent(new Event('pageshow'));
    } catch (error) { message.textContent = error.message; progress.hidden = true; }
    finally { upload.disabled = false; upload.value = ''; }
  });
})();