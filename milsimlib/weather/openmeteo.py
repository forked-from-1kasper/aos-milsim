# Copyright © 2024–2026 rzrn

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

from milsimlib.weather.webapi import WebProviderWeather

class OpenMeteo(WebProviderWeather):
    url = 'https://api.open-meteo.com/v1/forecast'

    payload_variables = [
        'temperature_2m',
        'relative_humidity_2m',
        'surface_pressure',
        'wind_speed_10m',
        'wind_direction_10m',
        'wind_gusts_10m',
        'cloud_cover'
    ]

    def send_payload(self):
        payload = {
            'latitude'           : self.latitude,
            'longitude'          : self.longitude,
            'current'            : ','.join(self.payload_variables),
            'temperature_unit'   : 'celsius',
            'precipitation_unit' : 'mm',
            'wind_speed_unit'    : 'ms'
        }

        return requests.get(self.url, params = payload, timeout = 10.0)

    def apply_response(self, json):
        curr = json['current']

        self.apply_conditions(
            temperature    = float(curr['temperature_2m']),             # Celsius
            humidity       = float(curr['relative_humidity_2m']) / 100, # % -> 1
            pressure       = float(curr['surface_pressure']) * 100,     # hPa -> Pa
            cover          = float(curr['cloud_cover']) / 100,          # % -> 1
            wind_speed     = float(curr['wind_speed_10m']),             # m/s
            wind_gusts     = float(curr['wind_gusts_10m']),             # m/s
            wind_direction = radians(float(curr['wind_direction_10m'])) # deg -> rad
        )
