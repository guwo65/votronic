from homeassistant import config_entries

from .const import DOMAIN


class VotronicConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):

    VERSION = 1

    async def async_step_bluetooth(self, discovery_info):

        await self.async_set_unique_id(discovery_info.address)

        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=discovery_info.name,
            data={
                "address": discovery_info.address,
            },
        )

    async def async_step_user(self, user_input=None):

        return self.async_show_form(step_id="user")
