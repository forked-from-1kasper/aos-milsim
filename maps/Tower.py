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

from random import randint, choice
from itertools import product
from math import radians

from pyspades.common import make_color

from milsimlib.vxl import VxlData
from milsimlib.maptools import *

name    = 'Tower'
version = '1.1'

StrongConcrete = Material(name = "strong concrete", ricochet = 1.0,  deflecting = radians(5),  durability = 120.0, strength = 5e+6,   density = 2400, absorption = 1e+15, crumbly = False)
StrongSteel    = Material(name = "strong steel",    ricochet = 1.0,  deflecting = radians(5),  durability = 600.0, strength = 500e+6, density = 7850, absorption = 1e+15, crumbly = False)
Sand2          = Material(name = "sand",            ricochet = 0.4,  deflecting = radians(83), durability = 1.0,   strength = 1500,   density = 1600, absorption = 50e+3, crumbly = True)

palette = {
    0xCCCCCC: StrongConcrete,
    0xAAAAAA: StrongSteel,
}

randfloor   = lambda: randint(0, 6)
blue_floor  = randfloor()
green_floor = randfloor()

blue_team_spawn  = [(256 - Δx, 256 - Δy) for Δx, Δy in product(range(33, 61), repeat = 2) if Δx % 4 != 0 or Δy % 4 != 0]
green_team_spawn = [(256 + Δx, 256 + Δy) for Δx, Δy in product(range(33, 61), repeat = 2) if Δx % 4 != 0 or Δy % 4 != 0]

def get_spawn_location(connection):
    if connection.team is connection.protocol.blue_team:
        x, y = choice(blue_team_spawn)
        return x, y, 59 - 8 * blue_floor
    elif connection.team is connection.protocol.green_team:
        x, y = choice(green_team_spawn)
        return x, y, 59 - 8 * green_floor
    else:
        return ServerConnection.get_spawn_location(connection)

def get_entity_location(team, entity_id):
    if entity_id == BLUE_FLAG:
        return 256 - 34, 256 - 34, 60 - 8 * blue_floor
    if entity_id == BLUE_BASE:
        return 256 - 50, 256 - 50, 60 - 8 * blue_floor
    if entity_id == GREEN_FLAG:
        return 256 + 34, 256 + 34, 60 - 8 * green_floor
    if entity_id == GREEN_BASE:
        return 258 + 50, 256 + 50, 60 - 8 * green_floor

def on_flag_capture(conn):
    global green_floor
    global blue_floor

    protocol = conn.protocol
    team     = conn.team.other

    if team is protocol.blue_team:
        blue_floor = randfloor()

    if team is protocol.green_team:
        green_floor = randfloor()

    team.set_base()
    team.base.update()

    team.set_flag()
    team.flag.update()

WATER    = (0, 170, 240)
CONCRETE = (0xCC, 0xCC, 0xCC)
STEEL    = (0xAA, 0xAA, 0xAA)

def rect(xsize, ysize):
    yield from product(range(-xsize, xsize + 1), range(-ysize, ysize + 1))

def inner(vxl, z1, z2, size):
    assert z1 % (2 * size + 1) == 0
    assert z2 % (2 * size + 1) == 0

    concrete = make_color(*CONCRETE)

    for Δx, Δy in rect(2 * size, 2 * size):
        x, y = 256 + Δx, 256 + Δy

        # columns around the tower
        if max(abs(Δx), abs(Δy)) == 2 * size:
            if (Δx + Δy) % 2 == 0:
                vxl.set_column_fast(x, y, z1, z2, z2, concrete)

        # walls covering the stairs
        if abs(Δx) <= size and abs(Δy) == size:
            vxl.set_column_fast(x, y, z1, z2, z2, concrete)

        if abs(Δx) <= size and abs(Δy) < size:
            # the stairs
            for z in range(z1 + 1, z2):
                if (z - 1) % (2 * size + 1) == size - Δx:
                    vxl.set_point(x, y, z, CONCRETE)
        else:
            # floors
            for z in range(z1, z2):
                if z % (2 * size + 1) == 0:
                    vxl.set_point(x, y, z, CONCRETE)

def annulus():
    for Δx, Δy in rect(64, 64):
        if 32 <= max(abs(Δx), abs(Δy)):
            yield Δx, Δy

def outer(vxl, z1, z2):
    steel = make_color(*STEEL)

    for Δx, Δy in annulus():
        x, y = 256 + Δx, 256 + Δy

        if Δx % 4 == 0 and Δy % 4 == 0:
            vxl.set_column_fast(x, y, z1, z2, z2, steel)

        # floors
        for z in range(z1, z2 + 1):
            if z % 8 == z1 % 8:
                vxl.set_point(x, y, z, CONCRETE)

def on_map_generation(dirname, seed):
    vxl = VxlData()

    for x, y in product(range(512), range(512)):
        vxl.set_point(x, y, 63, WATER)

    inner(vxl, z1 = 0, z2 = 63, size = 3)
    outer(vxl, z1 = 4, z2 = 63)

    return vxl

def on_environment_generation(dirname, seed):
    return Environment(
        default = StrongConcrete,
        build   = Sand2,
        water   = Water,
        palette = palette,
        size    = Box(xmin = 256 - 65, xmax = 256 + 65, ymin = 256 - 65, ymax = 256 + 65)
    )
