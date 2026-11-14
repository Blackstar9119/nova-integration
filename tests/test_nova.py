"""Tests von Nova Homeverse: Einrichtung, Module, WebSocket-API, Bereinigung, Bilder, todo-Abgleich."""

import base64
from datetime import timedelta

from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_fire_time_changed

from custom_components.nova_homeverse.const import CONF_MODULES, DOMAIN
from custom_components.nova_homeverse.sanitize import clean_html
from custom_components.nova_homeverse.todo_sync import fmt, parse

WEBP = b"RIFF\x1a\x00\x00\x00WEBPVP8L\x0d\x00\x00\x00/\x00\x00\x00\x10\x07\x10\x11\x11\x88\x88\xfe\x07\x00"


async def test_config_flow(hass):
    res = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    assert res["type"] == "form"
    res = await hass.config_entries.flow.async_configure(res["flow_id"], {})
    assert res["type"] == "create_entry"
    assert set(res["options"][CONF_MODULES]) == {"theme", "notes", "shopping", "recipes"}
    res = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    assert res["reason"] == "single_instance_allowed"


async def test_options_disable_module(hass, nova, ws):
    assert (await ws("nova_homeverse/info"))["result"][CONF_MODULES] == ["theme", "notes", "shopping", "recipes"]
    res = await hass.config_entries.options.async_init(nova.entry_id)
    await hass.config_entries.options.async_configure(res["flow_id"], {CONF_MODULES: ["theme", "notes"]})
    await hass.async_block_till_done()
    assert (await ws("nova_homeverse/info"))["result"][CONF_MODULES] == ["theme", "notes"]
    msg = await ws("nova_homeverse/shopping/item_save", item={"name": "Milch"})
    assert not msg["success"] and msg["error"]["code"] == "module_disabled"
    assert (await ws("nova_homeverse/notes/save", note={"title": "a"}))["success"]


def test_sanitize():
    dirty = '<b>ok</b><script>alert(1)</script><img src=x onerror=alert(1)><a href="javascript:1">x</a><span class="fs-l bad" style="x" onclick="y">g</span>'
    assert clean_html(dirty) == '<b>ok</b>x<span class="fs-l">g</span>'
    assert clean_html('<ul class="check"><li class="done">a<li>b') == '<ul class="check"><li class="done">a</li><li>b</li></ul>'
    assert clean_html("1 < 2 &amp; <i>x") == "1 &lt; 2 &amp; <i>x</i>"


def test_parse_fmt():
    assert parse("Milch") == {"name": "Milch"}
    assert parse("Milch (2 l)") == {"name": "Milch", "qty": 2.0, "unit": "l"}
    assert parse("3 Äpfel") == {"name": "Äpfel", "qty": 3.0, "unit": "Stk"}
    assert parse("2 große Äpfel")["name"] == "große Äpfel"
    assert fmt({"name": "Milch", "qty": 1, "unit": "Stk"}) == "Milch"
    assert fmt({"name": "Mehl", "qty": 500, "unit": "g"}) == "Mehl (500 g)"


async def test_theme(hass, ws):
    assert (await ws("nova_homeverse/theme/set", theme="velvet"))["success"]
    assert not (await ws("nova_homeverse/theme/set", theme="pink"))["success"]
    await ws.client.send_json({"id": 900, "type": "nova_homeverse/theme/subscribe"})
    assert (await ws.client.receive_json())["success"]
    assert (await ws.client.receive_json())["event"]["theme"] == "velvet"


async def test_theme_from_helper(hass):
    hass.states.async_set("input_select.nova_theme", "Nova Midnight")
    entry = MockConfigEntry(domain=DOMAIN, data={}, options={})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    assert hass.data[DOMAIN].theme_view()["theme"] == "midnight"


async def test_notes(hass, ws):
    note = (await ws("nova_homeverse/notes/save", note={"title": " Hallo ", "body": "<b>x</b><script>1</script>", "pinned": True}))["result"]["note"]
    assert note["title"] == "Hallo" and note["body"] == "<b>x</b>" and note["pinned"]
    upd = (await ws("nova_homeverse/notes/save", note={"id": note["id"], "pinned": False}))["result"]["note"]
    assert upd["title"] == "Hallo" and not upd["pinned"] and upd["updated"] >= note["updated"]
    assert len(hass.data[DOMAIN].notes) == 1
    await ws("nova_homeverse/notes/delete", note_id=note["id"])
    assert hass.data[DOMAIN].notes == []


