"""Einkaufsliste mit einer todo-Entität abgleichen (z. B. todo.shopping_list), damit Assist weiter funktioniert.

Nova ist führend, die todo-Liste ein Spiegel. Je Artikel merkt sich Nova die uid des todo-Eintrags und, was zuletzt
abgeglichen wurde (snap: uid → [Text, Status]). Weicht die todo-Liste davon ab, hat sie jemand anders geändert
(Assist, HA-Oberfläche) → Nova übernimmt. Danach wird die todo-Liste auf den Stand von Nova gebracht.

Text im todo-Eintrag: „Milch“ bzw. mit Menge „Milch (2 l)“. Neue Einträge von außen werden genauso gelesen.
"""

from __future__ import annotations

import asyncio
import logging
import re
from datetime import timedelta

from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.event import async_call_later, async_track_state_change_event, async_track_time_interval

from .const import UNITS
from .sanitize import from_plain, to_plain
from .storage import NovaData, hkey

_LOGGER = logging.getLogger(__name__)
DELAY = 1.0
POLL = timedelta(minutes=5)
OPEN, DONE = "needs_action", "completed"
QTY_RE = re.compile(r"^(?P<name>.+?)\s*\((?P<qty>\d+(?:[.,]\d+)?)\s*(?P<unit>[A-Za-zäöü]+)?\)\s*$")
LEAD_RE = re.compile(r"^(?P<qty>\d+(?:[.,]\d+)?)\s*(?P<unit>[A-Za-zäöü]+)?\s+(?P<name>.+)$")
UNIT_ALIAS = {u.lower(): u for u in UNITS} | {"stück": "Stk", "st": "Stk", "x": "Stk", "pck": "Packung", "pkg": "Packung", "packungen": "Packung", "liter": "l", "gramm": "g"}


def fmt(it: dict) -> str:
    q, u = it.get("qty", 1), it.get("unit", "Stk")
    if q == 1 and u == "Stk":
        return it["name"]
    return f"{it['name']} ({str(q).replace('.', ',')} {u})"


def parse(text: str) -> dict:
    """„Milch (2 l)“ oder „2 l Milch“ → name/qty/unit; sonst nur der Name."""
    text = " ".join(text.split())
    for rx in (QTY_RE, LEAD_RE):
        m = rx.match(text)
        if not m:
            continue
        unit = m.group("unit")
        if unit and unit.lower() not in UNIT_ALIAS:
            if rx is LEAD_RE:  # „2 große Äpfel“: Wort gehört zum Namen
                return {"name": f"{unit} {m.group('name')}", "qty": float(m.group("qty").replace(",", ".")), "unit": "Stk"}
            continue
        return {"name": m.group("name"), "qty": float(m.group("qty").replace(",", ".")), "unit": UNIT_ALIAS.get((unit or "").lower(), "Stk")}
    return {"name": text}


class _TodoMirror:
    """Gemeinsames Gerüst: auf die todo-Liste hören, Änderungen sammeln (DELAY), dann _reconcile() unter Sperre."""

    HOOK = ""  # Name des Rückrufs in NovaData, den storage.py nach jeder Änderung aufruft
    SECTION = ""  # Bereich der Einstellungen mit todo_entity

    def __init__(self, hass: HomeAssistant, data: NovaData) -> None:
        self.hass = hass
        self.data = data
        self._lock = asyncio.Lock()
        self._timer = None
        self._unsubs: list = []
        self._entity: str | None = None
        self._entity_unsub = []

    @property
    def running(self) -> bool:
        return bool(self._unsubs)

    async def start(self) -> None:
        if self.running:
            return
        setattr(self.data, self.HOOK, self.schedule)
        self._unsubs.append(async_track_time_interval(self.hass, callback(lambda _now: self.schedule()), POLL))
        self._watch()
        self.schedule()

    @callback
    def stop(self) -> None:
        setattr(self.data, self.HOOK, None)
        if self._timer:
            self._timer()
        for u in self._unsubs + self._entity_unsub:
            u()
        self._unsubs, self._entity_unsub = [], []
        self._timer, self._entity = None, None

    @property
    def entity(self) -> str | None:
        return self.data.settings[self.SECTION]["todo_entity"]

    @callback
    def _watch(self) -> None:
        """Auf Änderungen der todo-Liste hören (Zustand = Anzahl offen; Umbenennen über das Abo der Entität)."""
        if self._entity == self.entity:
            return
        for u in self._entity_unsub:
            u()
        self._entity_unsub = []
        self._entity = eid = self.entity
        if not eid:
            return
        self._entity_unsub.append(async_track_state_change_event(self.hass, [eid], self._on_state))
        # HA-INTERN: TodoListEntity.async_subscribe_updates meldet auch Änderungen ohne neuen Zustand (Umbenennen).
        # Fehlt es, bleibt der Zustand + Abgleich alle 5 Minuten.
        try:
            comp = self.hass.data.get("todo") or self.hass.data.get("entity_components", {}).get("todo")
            ent = comp.get_entity(eid) if comp else None
            if ent and hasattr(ent, "async_subscribe_updates"):
                self._entity_unsub.append(ent.async_subscribe_updates(callback(lambda *_a: self.schedule())))
        except Exception:  # noqa: BLE001
            _LOGGER.debug("todo-Abo für %s nicht möglich", eid)

    @callback
    def _on_state(self, _event: Event) -> None:
        self.schedule()

    @callback
    def schedule(self) -> None:
        self._watch()
        if not self.entity:
            return
        if self._timer:
            self._timer()
        self._timer = async_call_later(self.hass, DELAY, self._run)

    async def _run(self, _now=None) -> None:
        self._timer = None
        async with self._lock:
            try:
                await self._reconcile()
            except HomeAssistantError as err:
                _LOGGER.warning("Abgleich mit %s fehlgeschlagen: %s", self.entity, err)

    async def _items(self, eid: str) -> list[dict]:
        res = await self.hass.services.async_call("todo", "get_items", {"entity_id": eid}, blocking=True, return_response=True)
        return (res or {}).get(eid, {}).get("items", [])

    async def _call(self, service: str, data: dict) -> None:
        await self.hass.services.async_call("todo", service, {"entity_id": self.entity, **data}, blocking=True)

    async def _reconcile(self) -> None:
        raise NotImplementedError


