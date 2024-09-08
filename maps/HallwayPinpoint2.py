from random import randint, Random
from colorsys import hsv_to_rgb
from itertools import product

from pyspades.constants import *
from milsim.vxl import VxlData

from milsim.common import *

name    = 'HallwayPinpoint2'
version = '1.0'
author  = 'Siegmentation Fault'

StrongBricks = Material(name = "strong bricks", ricochet = 1.0,  deflecting = 5,  durability = 120.0, strength = 5e+6,   density = 2400, absorption = 1e+15, crumbly = False)
Sand2        = Material(name = "sand",          ricochet = 0.4,  deflecting = 83, durability = 1.0,   strength = 1500,   density = 1600, absorption = 50e+3, crumbly = True)

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
        z = M.get_z(x, y, height(x) + 1)

        return x, y, z
    elif connection.team is connection.protocol.green_team:
        x = uniform(max(256 + 64, wall2(y) + 1), 512 - 32)
        z = M.get_z(x, y, height(x) + 1)

        return x, y, z
    else:
        return ServerConnection.get_spawn_location(connection)

def get_entity_location(team, entity_id):
    if entity_id == BLUE_FLAG:
        return (256 - 128, 256, 63 - height(256 - 128))
    if entity_id == BLUE_BASE:
        return (256 - 146, 256, 63 - height(256 - 146))
    if entity_id == GREEN_FLAG:
        return (256 + 128, 256, 63 - height(256 + 128))
    if entity_id == GREEN_BASE:
        return (256 + 146, 256, 63 - height(256 + 146))

byte = lambda x: int(x * 255)

def texture(hue, rgen):
    r, g, b = hsv_to_rgb(hue, rgen.uniform(0.5, 1.0), 1.0)
    return byte(r), byte(g), byte(b)

WATER = (0, 170, 240)

def defaults():
    for x, Δy in product(range(512), range(64)):
        z = height(x)

        yield ((x, 256 - Δy, 63 - z), StrongBricks)
        yield ((x, 256 - Δy, z),      StrongBricks)
        yield ((x, 256 - Δy, 0),      StrongBricks)
        yield ((x, 256 + Δy, 63 - z), StrongBricks)
        yield ((x, 256 + Δy, z),      StrongBricks)
        yield ((x, 256 + Δy, 0),      StrongBricks)

    for y in range(256 - 64, 256 + 65):
        x1, x2 = wall1(y), wall2(y)

        if x1 < x2:
            for z, Δx in product(range(64), range(8)):
                yield ((x1 + Δx, y, z), StrongBricks)
                yield ((x2 - Δx, y, z), StrongBricks)

def on_map_generation(dirname, seed):
    vxl = VxlData()

    rgen = Random(seed)
    hue = rgen.uniform(0, 1)

    for x, y in product(range(512), range(512)):
        vxl.set_point(x, y, 63, WATER)

    for x, Δy in product(range(512), range(64)):
        z = height(x)

        vxl.set_column_fast(x, 256 - Δy, 63 - z, 63, 0, 0)
        vxl.set_column_fast(x, 256 + Δy, 63 - z, 63, 0, 0)

        vxl.set_column_fast(x, 256 - Δy, 0, z, 0, 0)
        vxl.set_column_fast(x, 256 + Δy, 0, z, 0, 0)

        vxl.set_point(x, 256 - Δy, 63 - z, texture(hue, rgen))
        vxl.set_point(x, 256 - Δy, z,      texture(hue, rgen))
        vxl.set_point(x, 256 - Δy, 0,      texture(hue, rgen))
        vxl.set_point(x, 256 + Δy, 63 - z, texture(hue, rgen))
        vxl.set_point(x, 256 + Δy, z,      texture(hue, rgen))
        vxl.set_point(x, 256 + Δy, 0,      texture(hue, rgen))

    for y in range(256 - 64, 256 + 65):
        x1, x2 = wall1(y), wall2(y)

        for x in range(x1, x2):
            vxl.set_column_fast(x, y, 1, 63, 0, 0)

        if x1 < x2:
            for z, Δx in product(range(64), range(8)):
                vxl.set_point(x1 + Δx, y, z, texture(hue, rgen))
                vxl.set_point(x2 - Δx, y, z, texture(hue, rgen))

    return vxl

def on_environment_generation(dirname, seed):
    return Environment(
        registry = [StrongBricks, Dirt, Sand2, Water],
        default  = Dirt,
        build    = Sand2,
        water    = Water,
        size     = Box(ymin = 256 - 64, ymax = 256 + 65),
        defaults = defaults()
    )
