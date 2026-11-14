"""WebSocket-API von Nova Homeverse: nova/<modul>/<befehl> (genutzt von Nova Cards, src/shared/nova-store.js)."""

from __future__ import annotations

import voluptuous as vol
from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.loader import async_get_integration

from .const import API_VERSION, CONF_MODULES, DOMAIN, IMAGE_MODULES, MODULES
from .recipe_import import RecipeImportError, import_recipe
from .settings import SECTIONS
from .storage import ModuleDisabled, NovaData


def _data(hass: HomeAssistant) -> NovaData | None:
    return hass.data.get(DOMAIN)


def _guard(module: str | None):
    """Fehler als WebSocket-Fehler zurückgeben: not_ready (nicht eingerichtet), module_disabled, invalid."""

    def deco(fn):
        async def wrapper(hass, connection, msg):
            data = _data(hass)
            if data is None:
                connection.send_error(msg["id"], "not_ready", "Nova ist nicht eingerichtet")
                return
            try:
                if module:
                    data.require(module)
                res = fn(hass, connection, msg, data)
                if hasattr(res, "__await__"):
                    await res
            except ModuleDisabled as err:
                connection.send_error(msg["id"], "module_disabled", f"Modul „{err}“ ist in den Optionen von Nova abgeschaltet")
            except ValueError as err:
                connection.send_error(msg["id"], "invalid", str(err))

        return wrapper

    return deco


def _subscribe(kind: str, view):
    # Einstellungen gibt es immer, alle anderen Abos hängen am Modul
    @_guard(None if kind == "settings" else kind)
    def handler(hass, connection, msg, data: NovaData):
        mid = msg["id"]

        @callback
        def send() -> None:
            connection.send_message(websocket_api.event_message(mid, view(data)))

        connection.subscriptions[mid] = data.listen(kind, send)
        connection.send_result(mid)
        send()

    return handler


@websocket_api.websocket_command({vol.Required("type"): "nova/info"})
@websocket_api.async_response
async def ws_info(hass, connection, msg):
    data = _data(hass)
    connection.send_result(msg["id"], {
        "api": API_VERSION,
        "ready": data is not None,
        CONF_MODULES: [m for m in MODULES if data and m in data.enabled],
        "settings": True,
        "version": (await async_get_integration(hass, DOMAIN)).version,
    })


# ---------- Einstellungen ----------
# Lesen: jeder angemeldete Nutzer. Schreiben/Zurücksetzen: nur Admins. Geheimnisse (Mealie-Token) gehen nie raus.
@websocket_api.websocket_command({vol.Required("type"): "nova/settings/get"})
@websocket_api.async_response
@_guard(None)
async def ws_settings_get(hass, connection, msg, data: NovaData):
    connection.send_result(msg["id"], data.settings_view())


@websocket_api.websocket_command({vol.Required("type"): "nova/settings/subscribe"})
@websocket_api.async_response
async def ws_settings_subscribe(hass, connection, msg):
    await _subscribe("settings", lambda d: d.settings_view())(hass, connection, msg)


@websocket_api.websocket_command({vol.Required("type"): "nova/settings/set", vol.Required("settings"): dict})
@websocket_api.require_admin
@websocket_api.async_response
@_guard(None)
async def ws_settings_set(hass, connection, msg, data: NovaData):
    connection.send_result(msg["id"], data.settings_set(msg["settings"]))


@websocket_api.websocket_command({vol.Required("type"): "nova/settings/reset", vol.Optional("bereich"): vol.In(SECTIONS)})
@websocket_api.require_admin
@websocket_api.async_response
@_guard(None)
async def ws_settings_reset(hass, connection, msg, data: NovaData):
    connection.send_result(msg["id"], data.settings_reset(msg.get("bereich")))


# ---------- Theme (alte Befehle, lesen/schreiben allgemein.theme der Einstellungen) ----------
# nova/theme/set darf jeder angemeldete Nutzer (Themes Schalter auf Wandpanels ohne Admin-Konto).
@websocket_api.websocket_command({vol.Required("type"): "nova/theme/subscribe"})
@websocket_api.async_response
async def ws_theme_subscribe(hass, connection, msg):
    await _subscribe("theme", lambda d: d.theme_view())(hass, connection, msg)


@websocket_api.websocket_command({vol.Required("type"): "nova/theme/set", vol.Required("theme"): str})
@websocket_api.async_response
@_guard("theme")
async def ws_theme_set(hass, connection, msg, data: NovaData):
    data.theme_set(msg["theme"])
    connection.send_result(msg["id"])


