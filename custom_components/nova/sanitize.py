"""Formatierten Text (HTML aus der Nova-Leiste) bereinigen.

Erlaubt ist nur eine feste Liste von Elementen und Klassen. Alles andere fliegt raus, Text bleibt erhalten
(escaped). Inhalte von script/style & Co. werden ganz verworfen. Dieselbe Liste steht in nova-cards
(src/shared/rich-text.js) – beide Seiten filtern, die Integration ist die letzte Instanz.
"""

from __future__ import annotations

import re
from html import escape
from html.parser import HTMLParser

MAX_LEN = 50_000

# Element → Name im Ergebnis (Synonyme werden vereinheitlicht)
TAGS = {
    "b": "b", "strong": "b",
    "i": "i", "em": "i",
    "u": "u",
    "s": "s", "strike": "s", "del": "s",
    "br": "br",
    "p": "p", "div": "p",
    "h3": "h3",
    "ul": "ul", "ol": "ul",
    "li": "li",
    "span": "span",
}
VOID = {"br"}
# Erlaubte Klassen je Element
CLASSES = {
    "span": {"fs-s", "fs-l", "c-accent", "c-warn", "c-muted"},
    "ul": {"check"},
    "li": {"done"},
}
DROP = {"script", "style", "iframe", "object", "embed", "template", "svg", "math", "noscript", "textarea", "select", "head", "title"}


class _Cleaner(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.out: list[str] = []
        self.stack: list[str | None] = []
        self.drop = 0

    def handle_starttag(self, tag, attrs):
        if tag in DROP:
            self.drop += 1
            return
        if self.drop:
            return
        name = TAGS.get(tag)
        if name in VOID:
            self.out.append("<br>")
            return
        if name is None:
            self.stack.append(None)
            return
        if name == "li":
            # <li> ohne Ende-Tag: ein noch offenes <li> derselben Liste schließen
            for i in range(len(self.stack) - 1, -1, -1):
                if self.stack[i] == "ul":
                    break
                if self.stack[i] == "li":
                    self.handle_endtag("li")
                    break
        allowed = CLASSES.get(name, set())
        cls = [c for c in (dict(attrs).get("class") or "").split() if c in allowed]
        if name == "span" and not cls:
            self.stack.append(None)
            return
        self.stack.append(name)
        self.out.append(f'<{name} class="{" ".join(dict.fromkeys(cls))}">' if cls else f"<{name}>")

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if TAGS.get(tag) not in VOID and tag not in DROP and not self.drop:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        if tag in DROP:
            self.drop = max(0, self.drop - 1)
            return
        if self.drop or TAGS.get(tag) in VOID:
            return
        name = TAGS.get(tag)
        # passendes offenes Element suchen, Dazwischenliegendes mit schließen
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i] == name or (name is None and self.stack[i] is None):
                for open_ in reversed(self.stack[i:]):
                    if open_:
                        self.out.append(f"</{open_}>")
                del self.stack[i:]
                return

    def handle_data(self, data):
        if not self.drop:
            self.out.append(escape(data, quote=False))

    def result(self) -> str:
        for open_ in reversed(self.stack):
            if open_:
                self.out.append(f"</{open_}>")
        self.stack.clear()
        return "".join(self.out)


def clean_html(value) -> str:
    """HTML auf die erlaubte Teilmenge reduzieren."""
    if not isinstance(value, str) or not value:
        return ""
    p = _Cleaner()
    p.feed(value[:MAX_LEN])
    p.close()
    return p.result()


def clean_text(value, limit: int = 200) -> str:
    """Einfacher Text (Titel, Namen): Steuerzeichen raus, Länge begrenzen."""
    if not isinstance(value, str):
        return ""
    return "".join(ch for ch in value if ch >= " " or ch == "\t").strip()[:limit]


BLOCK = {"p", "div", "li", "h1", "h2", "h3", "blockquote", "ul", "ol"}


def to_plain(value) -> str:
    """Formatierten Text in Klartext umwandeln (für die todo-Liste): Absätze und <br> werden Zeilenumbrüche."""
    if not isinstance(value, str) or not value:
        return ""
    out: list[str] = []

    class P(HTMLParser):
        def handle_starttag(self, tag, attrs):
            if tag == "br":
                out.append("\n")
            elif tag == "li":
                out.append("\0• ")
            elif tag in BLOCK:
                out.append("\0")

        def handle_endtag(self, tag):
            if tag in BLOCK:
                out.append("\0")

        def handle_data(self, data):
            out.append(data)

    p = P(convert_charrefs=True)
    p.feed(value[:MAX_LEN])
    p.close()
    # Grenzen von Absätzen/Listen (\0) zählen zusammen als ein Zeilenumbruch, <br> jeweils einzeln
    text = re.sub(r"\0+", "\n", "".join(out))
    return "\n".join(ln.strip() for ln in text.splitlines()).strip()


def from_plain(text) -> str:
    """Klartext (z. B. aus der todo-Liste) als formatierten Text: Zeilen werden Absätze."""
    if not isinstance(text, str) or not text.strip():
        return ""
    return "".join(f"<p>{escape(ln) or '<br>'}</p>" for ln in text.strip()[:MAX_LEN].splitlines())
