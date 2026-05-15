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

from collections.abc import Iterable
from typing import Dict, Tuple

from dataclasses import dataclass, field

from math import inf, sin, cos

from pyspades.color import interpolate_rgb
from pyspades.common import Vertex3

from milsimlib.engine import Material

@dataclass
class Box:
    xmin : float = -inf
    xmax : float = +inf
    ymin : float = -inf
    ymax : float = +inf
    zmin : float = -inf
    zmax : float = +inf

    def inside(self, v):
        return self.xmin <= v.x <= self.xmax and \
               self.ymin <= v.y <= self.ymax and \
               self.zmin <= v.z <= self.zmax

class Weather:
    clear_sky_fog         = (128, 232, 255)
    complete_coverage_fog = (200, 200, 200)

    def update(self, dt):
        raise NotImplementedError

    def temperature(self) -> float:
        raise NotImplementedError

    def pressure(self) -> float:
        raise NotImplementedError

    def humidity(self) -> float:
        raise NotImplementedError

    def wind(self) -> Tuple[float, float]:
        raise NotImplementedError

    def cloudiness(self) -> float:
        return NotImplementedError

    def fog(self):
        return interpolate_rgb(
            self.clear_sky_fog,
            self.complete_coverage_fog,
            self.cloudiness()
        )

class StaticWeather(Weather):
    def __init__(self, t = 15, p = 101325, φ = 0.3, w = (0, 0), k = 0):
        self.t = t
        self.p = p
        self.φ = φ
        self.w = w
        self.k = k

    def update(self, dt):
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

Vector3i = Tuple[int, int, int]

def void():
    yield from ()

@dataclass
class Environment:
    default  : Material
    build    : Material
    water    : Material
    size     : Box = field(default_factory = Box)
    palette  : Dict[int, Material] = field(default_factory = dict)
    defaults : Iterable[Tuple[Vector3i, Material]] = field(default_factory = void)
    north    : Vertex3 = Vertex3(1, 0, 0)
    weather  : Weather = field(default_factory = StaticWeather)
    ANL      : float = 30.0 # Ambient noise level (dB)

    def apply(self, o):
        o.default = self.default
        o.water   = self.water

        o.apply(self.palette)

        for (x, y, z), M in self.defaults:
            o[x, y, z] = M

    def ofPolar(self, r, θ):
        n = self.north
        x = n.x * cos(θ) - n.y * sin(θ)
        y = n.x * sin(θ) + n.y * cos(θ)

        return Vertex3(r * x, r * y, 0)

    @property
    def temperature(self):
        return self.weather.temperature()

    @property
    def pressure(self):
        return self.weather.pressure()

    @property
    def humidity(self):
        return self.weather.humidity()

    @property
    def wind(self):
        v, d = self.weather.wind()
        return self.ofPolar(v, d)
