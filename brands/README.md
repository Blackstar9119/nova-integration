# Bilder für home-assistant/brands

Vorbereitet für eine spätere Einreichung bei [home-assistant/brands](https://github.com/home-assistant/brands), noch nicht
eingereicht. Der Ordner `custom_integrations/nova_homeverse/` entspricht dem Aufbau dort:

| Datei | Größe | Inhalt |
|---|---|---|
| `icon.png` / `icon@2x.png` | 256 × 256 / 512 × 512 | Haus mit Stern, transparent |
| `logo.png` / `logo@2x.png` | Höhe 128 / 256 | Haus + „Nova Homeverse“ + „by </Blackstar>“, für helle Oberflächen |
| `dark_logo.png` / `dark_logo@2x.png` | Höhe 128 / 256 | dasselbe für dunkle Oberflächen |

PNG, transparent, ohne Rand, verlustfrei komprimiert (oxipng). Ein `dark_icon.png` braucht es nicht, das Icon wirkt auf
hellem und dunklem Grund.

Home Assistant zeigt die Bilder schon heute ohne Einreichung an: Dieselben Dateien liegen in
`custom_components/nova_homeverse/brand/`, von dort liest sie Home Assistant für eigene Integrationen direkt.

Quelle: `docs/images/logo/` (SVG). Das Original liegt dort als `logo-original.png`.
