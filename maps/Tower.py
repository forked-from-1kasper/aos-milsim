from random import randint, random
from itertools import product
from math import radians

from milsim.vxl import VxlData
from milsim.maptools import *

name    = 'Tower'
version = '1.0'
author  = 'Siegmentation Fault'

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

# be sure that player cannot spawn inside the column
pushout = lambda z: z if z % 4 != 0 else z + 1 if random() < 0.5 else z - 1

def get_spawn_location(connection):
    Δ1, Δ2 = randint(33, 61), randint(33, 61)

    if connection.team is connection.protocol.blue_team:
        return pushout(256 - Δ1), pushout(256 - Δ2), 59 - 8 * blue_floor
    elif connection.team is connection.protocol.green_team:
        return pushout(256 + Δ1), pushout(256 + Δ2), 59 - 8 * green_floor
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

def square(vxl, X, Y, Z, size, color):
    for i in range(-size, size + 1):
        vxl.set_point(X + i, Y - size, Z, color)
        vxl.set_point(X + i, Y + size, Z, color)
        vxl.set_point(X - size, Y + i, Z, color)
        vxl.set_point(X + size, Y + i, Z, color)

def dotted_square(vxl, X, Y, Z, size, color):
    for i in range(-size, size + 1):
        if i % 2 == 0:
            vxl.set_point(X + i, Y - size, Z, color)
            vxl.set_point(X + i, Y + size, Z, color)
            vxl.set_point(X - size, Y + i, Z, color)
            vxl.set_point(X + size, Y + i, Z, color)

def stairs(vxl, X, Y, offset, size, color):
    height = 2 * size + 1

    for i in range(-size, size + 1):
        # stairs
        for j in range(-size + 1, size):
            vxl.set_point(X + i, Y + j, offset - (i + size), color)

        # wall
        for k in range(0, height + 1):
            vxl.set_point(X + i, Y - size, offset - k, color)
            vxl.set_point(X + i, Y + size, offset - k, color)

    # platform
    square(vxl, X, Y, offset - height, size + 1, color)
    square(vxl, X, Y, offset - height, size + 2, color)
    square(vxl, X, Y, offset - height, size + 3, color)

    # columns around the stairs
    for k in range(0, height): dotted_square(vxl, X, Y, offset - k, size + 3, color)

# first floor & columns under the building
def basement(vxl, offset):
    for x, y in product(range(-64, 65), range(-64, 65)):
        if max(abs(x), abs(y)) >= 32:
            vxl.set_point(256 + x, 256 + y, offset, CONCRETE)

            if x % 4 == 0 and y % 4 == 0:
                for z in range(offset + 1, 63):
                    vxl.set_point(256 + x, 256 + y, z, STEEL)

def floor(vxl, offset, k):
    for x, y in product(range(-64, 65), range(-64, 65)):
        if max(abs(x), abs(y)) >= 32:
            vxl.set_point(256 + x, 256 + y, offset - 8 * k, CONCRETE)

            if x % 4 == 0 and y % 4 == 0:
                for z in range(offset - 8 * k + 1, offset - 8 * (k - 1)):
                    vxl.set_point(256 + x, 256 + y, z, STEEL)

def on_map_generation(dirname, seed):
    vxl = VxlData()

    for x, y in product(range(512), range(512)):
        vxl.set_point(x, y, 63, WATER)

    offset = 60
    basement(vxl, offset)
    for k in range(1, 8): floor(vxl, offset, k)
    for k in range(0, 8): stairs(vxl, 255, 255, 62 - 7 * k, 3, CONCRETE)

    return vxl

def on_environment_generation(dirname, seed):
    return Environment(
        default  = Dirt,
        build    = Sand2,
        water    = Water,
        palette  = palette,
        size     = Box(xmin = 256 - 64, xmax = 256 + 64, ymin = 256 - 64, ymax = 256 + 64)
    )
