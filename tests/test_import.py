"""Tests des Rezept-Imports per Link (schema.org Recipe / JSON-LD)."""

import json
import socket
from io import BytesIO
from unittest.mock import patch

from PIL import Image

from custom_components.nova_homeverse.const import DOMAIN
from custom_components.nova_homeverse.recipe_import import extract_recipe, build_draft, parse_ingredient

# Aufbau wie bei Chefkoch: Recipe neben anderen JSON-LD-Blöcken, Anleitung als ein Text, Zeiten als P0DT…
CHEFKOCH = """<html><head><title>Lasagne von Oma | Chefkoch</title>
<script type="application/ld+json">{"@context":"http://schema.org","@type":"BreadcrumbList","itemListElement":[]}</script>
<script type="application/ld+json">
{"@context":"http://schema.org","@type":"Recipe","name":"Lasagne von Oma","image":["https://img.example.org/lasagne.jpg"],
 "recipeYield":"4 Portionen","prepTime":"P0DT0H30M","cookTime":"P0DT0H45M","totalTime":"P0DT1H15M",
 "recipeCategory":"Hauptspeise","keywords":"Pasta, Auflauf, Hauptspeise",
 "recipeIngredient":["500 g Hackfleisch, gemischt","1 Zwiebel(n)","2 EL Olivenöl","1 Prise(n) Salz","1 Pck. Lasagneplatten",
  "½ TL Oregano","1 ½ Tasse/n Milch","n. B. Pfeffer","250g Mozzarella","1-2 Zehe/n Knoblauch"],
 "recipeInstructions":"Zwiebel würfeln &amp; anbraten.\\n\\nHack dazu und würzen.\\nSchichten und 45 Minuten backen."}
</script></head><body></body></html>"""

GRAPH = {"@context": "https://schema.org", "@graph": [
    {"@type": "WebPage", "name": "x"},
    {"@type": ["Recipe", "Thing"], "name": "Pfannkuchen", "recipeYield": ["2", "2 Stück"], "totalTime": "PT20M",
     "recipeIngredient": ["250 g Mehl"],
     "recipeInstructions": [{"@type": "HowToSection", "name": "Teig", "itemListElement": [
         {"@type": "HowToStep", "text": "Mehl und <b>Eier</b> verrühren"}]}, {"@type": "HowToStep", "text": "Backen"}]},
]}


def test_parse_ingredient():
    assert parse_ingredient("500 g Hackfleisch, gemischt") == {"qty": 500, "unit": "g", "name": "Hackfleisch, gemischt"}
    assert parse_ingredient("1 Zwiebel(n)") == {"qty": 1, "unit": "", "name": "Zwiebel"}
    assert parse_ingredient("1 Prise(n) Salz") == {"qty": 1, "unit": "Prise", "name": "Salz"}
    assert parse_ingredient("1 Pck. Lasagneplatten") == {"qty": 1, "unit": "Packung", "name": "Lasagneplatten"}
    assert parse_ingredient("½ TL Oregano") == {"qty": .5, "unit": "TL", "name": "Oregano"}
    assert parse_ingredient("1 ½ Tasse/n Milch") == {"qty": 1.5, "unit": "Tasse", "name": "Milch"}
    assert parse_ingredient("n. B. Pfeffer") == {"qty": None, "unit": "", "name": "n. B. Pfeffer"}
    assert parse_ingredient("250g Mozzarella") == {"qty": 250, "unit": "g", "name": "Mozzarella"}
    assert parse_ingredient("1-2 Zehe/n Knoblauch") == {"qty": 1, "unit": "Zehe", "name": "Knoblauch"}
    assert parse_ingredient("1/2 Liter Brühe") == {"qty": .5, "unit": "l", "name": "Brühe"}
    assert parse_ingredient("2 Tomate/n") == {"qty": 2, "unit": "", "name": "Tomate"}
    assert parse_ingredient("3 tablespoons butter, melted") == {"qty": 3, "unit": "EL", "name": "butter, melted"}
    assert parse_ingredient("  ") is None


