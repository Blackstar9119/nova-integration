"""Einrichtung der Nova-Integration: ein Eintrag ohne Eingaben, in den Optionen die aktiven Module."""

from __future__ import annotations

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import CONF_MODULES, DOMAIN, MODULES


class NovaConfigFlow(ConfigFlow, domain=DOMAIN):
    """Nova einrichten."""

    VERSION = 1

    async def async_step_user(self, user_input=None) -> ConfigFlowResult:
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")
        if user_input is not None:
            return self.async_create_entry(title="Nova", data={}, options={CONF_MODULES: list(MODULES)})
        return self.async_show_form(step_id="user")

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return NovaOptionsFlow()


class NovaOptionsFlow(OptionsFlow):
    """Module an- und abschalten."""

    async def async_step_init(self, user_input=None) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data={CONF_MODULES: [m for m in MODULES if m in user_input[CONF_MODULES]]})
        current = self.config_entry.options.get(CONF_MODULES, list(MODULES))
        schema = vol.Schema({
            vol.Required(CONF_MODULES, default=current): selector.SelectSelector(selector.SelectSelectorConfig(
                options=list(MODULES), multiple=True, mode=selector.SelectSelectorMode.LIST, translation_key=CONF_MODULES)),
        })
        return self.async_show_form(step_id="init", data_schema=schema)
