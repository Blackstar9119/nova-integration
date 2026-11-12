"""Nova – Speicher für Nova Cards: Theme, Notizen, Einkauf und Rezeptbuch, auf allen Geräten gleich."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import CONF_MODULES, DOMAIN, MODULES
from .storage import NovaData
from .todo_sync import TodoSync
from .websocket_api import async_register

REGISTERED = f"{DOMAIN}_registered"


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    enabled = {m for m in entry.options.get(CONF_MODULES, MODULES) if m in MODULES}
    data = NovaData(hass, enabled)
    await data.async_load()
    hass.data[DOMAIN] = data
    # WebSocket-Befehle lassen sich nicht wieder abmelden – deshalb nur einmal pro HA-Start anmelden
    if not hass.data.get(REGISTERED):
        async_register(hass)
        hass.data[REGISTERED] = True
    if "shopping" in enabled:
        sync = TodoSync(hass, data)
        entry.async_on_unload(sync.stop)
        await sync.start()
    entry.async_on_unload(entry.add_update_listener(_reload))
    return True


async def _reload(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    data: NovaData | None = hass.data.pop(DOMAIN, None)
    if data:
        await data.async_flush()
    return True