async def test_shopping_history_and_stores(hass, ws):
    data = hass.data[DOMAIN]
    store = (await ws("nova_homeverse/shopping/store_save", store={"name": "Lidl", "icon": "mdi:cart"}))["result"]["store"]
    it = (await ws("nova_homeverse/shopping/item_save", item={"name": "Milch", "qty": 2, "unit": "l", "store": store["id"], "icon": "mdi:cup-water", "note": "<i>fettarm</i><iframe>"}))["result"]["item"]
    assert it["qty"] == 2 and it["unit"] == "l" and it["note"] == "<i>fettarm</i>"
    assert not (await ws("nova_homeverse/shopping/item_save", item={"name": "  "}))["success"]
    await ws("nova_homeverse/shopping/item_save", item={"id": it["id"], "done": True})
    assert data.shop_view()["history"][0]["name"] == "Milch"
    assert (await ws("nova_homeverse/shopping/clear_done"))["result"]["removed"] == 1
    # Neuer Artikel mit gleichem Namen übernimmt Geschäft, Icon und Einheit aus dem Verlauf
    again = (await ws("nova_homeverse/shopping/item_save", item={"name": "milch"}))["result"]["item"]
    assert again["store"] == store["id"] and again["icon"] == "mdi:cup-water" and again["unit"] == "l"
    await ws("nova_homeverse/shopping/store_delete", store_id=store["id"])
    assert data.item(again["id"])["store"] is None
    bad = (await ws("nova_homeverse/shopping/item_save", item={"id": again["id"], "icon": "javascript:alert(1)//", "unit": "Fass"}))["result"]["item"]
    assert bad["icon"] is None and bad["unit"] == "Stk"


async def test_image_upload(hass, ws, tmp_path):
    data = hass.data[DOMAIN]
    data.image_root = tmp_path
    (tmp_path / "shopping").mkdir()
    res = await ws("nova_homeverse/image/upload", module="shopping", data="data:image/webp;base64," + base64.b64encode(WEBP).decode())
    name = res["result"]["image"]
    assert res["result"]["url"] == f"/local/nova_homeverse/shopping/{name}" and (tmp_path / "shopping" / name).read_bytes() == WEBP
    assert not (await ws("nova_homeverse/image/upload", module="shopping", data=base64.b64encode(b"<svg onload=1>").decode()))["success"]
    assert not (await ws("nova_homeverse/image/upload", module="notes", data="x"))["success"]
    it = (await ws("nova_homeverse/shopping/item_save", item={"name": "Brot", "image": name}))["result"]["item"]
    assert it["image"] == name
    assert (await ws("nova_homeverse/shopping/item_save", item={"id": it["id"], "image": "../../secrets.yaml"}))["result"]["item"]["image"] is None


async def test_recipes(hass, ws):
    data = hass.data[DOMAIN]
    rec = (await ws("nova_homeverse/recipes/save", recipe={
        "title": "Pfannkuchen", "servings": 2, "time": 20, "tags": ["süß", "süß", "schnell"],
        "ingredients": [{"name": "Mehl", "qty": 250, "unit": "g"}, {"name": "Eier", "qty": 2, "unit": "Stk"}, {"name": "Salz", "qty": 1, "unit": "Prise"}, {"name": ""}],
        "steps": "<ul><li>rühren</li></ul><style>x</style>",
    }))["result"]["recipe"]
    assert rec["tags"] == ["süß", "schnell"] and len(rec["ingredients"]) == 3 and rec["steps"] == "<ul><li>rühren</li></ul>"
    await ws("nova_homeverse/shopping/item_save", item={"name": "Mehl", "qty": 100, "unit": "g"})
    assert (await ws("nova_homeverse/recipes/to_shopping", recipe_id=rec["id"], servings=4))["result"]["added"] == 3
    items = {i["name"]: i for i in data.shop["items"]}
    assert items["Mehl"]["qty"] == 600 and items["Eier"]["qty"] == 4 and items["Salz"]["qty"] == 1
    # Küchen-Einheiten wie Tasse/Cup bleiben, unbekannte fallen weg
    cup = (await ws("nova_homeverse/recipes/save", recipe={"title": "Muffins", "ingredients": [{"name": "Mehl", "qty": 2, "unit": "Tasse"}, {"name": "Zucker", "qty": 1, "unit": "Cup"}, {"name": "Öl", "qty": 1, "unit": "Fass"}]}))["result"]["recipe"]
    assert [i["unit"] for i in cup["ingredients"]] == ["Tasse", "Cup", ""]
    await ws("nova_homeverse/recipes/delete", recipe_id=cup["id"])
    assert (await ws("nova_homeverse/recipes/to_shopping", recipe_id=rec["id"], only=[1]))["result"]["added"] == 1
    assert {i["name"]: i for i in data.shop["items"]}["Eier"]["qty"] == 6
    await ws("nova_homeverse/recipes/delete", recipe_id=rec["id"])
    assert data.recipes == []


