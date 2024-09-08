from __future__ import annotations

import asyncio

from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.const import (CONF_MODEL, MAJOR_VERSION, MINOR_VERSION)
from homeassistant.helpers.storage import Store

from .const import DOMAIN
import logging

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[str] = ["light"]


class Hub:
    def __init__(self, address: str = None, devices: list = None) -> None:
        """Init Govee dummy hub."""
        self.devices = devices
        self.address = address


UNIQUE_DEVICES = {}


async def async_setup_ble(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Govee BLE"""
    address = entry.unique_id
    assert address is not None
    ble_device = bluetooth.async_ble_device_from_address(hass, address.upper(), True)
    if not ble_device:
        raise ConfigEntryNotReady(
            f"Could not find Govee BLE device with address {address}"
        )

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = Hub(None, address=address)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Govee BLE device from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    if entry.data.get(CONF_MODEL):
        await async_setup_ble(hass, entry)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    if (MAJOR_VERSION, MINOR_VERSION) < (2023, 1):
        raise Exception("unsupported hass version")

    # init storage for registries
    hass.data[DOMAIN] = {}
    return True
