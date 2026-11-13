"""Daten der Nova-Integration: Theme, Notizen, Einkauf, Rezeptbuch und Bilder.

Gespeichert wird je Modul mit dem Store von Home Assistant (.storage/nova.<modul>). Bilder liegen verkleinert unter
/config/www/nova/<modul>/. Jede Änderung geht an alle Abonnenten (Karten auf allen Geräten).
"""

from __future__ import annotations

import base64
import re
import secrets
import time
import uuid
from collections.abc import Callable
from pathlib import Path

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.storage import Store

from .const import (
    HISTORY_MAX,
    IMAGE_DIR,
    IMAGE_MAX_BYTES,
    IMAGE_MODULES,
    IMAGE_URL,
    MODULES,
    RECIPE_UNITS,
    SAVE_DELAY,
    STORAGE_VERSION,
    THEME_HELPER,
    THEMES,
    UNITS,
)
from .recipe_import import clean_url
from .sanitize import clean_html, clean_text

ICON_RE = re.compile(r"^[a-z0-9-]{1,32}:[a-z0-9-]{1,64}$")
IMAGE_RE = re.compile(r"^[a-f0-9]{32}\.(webp|jpg|png)$")
# Erkennung über die ersten Bytes, nicht über Angaben des Browsers
MAGIC = ((b"RIFF", "webp"), (b"\xff\xd8\xff", "jpg"), (b"\x89PNG\r\n\x1a\n", "png"))


class ModuleDisabled(Exception):
    """Das Modul ist in den Optionen abgeschaltet."""


def _now() -> float:
    return round(time.time(), 3)


def _id() -> str:
    return uuid.uuid4().hex


def _icon(v) -> str | None:
    return v if isinstance(v, str) and ICON_RE.match(v) else None


def _image(v) -> str | None:
    return v if isinstance(v, str) and IMAGE_RE.match(v) else None


def _qty(v, default: float = 1) -> float:
    try:
        q = round(float(v), 3)
    except (TypeError, ValueError):
        return default
    q = min(max(q, 0), 99999)
    return int(q) if q == int(q) else q


def hkey(name: str) -> str:
    """Schlüssel im Verlauf: Name klein, ohne doppelte Leerzeichen."""
    return " ".join(name.lower().split())