async def _settle(hass):
    for _ in range(3):
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=5))
        await hass.async_block_till_done(wait_background_tasks=True)


async def _todo(hass, eid):
    res = await hass.services.async_call("todo", "get_items", {"entity_id": eid}, blocking=True, return_response=True)
    return {t["summary"]: t for t in res[eid]["items"]}


async def test_todo_sync(hass, ws, tmp_path):
    hass.config.config_dir = str(tmp_path)
    (tmp_path / ".storage").mkdir()
    todo = MockConfigEntry(domain="local_todo", data={"todo_list_name": "Einkauf", "storage_key": "einkauf"})
    todo.add_to_hass(hass)
    assert await hass.config_entries.async_setup(todo.entry_id)
    await hass.async_block_till_done()
    eid = "todo.einkauf"
    data = hass.data[DOMAIN]
    await hass.services.async_call("todo", "add_item", {"entity_id": eid, "item": "Butter"}, blocking=True)
    await ws("nova_homeverse/shopping/item_save", item={"name": "Milch", "qty": 2, "unit": "l"})
    assert (await ws("nova_homeverse/shopping/set_sync", entity_id=eid))["success"]
    await _settle(hass)
    # beide Richtungen zusammengeführt
    assert set(await _todo(hass, eid)) == {"Butter", "Milch (2 l)"}
    assert {i["name"] for i in data.shop["items"]} == {"Butter", "Milch"}
    # Assist setzt etwas auf die Liste
    await hass.services.async_call("todo", "add_item", {"entity_id": eid, "item": "3 Äpfel"}, blocking=True)
    await _settle(hass)
    apfel = next(i for i in data.shop["items"] if i["name"] == "Äpfel")
    assert apfel["qty"] == 3 and "Äpfel (3 Stk)" in await _todo(hass, eid)
    # Abhaken in Nova → todo erledigt
    await ws("nova_homeverse/shopping/item_save", item={"id": apfel["id"], "done": True})
    await _settle(hass)
    assert (await _todo(hass, eid))["Äpfel (3 Stk)"]["status"] == "completed"
    # Abhaken in der todo-Liste → Nova erledigt
    await hass.services.async_call("todo", "update_item", {"entity_id": eid, "item": "Butter", "status": "completed"}, blocking=True)
    await _settle(hass)
    assert next(i for i in data.shop["items"] if i["name"] == "Butter")["done"]
    # Löschen in Nova → todo-Eintrag weg; Löschen in todo → Nova-Artikel weg
    milch = next(i for i in data.shop["items"] if i["name"] == "Milch")
    await ws("nova_homeverse/shopping/item_delete", item_id=milch["id"])
    await _settle(hass)
    assert "Milch (2 l)" not in await _todo(hass, eid)
    await hass.services.async_call("todo", "remove_item", {"entity_id": eid, "item": ["Butter"]}, blocking=True)
    await _settle(hass)
    assert {i["name"] for i in data.shop["items"]} == {"Äpfel"}
    # „Erledigte löschen“ räumt auch die todo-Liste auf
    await ws("nova_homeverse/shopping/clear_done")
    await _settle(hass)
    assert await _todo(hass, eid) == {} and data.shop["items"] == []


async def test_schriften(hass, hass_client, nova):
    """Die Schriften des Rezeptbuchs kommen unter /nova_homeverse/static/fonts von Home Assistant selbst."""
    client = await hass_client()
    res = await client.get("/nova_homeverse/static/fonts/nova-hand-400.woff2")
    assert res.status == 200
    assert (await res.read())[:4] == b"wOF2"


