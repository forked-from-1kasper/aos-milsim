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

from random import weibullvariate
from math import log, isfinite
import requests

from requests.exceptions import RequestException
from requests.models import Response

from twisted.internet import threads

from pyspades.logger import getLogger

from milsimlib.types import StaticWeather
from milsimlib.common import clamp

log = getLogger()

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

        self.apply_noise()

class WebProviderWeather(NoiseWeather):
    def __init__(self, latitude, longitude, *w, **kw):
        NoiseWeather.__init__(self, *w, **kw)

        self.latitude  = latitude
        self.longitude = longitude

        try:
            self.download()
        except Exception as exc:
            pass

        self.download_stopwatch = Stopwatch(900, self.download)

    def send_payload(self) -> Response:
        raise NotImplementedError

    def apply_response(self, json):
        raise NotImplementedError

    def download(self):
        threads.deferToThread(self.web_task)

    def web_task(self):
        try:
            resp = self.send_payload()
        except RequestException as exc:
            log.error('GET {url}: {err}', url = self.url, err = str(exc))
        else:
            log.info('GET {url} ({status}) took {duration:.2f} s',
                url      = self.url,
                status   = resp.status_code,
                duration = resp.elapsed.total_seconds()
            )

            self.apply_response(resp.json())

    def update(self, dt):
        P = NoiseWeather.update(self, dt)
        Q = self.download_stopwatch.update(dt)
        return P or Q
