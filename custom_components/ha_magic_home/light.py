# -*- coding: utf-8 -*-
"""
The Ha Magic Home integration light File.
"""
from datetime import timedelta
import logging
import math
from typing import Any
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.components.light import LightEntity
from .iot.device_class import (Endpoint, Capability)

from .iot.common import control_req, report_state

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ColorMode,
    LightEntity,
    LightEntityFeature,
)

from .iot.const import (DOMAIN)

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=1)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up a config entry."""
    _LOGGER.debug('lightInit')
    device_list = hass.data[DOMAIN]['devices'][config_entry.entry_id]["LIGHT"]
    new_entities = []

    for device in device_list:
        new_entities.append(Light(device, config_entry.entry_id))
    if new_entities:
        async_add_entities(new_entities)


class Light(LightEntity):

    def __init__(self, device: Endpoint, entry_id: str):
        self._cookie = device.cookie
        self._capability_map: dict[str, Capability] = {}
        self._appliance_id = device.endpointId
        self._entry_id = entry_id

        self.device_id = device.endpointId
        self._is_on = device.isReachable
        self._attr_is_on = device.isReachable
        if device.isReachable == False:
            self._status = "off"
        else:
            self._status = "on"
        _LOGGER.debug(device.isReachable)
        _LOGGER.debug('status:')
        _LOGGER.debug(self._status)

        self._attr_unique_id = device.endpointId
        self._attr_name = device.friendlyName  #必须使用私有属性 赋值只读
        self._attr_supported_color_modes = set()
        self._attr_color_mode = None

        self._attr_supported_features = LightEntityFeature(0)
        # self._attr_supported_features |= LightEntityFeature.EFFECT
        # self._attr_effect_list = ["Rainbow", "Blink", "Pulse"]

        for capability in device.capabilities:
            for support in capability.actions.supported:
                self._capability_map[support.name] = capability
            if capability.properties.supported == None:
                continue
            for support in capability.properties.supported:
                if support.name == 'colortemp':
                    self._attr_supported_color_modes.add(ColorMode.COLOR_TEMP)
                    self._attr_min_color_temp_kelvin = 2700
                    self._attr_max_color_temp_kelvin = 6500
                elif support.name == 'color':
                    self._attr_supported_color_modes.add(ColorMode.RGB)
                elif support.name == 'brightness':
                    self._attr_supported_color_modes.add(ColorMode.BRIGHTNESS)

        # HA expects brightness to be implied by RGB/COLOR_TEMP.
        if ColorMode.RGB in self._attr_supported_color_modes or \
           ColorMode.COLOR_TEMP in self._attr_supported_color_modes:
            self._attr_supported_color_modes.discard(ColorMode.BRIGHTNESS)

        if self._attr_supported_color_modes:
            self._attr_color_mode = next(iter(self._attr_supported_color_modes))

    async def async_turn_on(self, **kwargs):
        """开启设备"""
        _LOGGER.debug('controlProp:')
        _LOGGER.debug(kwargs)

        res_state = await control_req(self, 'on', "ON")
        if res_state == 0:
            self._is_on = True
            self._attr_is_on = True

        for key, value in kwargs.items():
            _LOGGER.debug(key)
            _LOGGER.debug(value)
            if key == ATTR_BRIGHTNESS:
                value = math.ceil((value / 255) * 100)
            if key == ATTR_COLOR_TEMP_KELVIN:
                value = math.ceil((value - 2700) / (6500 - 2700) * 100)

            await control_req(self, key, value)

    async def async_turn_off(self, **kwargs):
        """关闭设备"""
        _LOGGER.debug('controlProp,%s', kwargs)
        self._is_on = False
        self._attr_is_on = False

        res_state = await control_req(self, 'off', "OFF")
        if res_state == 0:
            self._is_on = False
            self._attr_is_on = False

    async def async_remove(self):
        """Clean up the entity when it is removed from Home Assistant."""
        print(f"Removing entity {self.entity_id}")
        await super().async_remove()

    @property
    def is_on(self):
        """Return if the light is on."""
        return self._attr_is_on

    async def async_update(self) -> None:
        res, res_state = await report_state(self)
        if res_state != 0 or res.event.payload.status != 0:
            return

        for prop in res.context.properties:
            if prop.name == "powerState":
                self._attr_is_on = prop.value.value == "ON"
            elif prop.name == "brightness":
                try:
                    self._attr_brightness = math.ceil(
                        (float(prop.value.value) / 100) * 255
                    )
                except (TypeError, ValueError):
                    _LOGGER.debug("Invalid brightness value: %s", prop.value.value)
            elif prop.name == "colortemp":
                try:
                    self._attr_color_temp_kelvin = math.ceil(
                        (float(prop.value.value) / 100) * (6500 - 2700) + 2700
                    )
                except (TypeError, ValueError):
                    _LOGGER.debug("Invalid color temp value: %s", prop.value.value)
            elif prop.name == "color":
                color = prop.value.value
                if isinstance(color, dict):
                    if all(k in color for k in ("red", "green", "blue")):
                        self._attr_rgb_color = (
                            color["red"],
                            color["green"],
                            color["blue"],
                        )
                elif isinstance(color, (list, tuple)) and len(color) == 3:
                    self._attr_rgb_color = tuple(color)

        if getattr(self, "_attr_color_temp_kelvin", None) is not None:
            self._attr_color_mode = ColorMode.COLOR_TEMP
        elif getattr(self, "_attr_rgb_color", None) is not None:
            self._attr_color_mode = ColorMode.RGB
        elif getattr(self, "_attr_brightness", None) is not None:
            self._attr_color_mode = ColorMode.BRIGHTNESS
        else:
            self._attr_color_mode = ColorMode.ONOFF
