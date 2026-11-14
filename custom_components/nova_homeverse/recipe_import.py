"""Rezept-Import per Link: Seite laden und schema.org-Recipe (JSON-LD) auslesen.

Gespeichert wird hier nichts. Das Ergebnis ist ein Entwurf, den die Karte als Vorschau zeigt; erst „Ins Buch übernehmen“
speichert über nova_homeverse/recipes/save (und lädt das Bild über nova_homeverse/image/upload hoch, verkleinert von der Karte).
"""

from __future__ import annotations

import asyncio
import base64
import ipaddress
import json
import re
import socket
from io import BytesIO
from html import escape, unescape
from urllib.parse import urljoin, urlsplit

import logging

import aiohttp
from PIL import Image, UnidentifiedImageError
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import RECIPE_UNITS

_LOGGER = logging.getLogger(__name__)

PAGE_MAX = 3_000_000
IMAGE_MAX = 6_000_000
TIMEOUT = 15
HEADERS = {
    # Manche Seiten liefern ohne Browser-Kennung nur eine Sperrseite
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "de-DE,de;q=0.9,en;q=0.6",
}
# Bilder: lieber JPEG/PNG/WebP als AVIF, das kann nicht jede Pillow-Version
IMAGE_HEADERS = {**HEADERS, "Accept": "image/jpeg,image/png,image/webp;q=0.9,image/*;q=0.5,*/*;q=0.1"}
IMG_SIDE = 960  # wie die Karten beim Hochladen


