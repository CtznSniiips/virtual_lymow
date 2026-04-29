"""Config flow for Lymow integration."""

from __future__ import annotations

import ipaddress
import re
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback

from .const import (
    CONF_MOTION_THRESHOLD,
    CONF_MOWER_IP,
    CONF_MOWER_NAME,
    CONF_SCAN_INTERVAL,
    CONF_UNKNOWN_TIMEOUT,
    DEFAULT_MOTION_THRESHOLD,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_UNKNOWN_TIMEOUT,
    DOMAIN,
)

_HOSTNAME_LABEL = re.compile(r"(?!-)[A-Za-z0-9-]{1,63}(?<!-)$")


def _validate_mower_host(value: str) -> str:
    """Validate mower host as either an IP address or hostname."""
    host = vol.Coerce(str)(value).strip()
    if not host:
        raise vol.Invalid("Host cannot be empty")

    try:
        ipaddress.ip_address(host)
    except ValueError:
        normalized = host[:-1] if host.endswith(".") else host
        if len(normalized) > 253 or not normalized:
            raise vol.Invalid("Invalid hostname") from None
        if not all(_HOSTNAME_LABEL.fullmatch(label) for label in normalized.split(".")):
            raise vol.Invalid("Invalid hostname") from None
        return normalized.lower()
    else:
        return host


class LymowConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Lymow."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        schema = vol.Schema(
            {
                vol.Required(CONF_MOWER_NAME): str,
                vol.Required(CONF_MOWER_IP): vol.All(str, _validate_mower_host),
                vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): vol.All(
                    int,
                    vol.Range(min=15, max=3600),
                ),
                vol.Optional(CONF_MOTION_THRESHOLD, default=DEFAULT_MOTION_THRESHOLD): vol.All(
                    vol.Coerce(float),
                    vol.Range(min=1.0, max=255.0),
                ),
                vol.Optional(CONF_UNKNOWN_TIMEOUT, default=DEFAULT_UNKNOWN_TIMEOUT): vol.All(
                    int,
                    vol.Range(min=0, max=1440),
                ),
            }
        )
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                user_input = {**user_input, CONF_MOWER_IP: _validate_mower_host(user_input[CONF_MOWER_IP])}
            except vol.Invalid:
                errors[CONF_MOWER_IP] = "invalid_mower_ip"
            else:
                await self.async_set_unique_id(user_input[CONF_MOWER_IP])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=user_input[CONF_MOWER_NAME],
                    data=user_input,
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
                    CONF_UNKNOWN_TIMEOUT,
                    default=current.get(CONF_UNKNOWN_TIMEOUT, DEFAULT_UNKNOWN_TIMEOUT),
                ): vol.All(int, vol.Range(min=0, max=1440)),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
