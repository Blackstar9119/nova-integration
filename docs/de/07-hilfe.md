# Kapitel 7 – Hilfe bei Problemen

[← Inhaltsverzeichnis](../README.md)

Etwas klappt nicht? Keine Sorge, die meisten Probleme sind schnell gelöst. Such dir unten dein Problem aus.

## Ich finde Nova Homeverse nicht im Marketplace

Nova Homeverse steht noch nicht in der allgemeinen Liste. Du fügst es einmal über **Über Link hinzufügen** hinzu. Wie das geht, steht in
[Kapitel 2, Schritt 2](02-installation.md#schritt-2-nova-homeverse-hinzufügen).

## Ich finde Nova Homeverse nicht unter „Integration hinzufügen“

Dann fehlt meistens der Neustart. Home Assistant lädt neue Integrationen erst nach einem Neustart.
Gehe zu **Einstellungen**. Steht oben „Neustart für Nova Homeverse erforderlich“, klick darauf und dann auf **Neu starten**.
Kein Hinweis da? Dann starte über **Einstellungen → ⋮ (oben rechts) → Home Assistant neu starten**.

## Ich finde die Nova Cards nicht in der Kartenauswahl

- Wechsle in der Kartenauswahl oben auf den Reiter **Nach Karte** und suche nach „Nova“.
- Ist die Integration Nova Homeverse eingerichtet? Schau unter **Einstellungen → Geräte & Dienste** nach. Die Karten kommen mit der Integration.
- Lade die Seite einmal hart neu (siehe [Browser-Cache leeren](#browser-cache-leeren)).

## Die Karte ist grau, leer oder zeigt „nicht verfügbar“

Dann kommt von der Entität gerade nichts an. Das liegt fast nie an der Karte, sondern am Gerät.

1. Öffne **Einstellungen → Geräte & Dienste → Entitäten** und such die Entität.
2. Steht dort „Nicht verfügbar“, ist das Gerät offline. Prüf Strom, WLAN oder die Integration des Geräts.
3. Ist die Entität in Ordnung, öffne die Karte im Editor und wähl die Entität neu aus.

## Die Karte meldet, dass eine Entität fehlt

Die Karte sucht eine Entität, die es nicht (mehr) gibt. Das passiert, wenn du ein Gerät umbenennst oder entfernst.

1. Dashboard bearbeiten (Stift oben rechts) und die Karte antippen.
2. Im Editor das Feld mit der alten Entität suchen und die richtige auswählen.
3. **Speichern**.

> Eine Entitäts-ID ändert sich, wenn du sie umbenennst. Karten merken sich die alte ID. Darum musst du sie danach von Hand anpassen.

## Die Karte zeigt „Die Integration Nova Homeverse fehlt“

Einkauf, Notizen, Rezeptliste und Rezeptbuch speichern ihre Daten in der Integration. Ohne sie geht es nicht.
Richte die Integration ein, wie in [Kapitel 2, Schritt 5](02-installation.md#schritt-5-integration-nova-homeverse-hinzufügen) beschrieben.

## Die Karte zeigt nur einen Hinweis statt Liste oder Notizen

Dann ist das passende Modul abgeschaltet. Öffne links das **Nova-Panel**, dann **Allgemein → Module**, und schalt es wieder
an. Deine Daten sind noch da.

## Die Karte sieht nach einem Update komisch aus

Fast immer hat der Browser noch die alte Version im Speicher. Leer den Cache, wie unten beschrieben.

## Browser-Cache leeren

Der **Cache** ist ein Zwischenspeicher. Der Browser legt dort Dateien ab, damit Seiten schneller laden. Nach einem Update
hält er aber manchmal an alten Dateien fest.

- **Am PC:** Seite mit **Strg + Umschalt + R** neu laden (am Mac **Cmd + Umschalt + R**).
- **In der Home-Assistant-App:** In den App-Einstellungen gibt es unter „Companion App“ einen Punkt zum Zurücksetzen des
  Frontend-Caches. Danach die App einmal ganz schließen und neu öffnen.
- **Auf einem Wandtablet mit Kiosk-App:** Dort gibt es meist einen Punkt „Cache leeren“ in den Einstellungen der App.

## Eigene Bilder in Einkauf oder Rezepten werden nicht angezeigt

Nova Homeverse legt Bilder verkleinert im Ordner `www/nova` deiner Home-Assistant-Konfiguration ab. Gab es den Ordner `www` vorher
noch nicht, braucht Home Assistant einmal einen Neustart. Danach erscheinen die Bilder.

## Nova Homeverse aktualisieren

Gibt es eine neue Version, zeigt Home Assistant sie unter **Einstellungen** bei den **Updates** an.

1. Öffne den **Marketplace** und dort **Nova Homeverse**.
2. Klicke auf **Aktualisieren**.
3. Starte Home Assistant neu. Die Reparatur „Neustart für Nova Homeverse erforderlich“ hilft dir dabei.
4. Leer einmal den Browser-Cache.

Deine Dashboards und Daten bleiben dabei erhalten.

## Hinweis „Alte Nova-Cards-Ressource entfernen“

Früher gab es die Nova Cards als eigenen Download. Heute kommen sie mit der Integration. Steht die alte Datei noch in
deinem System, meldet Home Assistant das unter **Einstellungen → Reparaturen**. Folge einfach den Schritten im Hinweis.
Deine Dashboards bleiben, wie sie sind.

## Von „Nova“ auf „Nova Homeverse“ umsteigen

Nova heißt jetzt **Nova Homeverse**. Für Home Assistant ist das eine neue Integration. Darum steigst du einmal von Hand um.
Das dauert fünf Minuten, und **deine Daten bleiben erhalten**: Theme, Notizen, Einkaufsliste, Rezepte und Bilder übernimmt
Nova Homeverse automatisch. Dashboards und Karten musst du nicht anfassen.

1. **Einstellungen → Geräte & Dienste → Nova → ⋮ (drei Punkte) → Löschen.** Das ist der wichtigste Schritt.
2. Öffne den **Marketplace** und dort **Nova**. Wähle oben rechts **⋮ → Informationen aktualisieren**. Danach heißt der
   Eintrag **Nova Homeverse**.
3. Klicke auf **Aktualisieren** bzw. **Herunterladen** und bestätige.
4. Starte Home Assistant neu.
5. **Einstellungen → Geräte & Dienste → Integration hinzufügen → Nova Homeverse**, wie in
   [Kapitel 2, Schritt 5](02-installation.md#schritt-5-integration-nova-homeverse-hinzufügen).
6. Leer einmal den Browser-Cache.

Der alte Ordner `custom_components/nova` bleibt dabei eventuell liegen. Das stört nicht: Ohne Eintrag unter Geräte &
Dienste wird er nicht geladen.

Hast du Schritt 1 vergessen, startet Nova Homeverse nicht. Unter **Einstellungen → Reparaturen** steht dann
„Alte Integration „Nova“ entfernen“. Lösch die alte Integration, starte neu, fertig.

## Einen Fehler melden

Klappt etwas trotzdem nicht? Dann schreib uns. Fehler meldest du auf GitHub:
**[github.com/Blackstar9119/nova-integration/issues](https://github.com/Blackstar9119/nova-integration/issues)**.
Dafür brauchst du ein kostenloses GitHub-Konto.

Damit wir schnell helfen können, schreib bitte dazu:

- Welche Karte betroffen ist und was genau passiert.
- Die Version von Nova Homeverse. Sie steht im Nova-Panel unten links, zum Beispiel „Nova Homeverse 0.1.0b7“.
- Die Version von Home Assistant (**Einstellungen → Info**).
- Welches Gerät und welchen Browser du benutzt.
- Ein Bildschirmfoto hilft fast immer.
- Wenn du dich traust: Am PC **F12** drücken und im Reiter **Konsole** nach roten Zeilen schauen. Die kannst du mitschicken.

---

[← Kapitel 6: Rezepte für ganze Dashboards](06-dashboard-rezepte.md) · [Kapitel 8: Glossar →](08-glossar.md)
