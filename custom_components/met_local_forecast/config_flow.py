"""Config flow for Met.no local forecast integration."""
from __future__ import annotations
import logging
import voluptuous as vol
from typing import Any
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME
from homeassistant.data_entry_flow import FlowResult
from .met_api import MetApi
from .const import DOMAIN, NAME, NotFound

_LOGGER = logging.getLogger(__name__)
STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): str,
        vol.Required(CONF_LATITUDE): float,
        vol.Required(CONF_LONGITUDE): float,
    }
)


async def validate_input(hass: HomeAssistant, lat: float, lon: float) -> dict[str, Any]:
    """Validate the user input allows us to connect."""

    api = MetApi()
    await hass.async_add_executor_job(api.get_complete, lat, lon)
    return {"title": NAME}


@config_entries.HANDLERS.register(DOMAIN)
class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Met.no local forecast."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA
            )

        errors = {}
        lat = user_input[CONF_LATITUDE]
        lon = user_input[CONF_LONGITUDE]
        location_name = user_input[CONF_NAME]
        try:
            await validate_input(self.hass, lat, lon)
        except NotFound:
            errors["base"] = "not_found"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:

            unique_id = f"{str(lat)}{str(lon)}"
            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title=location_name, data=user_input, description=NAME
            )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )
