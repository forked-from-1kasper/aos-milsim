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

from math import log, isfinite, sqrt, pi
from random import weibullvariate
import requests

from requests.exceptions import RequestException
from requests.models import Response

import asyncio

from pyspades.logger import getLogger

from milsimlib.engine import shapeScaleWeibull
from milsimlib.types import StaticWeather
from milsimlib.common import clamp

logger = getLogger()

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

class NoiseWeather(StaticWeather):
    def __init__(self, *w, **kw):
        StaticWeather.__init__(self, *w, **kw)

        self.k = 0
        self.λ = 0

        self.wind_speed     = 0
        self.wind_gusts     = 0
        self.wind_direction = 0

        self.apply_noise_stopwatch = Stopwatch(10, self.apply_noise)

    def update(self, dt):
        return self.apply_noise_stopwatch.update(dt)

    def apply_noise(self):
        v = self.wind_speed if self.k < 1e-8 else weibullvariate(self.λ, self.k)
        self.w = (v, self.wind_direction)

    def apply_conditions(self, *, temperature, humidity, pressure, cover,
                         wind_speed, wind_gusts, wind_direction):
        self.t = temperature
        self.φ = humidity
        self.p = pressure
        self.c = cover

        self.wind_speed     = wind_speed
        self.wind_gusts     = wind_gusts
        self.wind_direction = wind_direction

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

        self.k, self.λ = shapeScaleWeibull(0.99, self.wind_gusts, self.wind_speed)

        if not isfinite(self.k) or not isfinite(self.λ):
            # Unable to fit the Weibull distribution, use the simple Rayleigh as a fallback instead.
            # [*] https://en.wikipedia.org/wiki/Rayleigh_distribution
            self.k, self.λ = 2.0, self.wind_speed * sqrt(2 / pi)

        self.apply_noise()

class WebProviderWeather(NoiseWeather):
    def __init__(self, latitude, longitude, *w, **kw):
        NoiseWeather.__init__(self, *w, **kw)

        self.latitude  = latitude
        self.longitude = longitude

        self.web_task() # Because this is called from the non-main thread

        self.download_stopwatch = Stopwatch(900, self.download)

    def send_payload(self) -> Response:
        raise NotImplementedError

    def apply_response(self, json):
        raise NotImplementedError

    def web_task_exception(self, task):
        if exc := task.exception():
            logger.error("GET {url}: unhandled error", url = self.url, exc_info = exc)

    def download(self):
        coro = asyncio.to_thread(self.web_task)
        task = asyncio.create_task(coro)

        task.add_done_callback(self.web_task_exception)

    def web_task(self):
        try:
            resp = self.send_payload()
        except RequestException as exc:
            logger.error('GET {url}: {err}', url = self.url, err = str(exc))
        else:
            logger.info('GET {url} ({status}) took {duration:.2f} s',
                url      = self.url,
                status   = resp.status_code,
                duration = resp.elapsed.total_seconds()
            )

            self.apply_response(resp.json())

    def update(self, dt):
        P = NoiseWeather.update(self, dt)
        Q = self.download_stopwatch.update(dt)
        return P or Q