async def test_notes_todo_sync(hass, ws, tmp_path):
    """Notizen ↔ todo-Liste: Nova → todo, Assist legt Notiz an, Ändern und Löschen in beide Richtungen."""
    hass.config.config_dir = str(tmp_path)
    (tmp_path / ".storage").mkdir()
    todo = MockConfigEntry(domain="local_todo", data={"todo_list_name": "Notizen", "storage_key": "notizen"})
    todo.add_to_hass(hass)
    assert await hass.config_entries.async_setup(todo.entry_id)
    await hass.async_block_till_done()
    eid = "todo.notizen"
    data = hass.data[DOMAIN]
    await ws("nova_homeverse/notes/save", note={"title": "Urlaub", "body": "<p>Pässe</p><ul><li>Koffer</li></ul>"})
    await ws("nova_homeverse/notes/save", note={"title": "", "body": "<p>Zahnarzt anrufen</p>"})
    assert (await ws("nova_homeverse/settings/set", settings={"notizen": {"todo_entity": eid}}))["success"]
    await _settle(hass)
    items = await _todo(hass, eid)
    assert set(items) == {"Urlaub", "Zahnarzt anrufen"}
    assert items["Urlaub"]["description"] == "Pässe\n• Koffer"
    # Assist legt etwas an → neue Notiz
    await hass.services.async_call("todo", "add_item", {"entity_id": eid, "item": "Geschenk Oma", "description": "Buch\nBlumen"}, blocking=True)
    await _settle(hass)
    oma = next(n for n in data.notes if n["title"] == "Geschenk Oma")
    assert oma["body"] == "<p>Buch</p><p>Blumen</p>"
    # Umbenennen in der todo-Liste → Titel der Notiz
    await hass.services.async_call("todo", "update_item", {"entity_id": eid, "item": "Urlaub", "rename": "Urlaub 2027"}, blocking=True)
    await _settle(hass)
    assert any(n["title"] == "Urlaub 2027" for n in data.notes)
    # Löschen in Nova → todo-Eintrag weg; Löschen in todo → Notiz weg
    await ws("nova_homeverse/notes/delete", note_id=oma["id"])
    await _settle(hass)
    assert "Geschenk Oma" not in await _todo(hass, eid)
    await hass.services.async_call("todo", "remove_item", {"entity_id": eid, "item": ["Zahnarzt anrufen"]}, blocking=True)
    await _settle(hass)
    assert [n["title"] for n in data.notes] == ["Urlaub 2027"]
    # Liste abwählen → Zuordnung vergessen
    await ws("nova_homeverse/settings/set", settings={"notizen": {"todo_entity": None}})
    assert data.notes[0]["todo_uid"] is None


def test_plain_text():
    from custom_components.nova_homeverse.sanitize import from_plain, to_plain

    assert to_plain("<p>a <b>b</b></p><p>c<br>d</p>") == "a b\nc\nd"
    assert from_plain("x < y\n\nz") == "<p>x &lt; y</p><p><br></p><p>z</p>"


async def test_config_flow_old_nova(hass):
    """Ist die alte Integration „Nova“ noch eingerichtet, bricht die Einrichtung mit Hinweis ab."""
    MockConfigEntry(domain="nova", title="Nova", data={}).add_to_hass(hass)
    res = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    assert res["type"] == "abort" and res["reason"] == "old_nova_installed"


async def test_setup_refuses_with_old_nova_loaded(hass):
    """Läuft die alte Integration „Nova“ noch, startet Nova Homeverse nicht und meldet es unter Reparaturen."""
    from homeassistant.config_entries import ConfigEntryState
    from homeassistant.helpers import issue_registry as ir

    hass.config.components.add("nova")
    entry = MockConfigEntry(domain=DOMAIN, data={}, options={CONF_MODULES: ["theme"]})
    entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.SETUP_ERROR
    assert ir.async_get(hass).async_get_issue(DOMAIN, "old_nova_installed") is not None
    assert DOMAIN not in hass.data

    hass.config.components.remove("nova")
    assert await hass.config_entries.async_reload(entry.entry_id)
    assert entry.state is ConfigEntryState.LOADED
    assert ir.async_get(hass).async_get_issue(DOMAIN, "old_nova_installed") is None