class NovaData:
    """Alle Daten + Abonnenten."""

    def __init__(self, hass: HomeAssistant, enabled: set[str]) -> None:
        self.hass = hass
        self.enabled = enabled
        self._stores = {m: Store(hass, STORAGE_VERSION, f"nova.{m}") for m in MODULES}
        self.theme: dict = {"theme": None}
        self.notes: list[dict] = []
        self.shop: dict = {}
        self.recipes: list[dict] = []
        self.image_root = Path(hass.config.path(IMAGE_DIR))
        self._listeners: dict[str, set[Callable[[], None]]] = {m: set() for m in MODULES}
        # wird von der todo-Synchronisation gesetzt: nach jeder Änderung an der Einkaufsliste aufrufen
        self.on_shop_change: Callable[[], None] | None = None

    async def async_load(self) -> None:
        load = {m: await self._stores[m].async_load() or {} for m in MODULES}
        self.theme = {"theme": load["theme"].get("theme")}
        if self.theme["theme"] not in THEMES:
            # Erster Start: Wert des bisherigen Helfers input_select.nova_theme übernehmen
            st = self.hass.states.get(THEME_HELPER)
            key = st.state.lower().removeprefix("nova ").strip() if st else None
            self.theme["theme"] = key if key in THEMES else None
        self.notes = load["notes"].get("notes", [])
        shop = load["shopping"]
        self.shop = {
            "items": shop.get("items", []),
            "stores": shop.get("stores", []),
            "history": shop.get("history", {}),
            "sync": shop.get("sync", {"entity_id": None, "snap": {}, "remove": []}),
        }
        self.recipes = load["recipes"].get("recipes", [])

        def mkdirs() -> None:
            for m in IMAGE_MODULES:
                (self.image_root / m).mkdir(parents=True, exist_ok=True)

        await self.hass.async_add_executor_job(mkdirs)

    def require(self, module: str) -> None:
        if module not in self.enabled:
            raise ModuleDisabled(module)

    def _dump(self, module: str) -> dict:
        return {"theme": self.theme, "notes": {"notes": self.notes}, "shopping": self.shop, "recipes": {"recipes": self.recipes}}[module]

    # ---------- Abonnenten ----------
    @callback
    def listen(self, kind: str, fn: Callable[[], None]) -> Callable[[], None]:
        self._listeners[kind].add(fn)
        return lambda: self._listeners[kind].discard(fn)

    @callback
    def _changed(self, kind: str, sync: bool = True) -> None:
        self._stores[kind].async_delay_save(lambda: self._dump(kind), SAVE_DELAY)
        if kind == "shopping" and sync and self.on_shop_change:
            self.on_shop_change()
        for fn in list(self._listeners[kind]):
            fn()

    async def async_flush(self) -> None:
        """Ausstehende Änderungen sofort schreiben (beim Entladen)."""
        for m in MODULES:
            await self._stores[m].async_save(self._dump(m))

    # ---------- Theme ----------
    def theme_view(self) -> dict:
        return {"theme": self.theme["theme"], "themes": list(THEMES)}

    @callback
    def theme_set(self, key: str) -> None:
        if key not in THEMES:
            raise ValueError(f"Unbekanntes Theme: {key}")
        if self.theme["theme"] != key:
            self.theme["theme"] = key
            self._changed("theme")

    # ---------- Notizen ----------
    def notes_view(self) -> dict:
        return {"notes": self.notes}

    @callback
    def note_save(self, data: dict) -> dict:
        nid = data.get("id")
        note = next((n for n in self.notes if n["id"] == nid), None) if nid else None
        if note is None:
            note = {"id": _id(), "created": _now(), "title": "", "body": "", "pinned": False}
            self.notes.insert(0, note)
        if "title" in data:
            note["title"] = clean_text(data["title"], 200)
        if "body" in data:
            note["body"] = clean_html(data["body"])
        if "pinned" in data:
            note["pinned"] = bool(data["pinned"])
        note["updated"] = _now()
        self._changed("notes")
        return note

    @callback
    def note_delete(self, nid: str) -> None:
        self.notes = [n for n in self.notes if n["id"] != nid]
        self._changed("notes")

    # ---------- Einkauf ----------
    def shop_view(self) -> dict:
        hist = sorted(self.shop["history"].values(), key=lambda h: h.get("last", 0), reverse=True)
        return {
            "items": self.shop["items"],
            "stores": self.shop["stores"],
            "history": hist[:60],
            "sync_entity": self.shop["sync"].get("entity_id"),
            "units": UNITS,
        }

    def item(self, iid: str) -> dict | None:
        return next((i for i in self.shop["items"] if i["id"] == iid), None)

    def _apply_item(self, it: dict, data: dict) -> None:
        if "name" in data:
            it["name"] = clean_text(data["name"], 120) or it.get("name") or "?"
        if "qty" in data:
            it["qty"] = _qty(data["qty"])
        if "unit" in data:
            it["unit"] = data["unit"] if data["unit"] in UNITS else "Stk"
        if "store" in data:
            sid = data["store"]
            it["store"] = sid if any(s["id"] == sid for s in self.shop["stores"]) else None
        if "icon" in data:
            it["icon"] = _icon(data["icon"])
        if "image" in data:
            it["image"] = _image(data["image"])
        if "note" in data:
            it["note"] = clean_html(data["note"])
        if "done" in data:
            done = bool(data["done"])
            if done and not it.get("done"):
                it["done_at"] = _now()
                self._remember(it)
            it["done"] = done
            if not done:
                it["done_at"] = None

    @callback
    def item_save(self, data: dict, sync: bool = True) -> dict:
        iid = data.get("id")
        it = self.item(iid) if iid else None
        if it is None:
            name = clean_text(data.get("name"), 120)
            if not name:
                raise ValueError("Name fehlt")
            hist = self.shop["history"].get(hkey(name), {})
            # Neuer Artikel übernimmt Icon/Bild/Geschäft/Einheit aus dem Verlauf, wenn nichts angegeben ist
            it = {"id": _id(), "created": _now(), "name": name, "qty": 1, "unit": hist.get("unit", "Stk"),
                  "store": hist.get("store"), "icon": hist.get("icon"), "image": hist.get("image"), "note": "",
                  "done": False, "done_at": None, "todo_uid": None}
            if it["store"] and not any(s["id"] == it["store"] for s in self.shop["stores"]):
                it["store"] = None
            self.shop["items"].insert(0, it)
        self._apply_item(it, data)
        it["updated"] = _now()
        self._gc_later()
        self._changed("shopping", sync)
        return it

    @callback
    def item_delete(self, iid: str, sync: bool = True) -> None:
        it = self.item(iid)
        if not it:
            return
        self.shop["items"].remove(it)
        if it.get("todo_uid"):
            self.shop["sync"].setdefault("remove", []).append(it["todo_uid"])
        self._gc_later()
        self._changed("shopping", sync)

    @callback
    def clear_done(self) -> int:
        done = [i for i in self.shop["items"] if i.get("done")]
        for it in done:
            self.shop["items"].remove(it)
            if it.get("todo_uid"):
                self.shop["sync"].setdefault("remove", []).append(it["todo_uid"])
        if done:
            self._gc_later()
            self._changed("shopping")
        return len(done)

    @callback
    def reorder(self, ids: list[str]) -> None:
        pos = {iid: n for n, iid in enumerate(ids)}
        self.shop["items"].sort(key=lambda i: pos.get(i["id"], len(pos)))
        self._changed("shopping", False)

    def _remember(self, it: dict) -> None:
        k = hkey(it["name"])
        h = self.shop["history"].get(k, {"count": 0})
        h.update({"key": k, "name": it["name"], "qty": it.get("qty", 1), "unit": it.get("unit", "Stk"),
                  "store": it.get("store"), "icon": it.get("icon"), "image": it.get("image"),
                  "count": h.get("count", 0) + 1, "last": _now()})
        self.shop["history"][k] = h
        if len(self.shop["history"]) > HISTORY_MAX:
            old = sorted(self.shop["history"].values(), key=lambda x: x.get("last", 0))
            for x in old[: len(old) - HISTORY_MAX]:
                self.shop["history"].pop(x["key"], None)

    @callback
    def history_delete(self, key: str) -> None:
        if self.shop["history"].pop(key, None):
            self._gc_later()
            self._changed("shopping", False)

    @callback
    def store_save(self, data: dict) -> dict:
        sid = data.get("id")
        st = next((s for s in self.shop["stores"] if s["id"] == sid), None) if sid else None
        if st is None:
            name = clean_text(data.get("name"), 60)
            if not name:
                raise ValueError("Name fehlt")
            st = {"id": _id(), "name": name, "icon": "mdi:store-outline"}
            self.shop["stores"].append(st)
        if "name" in data and clean_text(data["name"], 60):
            st["name"] = clean_text(data["name"], 60)
        if "icon" in data:
            st["icon"] = _icon(data["icon"]) or "mdi:store-outline"
        if "order" in data and isinstance(data["order"], int):
            self.shop["stores"].remove(st)
            self.shop["stores"].insert(max(0, min(data["order"], len(self.shop["stores"]))), st)
        self._changed("shopping", False)
        return st

    @callback
    def store_delete(self, sid: str) -> None:
        self.shop["stores"] = [s for s in self.shop["stores"] if s["id"] != sid]
        for it in self.shop["items"]:
            if it.get("store") == sid:
                it["store"] = None
        for h in self.shop["history"].values():
            if h.get("store") == sid:
                h["store"] = None
        self._changed("shopping", False)

    @callback
    def set_sync(self, entity_id: str | None) -> None:
        sync = self.shop["sync"]
        if sync.get("entity_id") == entity_id:
            return
        # Neue Liste: Zuordnung vergessen, beim nächsten Abgleich wird über den Namen zusammengeführt
        self.shop["sync"] = {"entity_id": entity_id, "snap": {}, "remove": []}
        for it in self.shop["items"]:
            it["todo_uid"] = None
        self._changed("shopping")

    # ---------- Rezeptbuch ----------
    def recipes_view(self) -> dict:
        return {"recipes": self.recipes, "units": RECIPE_UNITS}

    def recipe(self, rid: str) -> dict | None:
        return next((r for r in self.recipes if r["id"] == rid), None)

    @staticmethod
    def _ingredients(raw) -> list[dict]:
        out = []
        for x in raw if isinstance(raw, list) else []:
            if not isinstance(x, dict):
                continue
            name = clean_text(x.get("name"), 120)
            if not name:
                continue
            unit = x.get("unit") if x.get("unit") in RECIPE_UNITS else ""
            qty = x.get("qty")
            out.append({"name": name, "qty": None if qty in (None, "") else _qty(qty, 0), "unit": unit})
        return out[:100]

    @callback
    def recipe_save(self, data: dict) -> dict:
        rid = data.get("id")
        rec = self.recipe(rid) if rid else None
        if rec is None:
            if not clean_text(data.get("title"), 200):
                raise ValueError("Titel fehlt")
            rec = {"id": _id(), "created": _now(), "title": "", "image": None, "servings": 2, "time": None, "tags": [],
                   "ingredients": [], "steps": "", "favorite": False, "source": None}
            self.recipes.insert(0, rec)
        if "title" in data and clean_text(data["title"], 200):
            rec["title"] = clean_text(data["title"], 200)
        if "image" in data:
            rec["image"] = _image(data["image"])
        if "servings" in data:
            rec["servings"] = max(1, min(int(_qty(data["servings"], 2)), 99))
        if "time" in data:
            rec["time"] = None if data["time"] in (None, "") else max(0, min(int(_qty(data["time"], 0)), 6000))
        if "tags" in data:
            tags = [clean_text(t, 30) for t in data["tags"] if isinstance(t, str)]
            rec["tags"] = list(dict.fromkeys(t for t in tags if t))[:12]
        if "ingredients" in data:
            rec["ingredients"] = self._ingredients(data["ingredients"])
        if "steps" in data:
            rec["steps"] = clean_html(data["steps"])
        if "favorite" in data:
            rec["favorite"] = bool(data["favorite"])
        if "source" in data:
            rec["source"] = clean_url(data["source"])
        rec["updated"] = _now()
        self._gc_later()
        self._changed("recipes")
        return rec

    def recipe_duplicates(self, title: str, source: str | None) -> list[dict]:
        """Rezepte mit demselben Link oder (fast) demselben Titel – für die Nachfrage beim Import."""
        def norm(t) -> str:
            return re.sub(r"[^a-z0-9äöüß]+", "", (t or "").lower())
        key = norm(title)
        return [{"id": r["id"], "title": r["title"]} for r in self.recipes
                if (source and r.get("source") == source) or (key and norm(r["title"]) == key)]

    @callback
    def recipe_delete(self, rid: str) -> None:
        self.recipes = [r for r in self.recipes if r["id"] != rid]
        self._gc_later()
        self._changed("recipes")

    @callback
    def recipe_to_shopping(self, rid: str, servings: float | None = None, only: list[int] | None = None) -> int:
        """Zutaten (auf servings umgerechnet) auf die Einkaufsliste setzen. only = Positionen der Zutaten."""
        self.require("shopping")
        rec = self.recipe(rid)
        if not rec:
            raise ValueError("Rezept nicht gefunden")
        k = (servings / rec["servings"]) if servings and rec.get("servings") else 1
        n = 0
        for pos, ing in enumerate(rec["ingredients"]):
            if only is not None and pos not in only:
                continue
            unit = ing["unit"] if ing["unit"] in UNITS else "Stk"
            qty = round(ing["qty"] * k, 2) if ing["qty"] is not None and ing["unit"] in UNITS else 1
            # schon offen auf der Liste (gleicher Name, gleiche Einheit) → Menge erhöhen
            twin = next((i for i in self.shop["items"] if not i.get("done") and hkey(i["name"]) == hkey(ing["name"]) and i.get("unit") == unit), None)
            if twin:
                self.item_save({"id": twin["id"], "qty": twin.get("qty", 1) + qty})
            else:
                self.item_save({"name": ing["name"], "qty": qty, "unit": unit})
            n += 1
        return n

    # ---------- Bilder ----------
    def image_url(self, module: str, name: str) -> str:
        return IMAGE_URL.format(module=module, name=name)

    async def image_save(self, module: str, b64: str) -> str:
        if module not in IMAGE_MODULES:
            raise ValueError("Für dieses Modul gibt es keine Bilder")
        self.require(module)
        try:
            raw = base64.b64decode(b64.split(",", 1)[-1], validate=True)
        except (ValueError, TypeError) as err:
            raise ValueError("Bild ist kein gültiges Base64") from err
        if len(raw) > IMAGE_MAX_BYTES:
            raise ValueError("Bild ist zu groß – bitte vor dem Hochladen verkleinern")
        ext = next((e for m, e in MAGIC if raw.startswith(m)), None)
        if ext == "webp" and raw[8:12] != b"WEBP":
            ext = None
        if not ext:
            raise ValueError("Nur WebP, JPEG oder PNG")
        name = f"{secrets.token_hex(16)}.{ext}"
        await self.hass.async_add_executor_job((self.image_root / module / name).write_bytes, raw)
        return name

    @callback
    def _gc_later(self) -> None:
        """Nicht mehr benutzte Bilder nach einer Stunde löschen (frisch hochgeladene sind noch nirgends eingetragen)."""
        used = {
            "shopping": {i.get("image") for i in self.shop["items"]} | {h.get("image") for h in self.shop["history"].values()},
            "recipes": {r.get("image") for r in self.recipes},
        }
        root = self.image_root

        def run() -> None:
            cutoff = time.time() - 3600
            for module, names in used.items():
                for p in (root / module).glob("*.*"):
                    if p.name not in names and IMAGE_RE.match(p.name) and p.stat().st_mtime < cutoff:
                        p.unlink(missing_ok=True)

        self.hass.async_add_executor_job(run)