class TodoSync(_TodoMirror):
    """Einkaufsliste ↔ todo-Liste (einkauf.todo_entity)."""

    HOOK, SECTION = "on_shop_change", "einkauf"

    async def _reconcile(self) -> None:
        eid, data = self.entity, self.data
        if not eid or eid not in self.hass.states.async_entity_ids("todo"):
            return
        sync = data.shop["sync"]
        snap: dict = sync.setdefault("snap", {})
        todo = {t["uid"]: t for t in await self._items(eid)}
        changed = False

        # 1. In Nova gelöschte Artikel aus der todo-Liste entfernen
        remove = [u for u in sync.get("remove", []) if u in todo]
        if remove:
            await self._call("remove_item", {"item": remove})
            for u in remove:
                todo.pop(u, None)
                snap.pop(u, None)
        if sync.get("remove"):
            sync["remove"] = []
            changed = True

        # 2. Änderungen von außen übernehmen
        for it in list(data.shop["items"]):
            uid = it.get("todo_uid")
            if not uid:
                continue
            t = todo.get(uid)
            if t is None:
                if uid in snap:  # in der todo-Liste gelöscht
                    snap.pop(uid)
                    data.item_delete(it["id"], sync=False)
                    data.shop["sync"]["remove"] = [u for u in data.shop["sync"].get("remove", []) if u != uid]
                else:
                    it["todo_uid"] = None
                changed = True
                continue
            cur = [t["summary"], t["status"]]
            if uid in snap and snap[uid] != cur:
                upd = {"id": it["id"], "done": t["status"] == DONE}
                if t["summary"] != snap[uid][0]:
                    upd |= parse(t["summary"])
                data.item_save(upd, sync=False)
                changed = True

        # 3. Neue offene Einträge von außen: erst mit gleichnamigen Nova-Artikeln ohne uid verbinden, sonst neu anlegen
        mapped = {it.get("todo_uid") for it in data.shop["items"]}
        for uid, t in todo.items():
            if uid in mapped or uid in snap:
                continue
            p = parse(t["summary"])
            twin = next((it for it in data.shop["items"] if not it.get("todo_uid") and hkey(it["name"]) == hkey(p["name"])), None)
            if twin:
                twin["todo_uid"] = uid
                changed = True
            elif t["status"] == OPEN:
                it = data.item_save(p, sync=False)
                it["todo_uid"] = uid
                snap[uid] = [t["summary"], t["status"]]
                changed = True

        # 4. todo-Liste auf den Stand von Nova bringen
        added = []
        for it in data.shop["items"]:
            want = [fmt(it), DONE if it.get("done") else OPEN]
            uid = it.get("todo_uid")
            if uid and uid in todo:
                cur = [todo[uid]["summary"], todo[uid]["status"]]
                if cur != want:
                    await self._call("update_item", {"item": uid, "rename": want[0], "status": want[1]})
                snap[uid] = want
            elif not uid and not it.get("done"):
                await self._call("add_item", {"item": want[0]})
                added.append(it)
        if added:
            # uids der neuen Einträge über den Text zuordnen
            fresh = [t for t in await self._items(eid) if t["uid"] not in todo]
            for it in added:
                t = next((x for x in fresh if x["summary"] == fmt(it)), None)
                if t:
                    fresh.remove(t)
                    it["todo_uid"] = t["uid"]
                    snap[t["uid"]] = [t["summary"], t["status"]]
            changed = True

        # nicht mehr vorhandene uids vergessen
        live = {it.get("todo_uid") for it in data.shop["items"]}
        for uid in [u for u in snap if u not in live]:
            snap.pop(uid)
            changed = True
        if changed:
            data._changed("shopping", sync=False)  # noqa: SLF001


