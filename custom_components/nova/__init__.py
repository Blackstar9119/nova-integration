"""Nova – Speicher für Nova Cards: Theme, Notizen, Einkauf und Rezeptbuch, auf allen Geräten gleich."""

from __future__ import annotations

import os

from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import CONF_MODULES, DOMAIN, MODULES
from .storage import NovaData
from .todo_sync import TodoSync
from .websocket_api import async_register

REGISTERED = f"{DOMAIN}_registered"
# Schriften des Nova Rezeptbuchs (Caveat, EB Garamond, Latin-Subset, SIL Open Font License) – die Karte lädt sie erst,
# wenn ein Buch zu sehen ist. Nichts kommt aus dem Internet.
STATIC_URL = "/nova/static"


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
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
    # todo-Abgleich läuft nur mit Modul Einkauf – Umschalten in den Einstellungen wirkt sofort, ohne Neuladen
    sync = TodoSync(hass, data)
    entry.async_on_unload(sync.stop)

    async def apply_modules() -> None:
        if "shopping" in data.enabled:
            await sync.start()
        else:
            sync.stop()

    entry.async_on_unload(data.listen("settings", lambda: hass.async_create_task(apply_modules())))
    await apply_modules()
    entry.async_on_unload(entry.add_update_listener(_options_changed))
    return True


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
