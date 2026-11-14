"""Tests des Moduls Einstellungen: get/set/subscribe/reset, Rechte, Token-Abschirmung, Übernahme alter Daten."""

import json

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.nova_homeverse.const import CONF_MODULES, DOMAIN
from custom_components.nova_homeverse.settings import DEFAULTS, migrate, normalize

TOKEN = "geheim-1234567890"


async def test_get_defaults(hass, ws):
    res = (await ws("nova/settings/get"))["result"]
    assert res["allgemein"] == {"theme": None, "animationen": "normal", "schriftgroesse": "normal", "hintergrund": "keiner"}
    assert res["module"] == {"theme": True, "notes": True, "shopping": True, "recipes": True}
    assert res["rezepte"] == {"buch_variante": "old", "standard_portionen": 2}
    assert res["mealie"] == {"url": None, "token_gesetzt": False}
    assert (await ws("nova/info"))["result"]["settings"] is True


async def test_set_values_and_sections(hass, ws):
    res = await ws("nova/settings/set", settings={"allgemein": {"schriftgroesse": "gross"}, "rezepte": {"standard_portionen": "4"}})
    assert res["success"]
    assert res["result"]["allgemein"]["schriftgroesse"] == "gross" and res["result"]["allgemein"]["animationen"] == "normal"
    assert res["result"]["rezepte"] == {"buch_variante": "old", "standard_portionen": 4}
    # ganzer Bereich
    notizen = {"standard_schriftgroesse": "klein", "kompakt": True, "todo_entity": None}
    assert (await ws("nova/settings/set", settings={"notizen": notizen}))["result"]["notizen"] == notizen


@pytest.mark.parametrize("bad", [
    {"allgemein": {"animationen": "wild"}},
    {"allgemein": {"theme": "pink"}},
    {"allgemein": {"farbe": "rot"}},
    {"unbekannt": {}},
    {"rezepte": {"standard_portionen": 0}},
    {"rezepte": {"buch_variante": "comic"}},
    {"einkauf": {"todo_entity": "light.kueche"}},
    {"einkauf": {"standard_geschaeft": "gibtsnicht"}},
    {"mealie": {"url": "ftp://mealie.local"}},
    {"module": {"notes": "ja"}},
    {},
])
async def test_set_invalid(hass, ws, bad):
    before = (await ws("nova/settings/get"))["result"]
    res = await ws("nova/settings/set", settings={**bad, "notizen": {"kompakt": True}} if bad else bad)
    assert not res["success"] and res["error"]["code"] == "invalid"
    # nichts gespeichert, auch nicht der gültige Teil
    assert (await ws("nova/settings/get"))["result"] == before


async def test_invalid_names_field(hass, ws):
    res = await ws("nova/settings/set", settings={"allgemein": {"animationen": "wild"}})
    assert "allgemein.animationen" in res["error"]["message"]


async def test_standard_geschaeft(hass, ws):
    data = hass.data[DOMAIN]
    store = (await ws("nova/shopping/store_save", store={"name": "Lidl"}))["result"]["store"]
    assert (await ws("nova/settings/set", settings={"einkauf": {"standard_geschaeft": store["id"]}}))["success"]
    await ws("nova/shopping/store_delete", store_id=store["id"])
    assert data.settings["einkauf"]["standard_geschaeft"] is None


async def test_subscribe_event_order(hass, hass_ws_client, nova):
    sub = await hass_ws_client(hass)
    await sub.send_json({"id": 1, "type": "nova/settings/subscribe"})
    assert (await sub.receive_json())["success"]
    await sub.receive_json()
    other = await hass_ws_client(hass)
    await other.send_json({"id": 1, "type": "nova/settings/set", "settings": {"mealie": {"url": "http://mealie.local:9000/", "token": TOKEN}}})
    assert (await other.receive_json())["success"]
    ev = (await sub.receive_json())["event"]
    assert ev["mealie"] == {"url": "http://mealie.local:9000", "token_gesetzt": True}
    assert TOKEN not in json.dumps(ev)
    # gleiche Werte noch mal → kein neues Event
    await other.send_json({"id": 2, "type": "nova/settings/set", "settings": {"mealie": {"url": "http://mealie.local:9000"}}})
    assert (await other.receive_json())["success"]
    await other.send_json({"id": 3, "type": "nova/settings/set", "settings": {"rezepte": {"buch_variante": "fantasy"}}})
    assert (await other.receive_json())["success"]
    assert (await sub.receive_json())["event"]["rezepte"]["buch_variante"] == "fantasy"


