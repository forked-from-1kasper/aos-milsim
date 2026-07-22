# Copyright © 2026 rzrn

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.

# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

from math import radians
import requests

from pyspades.logger import getLogger

from milsimlib.weather.webapi import WebProviderWeather
from milsimlib.protocol import milsim_google_maps_key

log = getLogger()

class GoogleWeather(WebProviderWeather):
    url = 'https://weather.googleapis.com/v1/currentConditions:lookup'

    def send_payload(self):
        payload = {
            'key'                : milsim_google_maps_key,
            'location.latitude'  : self.latitude,
            'location.longitude' : self.longitude,
            'unitsSystem'        : 'METRIC'
        }

        return requests.get(self.url, params = payload, timeout = 10.0)

    def apply_response(self, json):
        if err := json.get('error'):
            log.error('{mesg}', mesg = err['message'])
        else:
            wind = json['wind']

            self.apply_conditions(
                temperature    = float(json['temperature']['degrees']),                     # Celsius
                humidity       = float(json['relativeHumidity']) / 100,                     # % -> 1
                pressure       = float(json['airPressure']['meanSeaLevelMillibars']) * 100, # mbar -> Pa
                cover          = float(json['cloudCover']) / 100,                           # % -> 1
                wind_speed     = float(wind['speed']['value']) * 10 / 36,                   # km/h -> m/s
                wind_gusts     = float(wind['gust']['value']),                              # km/h -> m/s
                wind_direction = radians(float(wind['direction']['degrees']))               # deg -> rad
            )
