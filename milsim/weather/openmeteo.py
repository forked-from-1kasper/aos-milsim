from math import radians, log, isfinite
from random import weibullvariate
import requests

from milsim.types import Weather
from milsim.common import clamp

class Stopwatch:
    def __init__(self, delay, pingback):
        self.pingback = pingback
        self.delay    = delay
        self.timer    = 0

    def update(self, dt):
        self.timer += dt

        if self.timer > self.delay:
            self.timer = 0

            try:
                self.pingback()
            except Exception as exc:
                pass

            return True
        else:
            return False

class OpenMeteo(Weather):
    url = 'https://api.open-meteo.com/v1/forecast'

    def __init__(self, latitude, longitude):
        self.stopwatch1 = Stopwatch(900, self.download)
        self.stopwatch2 = Stopwatch(10,  self.shake)

        self.latitude  = latitude
        self.longitude = longitude
        self.timer     = 0

        self.t = 0
        self.φ = 0
        self.p = 101300
        self.c = 0
        self.w = (0, 0)

        self.k = 0
        self.λ = 0

        try:
            self.download()
        except Exception as exc:
            pass

    def shake(self):
        v = self.wind_speed if self.k < 1e-8 else weibullvariate(self.λ, self.k)
        self.w = (v, self.wind_direction)

    def download(self):
        variables = [
            'temperature_2m',
            'relative_humidity_2m',
            'surface_pressure',
            'wind_speed_10m',
            'wind_direction_10m',
            'wind_gusts_10m',
            'cloud_cover'
        ]

        payload = {
            'latitude':           self.latitude,
            'longitude':          self.longitude,
            'current':            ",".join(variables),
            'temperature_unit':   'celsius',
            'precipitation_unit': 'mm',
            'wind_speed_unit':    'ms'
        }

        resp = requests.get(self.url, params = payload)
        json = resp.json()['current']

        self.t = float(json['temperature_2m'])              # Celsius
        self.φ = float(json['relative_humidity_2m']) / 100  # % -> 1
        self.p = float(json['surface_pressure']) * 100      # hPa -> Pa
        self.c = float(json['cloud_cover']) / 100           # % -> 1

        self.wind_speed     = float(json['wind_speed_10m'])              # m/s
        self.wind_gusts     = float(json['wind_gusts_10m'])              # m/s
        self.wind_direction = radians(float(json['wind_direction_10m'])) # deg -> rad

        # just to be sure
        if not isfinite(self.t): self.t = 0
        if not isfinite(self.p): self.p = 101300

        self.wind_speed = max(0, self.wind_speed)
        self.wind_gusts = max(0, self.wind_gusts)

        if not isfinite(self.wind_speed):     self.wind_speed     = 0
        if not isfinite(self.wind_gusts):     self.wind_gusts     = 0
        if not isfinite(self.wind_direction): self.wind_direction = 0

        self.φ = clamp(0, 1, self.φ)
        self.c = clamp(0, 1, self.c)

        # Estimate Weibull distribution parameters from two quantiles (https://www.johndcook.com/quantiles_parameters.pdf).
        # For this distribution mean value is Γ(1 + 1/k)(ln2)^(−1/k) times larger than mode.
        # It’s ≈1.4 for k = 1 and approaches 1 as k → +∞, so we take something between.
        p1, x1 = 0.50, self.wind_speed / 1.2
        p2, x2 = 0.99, self.wind_gusts

        ε1, ε2 = -log(1 - p1), -log(1 - p2)

        if x1 < 1e-3:
            self.k = 0 # almost no wind
        elif x2 < 1e-3:
            self.k = 0 # almost no gusts
        else:
            self.k = log(ε2 / ε1) / log(x2 / x1)

        self.λ = x1 / (ε1 ** (1 / self.k))

        self.shake()

    def update(self, dt):
        P = self.stopwatch1.update(dt)
        Q = self.stopwatch2.update(dt)
        return P or Q

    def temperature(self):
        return self.t

    def pressure(self):
        return self.p

    def humidity(self):
        return self.φ

    def wind(self):
        return self.w

    def cloudiness(self):
        return self.c