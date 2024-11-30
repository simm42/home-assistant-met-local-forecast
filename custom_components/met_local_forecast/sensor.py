"""Support for Met.no local forecast service."""
import logging
from dataclasses import dataclass
from datetime import timedelta, datetime
from random import randrange

from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass, SensorEntityDescription, SensorEntity
from homeassistant.components.weather import (
    WeatherEntityFeature, )
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_NAME,
    UnitOfTemperature,
    UnitOfSpeed,
    UnitOfLength, UnitOfPressure, PERCENTAGE,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, NAME
from .met_api import MetApi

_LOGGER = logging.getLogger(__name__)
SCAN_INTERVAL = timedelta(minutes=randrange(40, 50))


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Setup weather platform."""
    _LOGGER.info(f"Adding entities")
    api: MetApi = hass.data[DOMAIN]["api"]
    lat = entry.data[CONF_LATITUDE]
    lon = entry.data[CONF_LONGITUDE]
    name = entry.data[CONF_NAME]

    weather = LocalForecastData(hass, api, name, lat, lon)

    sensors = [
        LocalWeatherSensorEntity(
            hass,
            weather,
            field
        )
        for field in [
            LocalWeatherSensorEntityDescription(
                key="native_temperature",
                unit_of_measurement=UnitOfTemperature.CELSIUS,
                device_class=SensorDeviceClass.TEMPERATURE,
                state_class=SensorStateClass.MEASUREMENT,
            ),
            LocalWeatherSensorEntityDescription(
                key="native_pressure",
                unit_of_measurement=UnitOfPressure.HPA,
                device_class=SensorDeviceClass.PRESSURE,
                state_class=SensorStateClass.MEASUREMENT,
            ),
            LocalWeatherSensorEntityDescription(
                key="humidity",
                unit_of_measurement=PERCENTAGE,
                device_class=SensorDeviceClass.HUMIDITY,
                state_class=SensorStateClass.MEASUREMENT,
            ),
            LocalWeatherSensorEntityDescription(
                key="native_wind_speed",
                unit_of_measurement=UnitOfSpeed.MILES_PER_HOUR,
                device_class=SensorDeviceClass.WIND_SPEED,
                state_class=SensorStateClass.MEASUREMENT,
            ),
        ]
    ]

    async_add_entities(sensors, True)


@dataclass(frozen=True)
class LocalWeatherSensorEntityDescription(SensorEntityDescription):
    pass


class NotReadyError(RuntimeError):
    pass


class LocalForecastData:
    """Representation of a Met.no local forecast sensor."""

    _attr_native_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_native_wind_speed_unit = UnitOfSpeed.METERS_PER_SECOND
    _attr_native_precipitation_unit = UnitOfLength.MILLIMETERS
    _attr_supported_features = WeatherEntityFeature.FORECAST_HOURLY

    def __init__(
        self,
        hass: HomeAssistant,
        met_api: MetApi,
        location_name: str,
        lat: float,
        lon: float,
    ) -> None:
        """Initialize the sensor."""
        self._hass = hass
        self._met_api = met_api
        self.location_name = location_name
        self.lat = lat
        self.lon = lon
        self._raw_data = None
        self._forecast_json = {}
        self._updated = None

    @property
    def unique_id(self) -> str:
        """Return unique ID."""
        return f"local-forecast-{self.location_name}"

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return f"{NAME}: {self.location_name}"

    @property
    def native_temperature(self) -> float:
        """Return the temperature."""
        return self._first_timeserie["data"]["instant"]["details"]["air_temperature"]

    @property
    def native_pressure(self) -> float:
        """Return the pressure."""
        return self._first_timeserie["data"]["instant"]["details"][
            "air_pressure_at_sea_level"
        ]

    @property
    def humidity(self) -> float:
        """Return the humidity."""
        return self._first_timeserie["data"]["instant"]["details"]["relative_humidity"]

    @property
    def native_wind_speed(self) -> float:
        """Return the wind speed."""
        return self._first_timeserie["data"]["instant"]["details"]["wind_speed"]

    @property
    def wind_bearing(self) -> float:
        """Return the wind direction."""
        return self._first_timeserie["data"]["instant"]["details"][
            "wind_from_direction"
        ]

    @property
    def device_info(self):
        """Return the device_info of the device."""
        device_info = DeviceInfo(
            identifiers={(DOMAIN, self.location_name)},
            entry_type=DeviceEntryType.SERVICE,
            name=f"{NAME}: {self.location_name}",
            manufacturer="Met.no",
            model="Met.no local forecast",
            configuration_url="https://www.met.no/en",
        )
        return device_info

    @property
    def _first_timeserie(self):
        if self._raw_data is None:
            raise NotReadyError
        return self._raw_data["properties"]["timeseries"][0]

    async def async_update(self):
        """Retrieve latest state."""
        if self._updated is None or datetime.now() - self._updated > timedelta(seconds=300):
            self._updated = datetime.now()
            self._raw_data = await self._hass.async_add_executor_job(
                self._met_api.get_complete, self.lat, self.lon
            )
            _LOGGER.info("%s updated", self.location_name)


class LocalWeatherSensorEntity(SensorEntity):
    """Base sensor entity."""

    entity_description: SensorEntityDescription

    def __init__(
        self,
        hass: HomeAssistant,
        weather: LocalForecastData,
        description: LocalWeatherSensorEntityDescription,
    ) -> None:
        self._weather = weather
        self.entity_description = description

    async def async_update(self):
        """Retrieve latest state."""
        await self._weather.async_update()

    @property
    def unique_id(self) -> str:
        """Return unique ID."""
        return f"local-forecast-{self._weather.location_name}-{self.entity_description.key}"

    @property
    def native_unit_of_measurement(self) -> str | None:
        return self.entity_description.unit_of_measurement

    @property
    def state_class(self) -> str | None:
        return self.entity_description.state_class

    @property
    def device_class(self) -> str | None:
        return self.entity_description.device_class

    @property
    def native_value(self) -> int | float | None:
        """Return the raw state."""
        _LOGGER.info(f"Looking for {self.entity_description.key}")
        try:
            val = getattr(self._weather, self.entity_description.key)
        except NotReadyError:
            val = -1
        _LOGGER.info(f"returning {val} ({type(val)} for {self.entity_description.key}")
        return val