# ---------- Notizen ----------
@websocket_api.websocket_command({vol.Required("type"): "nova/notes/subscribe"})
@websocket_api.async_response
async def ws_notes_subscribe(hass, connection, msg):
    await _subscribe("notes", lambda d: d.notes_view())(hass, connection, msg)


@websocket_api.websocket_command({
    vol.Required("type"): "nova/notes/save",
    vol.Required("note"): {
        vol.Optional("id"): cv.string,
        vol.Optional("title"): str,
        vol.Optional("body"): str,
        vol.Optional("pinned"): bool,
    },
})
@websocket_api.async_response
@_guard("notes")
async def ws_notes_save(hass, connection, msg, data: NovaData):
    connection.send_result(msg["id"], {"note": data.note_save(msg["note"])})


@websocket_api.websocket_command({vol.Required("type"): "nova/notes/delete", vol.Required("note_id"): cv.string})
@websocket_api.async_response
@_guard("notes")
async def ws_notes_delete(hass, connection, msg, data: NovaData):
    data.note_delete(msg["note_id"])
    connection.send_result(msg["id"])


# ---------- Einkauf ----------
@websocket_api.websocket_command({vol.Required("type"): "nova/shopping/subscribe"})
@websocket_api.async_response
async def ws_shop_subscribe(hass, connection, msg):
    await _subscribe("shopping", lambda d: d.shop_view())(hass, connection, msg)


ITEM = {
    vol.Optional("id"): cv.string,
    vol.Optional("name"): str,
    vol.Optional("qty"): vol.Coerce(float),
    vol.Optional("unit"): str,
    vol.Optional("store"): vol.Any(None, str),
    vol.Optional("icon"): vol.Any(None, str),
    vol.Optional("image"): vol.Any(None, str),
    vol.Optional("note"): str,
    vol.Optional("done"): bool,
}


@websocket_api.websocket_command({vol.Required("type"): "nova/shopping/item_save", vol.Required("item"): ITEM})
@websocket_api.async_response
@_guard("shopping")
async def ws_item_save(hass, connection, msg, data: NovaData):
    connection.send_result(msg["id"], {"item": data.item_save(msg["item"])})


@websocket_api.websocket_command({vol.Required("type"): "nova/shopping/item_delete", vol.Required("item_id"): cv.string})
@websocket_api.async_response
@_guard("shopping")
async def ws_item_delete(hass, connection, msg, data: NovaData):
    data.item_delete(msg["item_id"])
    connection.send_result(msg["id"])


@websocket_api.websocket_command({vol.Required("type"): "nova/shopping/clear_done"})
@websocket_api.async_response
@_guard("shopping")
async def ws_clear_done(hass, connection, msg, data: NovaData):
    connection.send_result(msg["id"], {"removed": data.clear_done()})


@websocket_api.websocket_command({vol.Required("type"): "nova/shopping/reorder", vol.Required("ids"): [cv.string]})
@websocket_api.async_response
@_guard("shopping")
async def ws_reorder(hass, connection, msg, data: NovaData):
    data.reorder(msg["ids"])
    connection.send_result(msg["id"])


@websocket_api.websocket_command({vol.Required("type"): "nova/shopping/history_delete", vol.Required("key"): cv.string})
@websocket_api.async_response
@_guard("shopping")
async def ws_history_delete(hass, connection, msg, data: NovaData):
    data.history_delete(msg["key"])
    connection.send_result(msg["id"])


@websocket_api.websocket_command({
    vol.Required("type"): "nova/shopping/store_save",
    vol.Required("store"): {
        vol.Optional("id"): cv.string,
        vol.Optional("name"): str,
        vol.Optional("icon"): vol.Any(None, str),
        vol.Optional("order"): int,
    },
})
@websocket_api.async_response
@_guard("shopping")
async def ws_store_save(hass, connection, msg, data: NovaData):
    connection.send_result(msg["id"], {"store": data.store_save(msg["store"])})


@websocket_api.websocket_command({vol.Required("type"): "nova/shopping/store_delete", vol.Required("store_id"): cv.string})
@websocket_api.async_response
@_guard("shopping")
async def ws_store_delete(hass, connection, msg, data: NovaData):
    data.store_delete(msg["store_id"])
    connection.send_result(msg["id"])