def test_extract_chefkoch():
    d = build_draft(extract_recipe(CHEFKOCH), "https://www.chefkoch.de/rezepte/1/lasagne.html")
    assert d["title"] == "Lasagne von Oma" and d["servings"] == 4 and d["time"] == 75
    assert d["tags"] == ["Hauptspeise", "Pasta", "Auflauf"]
    assert len(d["ingredients"]) == 10 and d["ingredients"][2] == {"qty": 2, "unit": "EL", "name": "Olivenöl"}
    assert d["steps"] == "<ol><li>Zwiebel würfeln &amp; anbraten.</li><li>Hack dazu und würzen.</li><li>Schichten und 45 Minuten backen.</li></ol>"
    assert d["source"].startswith("https://www.chefkoch.de/")


def test_extract_graph():
    page = f'<script type="application/ld+json">{json.dumps(GRAPH)}</script>'
    d = build_draft(extract_recipe(page), "https://x.example/p")
    assert d["title"] == "Pfannkuchen" and d["servings"] == 2 and d["time"] == 20
    assert d["steps"] == "<ol><li>Mehl und Eier verrühren</li><li>Backen</li></ol>"
    assert extract_recipe("<html><p>kein Rezept</p></html>") is None


def test_image_reference():
    """Chefkoch/Yoast: "image" ist nur ein Verweis {"@id": …} auf ein ImageObject im @graph."""
    from custom_components.nova_homeverse.recipe_import import _image_url, _index, _ld_blocks
    page = '<script type="application/ld+json">' + json.dumps({"@graph": [
        {"@type": "Recipe", "name": "x", "image": {"@id": "https://s.de/r#primaryimage"}},
        {"@type": "ImageObject", "@id": "https://s.de/r#primaryimage", "url": "/bilder/lasagne.jpg"}]}) + "</script>"
    idx = {}
    for d in _ld_blocks(page):
        _index(d, idx)
    assert _image_url(extract_recipe(page)["image"], "https://s.de/r", idx) == "https://s.de/bilder/lasagne.jpg"


def _jpeg() -> bytes:
    out = BytesIO()
    Image.new("RGB", (2000, 1000), (200, 120, 40)).save(out, "JPEG")
    return out.getvalue()


def _public(*_a, **_k):
    return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 0))]


async def test_ws_import(hass, nova, ws, aioclient_mock):
    url = "https://www.chefkoch.de/rezepte/1/lasagne.html"
    aioclient_mock.get(url, text=CHEFKOCH, headers={"Content-Type": "text/html; charset=utf-8"})
    aioclient_mock.get("https://img.example.org/lasagne.jpg", content=_jpeg())
    aioclient_mock.get("https://www.example.org/blog", text="<html><title>Mein Blog</title></html>")
    aioclient_mock.get("https://www.example.org/zu", status=403)
    with patch("custom_components.nova_homeverse.recipe_import.socket.getaddrinfo", _public):
        res = (await ws("nova_homeverse/recipes/import", url=url))["result"]
        rec = res["recipe"]
        assert rec["title"] == "Lasagne von Oma" and res["duplicates"] == []
        img = Image.open(BytesIO(__import__("base64").b64decode(rec["image_data"].split(",", 1)[1])))
        assert max(img.size) == 960
        # nichts gespeichert
        assert hass.data[DOMAIN].recipes == []
        # übernehmen → beim nächsten Import als doppelt erkannt (Link und Titel)
        saved = (await ws("nova_homeverse/recipes/save", recipe={"title": "Lasagne von Oma!", "source": url}))["result"]["recipe"]
        assert saved["source"] == url
        dup = (await ws("nova_homeverse/recipes/import", url=url))["result"]["duplicates"]
        assert dup == [{"id": saved["id"], "title": "Lasagne von Oma!"}]
        err = await ws("nova_homeverse/recipes/import", url="https://www.example.org/blog")
        assert err["error"]["code"] == "no_recipe" and err["error"]["message"] == "Mein Blog"
        assert (await ws("nova_homeverse/recipes/import", url="https://www.example.org/zu"))["error"]["code"] == "blocked"
        assert (await ws("nova_homeverse/recipes/import", url="javascript:alert(1)"))["error"]["code"] == "invalid_url"
    # Adressen im eigenen Netz werden nicht abgerufen
    with patch("custom_components.nova_homeverse.recipe_import.socket.getaddrinfo", lambda *_a: [(2, 1, 6, "", ("192.168.1.5", 0))]):
        assert (await ws("nova_homeverse/recipes/import", url="http://router.local/"))["error"]["code"] == "blocked"
    bad = (await ws("nova_homeverse/recipes/save", recipe={"id": saved["id"], "source": "javascript:alert(1)"}))["result"]["recipe"]
    assert bad["source"] is None
