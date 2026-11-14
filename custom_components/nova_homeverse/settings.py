"""Einstellungen von Nova Homeverse: Standardwerte, Prüfung (voluptuous) und Migration des Speichers.

Gespeichert in .storage/nova_homeverse.settings. Die Daten selbst verwaltet NovaData in storage.py; hier steht nur, welche Werte
es gibt und welche erlaubt sind. Geheimnisse (Mealie-Token) gehen nie an Karten oder Panel – view() ersetzt sie durch
„gesetzt: ja/nein“.
"""

from __future__ import annotations

import copy

import voluptuous as vol
from homeassistant.helpers import config_validation as cv

from .const import BOOK_STYLES, MODULES, THEMES

SETTINGS_VERSION = 1
SETTINGS_MINOR_VERSION = 2

SIZES = ("klein", "normal", "gross")
ANIMATIONS = ("normal", "vereinfacht", "aus")
GROUPING = ("geschaeft", "keine")
# Hintergrund der Dashboards mit Nova Cards: keiner (wie bisher), passend zum Theme oder ein fester
BACKGROUNDS = ("keiner", "passend", *THEMES)

DEFAULTS: dict = {
    "allgemein": {"theme": None, "animationen": "normal", "schriftgroesse": "normal", "hintergrund": "keiner"},
    "module": {m: True for m in MODULES},
    "einkauf": {"standard_geschaeft": None, "gruppierung": "geschaeft", "todo_entity": None, "bilder": True},
    "notizen": {"standard_schriftgroesse": "normal", "kompakt": False, "todo_entity": None},
    "rezepte": {"buch_variante": "old", "standard_portionen": 2},
    "mealie": {"url": None, "token": None},
}
SECTIONS = tuple(DEFAULTS)
# Felder, die nur auf dem Server bleiben: in view() steht stattdessen <feld>_gesetzt
SECRETS = {"mealie": ("token",)}


def _empty_none(v):
    """Leerer Text = nicht gesetzt."""
    if v is None:
        return None
    if isinstance(v, str) and not v.strip():
        return None
    return v


def _url(v):
    v = _empty_none(v)
    if v is None:
        return None
    v = cv.url(str(v).strip())
    if not v.startswith(("http://", "https://")):
        raise vol.Invalid("nur http:// oder https://")
    return v.rstrip("/")


def _token(v):
    v = _empty_none(v)
    if v is None:
        return None
    if not isinstance(v, str) or len(v.strip()) > 2000:
        raise vol.Invalid("Token ist zu lang")
    return v.strip()


def _choice(options):
    return vol.All(str, vol.In(options, msg=f"erlaubt: {', '.join(options)}"))


SCHEMA = vol.Schema({
    vol.Optional("allgemein"): {
        vol.Optional("theme"): vol.Any(None, _choice(THEMES)),
        vol.Optional("animationen"): _choice(ANIMATIONS),
        vol.Optional("schriftgroesse"): _choice(SIZES),
        vol.Optional("hintergrund"): _choice(BACKGROUNDS),
    },
    vol.Optional("module"): {vol.Optional(m): bool for m in MODULES},
    vol.Optional("einkauf"): {
        vol.Optional("standard_geschaeft"): vol.Any(None, vol.All(str, vol.Length(min=1, max=64))),
        vol.Optional("gruppierung"): _choice(GROUPING),
        vol.Optional("todo_entity"): vol.All(_empty_none, vol.Any(None, cv.entity_domain("todo"))),
        vol.Optional("bilder"): bool,
    },
    vol.Optional("notizen"): {
        vol.Optional("standard_schriftgroesse"): _choice(SIZES),
        vol.Optional("kompakt"): bool,
        vol.Optional("todo_entity"): vol.All(_empty_none, vol.Any(None, cv.entity_domain("todo"))),
    },
    vol.Optional("rezepte"): {
        vol.Optional("buch_variante"): _choice(BOOK_STYLES),
        vol.Optional("standard_portionen"): vol.All(vol.Coerce(int), vol.Range(min=1, max=50)),
    },
    vol.Optional("mealie"): {
        vol.Optional("url"): _url,
        vol.Optional("token"): _token,
    },
}, extra=vol.PREVENT_EXTRA)


def defaults() -> dict:
    return copy.deepcopy(DEFAULTS)


def validate(patch) -> dict:
    """Änderung prüfen. Ungültig → ValueError mit dem Feld, das schuld ist; dann wird nichts gespeichert."""
    if not isinstance(patch, dict) or not patch:
        raise ValueError("Keine Einstellungen angegeben")
    try:
        return SCHEMA(patch)
    except vol.Invalid as err:
        errs = err.errors if isinstance(err, vol.MultipleInvalid) else [err]
        parts = []
        for e in errs:
            path = ".".join(str(p) for p in e.path) or "einstellungen"
            msg = "unbekanntes Feld" if e.error_message == "extra keys not allowed" else e.error_message
            parts.append(f"{path}: {msg}")
        raise ValueError("Ungültige Einstellung – " + "; ".join(parts)) from err


def normalize(raw) -> dict:
    """Gespeicherten Stand auf die aktuellen Felder bringen: fehlende Werte = Standard, ungültige/unbekannte fallen weg."""
    out = defaults()
    for sec, fields in (raw or {}).items() if isinstance(raw, dict) else ():
        if sec not in out or not isinstance(fields, dict):
            continue
        for key, val in fields.items():
            if key not in out[sec]:
                continue
            try:
                out[sec][key] = SCHEMA({sec: {key: val}})[sec][key]
            except vol.Invalid:
                pass
    return out


def view(settings: dict) -> dict:
    """Stand für Karten und Panel: ohne Geheimnisse, stattdessen <feld>_gesetzt."""
    out = copy.deepcopy(settings)
    for sec, keys in SECRETS.items():
        for key in keys:
            out[sec][f"{key}_gesetzt"] = bool(out[sec].pop(key, None))
    return out


async def migrate(old_major: int, old_minor: int, data: dict) -> dict:
    """Speicher älterer Versionen umbauen. Neue Version: SETTINGS_VERSION/MINOR erhöhen und hier einen Schritt ergänzen.

    1.1 → 1.2: neue Felder allgemein.hintergrund und notizen.todo_entity (Standardwerte, sonst nichts).
    Was die Prüfung nicht kennt, räumt normalize() beim Laden ohnehin weg.
    """
    if old_major > SETTINGS_VERSION:
        raise NotImplementedError("Gespeicherte Einstellungen sind neuer als diese Nova-Version")
    if old_major == 1 and old_minor < 2:
        data = copy.deepcopy(data or {})
        data.setdefault("allgemein", {}).setdefault("hintergrund", "keiner")
        data.setdefault("notizen", {}).setdefault("todo_entity", None)
    return data