@websocket_api.websocket_command({
    vol.Required("type"): "nova/shopping/set_sync",
    vol.Required("entity_id"): vol.Any(None, cv.entity_domain("todo")),
})
@websocket_api.async_response
@_guard("shopping")
async def ws_set_sync(hass, connection, msg, data: NovaData):
    # Alter Befehl, schreibt einkauf.todo_entity. Bleibt für alle offen: die Einkauf Card ruft ihn selbst auf.
    data.set_sync(msg["entity_id"])
    connection.send_result(msg["id"])


# ---------- Rezeptbuch ----------
@websocket_api.websocket_command({vol.Required("type"): "nova/recipes/subscribe"})
@websocket_api.async_response
async def ws_recipes_subscribe(hass, connection, msg):
    await _subscribe("recipes", lambda d: d.recipes_view())(hass, connection, msg)


@websocket_api.websocket_command({
    vol.Required("type"): "nova/recipes/save",
    vol.Required("recipe"): {
        vol.Optional("id"): cv.string,
        vol.Optional("title"): str,
        vol.Optional("image"): vol.Any(None, str),
        vol.Optional("servings"): vol.Coerce(float),
        vol.Optional("time"): vol.Any(None, vol.Coerce(float)),
        vol.Optional("tags"): [str],
        vol.Optional("ingredients"): [dict],
        vol.Optional("steps"): str,
        vol.Optional("favorite"): bool,
        vol.Optional("source"): vol.Any(None, str),
    },
})
@websocket_api.async_response
@_guard("recipes")
async def ws_recipes_save(hass, connection, msg, data: NovaData):
    connection.send_result(msg["id"], {"recipe": data.recipe_save(msg["recipe"])})


@websocket_api.websocket_command({vol.Required("type"): "nova/recipes/delete", vol.Required("recipe_id"): cv.string})
@websocket_api.async_response
@_guard("recipes")
async def ws_recipes_delete(hass, connection, msg, data: NovaData):
    data.recipe_delete(msg["recipe_id"])
    connection.send_result(msg["id"])


@websocket_api.websocket_command({
    vol.Required("type"): "nova/recipes/to_shopping",
    vol.Required("recipe_id"): cv.string,
    vol.Optional("servings"): vol.Coerce(float),
    vol.Optional("only"): [int],
})
@websocket_api.async_response
@_guard("recipes")
async def ws_recipes_to_shopping(hass, connection, msg, data: NovaData):
    connection.send_result(msg["id"], {"added": data.recipe_to_shopping(msg["recipe_id"], msg.get("servings"), msg.get("only"))})


@websocket_api.websocket_command({vol.Required("type"): "nova/recipes/import", vol.Required("url"): str})
@websocket_api.async_response
@_guard("recipes")
async def ws_recipes_import(hass, connection, msg, data: NovaData):
    """Rezeptseite lesen und als Entwurf zurückgeben (nichts wird gespeichert), dazu mögliche Doppelte."""
    try:
        draft = await import_recipe(hass, msg["url"])
    except RecipeImportError as err:
        connection.send_error(msg["id"], err.code, str(err))
        return
    connection.send_result(msg["id"], {"recipe": draft, "duplicates": data.recipe_duplicates(draft["title"], draft["source"])})


# ---------- Bilder ----------
@websocket_api.websocket_command({
    vol.Required("type"): "nova/image/upload",
    vol.Required("module"): vol.In(IMAGE_MODULES),
    vol.Required("data"): str,
})
@websocket_api.async_response
@_guard(None)
async def ws_image_upload(hass, connection, msg, data: NovaData):
    name = await data.image_save(msg["module"], msg["data"])
    connection.send_result(msg["id"], {"image": name, "url": data.image_url(msg["module"], name)})


COMMANDS = (
    ws_info, ws_settings_get, ws_settings_subscribe, ws_settings_set, ws_settings_reset,
    ws_theme_subscribe, ws_theme_set, ws_notes_subscribe, ws_notes_save, ws_notes_delete,
    ws_shop_subscribe, ws_item_save, ws_item_delete, ws_clear_done, ws_reorder, ws_history_delete,
    ws_store_save, ws_store_delete, ws_set_sync,
    ws_recipes_subscribe, ws_recipes_save, ws_recipes_delete, ws_recipes_to_shopping, ws_recipes_import, ws_image_upload,
)


@callback
def async_register(hass: HomeAssistant) -> None:
    for cmd in COMMANDS:
        websocket_api.async_register_command(hass, cmd)
