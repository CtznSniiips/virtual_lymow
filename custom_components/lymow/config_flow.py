"""Config flow for Lymow integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
)

from .const import (
    CONF_DOCKED_STILL_POLLS,
    CONF_MOTION_THRESHOLD,
    CONF_MOWER_IP,
    CONF_SCAN_INTERVAL,
    DEFAULT_DOCKED_STILL_POLLS,
    DEFAULT_MOTION_THRESHOLD,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)


class LymowConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Lymow."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}
        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_MOWER_IP])
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=f"Virtual Lymow {user_input[CONF_MOWER_IP]}",
                data=user_input,
            )

        schema = vol.Schema(
            {
                vol.Required(CONF_MOWER_IP): str,
                vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): vol.All(
                    int,
                    vol.Range(min=15, max=3600),
                ),
                vol.Optional(CONF_MOTION_THRESHOLD, default=DEFAULT_MOTION_THRESHOLD): vol.All(
                    vol.Coerce(float),
                    vol.Range(min=1.0, max=255.0),
                ),
                vol.Optional(
                    CONF_DOCKED_STILL_POLLS,
                    default=DEFAULT_DOCKED_STILL_POLLS,
                ): NumberSelector(
                    NumberSelectorConfig(min=1, max=100, step=1, mode=NumberSelectorMode.BOX)
                ),
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return LymowOptionsFlowHandler()


class LymowOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow for Lymow."""

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current = {**self.config_entry.data, **self.config_entry.options}
        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_SCAN_INTERVAL,
                    default=current.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
                ): vol.All(int, vol.Range(min=15, max=3600)),
                vol.Optional(
                    CONF_MOTION_THRESHOLD,
                    default=current.get(CONF_MOTION_THRESHOLD, DEFAULT_MOTION_THRESHOLD),
                ): vol.All(vol.Coerce(float), vol.Range(min=1.0, max=255.0)),
                vol.Optional(
                    CONF_DOCKED_STILL_POLLS,
                    default=current.get(CONF_DOCKED_STILL_POLLS, DEFAULT_DOCKED_STILL_POLLS),
                ): NumberSelector(
                    NumberSelectorConfig(min=1, max=100, step=1, mode=NumberSelectorMode.BOX)
                ),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
