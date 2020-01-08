"""Support for STIB (Brussels public transport) information."""
import logging
from datetime import datetime, timedelta
import requests
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle
from homeassistant.const import CONF_NAME, ATTR_ATTRIBUTION, STATE_UNKNOWN
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

_RESOURCE = 'https://opendata-api.stib-mivb.be/OperationMonitoring/4.0/PassingTimeByPoint/'
_POINT_DETAIL_URL = 'https://opendata-api.stib-mivb.be/NetworkDescription/1.0/PointDetail/'

ATTR_NEXT = 'next_departure'
ATTR_UPCOMING = 'upcoming_departure'
ATTR_STOPNAME = 'stop_name'
ATTR_NEXT_DESTINATION = 'next_destination'
ATTR_UPCOMING_DESTINATION = 'upcoming_destination'
ATTR_LINE_ID = 'line'
ATTR_ATTRIBUTION = 'Data provided by opendata-api.stib-mivb.be'


CONF_STOP_LIST = 'station_ids'
CONF_API_KEY = "api_key"
SCAN_INTERVAL = timedelta(seconds=30)
DEFAULT_NAME = 'STIB'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_API_KEY): cv.string,
    vol.Optional(CONF_STOP_LIST, 'station_filter'):
            vol.All(
                cv.ensure_list,
                vol.Length(min=1),
                [cv.string])
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    api_key = config[CONF_API_KEY]
    sensors = []
    stations_list = set(config.get(CONF_STOP_LIST, []))
    interval = SCAN_INTERVAL
    for station in stations_list:
        data = StibData(station,  api_key)
        data.update()
        stop_name = data.stop_name
        for line in data.lines:
            sensors.append(StibSensor(station, line, data, stop_name))
    add_devices(sensors, True)


class StibSensor(Entity):
    def __init__(self, stop_id, line_id, data, stop_name):
        self._stop_id = stop_id
        self._line_id = line_id
        self._data = data
        self._stop_name = stop_name
        self._name = line_id + " " + self._stop_name
        self._state = STATE_UNKNOWN
        self._next = None
        self._next_destination = None
        self._upcoming = None
        self._upcoming_destination = None

    @property
    def name(self):
        return self._name

    @property
    def state(self):
        return self._state

    @property
    def device_state_attributes(self):
        if self._data is not None:
            return {
                    ATTR_STOPNAME: self._stop_name,
                    ATTR_NEXT: self._next,
                    ATTR_NEXT_DESTINATION: self._next_destination,
                    ATTR_UPCOMING: self._upcoming,
                    ATTR_UPCOMING_DESTINATION: self._upcoming_destination,
                    ATTR_LINE_ID: self._line_id,
                    }

    @property
    def icon(self):
        return 'mdi:bus'

    def update(self):
        self._data.update()
        lines = self._data.lines
        if lines is not None and self._line_id in lines:
            passages = lines[self._line_id]
            self._next = passages[0]['minutes']
            self._next_destination = passages[0]['destination']
            self._state = str(self._next) + " (" + self._next_destination + ")"
            if len(passages) == 2:
                self._upcoming = passages[1]['minutes']
                self._upcoming_destination = passages[1]['destination']
                self._state = self._state + " - " + str(self._upcoming) + " (" + self._upcoming_destination + ")"
        else:
            self._next = None
            self._next_destination = None
            self._upcoming = None
            self._upcoming_destination = None
            self._state = ""

class StibData(object):
    def __init__(self, stop,  api_key):
        self.stop = stop
        self.lines = {}
        self.api_key = api_key
        response = requests.get(_POINT_DETAIL_URL + self.stop, headers={'Accept': 'application/json', 'Authorization': 'Bearer ' + self.api_key})
        try:
            self.stop_name = response.json()['points'][0]['name']['fr'].title()
        except:
            _LOGGER.error("STIB Wrong stopID, check %s", self.stop)

    def update(self):
        response = requests.get(_RESOURCE + self.stop, headers={'Accept': 'application/json', 'Authorization': 'Bearer  ' + self.api_key})
        if response.status_code == 200:
            passing_times = response.json()['points'][0]['passingTimes']

            lines = {}

            for passing_time in passing_times:
                line_id = passing_time['lineId']
                
                if 'destination' not in passing_time:
                    continue
                
                destination = passing_time['destination']['fr'].title()
                arrival_time = passing_time['expectedArrivalTime']
                arrival_datetime = datetime.strptime(arrival_time.split('+')[0], '%Y-%m-%dT%H:%M:%S')
                minutes = int(round(abs((arrival_datetime - datetime.now()).total_seconds()) / 60))
                
                passage = {}
                passage['minutes'] = minutes
                passage['destination'] = destination
                
                if line_id not in lines:
                    lines[line_id] = [passage]
                else:
                    if minutes < lines[line_id][0]['minutes']:
                        lines[line_id].insert(0,  passage)
                    else:
                        lines[line_id].append(passage)
                
        else:
            _LOGGER.error("Impossible to get data from STIB api. Response code: %s. Check %s", response.status_code, response.url)
            lines = None

        self.lines = lines
