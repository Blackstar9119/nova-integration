"""Einrichtung von Nova Homeverse: ein Eintrag ohne Eingaben, in den Optionen die aktiven Module."""

from __future__ import annotations

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import CONF_MODULES, DOMAIN, MODULES, OLD_DOMAIN


class NovaConfigFlow(ConfigFlow, domain=DOMAIN):
    """Nova Homeverse einrichten."""

    VERSION = 1

    async def async_step_user(self, user_input=None) -> ConfigFlowResult:
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")
        # Die alte Integration „Nova“ muss vorher weg – beide zusammen vertragen sich nicht
        if self.hass.config_entries.async_entries(OLD_DOMAIN):
            return self.async_abort(reason="old_nova_installed")
        if user_input is not None:
            return self.async_create_entry(title="Nova Homeverse", data={}, options={CONF_MODULES: list(MODULES)})
        return self.async_show_form(step_id="user")

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return NovaOptionsFlow()


class NovaOptionsFlow(OptionsFlow):
    """Module an- und abschalten (landet in den Einstellungen unter module.*)."""

    async def async_step_init(self, user_input=None) -> ConfigFlowResult:
        if user_input is not None:
            mods = [m for m in MODULES if m in user_input[CONF_MODULES]]
            # direkt übernehmen: sind die Optionen unverändert, ruft HA den Update-Listener nicht auf
            if data := self.hass.data.get(DOMAIN):
                data.settings_set({"module": {m: m in mods for m in MODULES}})
            return self.async_create_entry(data={CONF_MODULES: mods})
        # Stand aus den Einstellungen (module.*), die auch per nova_homeverse/settings/set geändert werden können
        data = self.hass.data.get(DOMAIN)
        current = sorted(data.enabled, key=MODULES.index) if data else self.config_entry.options.get(CONF_MODULES, list(MODULES))
        schema = vol.Schema({
            vol.Required(CONF_MODULES, default=current): selector.SelectSelector(selector.SelectSelectorConfig(
                options=list(MODULES), multiple=True, mode=selector.SelectSelectorMode.LIST, translation_key=CONF_MODULES)),
        })
        return self.async_show_form(step_id="init", data_schema=schema)
