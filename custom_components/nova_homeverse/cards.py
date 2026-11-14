"""Nova Cards aus der Integration: Datei ausliefern, im Frontend anmelden, alte Dashboard-Ressource erkennen.

Die Karten (static/nova-cards.js) werden aus den Quellen der Nova Cards gebaut („npm run integration“) – nicht
direkt bearbeiten. Angemeldet wird über frontend.add_extra_js_url: Das ist offizielle API, braucht keinen Eintrag unter
Dashboards → Ressourcen und geht auch bei Dashboards im YAML-Modus. Der Parameter ?v= ändert sich mit jeder Version und
jedem Build, damit Browser nach einem Update die neue Datei laden.
"""

from __future__ import annotations

import hashlib
import logging
import os
from collections.abc import Callable
from urllib.parse import urlsplit

from homeassistant.components import frontend
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import CoreState, Event, HomeAssistant, callback
from homeassistant.helpers import issue_registry as ir
from homeassistant.loader import async_get_integration

from .const import CARDS_FILE, CARDS_URL, DOMAIN

_LOGGER = logging.getLogger(__name__)

ISSUE_OLD_RESOURCE = "old_cards_resource"
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")


def _digest(path: str) -> str | None:
    """Kurzer Fingerabdruck der Datei – None, wenn sie fehlt."""
    try:
        with open(path, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()[:8]
    except OSError:
        return None


def is_old_resource(url: str) -> bool:
    """Eintrag unter Ressourcen, der auf eine separat installierte nova-cards.js zeigt (Marketplace, /local, CDN).

    Die eigene Datei der Integration (/nova_homeverse/static/…) und der Dev-Build (nova-dev-cards.js) zählen nicht.
    """
    path = urlsplit(url or "").path
    return path.rsplit("/", 1)[-1] == CARDS_FILE and not path.startswith(CARDS_URL.rsplit("/", 1)[0] + "/")


class NovaCards:
    """Karten anmelden und abmelden; alte Ressource prüfen, solange die Integration läuft."""

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass
        self.url: str | None = None
        self._unsubs: list[Callable[[], None]] = []
        self._unsub_start: Callable[[], None] | None = None

    async def start(self) -> None:
        version = (await async_get_integration(self.hass, DOMAIN)).version
        digest = await self.hass.async_add_executor_job(_digest, os.path.join(STATIC_DIR, CARDS_FILE))
        if digest is None:
            _LOGGER.warning("Nova Cards fehlen in der Integration (static/%s) – Karten werden nicht geladen", CARDS_FILE)
        else:
            self.url = f"{CARDS_URL}?v={version}-{digest}"
            frontend.add_extra_js_url(self.hass, self.url)
        # Ressourcen sind erst nach dem Start sicher geladen – dann prüfen und bei Änderungen erneut
        if self.hass.state is CoreState.running:
            await self._watch()
        else:
            self._unsub_start = self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, self._started)

    async def _started(self, _event: Event) -> None:
        self._unsub_start = None  # async_listen_once meldet sich selbst ab
        await self._watch()

    @callback
    def stop(self) -> None:
        if self._unsub_start:
            self._unsub_start()
            self._unsub_start = None
        for unsub in self._unsubs:
            unsub()
        self._unsubs.clear()
        if self.url:
            frontend.remove_extra_js_url(self.hass, self.url)
            self.url = None
        ir.async_delete_issue(self.hass, DOMAIN, ISSUE_OLD_RESOURCE)

    def _resources(self):
        # HA-INTERN: hass.data["lovelace"].resources (Ressourcen-Sammlung von Lovelace). Fehlt sie, gibt es keinen Hinweis.
        lovelace = self.hass.data.get("lovelace")
        resources = getattr(lovelace, "resources", None)
        if resources is None and isinstance(lovelace, dict):
            resources = lovelace.get("resources")
        return resources if hasattr(resources, "async_items") else None

    async def _watch(self) -> None:
        resources = self._resources()
        if resources is None:
            return
        listen = getattr(resources, "async_add_listener", None)
        if callable(listen):

            async def changed(*_args) -> None:
                await self.check()

            self._unsubs.append(listen(changed))
        await self.check()

    async def check(self) -> None:
        """Nur lesen: Steht noch die alte nova-cards.js unter Ressourcen, zeigt Reparaturen einen Hinweis."""
        resources = self._resources()
        if resources is None:
            return
        try:
            # Gespeicherte Ressourcen werden erst bei Bedarf geladen
            if hasattr(resources, "async_get_info"):
                await resources.async_get_info()
            old = [i.get("url", "") for i in resources.async_items() if is_old_resource(i.get("url", ""))]
        except Exception:  # noqa: BLE001 – interne API, im Zweifel kein Hinweis
            _LOGGER.debug("Dashboard-Ressourcen nicht lesbar", exc_info=True)
            return
        if old and self.url:
            ir.async_create_issue(
                self.hass,
                DOMAIN,
                ISSUE_OLD_RESOURCE,
                is_fixable=False,
                is_persistent=False,
                severity=ir.IssueSeverity.WARNING,
                translation_key=ISSUE_OLD_RESOURCE,
                translation_placeholders={"url": ", ".join(old)},
            )
        else:
            ir.async_delete_issue(self.hass, DOMAIN, ISSUE_OLD_RESOURCE)
