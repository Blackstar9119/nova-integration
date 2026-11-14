"""Nova Homeverse – Speicher für Nova Cards: Theme, Notizen, Einkauf und Rezeptbuch, auf allen Geräten gleich."""

from __future__ import annotations

import os

from homeassistant.components import frontend, panel_custom
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.loader import async_get_integration

from .cards import NovaCards
from .const import CONF_MODULES, DOMAIN, ISSUE_OLD_DOMAIN, MODULES, OLD_DOMAIN
from .storage import NovaData
from .todo_sync import NoteSync, TodoSync
from .websocket_api import async_register

REGISTERED = f"{DOMAIN}_registered"
# Schriften des Nova Rezeptbuchs (Caveat, EB Garamond, Latin-Subset, SIL Open Font License) – die Karte lädt sie erst,
# wenn ein Buch zu sehen ist. Nichts kommt aus dem Internet.
STATIC_URL = "/nova/static"
# Nova-Panel in der Seitenleiste (Einstellungen, nur Admins). Die Datei static/nova-panel.js wird in nova-cards gebaut
# („npm run panel“ aus src/panel.js) und hierher kopiert – nicht direkt bearbeiten.
PANEL_URL = "nova"
PANEL_ELEMENT = "nova-settings-panel"


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    # Läuft noch die alte Integration „Nova“, würden sich WebSocket-Befehle und Pfade doppeln → nicht starten, Hinweis zeigen
    if OLD_DOMAIN in hass.config.components:
        ir.async_create_issue(
            hass, DOMAIN, ISSUE_OLD_DOMAIN, is_fixable=False, severity=ir.IssueSeverity.ERROR,
            translation_key=ISSUE_OLD_DOMAIN,
        )
        return False
    ir.async_delete_issue(hass, DOMAIN, ISSUE_OLD_DOMAIN)
    # Welche Module laufen, steht in den Einstellungen (module.*); die Optionen zählen nur beim allerersten Start
    data = NovaData(hass, {m for m in entry.options.get(CONF_MODULES, MODULES) if m in MODULES})
    await data.async_load()
    hass.data[DOMAIN] = data
    # WebSocket-Befehle lassen sich nicht wieder abmelden – deshalb nur einmal pro HA-Start anmelden
    if not hass.data.get(REGISTERED):
        async_register(hass)
        # Statische Pfade lassen sich ebenfalls nicht abmelden
        static = os.path.join(os.path.dirname(__file__), "static")
        await hass.http.async_register_static_paths([StaticPathConfig(STATIC_URL, static, True)])
        hass.data[REGISTERED] = True
    # todo-Abgleich läuft nur mit Modul Einkauf bzw. Notizen – Umschalten in den Einstellungen wirkt sofort, ohne Neuladen
    syncs = {"shopping": TodoSync(hass, data), "notes": NoteSync(hass, data)}
    for sync in syncs.values():
        entry.async_on_unload(sync.stop)

    async def apply_modules() -> None:
        for module, sync in syncs.items():
            if module in data.enabled:
                await sync.start()
            else:
                sync.stop()

    entry.async_on_unload(data.listen("settings", lambda: hass.async_create_task(apply_modules())))
    await apply_modules()
    entry.async_on_unload(entry.add_update_listener(_options_changed))
    await _register_panel(hass)
    # Nova Cards kommen mit der Integration – keine eigene Dashboard-Ressource nötig
    cards = NovaCards(hass)
    await cards.start()
    entry.async_on_unload(cards.stop)
    entry.async_on_unload(lambda: frontend.async_remove_panel(hass, PANEL_URL, warn_if_unknown=False))
    return True


async def _register_panel(hass: HomeAssistant) -> None:
    version = (await async_get_integration(hass, DOMAIN)).version
    await panel_custom.async_register_panel(
        hass,
        frontend_url_path=PANEL_URL,
        webcomponent_name=PANEL_ELEMENT,
        sidebar_title="Nova Homeverse",
        sidebar_icon="mdi:star-four-points-outline",
        # Version im Pfad, damit Browser nach einem Update die neue Datei laden
        module_url=f"{STATIC_URL}/nova-panel.js?v={version}",
        require_admin=True,
        config={},
    )


async def _options_changed(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Module im Options-Dialog geändert → in die Einstellungen übernehmen (wirkt live)."""
    data: NovaData | None = hass.data.get(DOMAIN)
    if data:
        mods = set(entry.options.get(CONF_MODULES, MODULES))
        data.settings_set({"module": {m: m in mods for m in MODULES}})


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    data: NovaData | None = hass.data.pop(DOMAIN, None)
    if data:
        await data.async_flush()
    return True
