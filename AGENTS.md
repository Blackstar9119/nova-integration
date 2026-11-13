# Nova – Hinweise für Entwickler und Agenten

## Projekt

Nova ist die Home-Assistant-Integration (`custom_components/nova`, Domain `nova`) zu den
[Nova Cards](https://github.com/Blackstar9119/nova-cards). Sie speichert, was auf allen Geräten gleich sein soll:
Theme, Notizen, Einkaufsliste und Rezeptbuch. Die Karten reden über eine WebSocket-API mit ihr.
Installiert wird über den **Marketplace** (Benutzerdefiniertes Repository, Typ „Integration“), eingerichtet in der
Oberfläche – kein YAML.

## Ordnerstruktur

```
custom_components/nova/
  manifest.json        Metadaten, Versionsnummer (einzige Stelle)
  __init__.py          Einrichten/Entladen des Eintrags, startet/stoppt den todo-Abgleich je nach Modul Einkauf
  config_flow.py       Einrichtung (ohne Eingaben) und Optionen (aktive Module, schreibt module.* der Einstellungen)
  const.py             Konstanten: Domain, Module, Einheiten, Themes, Bildordner
  storage.py           NovaData – ALLE Daten und ihre Regeln (prüfen, bereinigen, speichern, Abonnenten benachrichtigen)
  settings.py          Einstellungen: Standardwerte, voluptuous-Schema, Migration des Speichers, Ansicht ohne Geheimnisse
  websocket_api.py     WebSocket-Befehle nova/<modul>/<befehl> – dünn, ruft nur storage.py auf
  recipe_import.py     Rezept-Import per Link: Seite laden (nur öffentliche Adressen), schema.org Recipe aus JSON-LD lesen,
                       Zutaten zerlegen, Bild verkleinern (Pillow) – liefert nur einen Entwurf, speichert nichts
  sanitize.py          Bereinigung von formatiertem Text (feste Liste erlaubter Elemente) und einfachem Text
  todo_sync.py         Abgleich der Einkaufsliste mit einer todo-Entität (für Assist)
  translations/        de.json, en.json
  static/fonts/        Schriften des Nova Rezeptbuchs (Caveat, EB Garamond als Latin-Subset, OFL), ausgeliefert unter /nova/static
tests/                 pytest (pytest-homeassistant-custom-component)
hacs.json              Metadaten für den Marketplace
README.md              Kurzbeschreibung für Nutzer
```

## Regeln

- **Module:** `theme`, `notes`, `shopping`, `recipes` (Liste `MODULES` in `const.py`). Ein neues Modul bekommt: Eintrag in
  `MODULES`, Daten + Methoden in `storage.py`, Befehle in `websocket_api.py` (mit `@_guard("<modul>")`), Übersetzung des
  Namens in `translations/*.json` und Tests. Abgeschaltete Module behalten ihre Daten, antworten aber mit `module_disabled`.
- **Einstellungen** (`nova/settings/get|set|subscribe|reset`, Speicher `.storage/nova.settings`): Bereiche `allgemein`, `module`,
  `einkauf`, `notizen`, `rezepte`, `mealie`. Sie sind immer an (kein Modul). Neue Felder: Standardwert in `DEFAULTS` und Prüfung
  in `SCHEMA` (`settings.py`); ändert sich der Aufbau, `SETTINGS_VERSION`/`SETTINGS_MINOR_VERSION` erhöhen und `migrate()`
  ergänzen. `set`/`reset` nur Admins, Lesen alle. Das Theme steht dort (`allgemein.theme`), ebenso die aktiven Module
  (`module.*`, der Options-Dialog schreibt dorthin, Umschalten wirkt ohne Neuladen) und die todo-Liste (`einkauf.todo_entity`).
  `nova/theme/*` und `nova/shopping/set_sync` bleiben als alte Befehle und dürfen weiter alle Nutzer.
- **Geheimnisse** (z. B. `mealie.token`, Liste `SECRETS` in `settings.py`) gehen nie an Karten oder Panel: `settings_view()`
  liefert nur `<feld>_gesetzt`. Auf dem Server liest man sie mit `NovaData.secret()`.
- **Speicher nur über den HA-Store** (`.storage/nova.<name>`, Liste `STORES`), nie eigene Dateien. Einzige Ausnahme: Bilder, die liegen
  verkleinert in `/config/www/nova/<modul>/` (ausgeliefert als `/local/nova/<modul>/<datei>`).
- **Nichts ungeprüft speichern.** Alles, was von einer Karte kommt, geht in `storage.py` durch `clean_text`/`clean_html`,
  Icons und Bildnamen durch die Muster dort. Formatierter Text ist HTML aus einer festen Liste (`sanitize.py`); dieselbe Liste
  steht in nova-cards (`src/shared/rich-text.js`) – beide Stellen zusammen ändern. Bilder werden an den ersten Bytes erkannt
  (WebP, JPEG, PNG), kein SVG.
- **WebSocket-API stabil halten:** Karten in freier Wildbahn sind älter als die Integration. Felder nur ergänzen, nicht
  umbenennen; bei einem Bruch `API_VERSION` in `const.py` erhöhen. Parameter nie `id` nennen (das ist die Nummer der
  WebSocket-Nachricht), sondern `note_id`, `item_id` …
- **Jede Änderung der Daten geht über `_changed()`** – das speichert (verzögert) und benachrichtigt alle Abonnenten.
- **Kein blockierender Code im Event-Loop:** Dateizugriffe über `hass.async_add_executor_job`.
- **Version** nur in `manifest.json`. Releases (Tag, GitHub-Release) nur, wenn der Nutzer es ausdrücklich sagt.
- **Versionsschema:** Betas heißen `vX.Y.ZbN` (z. B. `v0.1.0b1`, `v0.1.0b2`), stabile Releases `vX.Y.Z`. In `manifest.json` steht
  dieselbe Nummer ohne `v` (`0.1.0b1`), der Git-Tag mit `v`. Betas werden auf GitHub als „Pre-release“ markiert.
- **Alles auf Deutsch:** Kommentare, Fehlermeldungen, README. Übersetzungen immer `de.json` und `en.json`.
- **Im Text für Nutzer heißt es „Marketplace“**, nicht HACS.
- **Tests:** vor jedem Commit `pytest`. Neue Befehle bekommen einen Test.
- **Commits, Branches und PRs:** keine `Co-Authored-By`-Zeilen und keine Erwähnung von KI-Tools
  (auch nicht in Branch-Namen; Branches heißen `feature/...`).
- **Commits immer als Blackstar9119 mit 209100092+Blackstar9119@users.noreply.github.com, nie mit privater Mail.**
- **Pushen und PRs immer über `git` und `gh`**, nie über den Browser.
- **Getestet wird auf HA Dev** (192.168.178.84), nie auf dem Produktivsystem.

## Abhängigkeiten von HA-Interna

Mit `# HA-INTERN:` markiert, jeweils mit Fallback:

| Stelle | Datei | Fallback |
|---|---|---|
| `TodoListEntity.async_subscribe_updates` (Änderungen ohne neuen Zustand, z. B. Umbenennen) | `todo_sync.py` | Zustandsänderung der Liste + Abgleich alle 5 Minuten |

## Tests ausführen

```
python -m venv .venv && .venv/bin/pip install pytest-homeassistant-custom-component ical
.venv/bin/pytest
```