async def test_token_never_leaves(hass, ws):
    res = await ws("nova/settings/set", settings={"mealie": {"url": "https://mealie.example", "token": TOKEN}})
    assert TOKEN not in json.dumps(res)
    assert TOKEN not in json.dumps(await ws("nova/settings/get"))
    data = hass.data[DOMAIN]
    assert data.secret("mealie", "token") == TOKEN
    # nur URL ändern lässt das Token stehen
    await ws("nova/settings/set", settings={"mealie": {"url": "https://mealie2.example"}})
    assert data.secret("mealie", "token") == TOKEN
    # leerer Text löscht
    res = await ws("nova/settings/set", settings={"mealie": {"token": ""}})
    assert res["result"]["mealie"]["token_gesetzt"] is False and data.secret("mealie", "token") is None


async def test_reset(hass, ws):
    data = hass.data[DOMAIN]
    await ws("nova/settings/set", settings={
        "allgemein": {"animationen": "aus"}, "notizen": {"kompakt": True}, "mealie": {"url": "http://m.local", "token": TOKEN},
    })
    res = await ws("nova/settings/reset", bereich="notizen")
    assert res["result"]["notizen"] == DEFAULTS["notizen"] and res["result"]["allgemein"]["animationen"] == "aus"
    await ws("nova/settings/reset", bereich="mealie")
    assert data.secret("mealie", "token") is None
    assert not (await ws("nova/settings/reset", bereich="quatsch"))["success"]
    await ws("nova/settings/reset")
    assert data.settings == DEFAULTS


async def test_rights(hass, nova, hass_ws_client, hass_read_only_access_token):
    user = await hass_ws_client(hass, hass_read_only_access_token)
    await user.send_json({"id": 1, "type": "nova/settings/get"})
    assert (await user.receive_json())["success"]
    for n, (t, extra) in enumerate([("nova/settings/set", {"settings": {"notizen": {"kompakt": True}}}), ("nova/settings/reset", {})], 2):
        await user.send_json({"id": n, "type": t, **extra})
        msg = await user.receive_json()
        assert not msg["success"] and msg["error"]["code"] == "unauthorized"
    # Themes Schalter: Theme darf jeder umstellen
    await user.send_json({"id": 9, "type": "nova/theme/set", "theme": "hell"})
    assert (await user.receive_json())["success"]
    assert hass.data[DOMAIN].settings["allgemein"]["theme"] == "hell"


async def test_theme_alias(hass, hass_ws_client, nova):
    """Alte Theme-Befehle lesen/schreiben allgemein.theme – beide Abos bekommen die Änderung sofort."""
    sub = await hass_ws_client(hass)
    await sub.send_json({"id": 1, "type": "nova/theme/subscribe"})
    await sub.send_json({"id": 2, "type": "nova/settings/subscribe"})
    got = [await sub.receive_json() for _ in range(4)]
    assert {m["id"] for m in got} == {1, 2}
    other = await hass_ws_client(hass)
    await other.send_json({"id": 1, "type": "nova/settings/set", "settings": {"allgemein": {"theme": "midnight"}}})
    assert (await other.receive_json())["success"]
    ev = {m["id"]: m["event"] for m in [await sub.receive_json(), await sub.receive_json()]}
    assert ev[1]["theme"] == "midnight" and ev[2]["allgemein"]["theme"] == "midnight"
    await other.send_json({"id": 2, "type": "nova/theme/set", "theme": "velvet"})
    assert (await other.receive_json())["success"]
    ev = {m["id"]: m["event"] for m in [await sub.receive_json(), await sub.receive_json()]}
    assert ev[1]["theme"] == "velvet" and ev[2]["allgemein"]["theme"] == "velvet"


async def test_modules_live(hass, ws):
    data = hass.data[DOMAIN]
    await ws("nova/settings/set", settings={"module": {"shopping": False}})
    await hass.async_block_till_done()
    assert (await ws("nova/info"))["result"][CONF_MODULES] == ["theme", "notes", "recipes"]
    assert (await ws("nova/shopping/item_save", item={"name": "Milch"}))["error"]["code"] == "module_disabled"
    assert data.on_shop_change is None  # todo-Abgleich gestoppt
    await ws("nova/settings/set", settings={"module": {"shopping": True}})
    await hass.async_block_till_done()
    assert (await ws("nova/shopping/item_save", item={"name": "Milch"}))["success"]
    assert data.on_shop_change is not None


async def test_set_sync_alias(hass, ws):
    assert (await ws("nova/shopping/set_sync", entity_id="todo.einkauf"))["success"]
    assert (await ws("nova/settings/get"))["result"]["einkauf"]["todo_entity"] == "todo.einkauf"
    await ws("nova/settings/set", settings={"einkauf": {"todo_entity": None}})
    data = hass.data[DOMAIN]
    assert data.shop_view()["sync_entity"] is None and data.shop["sync"]["entity_id"] is None


