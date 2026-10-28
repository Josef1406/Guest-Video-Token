# Zertifikatserneuerung für den Video-Token

## Ergebnis
- Der Admin legt weiterhin dauerhaft Direkt- oder Zertifikat-Modus fest; Gäste können nichts umstellen.
- Im Zertifikat-Modus sehen Gäste den tatsächlichen Status, einen Erneuerungsbutton, Fortschritt und erst nach geprüfter Aktivierung die Anleitung zum normalen Kamera-Scan.
- Private Schlüssel und Videos bleiben auf dem Pi. Der Hetzner-Zugang bleibt ausschließlich beim geschützten Online-Ausstellungsdienst.

## Einrichtung und Ablauf
1. Den Pi einmalig durch den Eigentümer freigeben. Die Freigabe bindet die Ausstellung an den öffentlichen Schlüssel dieses Pi und ausschließlich an `video.gaestebuch.cloud`.
2. Der Pi erstellt eine signierte Erneuerungsanfrage, die auf dem Handy gespeichert wird.
3. Falls das Handy im Token-WLAN kein Internet erreicht: WLAN kurz verlassen, die Online-Erneuerungsseite öffnen und die Anfrage hochladen. Dort läuft die DNS-Prüfung und Zertifikatsausstellung mit sichtbarem Fortschritt.
4. Das Handy lädt das öffentliche Zertifikat herunter, verbindet sich wieder mit `Video_GB` und überträgt es auf der lokalen Startseite.
5. Der Pi prüft Ausstellerkette, Domain, Schlüsselzugehörigkeit und Gültigkeit. Er aktiviert HTTPS mit Rückfall auf den alten Stand bei Fehlern. Die Startseite wechselt erst nach bestätigter Aktivierung zur Scan-Anleitung.

Eine automatische gleichzeitige Internet-/Token-Verbindung wird nicht vorausgesetzt. Der WLAN-Wechsel ist der verlässliche Rückfallweg.

## Technische Umsetzung
- Lovable Cloud speichert Gerätefreigaben und Ausstellungsaufträge dauerhaft; kein öffentlicher Zugriff auf diese Tabellen.
- Geschützte TanStack-Endpunkte bearbeiten ausschließlich autorisierte Geräteanfragen. DNS-01 verändert nur die Zertifikats-Prüfeinträge, keine bestehenden Website- oder E-Mail-Einträge.
- Einen etablierten ACME-Client mit nachgewiesener Unterstützung der Hosting-Umgebung verwenden; zunächst gegen den Test-Aussteller prüfen, erst danach echte Zertifikate ausstellen.
- Pi-Dienst, nginx, Offline-Seiten und Update-Paket um Zertifikatsimport, HTTPS-Konfiguration und Status ergänzen. Offline-Uhrzeit explizit behandeln, niemals durch eine ungeprüfte Handyzeit ersetzen.

## Prüfung und verbleibende Schritte
- Tests für Moduspersistenz, Gastschutz, Gerätebindung, falsche/abgelaufene Zertifikate und Rückfall bei Aktivierungsfehlern.
- Online- und lokale Handy-Abläufe im Browser prüfen; keine simulierten Antworten als echte Ausstellung ausgeben.
- Anschließend muss der neue Online-Dienst veröffentlicht und das Pi-Update installiert werden. Der abschließende Kamera-Scan und der WLAN-Wechsel benötigen einen Test mit deinem echten Pi und iPhone.

## Dauer
Die Umsetzung umfasst mehrere Sicherheits- und Verbindungsschritte. Eine belastbare Fertigstellungszeit lässt sich vor der Bibliotheks- und Ausstellerprüfung nicht versprechen; die spätere Ausstellung kann zusätzlich mehrere Minuten für die DNS-Prüfung benötigen.