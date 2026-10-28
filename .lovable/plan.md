# Zwei Video-Link-Modi und Zertifikatserneuerung

## Gäste und Admin
- Übersichtliche Startseite beim Verbinden mit Video_GB, mit Admin-Einstieg und PIN-Anmeldung.
- Zwei dauerhaft gespeicherte Video-Link-Modi, unabhängig vom bisherigen AP-/Wartungsmodus und der GPIO-/LED-Steuerung.
- **Normal:** bestehende QR-Codes mit `http://192.168.4.1/v/…`, normaler Kamera-Scan, keine Zertifikatsseite. Vorhandener Foto-Scanner bleibt als Alternative erreichbar.
- **HTTPS:** bestehende QR-Codes mit `https://video.gaestebuch.cloud/v/…`. Startseite zeigt Zertifikatsstatus, Gültigkeit, „Zertifikat erneuern“, echten Fortschritt und Abschlussbestätigung.
- Bestätigung erst nach erfolgreicher Prüfung und Aktivierung. Ohne gültiges Zertifikat wird HTTPS als noch nicht einsatzbereit angezeigt.
- Hinweise zum iPhone-Dialog „Ohne Internet verwenden“ erhalten. Die Webseite kann diese Systementscheidung nicht automatisch bestätigen.

## Handy-Erneuerung
- Anfrage am Token vorbereiten, Zertifikat online ausstellen lassen, übertragen, prüfen und aktivieren.
- Automatische Übertragung nur, wenn Internet und lokale Verbindung tatsächlich gleichzeitig erreichbar sind.
- Verlässliche Alternative: Anfrage auf dem Handy speichern, Token-WLAN kurz verlassen, Zertifikat online abholen, wieder verbinden und übertragen. Kein Versprechen einer vollautomatischen Ein-Klick-Erneuerung.
- Gäste können nur bereits autorisierte Erneuerungen für diesen Token starten; erstmalige Einrichtung und Moduswahl bleiben PIN-geschützt.
- Nach erfolgreicher HTTPS-Einrichtung öffnet die normale Kamera den Cloud-QR lokal, sofern das Handy die lokale Namensauflösung verwendet und das Video vorhanden ist.

## Noch fehlende Voraussetzung
Die geprüften Nameserver gehören zu Hetzner. Wer den Domain-Zugang verwaltet, ist noch unbekannt.

Für echte Online-Ausstellung benötigt ein berechtigter Domain-Verwalter DNS-Zugriff oder eine delegierte Zertifikatsvalidierung. Das vorhandene Cloud-Zertifikat ist nicht automatisch auf dem Pi verfügbar.

**Bis zur Freigabe können Startseiten, Moduswahl und lokale Vorbereitung gebaut werden. Echte Online-Erneuerung und vollständig funktionierender HTTPS-Modus bleiben blockiert.** Die laufende Cloud-Domain wird nicht auf dieses Projekt umgestellt.

## Technische Umsetzung
- Offline-Seiten in `web/`, Erweiterungen des vorhandenen Python-Dienstes und nginx in `pi/`; passende Lovable-Vorschau ohne vorgetäuschte Pi-Verbindung.
- Separate persistente Video-Link-Einstellung; Installer und Neustarts erhalten Einstellungen und Zertifikate.
- Privaten Schlüssel pro Pi lokal erzeugen und behalten. Nur CSR und öffentliche Zertifikatskette über das Handy transportieren; keine privaten Cloud-Schlüssel oder DNS-Zugangsdaten verteilen.
- Online-Ausstellungsdienst mit DNS-01, Domain-Autorisierung und begrenzter Geräteberechtigung erst nach geklärtem Domain-Zugriff integrieren.
- Zertifikate für dieselbe Cloud-Domain erlauben jedem ausgestatteten Pi, diese Domain darzustellen. Dieses Risiko muss vor der Ausstellung berücksichtigt werden.
- Domain, Schlüsselpaar, Vertrauenskette und Laufzeit prüfen; atomar installieren, nginx testen, bei Fehlern zurückrollen. Offline-Uhrzeit berücksichtigen.
- HTTP für Captive-Portal und Wiederherstellung erhalten; HTTPS nur mit gültigem Zertifikat aktivieren.

## Prüfung und Lieferung
- Tests für beide Modi, PIN-Schutz, dauerhafte Speicherung und abgelehnte Zertifikate ergänzen und ausführen.
- Gäste- und Admin-Ablauf, Video und Download im Browser prüfen.
- Installer und README aktualisieren.
- Echte Ausstellung und iPhone-Kamera-Scan auf dem Pi erst nach Domain-Freigabe und Gerätestest als bestätigt melden.
