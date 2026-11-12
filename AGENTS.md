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
  __init__.py          Einrichten/Entladen des Eintrags, Module aus den Optionen, startet den todo-Abgleich
  config_flow.py       Einrichtung (ohne Eingaben) und Optionen (aktive Module)
  const.py             Konstanten: Domain, Module, Einheiten, Themes, Bildordner
  storage.py           NovaData – ALLE Daten und ihre Regeln (prüfen, bereinigen, speichern, Abonnenten benachrichtigen)
  websocket_api.py     WebSocket-Befehle nova/<modul>/<befehl> – dünn, ruft nur storage.py auf
  sanitize.py          Bereinigung von formatiertem Text (feste Liste erlaubter Elemente) und einfachem Text
  todo_sync.py         Abgleich der Einkaufsliste mit einer todo-Entität (für Assist)
  translations/        de.json, en.json
tests/                 pytest (pytest-homeassistant-custom-component)
hacs.json              Metadaten für den Marketplace
README.md              Kurzbeschreibung für Nutzer
```

## Regeln

- **Module:** `theme`, `notes`, `shopping`, `recipes` (Liste `MODULES` in `const.py`). Ein neues Modul bekommt: Eintrag in
  `MODULES`, Daten + Methoden in `storage.py`, Befehle in `websocket_api.py` (mit `@_guard("<modul>")`), Übersetzung des
  Namens in `translations/*.json` und Tests. Abgeschaltete Module behalten ihre Daten, antworten aber mit `module_disabled`.
- **Speicher nur über den HA-Store** (`.storage/nova.<modul>`), nie eigene Dateien. Einzige Ausnahme: Bilder, die liegen
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