async def test_migration_from_old_data(hass, hass_storage):
    """Erster Start mit Einstellungen: Theme, Module und todo-Liste werden übernommen, nova.theme verschwindet."""
    hass_storage["nova.theme"] = {"version": 1, "key": "nova.theme", "data": {"theme": "velvet"}}
    hass_storage["nova.shopping"] = {"version": 1, "key": "nova.shopping", "data": {
        "items": [], "stores": [], "history": {}, "sync": {"entity_id": "todo.einkauf", "snap": {"u1": ["Milch", "needs_action"]}, "remove": []}}}
    entry = MockConfigEntry(domain=DOMAIN, data={}, options={CONF_MODULES: ["theme", "shopping"]})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    data = hass.data[DOMAIN]
    assert data.settings["allgemein"]["theme"] == "velvet"
    assert data.settings["module"] == {"theme": True, "notes": False, "shopping": True, "recipes": False}
    assert data.settings["einkauf"]["todo_entity"] == "todo.einkauf"
    assert data.shop["sync"]["snap"] == {"u1": ["Milch", "needs_action"]}  # gleiche Liste → Zuordnung bleibt
    assert "nova.theme" not in hass_storage
    assert hass_storage["nova.settings"]["version"] == 1 and hass_storage["nova.settings"]["data"]["allgemein"]["theme"] == "velvet"


async def test_load_repairs_stored_settings(hass, hass_storage):
    """Gespeicherter Stand mit kaputten/unbekannten Werten: Standard statt Absturz, Optionen zählen nicht mehr."""
    hass_storage["nova.settings"] = {"version": 1, "minor_version": 1, "key": "nova.settings", "data": {
        "allgemein": {"theme": "pink", "schriftgroesse": "klein", "alt": 1},
        "module": {"recipes": False},
        "weg": {"x": 1},
    }}
    entry = MockConfigEntry(domain=DOMAIN, data={}, options={CONF_MODULES: ["theme"]})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    s = hass.data[DOMAIN].settings
    assert s["allgemein"] == {"theme": None, "animationen": "normal", "schriftgroesse": "klein", "hintergrund": "keiner"}
    assert s["module"] == {"theme": True, "notes": True, "shopping": True, "recipes": False}
    assert "weg" not in s


async def test_migrate_func():
    data = {"allgemein": {"theme": "hell"}}
    # 1.1 → 1.2: Hintergrund und todo-Liste der Notizen kommen dazu
    assert await migrate(1, 1, data) == {"allgemein": {"theme": "hell", "hintergrund": "keiner"}, "notizen": {"todo_entity": None}}
    assert data == {"allgemein": {"theme": "hell"}}
    assert await migrate(1, 2, data) == data
    with pytest.raises(NotImplementedError):
        await migrate(2, 1, data)
    assert normalize(None) == DEFAULTS


async def test_options_flow_writes_settings(hass, ws, nova):
    await ws("nova/settings/set", settings={"module": {"notes": False}})
    res = await hass.config_entries.options.async_init(nova.entry_id)
    # Options-Dialog zeigt den Stand der Einstellungen
    assert res["data_schema"]({})[CONF_MODULES] == ["theme", "shopping", "recipes"]
    await hass.config_entries.options.async_configure(res["flow_id"], {CONF_MODULES: ["theme", "notes", "shopping", "recipes"]})
    await hass.async_block_till_done()
    assert hass.data[DOMAIN].settings["module"]["notes"] is True


async def test_panel(hass, hass_client, nova):
    """Panel „Nova“ in der Seitenleiste (nur Admins), Datei kommt unter /nova/static."""
    panels = hass.data["frontend_panels"]
    assert "nova" in panels
    panel = panels["nova"]
    assert panel.require_admin and panel.sidebar_title == "Nova Homeverse"
    assert panel.config["_panel_custom"]["name"] == "nova-settings-panel"
    url = panel.config["_panel_custom"]["module_url"]
    client = await hass_client()
    res = await client.get(url)
    assert res.status == 200 and "nova-settings-panel" in await res.text()
    # Entladen nimmt das Panel wieder raus
    assert await hass.config_entries.async_unload(nova.entry_id)
    assert "nova" not in hass.data["frontend_panels"]


async def test_hintergrund(hass, ws, nova):
    res = await ws("nova/settings/set", settings={"allgemein": {"hintergrund": "passend"}})
    assert res["result"]["allgemein"]["hintergrund"] == "passend"
    assert not (await ws("nova/settings/set", settings={"allgemein": {"hintergrund": "pink"}}))["success"]
    res = await ws("nova/settings/set", settings={"notizen": {"todo_entity": "light.x"}})
    assert not res["success"]


async def test_todo_lists_distinct(hass, ws, nova):
    assert (await ws("nova/settings/set", settings={"einkauf": {"todo_entity": "todo.a"}}))["success"]
    res = await ws("nova/settings/set", settings={"notizen": {"todo_entity": "todo.a"}})
    assert not res["success"] and "Einkauf" in res["error"]["message"]
    assert (await ws("nova/info"))["result"]["version"]
