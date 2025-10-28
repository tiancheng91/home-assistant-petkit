"""DataUpdateCoordinator for the PetKit integration."""
from __future__ import annotations

from datetime import timedelta
import json
import asyncio

from petkitaio import PetKitClient
from petkitaio.exceptions import AuthError, PetKitError, RegionError, ServerError
from petkitaio.model import PetKitData


from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    DOMAIN,
    LOGGER,
    POLLING_INTERVAL,
    REGION,
    TIMEOUT,
    TIMEZONE,
    USE_BLE_RELAY,
)


class PetKitDataUpdateCoordinator(DataUpdateCoordinator):
    """PetKit Data Update Coordinator."""

    data: PetKitData

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the PetKit coordinator."""

        if entry.options[TIMEZONE] == "Set Automatically":
            tz = None
        else:
            tz = entry.options[TIMEZONE]
        self.fast_poll_expiration = None
        try:
            self.client = PetKitClient(
                entry.data[CONF_EMAIL],
                entry.data[CONF_PASSWORD],
                session=async_get_clientsession(hass),
                region=entry.options[REGION],
                timezone=tz,
                timeout=TIMEOUT,
            )
            self.client.use_ble_relay = entry.options[USE_BLE_RELAY]
            super().__init__(
                hass,
                LOGGER,
                name=DOMAIN,
                update_interval=timedelta(seconds=entry.options[POLLING_INTERVAL]),
            )
        except RegionError as error:
            raise ConfigEntryAuthFailed(error) from error

    async def _async_update_data(self) -> PetKitData:
        """Fetch data from PetKit."""

        # 尝试获取数据，最多重试一次
        for attempt in range(3):
            try:
                data = await self.client.get_petkit_data()
                nl = '\n'
                LOGGER.debug(f'Found the following PetKit devices/pets: {nl}{json.dumps(data, default=vars, indent=4)}')
                return data
            except TypeError:
                LOGGER.error('Encountered TypeError while formatting returned PetKit devices for logging.')
                return data
            except (AuthError, RegionError) as error:
                # 认证错误不重试，直接抛出
                raise ConfigEntryAuthFailed(error) from error
            except Exception as error:
                await asyncio.sleep(1)
                LOGGER.warning(f'Failed to update PetKit data (attempt {attempt + 1}/3): {error}. Retrying...')

        # 理论上不会到达这里，但为了类型检查添加
        return self.data if self.data is not None else PetKitData()