class RecipeImportError(Exception):
    """Fehler beim Import – code geht als WebSocket-Fehlercode an die Karte."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


# ---------- Zutaten zerlegen ----------
# Schreibweisen → Einheit aus RECIPE_UNITS (Kleinschreibung, ohne Punkt und „(n)“)
UNIT_WORDS = {
    "g": "g", "gr": "g", "gramm": "g", "kg": "kg", "kilo": "kg", "kilogramm": "kg",
    "ml": "ml", "milliliter": "ml", "l": "l", "liter": "l", "cl": "cl", "zentiliter": "cl",
    "el": "EL", "essl": "EL", "esslöffel": "EL", "eßlöffel": "EL", "tbsp": "EL", "tablespoon": "EL", "tablespoons": "EL",
    "tl": "TL", "teel": "TL", "teelöffel": "TL", "tsp": "TL", "teaspoon": "TL", "teaspoons": "TL",
    "prise": "Prise", "prisen": "Prise", "msp": "Msp.", "messerspitze": "Msp.", "messerspitzen": "Msp.",
    "tasse": "Tasse", "tassen": "Tasse", "cup": "Cup", "cups": "Cup", "becher": "Becher",
    "bund": "Bund", "dose": "Dose", "dosen": "Dose", "glas": "Glas", "gläser": "Glas",
    "zehe": "Zehe", "zehen": "Zehe", "scheibe": "Scheibe", "scheiben": "Scheibe",
    "blatt": "Blatt", "blätter": "Blatt", "handvoll": "Handvoll",
    "stk": "Stk", "stück": "Stk", "st": "Stk",
    "pck": "Packung", "pkg": "Packung", "pk": "Packung", "pkt": "Packung", "päckchen": "Packung", "packung": "Packung", "packungen": "Packung",
}
FRACTIONS = {"½": .5, "⅓": 1 / 3, "⅔": 2 / 3, "¼": .25, "¾": .75, "⅕": .2, "⅛": .125}
NUM = r"(?:\d+(?:[.,]\d+)?(?:\s*/\s*\d+)?|[½⅓⅔¼¾⅕⅛])"
QTY_RE = re.compile(rf"^\s*({NUM}(?:\s*[½⅓⅔¼¾⅕⅛])?)(?:\s*(?:-|–|bis)\s*{NUM})?\s*(.*)$")


def _num(s: str) -> float | None:
    s = s.strip().replace(",", ".")
    total = 0.0
    for ch, v in FRACTIONS.items():
        if ch in s:
            total += v
            s = s.replace(ch, "")
    s = s.strip()
    if "/" in s:
        a, _, b = s.partition("/")
        try:
            total += float(a) / float(b)
        except (ValueError, ZeroDivisionError):
            return None
    elif s:
        try:
            total += float(s)
        except ValueError:
            return None
    return round(total, 3) if total else None


def parse_ingredient(text: str) -> dict | None:
    """„250 g Mehl“ → {qty: 250, unit: "g", name: "Mehl"}. Was nicht passt, bleibt ganz im Namen."""
    s = re.sub(r"\s+", " ", _plain(text)).strip(" ,;")
    if not s:
        return None
    m = QTY_RE.match(s)
    if not m or not m.group(2):
        return {"qty": None, "unit": "", "name": s[:120]}
    qty, rest = _num(m.group(1)), m.group(2)
    first, _, tail = rest.partition(" ")
    key = re.sub(r"\(.*?\)|/\w{1,3}$|\.$", "", first).lower()
    unit = UNIT_WORDS.get(key, "")
    if unit not in RECIPE_UNITS:
        unit = ""
    name = (tail if unit and tail else rest).strip()
    # Chefkoch schreibt „Zwiebel(n)“, „Ei(er)“, „Tomate/n“
    name = re.sub(r"\((n|en|e|er|s|nen)\)|(?<=\w)/(n|en|e|er|s)\b", "", name).strip() or rest
    return {"qty": qty, "unit": unit, "name": name[:120]}


# ---------- Hilfen ----------
def _plain(v) -> str:
    """Text ohne HTML-Tags und Entities."""
    if not isinstance(v, str):
        return ""
    return re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", v))).strip()


def _minutes(v) -> int | None:
    """ISO-8601-Dauer (PT1H30M, P0DT0H20M) → Minuten."""
    if not isinstance(v, str):
        return None
    m = re.fullmatch(r"P(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?(?:\d+(?:\.\d+)?S)?)?", v.strip(), re.I)
    if not m:
        return None
    d, h, mi = (int(x or 0) for x in m.groups())
    total = d * 1440 + h * 60 + mi
    return total or None


def _servings(v) -> int:
    for x in v if isinstance(v, list) else [v]:
        if isinstance(x, (int, float)) and x > 0:
            return max(1, min(int(x), 99))
        if isinstance(x, str) and (m := re.search(r"\d+", x)):
            return max(1, min(int(m.group()), 99))
    return 2


def _types(node: dict) -> set[str]:
    t = node.get("@type")
    return {x.split("/")[-1] for x in (t if isinstance(t, list) else [t]) if isinstance(x, str)}


def _find_recipe(node):
    """Tiefensuche nach dem ersten Objekt vom Typ Recipe (auch in @graph und Listen)."""
    if isinstance(node, list):
        for x in node:
            if (r := _find_recipe(x)) is not None:
                return r
    elif isinstance(node, dict):
        if "Recipe" in _types(node):
            return node
        for k in ("@graph", "mainEntity", "mainEntityOfPage", "itemListElement"):
            if k in node and (r := _find_recipe(node[k])) is not None:
                return r
    return None


LD_RE = re.compile(r"<script[^>]*type\s*=\s*[\"']?application/ld\+json[\"']?[^>]*>(.*?)</script>", re.I | re.S)


def _ld_blocks(page: str) -> list:
    out = []
    for block in LD_RE.findall(page):
        block = block.strip().removeprefix("<!--").removesuffix("-->").strip()
        block = re.sub(r"^//\s*<!\[CDATA\[|//\s*\]\]>$", "", block).strip()
        try:
            out.append(json.loads(block, strict=False))
        except ValueError:
            continue
    return out


def _index(node, idx: dict) -> dict:
    """Alle Objekte mit @id sammeln – Angaben wie "image": {"@id": "…#primaryimage"} verweisen darauf (Yoast, Chefkoch)."""
    if isinstance(node, list):
        for x in node:
            _index(x, idx)
    elif isinstance(node, dict):
        if isinstance(node.get("@id"), str) and len(node) > 1:
            idx.setdefault(node["@id"], node)
        for v in node.values():
            if isinstance(v, (dict, list)):
                _index(v, idx)
    return idx


def extract_recipe(page: str) -> dict | None:
    for data in _ld_blocks(page):
        if (r := _find_recipe(data)) is not None:
            return r
    return None


def _steps(v) -> list[str]:
    out: list[str] = []
    if isinstance(v, str):
        # ein einziger Text: Absätze bzw. Zeilen werden zu Schritten
        txt = re.sub(r"<br\s*/?>|</p>|</li>", "\n", v, flags=re.I)
        out += [p for p in (_plain(x) for x in re.split(r"\n\s*\n|\n", txt)) if p]
    elif isinstance(v, list):
        for x in v:
            out += _steps(x)
    elif isinstance(v, dict):
        if "HowToSection" in _types(v):
            out += _steps(v.get("itemListElement"))
        else:
            out += _steps(v.get("text") or v.get("name") or "")
    return out


def _image_url(v, base: str, idx: dict | None = None, depth: int = 0) -> str | None:
    if depth > 4:
        return None
    if isinstance(v, list):
        for x in v:
            if u := _image_url(x, base, idx, depth + 1):
                return u
        return None
    if isinstance(v, dict):
        # nur ein Verweis per @id → das Objekt dazu nachschlagen
        if not (v.get("url") or v.get("contentUrl")) and idx and (ref := idx.get(v.get("@id"))) is not None and ref is not v:
            return _image_url(ref, base, idx, depth + 1)
        return _image_url(v.get("url") or v.get("contentUrl"), base, idx, depth + 1)
    if isinstance(v, str) and v.strip():
        u = urljoin(base, v.strip())
        return u if urlsplit(u).scheme in ("http", "https") else None
    return None


def _tags(r: dict) -> list[str]:
    raw: list = []
    for k in ("recipeCategory", "keywords"):
        v = r.get(k)
        raw += v if isinstance(v, list) else (v.split(",") if isinstance(v, str) else [])
    tags = [_plain(t)[:30] for t in raw if isinstance(t, str)]
    return list(dict.fromkeys(t for t in tags if t))[:6]


def build_draft(r: dict, source: str) -> dict:
    steps = _steps(r.get("recipeInstructions"))
    time = _minutes(r.get("totalTime"))
    if time is None:
        parts = [_minutes(r.get(k)) for k in ("prepTime", "cookTime")]
        time = sum(p for p in parts if p) or None
    ings = [p for p in (parse_ingredient(x) for x in (r.get("recipeIngredient") or r.get("ingredients") or []) if isinstance(x, str)) if p]
    return {
        "title": _plain(r.get("name"))[:200],
        "servings": _servings(r.get("recipeYield")),
        "time": time,
        "tags": _tags(r),
        "ingredients": ings[:100],
        "steps": "<ol>" + "".join(f"<li>{escape(s)}</li>" for s in steps) + "</ol>" if steps else "",
        "source": source,
    }


def shrink(data: bytes) -> bytes | None:
    """Bild auf höchstens 960 px (längste Seite) als JPEG – läuft im Executor."""
    try:
        with Image.open(BytesIO(data)) as im:
            im.thumbnail((IMG_SIDE, IMG_SIDE))
            out = BytesIO()
            im.convert("RGB").save(out, "JPEG", quality=82, optimize=True)
            return out.getvalue()
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
        return None


# ---------- Laden ----------
async def _check_host(hass: HomeAssistant, url: str) -> None:
    """Nur öffentliche Adressen – keine Geräte im eigenen Netz über den Server abrufen."""
    host = urlsplit(url).hostname or ""
    try:
        infos = await hass.async_add_executor_job(socket.getaddrinfo, host, None)
    except OSError as err:
        raise RecipeImportError("fetch_failed", "Die Seite ist nicht erreichbar") from err
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if not ip.is_global:
            raise RecipeImportError("blocked", "Adressen im eigenen Netz werden nicht importiert")


async def _get(hass: HomeAssistant, url: str, limit: int, headers: dict = HEADERS) -> tuple[bytes, str, str]:
    await _check_host(hass, url)
    session = async_get_clientsession(hass)
    try:
        async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=TIMEOUT), allow_redirects=True, max_redirects=5) as resp:
            _LOGGER.debug("Rezept-Import: GET %s → HTTP %s, Content-Type %r, Ziel %s", url, resp.status, resp.headers.get("Content-Type"), resp.url)
            if resp.status in (401, 403, 429):
                raise RecipeImportError("blocked", "Die Seite lässt keinen Abruf zu")
            if resp.status >= 400:
                raise RecipeImportError("fetch_failed", f"Die Seite antwortet mit Fehler {resp.status}")
            # Weiterleitung auf eine Adresse im eigenen Netz abfangen
            if str(resp.url) != url:
                await _check_host(hass, str(resp.url))
            body = b""
            async for chunk in resp.content.iter_chunked(65536):
                body += chunk
                if len(body) > limit:
                    raise RecipeImportError("too_large", "Die Seite ist zu groß")
            return body, resp.headers.get("Content-Type", ""), str(resp.url)
    except (aiohttp.ClientError, asyncio.TimeoutError) as err:
        _LOGGER.debug("Rezept-Import: GET %s fehlgeschlagen: %r", url, err)
        raise RecipeImportError("fetch_failed", "Die Seite ist nicht erreichbar") from err


def clean_url(url) -> str | None:
    if not isinstance(url, str):
        return None
    url = url.strip()
    p = urlsplit(url)
    if p.scheme not in ("http", "https") or not p.hostname or len(url) > 500 or any(c.isspace() for c in url):
        return None
    return url


async def import_recipe(hass: HomeAssistant, url: str) -> dict:
    """Entwurf aus einer Rezeptseite. Bild als data:-URL (nur Vorschau, wird nicht gespeichert)."""
    url = clean_url(url)
    if not url:
        raise RecipeImportError("invalid_url", "Das ist kein gültiger Link")
    raw, ctype, final = await _get(hass, url, PAGE_MAX)
    charset = re.search(r"charset=([\w-]+)", ctype)
    page = raw.decode(charset.group(1) if charset else "utf-8", errors="replace")
    r = extract_recipe(page)
    if r is None:
        title = re.search(r"<title[^>]*>(.*?)</title>", page, re.I | re.S)
        raise RecipeImportError("no_recipe", _plain(title.group(1))[:200] if title else "")
    draft = build_draft(r, url)
    if not draft["title"] and not draft["ingredients"]:
        raise RecipeImportError("no_recipe", "")
    draft["image_data"] = None
    idx: dict = {}
    for data in _ld_blocks(page):
        _index(data, idx)
    img = _image_url(r.get("image") or r.get("thumbnailUrl"), final, idx)
    if not img:
        # Ersatz: Vorschaubild der Seite (og:image)
        og = re.search(r"<meta[^>]+property=[\"']og:image[\"'][^>]+content=[\"']([^\"']+)", page, re.I) or \
            re.search(r"<meta[^>]+content=[\"']([^\"']+)[\"'][^>]+property=[\"']og:image[\"']", page, re.I)
        img = _image_url(unescape(og.group(1)), final) if og else None
    _LOGGER.debug("Rezept-Import: Bild-Angabe %r → %s", r.get("image") or r.get("thumbnailUrl"), img)
    if img:
        try:
            # Referer wie im Browser: manche Bild-Server (CDN) liefern sonst nichts oder ein anderes Format
            data, ctype, _ = await _get(hass, img, IMAGE_MAX, {**IMAGE_HEADERS, "Referer": final})
            # Pillow erkennt das Format selbst (JPEG, PNG, WebP, AVIF …), gespeichert wird später immer JPEG
            small = await hass.async_add_executor_job(shrink, data)
            if small:
                draft["image_data"] = "data:image/jpeg;base64," + base64.b64encode(small).decode()
            else:
                _LOGGER.debug("Rezept-Import: Bild %s nicht lesbar (%s, %d Bytes, Anfang %r)", img, ctype, len(data), data[:16])
        except RecipeImportError as err:
            _LOGGER.debug("Rezept-Import: Bild %s nicht geladen: %s", img, err)  # ohne Bild geht es auch
    return draft
