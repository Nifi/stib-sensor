"""Support for STIB (Brussels public transport) information."""
import logging
from datetime import datetime, timedelta
import requests
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.helpers.entity import Entity
from homeassistant.const import ATTR_ATTRIBUTION, STATE_UNKNOWN
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

_POINT_DETAIL_URL = (
    "https://opendata-api.stib-mivb.be/NetworkDescription/1.0/PointDetail/"
)
_PASSING_TIME_URL = (
    "https://opendata-api.stib-mivb.be/OperationMonitoring/4.0/PassingTimeByPoint/"
)

ATTR_NEXT = "next_departure"
ATTR_UPCOMING = "upcoming_departure"
ATTR_STOPNAME = "stop_name"
ATTR_NEXT_DESTINATION = "next_destination"
ATTR_UPCOMING_DESTINATION = "upcoming_destination"
ATTR_LINE = "line"

ATTRIBUTION = "Data provided by opendata-api.stib-mivb.be"

CONF_STOP_LIST = "stops"
CONF_API_KEY = "api_key"
CONF_LANG = "language"
DEFAULT_LANG = "fr"
SCAN_INTERVAL = timedelta(seconds=20)
DEFAULT_NAME = "STIB"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_API_KEY): cv.string,
        vol.Optional(CONF_STOP_LIST): vol.All(
            cv.ensure_list, vol.Length(min=1), [cv.string]
        ),
        vol.Optional(CONF_LANG, default=DEFAULT_LANG): vol.In(["fr", "nl"]),
    }
)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Create the sensor."""
    api_key = config[CONF_API_KEY]
    stops = set(config.get(CONF_STOP_LIST, []))
    lang = config[CONF_LANG]
    stib_data = StibData(stops, api_key, lang)
    stib_data.update()
    sensors = []
    for stop, point_lines in stib_data.lines.items():
        stop_name = stib_data.stop_names[stop]
        for line in point_lines:
            sensors.append(StibSensor(stop, line, stib_data, stop_name))
    add_devices(sensors, True)


class StibSensor(Entity):
    """Representation of a Stib sensor."""

    def __init__(self, stop, line, data, stop_name):
        """Initialize the sensor."""
        self._stop = stop
        self._line = line
        self._data = data
        self._stop_name = stop_name
        self._name = "stib " + stop + " " + line
        self._state = STATE_UNKNOWN
        self._next = None
        self._next_destination = None
        self._upcoming = None
        self._upcoming_destination = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def device_state_attributes(self):
        """Return attributes for the sensor."""
        return {
            ATTR_STOPNAME: self._stop_name,
            ATTR_NEXT: self._next,
            ATTR_NEXT_DESTINATION: self._next_destination,
            ATTR_UPCOMING: self._upcoming,
            ATTR_UPCOMING_DESTINATION: self._upcoming_destination,
            ATTR_LINE: self._line,
            ATTR_ATTRIBUTION: ATTRIBUTION,
        }

    @property
    def icon(self):
        """Return the icon of the sensor."""
        return "mdi:bus"

    def update(self):
        """Get the latest data if needed and update the state attributes."""
        if (datetime.now() - self._data._last_updated) > (SCAN_INTERVAL / 2):
            self._data.update()

        lines = self._data.lines
        if (
            lines is not None
            and self._stop in lines
            and self._line in lines[self._stop]
        ):
            passages = lines[self._stop][self._line]
            self._next = passages[0]["minutes"]
            self._next_destination = passages[0]["destination"]
            self._state = f"{str(self._next)} ({self._next_destination})"
            if len(passages) == 2:
                self._upcoming = passages[1]["minutes"]
                self._upcoming_destination = passages[1]["destination"]
                self._state = f"{self._state} - {str(self._upcoming)} ({self._upcoming_destination})"
        else:
            self._next = None
            self._next_destination = None
            self._upcoming = None
            self._upcoming_destination = None
            self._state = ""


class StibData(object):
    """The Class for handling the data retrieval."""

    def __init__(self, stops, api_key, lang):
        """Initialize the data object."""
        self.stops = stops
        self.lang = lang
        self.lines = {}
        self.headers = {
            "Accept": "application/json",
            "Authorization": "Bearer " + api_key,
        }
        response = requests.get(
            _POINT_DETAIL_URL + "%2C".join(self.stops), headers=self.headers
        )
        self.stop_names = {}
        for point in response.json()["points"]:
            self.stop_names[point["id"]] = point["name"][self.lang].title()
        self._last_updated = None

    def update(self):
        """Get the latest data from opendata-api.stib-mivb.be."""
        response = requests.get(
            _PASSING_TIME_URL + "%2C".join(self.stops), headers=self.headers
        )
        if response.status_code == 200:
            lines = {}
            for point in response.json()["points"]:
                pointId = point["pointId"]
                passingTimes = point["passingTimes"]

                point_lines = {}

                for passing_time in passingTimes:
                    line = passing_time["lineId"]

                    if "destination" not in passing_time:
                        continue

                    destination = passing_time["destination"][self.lang].title()
                    arrival_time = passing_time["expectedArrivalTime"]
                    arrival_datetime = datetime.strptime(
                        arrival_time.split("+")[0], "%Y-%m-%dT%H:%M:%S"
                    )
                    minutes = int(
                        round(
                            abs((arrival_datetime - datetime.now()).total_seconds())
                            / 60
                        )
                    )

                    passage = {}
                    passage["minutes"] = minutes
                    passage["destination"] = destination

                    if line not in point_lines:
                        point_lines[line] = [passage]
                    else:
                        if minutes < point_lines[line][0]["minutes"]:
                            point_lines[line].insert(0, passage)
                        else:
                            point_lines[line].append(passage)
                lines[pointId] = point_lines
            self._last_updated = datetime.now()

        else:
            _LOGGER.error(
                "Impossible to get data from STIB api. Response code: %s. Check %s",
                response.status_code,
                response.url,
            )
            lines = None

        self.lines = lines
