# Kapitel 3 – Erste Schritte

[← Inhaltsverzeichnis](../README.md)

Nova ist installiert. Jetzt wird es bunt: Du wählst ein Theme, legst dein erstes Dashboard an und setzt deine erste
Nova Card darauf.

## 1. Das Nova-Panel

Links in der Seitenleiste steht jetzt **Nova**. Das ist das **Nova-Panel**, die Einstellungsseite von Nova. Ein **Panel**
ist in Home Assistant einfach eine eigene Seite in der Seitenleiste. Das Nova-Panel sehen nur Administratoren.

<p align="center"><img src="../images/ui/start-01-panel.webp" alt="Das Nova-Panel mit den allgemeinen Einstellungen" width="720"></p>

Unter **Allgemein** stellst du ein:

- **Theme:** die Farben aller Nova Cards.
- **Hintergrund:** die Farbe hinter den Karten. „Passend“ folgt dem Theme.
- **Animationen:** „Vereinfacht“ oder „Aus“ sind gut für schwache Wandtablets.
- **Schriftgröße:** Klein, Normal oder Groß.
- **Module:** dieselben Schalter wie in Kapitel 2, Schritt 6.

Links findest du außerdem Einstellungen für **Einkauf**, **Notizen** und **Rezepte**. Die brauchst du am Anfang nicht.

## 2. Theme wählen

Klicke unter **Theme** auf das Theme, das dir gefällt. Hier wählen wir **Blau**.

<p align="center"><img src="../images/ui/start-02-theme.webp" alt="Theme Blau im Nova-Panel auswählen" width="720"></p>

Die Änderung gilt sofort, auf allen Geräten. Speichern musst du nichts.

<p align="center"><img src="../images/ui/start-03-theme-blau.webp" alt="Das Nova-Panel nach dem Wechsel auf Nova Blau" width="720"></p>

> Das Theme kannst du jederzeit wieder ändern. Wenn du es öfter wechselst, ist der
> [Nova Themes Schalter](karten/themes-schalter.md) bequemer: Den legst du als Karte direkt ins Dashboard.

## 3. Erstes Dashboard anlegen

Ein **Dashboard** ist eine Seite mit Karten. Home Assistant hat schon eins, die „Übersicht“. Die baut Home Assistant aber
selbst. Für Nova legst du dir ein eigenes an, das dir ganz allein gehört.

Gehe zu **Einstellungen → Dashboards** und klicke unten rechts auf **Dashboard hinzufügen**.

<p align="center"><img src="../images/ui/start-04-dashboards.webp" alt="Liste der Dashboards mit dem Knopf Dashboard hinzufügen" width="720"></p>

Wähle **Neues Dashboard von Grund auf**.

<p align="center"><img src="../images/ui/start-05-dashboard-art.webp" alt="Auswahl Neues Dashboard von Grund auf" width="720"></p>

Gib einen **Titel** ein, zum Beispiel „Mein Zuhause“. Beim **Seitenleistensymbol** suchst du dir ein Icon aus, zum Beispiel
`mdi:home-heart`. Die **URL** füllt Home Assistant selbst aus. Klicke auf **Erstellen**.

<p align="center"><img src="../images/ui/start-06-dashboard-anlegen.webp" alt="Formular Neues Dashboard hinzufügen" width="720"></p>

Dein Dashboard steht jetzt in der Liste und links in der Seitenleiste.

<p align="center"><img src="../images/ui/start-07-dashboard-seitenleiste.webp" alt="Das neue Dashboard Mein Zuhause in der Seitenleiste" width="720"></p>

## 4. Erste Karte hinzufügen

Klicke links auf **Mein Zuhause**. Das Dashboard ist noch leer. Klicke oben rechts auf den **Stift**. Damit schaltest du
den **Bearbeitungsmodus** ein.

<p align="center"><img src="../images/ui/start-08-dashboard-leer.webp" alt="Leeres Dashboard mit dem Stift oben rechts" width="720"></p>

Jetzt siehst du gestrichelte Rahmen. Jeder Rahmen ist ein **Abschnitt**, eine Gruppe von Karten. Klicke im Abschnitt
„Neuer Abschnitt“ auf das **+**.

<p align="center"><img src="../images/ui/start-09-bearbeiten.webp" alt="Bearbeitungsmodus mit dem Plus im Abschnitt" width="720"></p>

Es öffnet sich die Kartenauswahl. Wechsle oben auf den Reiter **Nach Karte** und tippe **Nova** ins Suchfeld. Jetzt siehst du
alle Nova Cards mit einer kleinen Vorschau.

<p align="center"><img src="../images/ui/start-10-kartenauswahl.webp" alt="Kartenauswahl mit der Suche nach Nova" width="720"></p>

Für den Anfang nimmst du die **Nova Raum Card**. Tippe dafür „Nova Raum“ ins Suchfeld und klicke auf die Karte.

<p align="center"><img src="../images/ui/start-11-nova-raum.webp" alt="Kartenauswahl mit der Nova Raum Card" width="720"></p>

Jetzt öffnet sich der **Editor**. Links stellst du alles ein, rechts siehst du sofort das Ergebnis. Gib unter
**Allgemein** einen Namen ein und klappe die anderen Bereiche auf, wenn du magst. Was in jedem Bereich steckt, steht auf
der Seite der [Raum Card](karten/raum.md). Klicke auf **Speichern**.

<p align="center"><img src="../images/ui/start-12-karten-editor.webp" alt="Editor der Nova Raum Card mit Vorschau" width="720"></p>

Die Karte liegt jetzt im Abschnitt. Klicke oben rechts auf **Fertig**, um den Bearbeitungsmodus zu verlassen.

<p align="center"><img src="../images/ui/start-13-gespeichert.webp" alt="Die Karte im Abschnitt, oben rechts der Knopf Fertig" width="720"></p>

Geschafft! Deine erste Nova Card ist da.

<p align="center"><img src="../images/ui/start-14-fertig.webp" alt="Das Dashboard Mein Zuhause mit der ersten Nova Card" width="720"></p>

## Wie geht es weiter?

- Lies in [Kapitel 4](04-grundbegriffe.md) nach, was Dashboard, Ansicht, Karte und Entität genau bedeuten.
- Stöbere in [Kapitel 5](karten/README.md) durch alle Karten und such dir aus, was du brauchst.
- Hol dir in [Kapitel 6](06-dashboard-rezepte.md) Ideen für ganze Dashboards.

---

[← Kapitel 2: Installation](02-installation.md) · [Kapitel 4: Grundbegriffe →](04-grundbegriffe.md)
