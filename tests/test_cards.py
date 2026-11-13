"""Nova Cards aus der Integration: Auslieferung, Anmeldung im Frontend, Hinweis bei alter Ressource."""

import pytest
from homeassistant.components.frontend import DATA_EXTRA_MODULE_URL
from homeassistant.helpers import issue_registry as ir
from homeassistant.loader import async_get_integration
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.nova.cards import ISSUE_OLD_RESOURCE, is_old_resource
from custom_components.nova.const import DOMAIN


def _card_urls(hass):
    return [u for u in hass.data[DATA_EXTRA_MODULE_URL].urls if "nova-cards.js" in u]


@pytest.mark.parametrize(
    ("url", "old"),
    [
        ("/hacsfiles/nova-cards/nova-cards.js", True),
        ("/hacsfiles/nova-cards/nova-cards.js?hacstag=123", True),
        ("/local/nova-cards.js", True),
        ("https://cdn.jsdelivr.net/gh/Blackstar9119/nova-cards@main/nova-cards.js", True),
        ("/nova/static/nova-cards.js?v=1", False),
        ("https://cdn.jsdelivr.net/gh/Blackstar9119/nova-cards@abc/nova-dev-cards.js", False),
        ("/hacsfiles/button-card/button-card.js", False),
        ("", False),
    ],
)
def test_is_old_resource(url, old):
    assert is_old_resource(url) is old


async def test_cards_served_and_registered(hass, hass_client, nova):
    """Die Karten kommen unter /nova/static mit ?v=<Version>-<Fingerabdruck> und stehen in den Frontend-Modulen."""
    urls = _card_urls(hass)
    assert len(urls) == 1
    url = urls[0]
    assert url.startswith("/nova/static/nova-cards.js?v=")
    manifest = (await async_get_integration(hass, DOMAIN)).version
    assert url.split("?v=")[1].startswith(f"{manifest}-")
    client = await hass_client()
    res = await client.get(url)
    assert res.status == 200
    assert "Nova Cards v" in await res.text()
    # Entladen meldet die Karten wieder ab
    assert await hass.config_entries.async_unload(nova.entry_id)
    assert _card_urls(hass) == []


async def test_old_resource_issue(hass, hass_ws_client):
    """Steht die alte nova-cards.js unter Ressourcen, gibt es einen Hinweis; ist sie weg, verschwindet er."""
    assert await async_setup_component(hass, "lovelace", {})
    resources = hass.data["lovelace"].resources
    await resources.async_get_info()
    item = await resources.async_create_item({"res_type": "module", "url": "/hacsfiles/nova-cards/nova-cards.js?hacstag=1"})
    await resources.async_create_item({"res_type": "module", "url": "/hacsfiles/other/other.js"})

    entry = MockConfigEntry(domain=DOMAIN, title="Nova", data={})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    reg = ir.async_get(hass)
    issue = reg.async_get_issue(DOMAIN, ISSUE_OLD_RESOURCE)
    assert issue is not None
    assert "/hacsfiles/nova-cards/nova-cards.js" in issue.translation_placeholders["url"]
    # Ressourcen werden nur gelesen
    assert len(resources.async_items()) == 2

    # Alte Ressource gelöscht → Hinweis weg
    await resources.async_delete_item(item["id"])
    await hass.async_block_till_done()
    assert reg.async_get_issue(DOMAIN, ISSUE_OLD_RESOURCE) is None

    # Wieder eingetragen → Hinweis kommt zurück, Entladen nimmt ihn mit
    await resources.async_create_item({"res_type": "module", "url": "/local/nova-cards.js"})
    await hass.async_block_till_done()
    assert reg.async_get_issue(DOMAIN, ISSUE_OLD_RESOURCE) is not None
    assert await hass.config_entries.async_unload(entry.entry_id)
    assert reg.async_get_issue(DOMAIN, ISSUE_OLD_RESOURCE) is None
