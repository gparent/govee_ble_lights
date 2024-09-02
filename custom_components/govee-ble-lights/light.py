from __future__ import annotations

import math
import logging

from enum import IntEnum
import bleak_retry_connector

from bleak import BleakClient
from homeassistant.components import bluetooth
from homeassistant.components.light import (ATTR_BRIGHTNESS, ATTR_RGB_COLOR, ColorMode, LightEntity,
                                            LightEntityFeature)

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.storage import Store
from homeassistant.util.color import brightness_to_value, color_temperature_to_rgb, value_to_brightness

from .const import DOMAIN
from pathlib import Path
from .govee_utils import prepareMultiplePacketsData, prepareSinglePacketData
import base64
from . import Hub

_LOGGER = logging.getLogger(__name__)

BRIGHTNESS_SCALE = (1, 100)
BRIGHTNESS_MODELS = ['H6006', 'H6008']
COLOR_TEMP_MODELS = ['H6006', 'H6008']
UUID_CONTROL_CHARACTERISTIC = '00010203-0405-0607-0809-0a0b0c0d2b11'

class LedCommand(IntEnum):
    """ A control command packet's type. """
    POWER = 0x01
    BRIGHTNESS = 0x04
    COLOR = 0x05


class LedMode(IntEnum):
    """
    The mode in which a color change happens in.

    Currently only RGBWW is supported.
    """
    RGBWW = 0x0d


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities):
    if config_entry.entry_id in hass.data[DOMAIN]:
        hub: Hub = hass.data[DOMAIN][config_entry.entry_id]
    else:
        return

    if hub.address is not None:
        ble_device = bluetooth.async_ble_device_from_address(hass, hub.address.upper(), False)
        async_add_entities([GoveeBluetoothLight(hub, ble_device, config_entry)])


class GoveeBluetoothLight(LightEntity):
    _attr_supported_color_modes: set[ColorMode]
    _attr_supported_features = LightEntityFeature(
        LightEntityFeature.FLASH | LightEntityFeature.TRANSITION)
    _fixed_color_mode: ColorMode | None = None

    def __init__(self, hub: Hub, ble_device, config_entry: ConfigEntry) -> None:
        """Initialize an bluetooth light."""
        self._mac = hub.address
        self._model = config_entry.data["model"]
        self._is_color_temp = self._model in COLOR_TEMP_MODELS
        self._has_brightness = self._model in BRIGHTNESS_MODELS

        color_modes: set[ColorMode] = {ColorMode.ONOFF}

        if self._is_color_temp:
            color_modes.add(ColorMode.COLOR_TEMP)
            self._attr_min_color_temp_kelvin = 2000
            self._attr_max_color_temp_kelvin = 9000

        if self._has_brightness:
            color_modes.add(ColorMode.BRIGHTNESS)

        self._attr_supported_color_modes = filter_supported_color_modes(color_modes)
        if len(self._attr_supported_color_modes) == 1:
            # If the light supports only a single color mode, set it now
            self._fixed_color_mode = next(iter(self._attr_supported_color_modes))

        self._ble_device = ble_device
        self._state = None
        self._brightness = None

    @property
    def name(self) -> str:
        """Return the name of the switch."""
        return "GOVEE Light"

    @property
    def unique_id(self) -> str:
        """Return a unique, Home Assistant friendly identifier for this entity."""
        return self._mac.replace(":", "")

    @property
    def brightness(self):
        return value_to_brightness(BRIGHTNESS_SCALE, self._brightness)

    @property
    def is_on(self) -> bool | None:
        """Return true if light is on."""
        return self._state

    async def async_turn_on(self, **kwargs) -> None:
        await self._send_command(self.prepareSinglePacketData(LedCommand.POWER, [0x1]))
        self._state = True

        if ATTR_BRIGHTNESS in kwargs:
            brightness = brightness_to_value(BRIGHTNESS_SCALE, kwargs.get(ATTR_BRIGHTNESS, 255))
            await self._send_command(self.prepareSinglePacketData(LedCommand.BRIGHTNESS, [brightness]))
            self._brightness = brightness

        if ATTR_RGB_COLOR in kwargs:
            red, green, blue = (math.ceil(x) for x in kwargs[ATTR_RGB_COLOR])
            await self._send_command(self.prepareSinglePacketData(LedCommand.COLOR, [LedMode.RGBWW, red, green, blue]))

            self._attr_color_mode = ColorMode.RGB
            self._attr_rgb_color = kwargs[ATTR_RGB_COLOR]
        elif ATTR_COLOR_TEMP_KELVIN in kwargs:
            kelvin = kwargs[ATTR_COLOR_TEMP_KELVIN]

            red, green, blue = (math.ceil(x) for x in color_temperature_to_rgb(kelvin))
            kelvin_bytes = kelvin.to_bytes(2)

            await self._send_command(self.prepareSinglePacketData(LedCommand.COLOR,
                                                          [LedMode.RGBWW, red, green, blue,
                                                           int(kelvin_bytes[0]), int(kelvin_bytes[1]),
                                                           red, green, blue]))

            self._attr_color_temp_kelvin = kelvin
            self._attr_color_mode = ColorMode.COLOR_TEMP

    async def async_turn_off(self, **kwargs) -> None:
        await self._send_command(self.prepareSinglePacketData(LedCommand.POWER, [0x0]), False)
        self._state = False

    async def _connectBluetooth(self) -> BleakClient:
        for i in range(3):
            try:
                client = await bleak_retry_connector.establish_connection(BleakClient, self._ble_device, self.unique_id)
                return client
            except:
                continue

    async def _send_command(self, command) -> None:
        client = await self._connectBluetooth()
        await client.write_gatt_char(UUID_CONTROL_CHARACTERISTIC, command, False)
