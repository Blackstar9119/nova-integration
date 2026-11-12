# Nova

Home-Assistant-Integration zu den [Nova Cards](https://github.com/Blackstar9119/nova-cards). Sie speichert Theme,
Notizen, Einkaufsliste und Rezeptbuch in Home Assistant – so sehen alle Geräte dasselbe.

## Installation

1. Im Marketplace dieses Repository als **Benutzerdefiniertes Repository** vom Typ **Integration** hinzufügen und „Nova“ herunterladen.
2. Home Assistant neu starten.
3. **Einstellungen → Geräte & Dienste → Integration hinzufügen → Nova.**

Welche Module laufen (Theme, Notizen, Einkauf, Rezeptbuch), stellst du unter **Konfigurieren** ein.

## Gut zu wissen

- Die Einkaufsliste lässt sich mit einer `todo.*`-Liste abgleichen (einstellbar in der Nova Einkauf Card) – dann
  funktionieren Sprachbefehle wie „Setz Milch auf die Einkaufsliste“ weiter.
- Bilder liegen verkleinert unter `/config/www/nova/`. Gab es den Ordner `www` vorher nicht, braucht Home Assistant
  einmal einen Neustart, bevor die Bilder angezeigt werden.

Ausführliche Doku folgt.
