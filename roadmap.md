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
- [x] Hetzner-Zugang und korrekte DNS-Zone ausschließlich lesend prüfen; Zugang erfolgreich, keine DNS-Änderungen vorgenommen.
- [x] Gerätegebundene Eigentümerfreigabe, signierte Handy-Anfragen, persistente Staging-Ausstellung, geprüften Pi-Import mit nginx-Rollback und Gästeablauf implementieren; 32 Pi-, 15 Web- und 4 Signaturtests sowie öffentlicher Browserablauf geprüft.
- [x] Eigentümerkonto anmelden und nach verifizierter Zuordnung autorisieren — Josef-Konto über verifizierte Lovable-Zuordnung und bestätigte Anmeldung geprüft und gezielt als Zertifikatsoperator freigegeben; keine automatische Erstbenutzerfreigabe.
- [ ] Echte Test-Ausstellung und veröffentlichte Hosting-Laufzeit prüfen — wartet auf Eigentümerfreigabe und Veröffentlichungsauftrag; Produktionsausstellung bleibt standardmäßig gesperrt.
- [ ] Echte Erneuerung und direkten Cloud-QR-Kamera-Scan am Pi/iPhone prüfen — wartet auf Pi-Update, echte Gerätefreigabe und Vor-Ort-Test.

# Software-Update ohne Wartungsmodus
- [x] Update-Knopf in der Admin-Seite: lädt `web/` + `pi/` von GitHub über das Handy-Internet und überträgt sie PIN-geschützt an den Token.
- [x] Token-seitige Prüfung (Pfad-Whitelist, Git-Prüfsummen, Rollback), Installation an die Installer-Pfade, Versionsanzeige, Neustart-/Reboot-Endpunkte.
- [x] Tests (Paketprüfung, Installation, HTTP-Endpunkte) und Browser-Durchlauf mit simuliertem GitHub; README und Installer aktualisiert.