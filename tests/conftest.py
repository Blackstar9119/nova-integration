"""Gemeinsames für die Tests: Custom Integrations laden, Nova einrichten."""

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.nova.const import CONF_MODULES, DOMAIN, MODULES


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield


@pytest.fixture
async def nova(hass):
    entry = MockConfigEntry(domain=DOMAIN, title="Nova", data={}, options={CONF_MODULES: list(MODULES)})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


@pytest.fixture
async def ws(hass, nova, hass_ws_client):
    client = await hass_ws_client(hass)
    n = 0

    async def call(type_, **data):
        nonlocal n
        n += 1
        await client.send_json({"id": n, "type": type_, **data})
        while True:
            msg = await client.receive_json()
            if msg["id"] == n and msg["type"] == "result":
                return msg

    call.client = client
    return call
