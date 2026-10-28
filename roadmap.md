# Lokaler Cloud-QR-Scan
- [x] Offline-Foto-Scanner und sichere lokale Link-Zuordnung erstellen.
- [x] Captive-Seiten und Dokumentation ergänzen.
- [x] Link-Regeln testen und Foto → Video im Browser prüfen.

# Zwei Video-Link-Modi und Zertifikatserneuerung
- [x] Gästeablauf korrigieren: Kamera-Anleitung im Direkt-Modus sofort, im HTTPS-Modus erst nach bestätigter Zertifikatsaktivierung; Statuswechsel automatisch prüfen (Browser mit simuliertem Status und Regeltests bestanden; echte Aktivierung weiterhin offen).
- [x] Startseite ausschließlich nach gespeicherter Admin-Auswahl anzeigen; Gastschutz und dauerhafte Auswahl prüfen.
- [x] DNS-Anbieter ermittelt (Hetzner-Nameserver); Grenzen der Handy-Brücke und Schlüsseltransport geklärt.
- [x] PIN-geschützte dauerhafte Moduswahl und passende Gäste-Startseiten umsetzen.
- [x] Lokale CSR-Vorbereitung mit echtem Fortschritt und sicher auf dem Pi verbleibendem Schlüssel umsetzen.
- [x] Beide Modi, PIN-Schutz und Fehlerfälle testen; Installation und Dokumentation aktualisieren.
- [ ] Domain-autorisierte Online-Ausstellung, Zertifikatsimport/-prüfung und HTTPS-Aktivierung integrieren — Hetzner-Schlüssel sicher gespeichert; Lovable Cloud aktiviert; gerätegebundene Freigabe, Ausstellung und Handy-Übertragung umsetzen.
- [ ] Echte Erneuerung und direkten Cloud-QR-Kamera-Scan am Pi/iPhone prüfen — wartet auf Domain-Freigabe und HTTPS-Einrichtung.

# Software-Update ohne Wartungsmodus
- [x] Update-Knopf in der Admin-Seite: lädt `web/` + `pi/` von GitHub über das Handy-Internet und überträgt sie PIN-geschützt an den Token.
- [x] Token-seitige Prüfung (Pfad-Whitelist, Git-Prüfsummen, Rollback), Installation an die Installer-Pfade, Versionsanzeige, Neustart-/Reboot-Endpunkte.
- [x] Tests (Paketprüfung, Installation, HTTP-Endpunkte) und Browser-Durchlauf mit simuliertem GitHub; README und Installer aktualisiert.