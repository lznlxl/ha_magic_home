# -*- coding: utf-8 -*-
"""
The Ha Magic Home integration binary_sensor File.
"""
from datetime import timedelta
import logging
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorDeviceClass,
)

from .iot.device_class import Endpoint
from .iot.common import report_state
from .iot.const import DOMAIN

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=1)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up binary sensors from a config entry."""
    device_list = hass.data[DOMAIN]["devices"][config_entry.entry_id].get(
        "SENSOR", []
    )
    new_entities = []

    for device in device_list:
        new_entities.append(MotionBinarySensor(device, config_entry.entry_id))
    if new_entities:
        async_add_entities(new_entities)


class MotionBinarySensor(BinarySensorEntity):
    """Motion binary sensor for DNA.SensorControl detectionState."""

    _attr_device_class = BinarySensorDeviceClass.MOTION
    _attr_should_poll = True

    def __init__(self, device: Endpoint, entry_id: str):
        self._entry_id = entry_id
        self.device_id = device.endpointId
        self._cookie = device.cookie
        self._attr_unique_id = device.endpointId
        self._attr_name = device.friendlyName
        self._attr_is_on = device.isReachable

    async def async_update(self) -> None:
        res, res_state = await report_state(self)
        if res_state != 0 or res.event.payload.status != 0:
            return

        for prop in res.context.properties:
            if prop.name == "detectionState":
                self._attr_is_on = prop.value.value == "DETECTED"
                return
