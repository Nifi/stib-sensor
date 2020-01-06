#########################################################################################
# Stib Sensor
# 
# To obtain stop id visit http://m.stib.be/api/getitinerary.php?line=54&iti=1
# replace line=xx with a line number passing by your stop
# replace iti=2 to obtain the return trip
#########################################################################################

import logging
import re
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

ATTR_NEXT = 'Next departure'
ATTR_UPCOMING = 'Upcoming departure'
ATTR_STOPNAME = 'Stop name'
ATTR_DESTINATION = 'Next Destination'
ATTR_UPCOMING_DESTINATION = 'Upcoming Destination'
ATTR_MODE = 'Mode'
ATTR_LINE_ID = 'line'
ATTR_ATTRIBUTION = 'Data provided by api.stib.be'


ICON = 'mdi:bus'
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
    url = _RESOURCE
    interval = SCAN_INTERVAL
    for station in stations_list:
       d = StibData(station,  api_key)
       d.update()
       data = d.stop_data
       lines = data['lines']
       stop_name = data["stop_name"][0].replace("-", "_").replace(" ","_")
       for l in lines:
           line = lines[l][0]['line']
           sensors.append(StibSensor(station, line, d, stop_name))
    
    add_devices(sensors, True)


class StibSensor(Entity):
    def __init__(self, stop, line, data, name):
        self._stop = stop
        self._line = line
        self._name = name
        self._data = data
        self._stop_name = None
        self._destination = None
        self._state = STATE_UNKNOWN
        self._next = None
        self._upcoming = None
        self._upcoming_destination = None
        self._lines = None
        self._mode = None
        self._line_id = None

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
                    ATTR_DESTINATION: self._destination,
                    ATTR_UPCOMING: self._upcoming,
                    ATTR_UPCOMING_DESTINATION: self._upcoming_destination,
                    ATTR_LINE_ID: self._line_id,
                    ATTR_MODE: self._mode,
                    }
    @property
    def icon(self):
        if self._mode is not None:
            if self._mode == 'B':
                return 'mdi:bus'
            if self._mode == 'T':
                return 'mdi:tram'
            if self.mode == 'M':
                return 'mdi:subway'
        return ICON


    def update(self):
        self._data.update()
        stop_data = self._data.stop_data
        line = 'line_' + str(self._line)
        minutes = -1
        t = []
        d = {}
        state = ""
        other_lines = []
        if stop_data is not None:
            lines = stop_data['lines']
            self._stop_name = stop_data['stop_name']
            for o_line in lines:
                # all_line_id = lines[o_line][0]['mode'] + lines[o_line][0]['line']
                all_line_id = lines[o_line][0]['line']
                other_lines.append(all_line_id)
            self._lines = other_lines
            if line in lines:
                for l in lines[line]:
                    m = lines[line][l]['minutes']
                    t.append(m)
                    d[m] = lines[line][l]['destination']
                    line_id = lines[line][l]['line']
                    self._mode  = None # lines[line][l]['mode']
            else:
                _LOGGER.info("Line %s doesn't stop at stop %s. Check your line number",self._line, self._stop_name)
            if len(t) is not 0:
                minutes = max(t)         
                self._next = min(t)
                self._upcoming = max(t)
                self._line_id = line_id
                self._destination = d[self._next].title()
                self._upcoming_destination = d[self._upcoming].title()
                # self._name = "stib " + self._stop + " " + self._stop_name + " " + self._mode + line_id
                self._name = line_id + " " + self._stop_name
                state = str(self._next) + " (" + self._destination + ")"
                if len(t) == 2:
                    state = state + " - " + str(self._upcoming) + " (" + self._upcoming_destination + ")"
                    
        self._state = state



class StibData(object):
    def __init__(self, stop,  api_key):
        self.stop = stop
        self.stop_data = {}
        self.api_key = api_key
        response = requests.get(_POINT_DETAIL_URL + self.stop, headers={'Accept': 'application/json', 'Authorization': 'Bearer '  + self.api_key})
        try:
            self.stop_name = response.json()['points'][0]['name']['fr']
        except:
             _LOGGER.error("STIB Wrong stopID, check %s", self.stop)

    def update(self):
        response = requests.get(_RESOURCE + self.stop, headers={'Accept': 'application/json', 'Authorization': 'Bearer  '  + self.api_key})
        stop_waiting_times = {}
        stop_waiting_times['stop_name'] = self.stop_name
        if response.status_code == 200:
           passing_times = response.json()['points'][0]['passingTimes']
            
           stop_waiting_times['lines'] = {}
           
           for passing_time in passing_times:
               line_id = passing_time['lineId']
               destination = passing_time['destination']['fr']
               arrival_time = passing_time['expectedArrivalTime']
               arrival_datetime = datetime.strptime(arrival_time.split('+')[0], '%Y-%m-%dT%H:%M:%S')
               minutes = divmod((arrival_datetime - datetime.now()).seconds, 60)[0]
               
               wt_tmp = {}
               wt_tmp['line'] = line_id
               wt_tmp['minutes'] = minutes
               wt_tmp['destination'] = destination
               
               l_key = 'line_' + line_id
               l_idx = 0
               if l_key in stop_waiting_times['lines']:
                   l_idx = len(stop_waiting_times['lines'][l_key])
               else:
                   stop_waiting_times['lines'][l_key] = {}
                   stop_waiting_times['lines'][l_key][l_idx] = {}
               stop_waiting_times['lines'][l_key][l_idx] = wt_tmp  #'lines': {'line_54':{0:{'line':54, 'minutes' : 11, ...}}}
        else:
            _LOGGER.error("Impossible to get data from STIB api. Response code: %s. Check %s", response.status_code, response.url)
            stop_waiting_times = None

        self.stop_data = stop_waiting_times 
