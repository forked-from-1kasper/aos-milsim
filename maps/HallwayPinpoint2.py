# Copyright © 2024 rzrn

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

from itertools import product
from random import randint
from math import radians

from milsimlib.types import StaticWeather
from milsimlib.vxl import VxlData
from milsimlib.maptools import *

name    = 'HallwayPinpoint2'
version = '1.0'
author  = 'izzy (orig.)'

StrongBricks = Material(name = "strong bricks", ricochet = 1.0,  deflecting = radians(5),  durability = 120.0, strength = 5e+6,   density = 2400, absorption = 1e+15, crumbly = False)
Sand2        = Material(name = "sand",          ricochet = 0.4,  deflecting = radians(83), durability = 1.0,   strength = 1500,   density = 1600, absorption = 50e+3, crumbly = True)

height = lambda x: abs(x - 256) // 8
width  = lambda y: abs(y - 256) * 8
wall1  = lambda y: max(0, 256 - width(y) + 1)
wall2  = lambda y: min(256 + width(y) - 1, 511)

uniform = lambda a, b: a if b <= a else randint(a, b)

def get_spawn_location(connection):
    M = connection.protocol.map

    y = randint(256 - 16, 256 + 16)

    if connection.team is connection.protocol.blue_team:
        x = uniform(32, min(wall1(y), 256 - 64))
        return x, y, M.get_z(x, y, height(x) + 1)
    elif connection.team is connection.protocol.green_team:
        x = uniform(max(256 + 64, wall2(y) + 1), 512 - 32)
        return x, y, M.get_z(x, y, height(x) + 1)
    else:
        return ServerConnection.get_spawn_location(connection)

def get_entity_location(team, entity_id):
    if entity_id == BLUE_FLAG:
        return 256 - 128, 256, 63 - height(256 - 128)
    if entity_id == BLUE_BASE:
        return 256 - 146, 256, 63 - height(256 - 146)
    if entity_id == GREEN_FLAG:
        return 256 + 128, 256, 63 - height(256 + 128)
    if entity_id == GREEN_BASE:
        return 256 + 146, 256, 63 - height(256 + 146)

def defaults():
    for x, Δy in product(range(512), range(64)):
        z = height(x)

        yield (x, 256 - Δy, 63 - z), StrongBricks
        yield (x, 256 - Δy, z),      StrongBricks
        yield (x, 256 - Δy, 0),      StrongBricks
        yield (x, 256 + Δy, 63 - z), StrongBricks
        yield (x, 256 + Δy, z),      StrongBricks
        yield (x, 256 + Δy, 0),      StrongBricks

    for y in range(256 - 64, 256 + 65):
        x1, x2 = wall1(y), wall2(y)

        if x1 < x2:
            for z, Δx in product(range(64), range(8)):
                yield (x1 + Δx, y, z), StrongBricks
                yield (x2 - Δx, y, z), StrongBricks

rgen = RNG(self.seed)
huef = rgen.uniform(0, 1)

def on_map_generation(dirname, seed):
    vxl = VxlData()

    water = rgen.hsvi(0.5, 0.7, hue = huef)

    for x, y in product(range(512), range(512)):
        vxl.set_point(x, y, 63, water)

    for x, Δy in product(range(512), range(64)):
        z = height(x)

        vxl.set_column_fast(x, 256 - Δy, 63 - z, 63, 0, 0)
        vxl.set_column_fast(x, 256 + Δy, 63 - z, 63, 0, 0)

        vxl.set_column_fast(x, 256 - Δy, 0, z, 0, 0)
        vxl.set_column_fast(x, 256 + Δy, 0, z, 0, 0)

        vxl.set_point(x, 256 - Δy, 63 - z, rgen.hsvi(hue = huef))
        vxl.set_point(x, 256 - Δy, z,      rgen.hsvi(hue = huef))
        vxl.set_point(x, 256 - Δy, 0,      rgen.hsvi(hue = huef))
        vxl.set_point(x, 256 + Δy, 63 - z, rgen.hsvi(hue = huef))
        vxl.set_point(x, 256 + Δy, z,      rgen.hsvi(hue = huef))
        vxl.set_point(x, 256 + Δy, 0,      rgen.hsvi(hue = huef))

    for y in range(256 - 64, 256 + 65):
        x1, x2 = wall1(y), wall2(y)

        for x in range(x1, x2):
            vxl.set_column_fast(x, y, 1, 63, 0, 0)

        if x1 < x2:
            for z, Δx in product(range(64), range(8)):
                vxl.set_point(x1 + Δx, y, z, rgen.hsvi(hue = huef))
                vxl.set_point(x2 - Δx, y, z, rgen.hsvi(hue = huef))

    return vxl

def on_environment_generation(dirname, seed):
    weather = StaticWeather()
    weather.clear_sky_fog = rgen.hsvi(0.1, 0.4, hue = huef)

    return Environment(
        default  = Dirt,
        build    = Sand2,
        water    = Water,
        size     = Box(ymin = 256 - 64, ymax = 256 + 65),
        defaults = defaults(),
        weather  = weather
    )
