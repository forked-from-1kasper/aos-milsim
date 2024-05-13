from math import radians
import requests

from milsim.types import Weather

class OpenMeteo(Weather):
    url = 'https://api.open-meteo.com/v1/forecast'

    def __init__(self, latitude, longitude):
        self.latitude  = latitude
        self.longitude = longitude
        self.timer     = 0

        self.t = 0
        self.φ = 0
        self.p = 101300
        self.k = 0
        self.w = (0, 0)

        try:
            self.download()
        except Exception as exc:
            pass

    def download(self):
        payload = {
            'latitude':        self.latitude,
            'longitude':       self.longitude,
            'current':         'temperature_2m,relative_humidity_2m,weather_code,cloud_cover,surface_pressure,wind_speed_10m,wind_direction_10m,wind_gusts_10m',
            'wind_speed_unit': 'ms'
        }

        resp = requests.get(self.url, params = payload)
        json = resp.json()['current']

        self.t = json['temperature_2m']              # Celsius
        self.φ = json['relative_humidity_2m'] / 100  # % -> 1
        self.p = json['surface_pressure'] * 100      # hPa -> Pa
        self.k = json['cloud_cover'] / 100           # % -> 1

        self.w = (
            json['wind_speed_10m'],             # m/s
            radians(json['wind_direction_10m']) # deg -> rad
        )

    def update(self, dt):
        self.timer += dt

        if self.timer > 900:
            self.timer = 0

            try:
                self.download()
            except Exception as exc:
                pass

            return True
        else:
            return False

    def temperature(self):
        return self.t

    def pressure(self):
        return self.p

    def humidity(self):
        return self.φ

    def wind(self):
        return self.w

    def cloudiness(self):
        return self.k