def note_summary(note: dict) -> str:
    """Titel des todo-Eintrags: Titel der Notiz, sonst die erste Textzeile."""
    title = note.get("title") or next((ln for ln in to_plain(note.get("body", "")).splitlines() if ln.strip()), "")
    return (title.strip() or "Notiz")[:200]


class NoteSync(_TodoMirror):
    """Notizen ↔ todo-Liste (notizen.todo_entity), z. B. damit Assist Notizen anlegen kann.

    Je Notiz ein todo-Eintrag: Titel = Titel der Notiz, Beschreibung = Text als Klartext. Nova ist führend.
    Von außen: neuer offener Eintrag → neue Notiz, geänderter Titel/Beschreibung → Notiz übernimmt ihn
    (Formatierung geht dabei verloren), gelöschter Eintrag → Notiz weg. Abhaken spielt keine Rolle.
    """

    HOOK, SECTION = "on_notes_change", "notizen"

    async def _reconcile(self) -> None:
        eid, data = self.entity, self.data
        if not eid or eid not in self.hass.states.async_entity_ids("todo"):
            return
        sync = data.notes_sync
        snap: dict = sync.setdefault("snap", {})
        todo = {t["uid"]: t for t in await self._items(eid)}
        changed = False

        remove = [u for u in sync.get("remove", []) if u in todo]
        if remove:
            await self._call("remove_item", {"item": remove})
            for u in remove:
                todo.pop(u, None)
                snap.pop(u, None)
        if sync.get("remove"):
            sync["remove"] = []
            changed = True

        # Änderungen von außen übernehmen
        for note in list(data.notes):
            uid = note.get("todo_uid")
            if not uid:
                continue
            t = todo.get(uid)
            if t is None:
                if uid in snap:  # in der todo-Liste gelöscht
                    snap.pop(uid)
                    data.note_delete(note["id"], sync=False)
                else:
                    note["todo_uid"] = None
                changed = True
                continue
            cur = [t["summary"], t.get("description") or ""]
            if uid in snap and snap[uid] != cur:
                upd = {"id": note["id"]}
                if cur[0] != snap[uid][0]:
                    upd["title"] = cur[0]
                if cur[1] != snap[uid][1]:
                    upd["body"] = from_plain(cur[1])
                data.note_save(upd, sync=False)
                changed = True

        # Neue offene Einträge von außen → neue Notiz
        mapped = {n.get("todo_uid") for n in data.notes}
        for uid, t in todo.items():
            if uid in mapped or uid in snap or t["status"] != OPEN:
                continue
            note = data.note_save({"title": t["summary"], "body": from_plain(t.get("description") or "")}, sync=False)
            note["todo_uid"] = uid
            snap[uid] = [t["summary"], t.get("description") or ""]
            changed = True

        # todo-Liste auf den Stand von Nova bringen
        added = []
        for note in data.notes:
            want = [note_summary(note), to_plain(note.get("body", ""))]
            uid = note.get("todo_uid")
            if uid and uid in todo:
                if [todo[uid]["summary"], todo[uid].get("description") or ""] != want:
                    await self._call("update_item", {"item": uid, "rename": want[0], "description": want[1]})
                snap[uid] = want
            elif not uid:
                await self._call("add_item", {"item": want[0], "description": want[1]})
                added.append((note, want))
        if added:
            fresh = [t for t in await self._items(eid) if t["uid"] not in todo]
            for note, want in added:
                t = next((x for x in fresh if x["summary"] == want[0]), None)
                if t:
                    fresh.remove(t)
                    note["todo_uid"] = t["uid"]
                    snap[t["uid"]] = [t["summary"], t.get("description") or ""]
            changed = True

        live = {n.get("todo_uid") for n in data.notes}
        for uid in [u for u in snap if u not in live]:
            snap.pop(uid)
            changed = True
        if changed:
            data._changed("notes", sync=False)  # noqa: SLF001
