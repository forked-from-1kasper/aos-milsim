from itertools import product
from math import radians

from random import randint, choice

from pyspades.common import make_color

from milsim.types import StaticWeather
from milsim.vxl import VxlData
from milsim.maptools import *

name    = 'Babylon'
version = '1.1'
author  = 'Siegmentation Fault'

WetSand = Material(name = "wet sand", ricochet = 0.35, deflecting = radians(89), durability = 5.0, strength = 1500, density = 2000, absorption = 1e+15, crumbly = True)
StrongConcrete = Material(name = "strong concrete", ricochet = 1.0, deflecting = radians(5), durability = 120.0, strength = 5e+6, density = 2400, absorption = 1e+15, crumbly = False)

rgen = RNG(self.seed)

huef = rgen.uniform(0.0, 1.0)

water    = rgen.hsvi(0.5, 0.7, hue = huef)
concrete = rgen.hsvi(0.0, 0.3, hue = huef)
fog      = rgen.hsvi(0.1, 0.4, hue = huef)

height = 15
scale  = 4

wsize, hsize = 16, 16

x0, y0 = 256 - 64, 256 - 64

def gap(vxl, x0, y0, z0):
    pass

def bridge1(vxl, x0, y0, z0):
    for i, j in product(range(scale), range(1, scale - 1)):
        vxl.set_point(x0 + j, y0 + i, z0, concrete)

def stairs1(vxl, x0, y0, z0):
    for i, j in product(range(scale), range(scale)):
        vxl.set_point(x0 + j, y0 + i,     z0 - i, concrete)
        vxl.set_point(x0 + j, y0 + i + 1, z0 - i, concrete)

def stairsrev1(vxl, x0, y0, z0):
    for i, j in product(range(scale), range(scale)):
        vxl.set_point(x0 + j, y0 + i,     z0 + (i - (scale - 1)), concrete)
        vxl.set_point(x0 + j, y0 + i - 1, z0 + (i - (scale - 1)), concrete)

def bridge2(vxl, x0, y0, z0):
    for i, j in product(range(scale), range(1, scale - 1)):
        vxl.set_point(x0 + i, y0 + j, z0, concrete)

def stairs2(vxl, x0, y0, z0):
    for i, j in product(range(scale), range(scale)):
        vxl.set_point(x0 + i,     y0 + j, z0 - i, concrete)
        vxl.set_point(x0 + i + 1, y0 + j, z0 - i, concrete)

def stairsrev2(vxl, x0, y0, z0):
    for i, j in product(range(scale), range(scale)):
        vxl.set_point(x0 + i,     y0 + j, z0 + (i - (scale - 1)), concrete)
        vxl.set_point(x0 + i - 1, y0 + j, z0 + (i - (scale - 1)), concrete)

next1 = {
    stairs1:    [gap],
    stairsrev1: [gap],
    bridge1:    [gap, bridge1, stairs1, stairsrev1],
    gap:        [gap, bridge1, stairs1, stairsrev1]
}

next2 = {
    stairs2:    [gap],
    stairsrev2: [gap],
    bridge2:    [gap, bridge2, stairs2, stairsrev2],
    gap:        [gap, bridge2, stairs2, stairsrev2]
}

xsize, ysize = 2 * wsize * scale, 2 * hsize * scale

def boundary(i, j):
    Δxmin, Δymin = (2 * i + 0) * scale, (2 * j + 0) * scale
    Δxmax, Δymax = (2 * i + 1) * scale, (2 * j + 1) * scale

    return x0 + Δxmin, x0 + Δxmax, y0 + Δymin, y0 + Δymax

def center(i, j):
    xmin, xmax, ymin, ymax = boundary(i, j)
    return (xmin + xmax) / 2, (ymin + ymax) / 2

def boundaries():
    for i, j in product(range(wsize), range(hsize)):
        yield boundary(i, j)

def columns():
    for xmin, xmax, ymin, ymax in boundaries():
        yield xmin, ymin
        yield xmin, ymax - 1

        yield xmax - 1, ymin
        yield xmax - 1, ymax - 1

def floors():
    for xmin, xmax, ymin, ymax in boundaries():
        yield from product(range(xmin, xmax), range(ymin, ymax))

def defaults():
    for x, y in columns():
        for Δz in range(height * scale):
            yield (x, y, 62 - Δz), StrongConcrete

def on_map_generation(dirname, seed):
    vxl = VxlData()

    for x, y in product(range(512), range(512)):
        vxl.set_point(x, y, 63, water)

    for x, y in columns():
        for Δz in range(height * scale):
            vxl.set_point(x, y, 62 - Δz, concrete)

    for x, y in floors():
        for k in range(height + 1):
            vxl.set_point(x, y, 62 - k * scale, concrete)

    step = lambda prev, func: {k : rgen.choice(func[v]) for k, v in prev.items()}

    prev1 = {(i, j) : gap for i, j in product(range(wsize - 1), range(hsize))}
    prev2 = {(i, j) : gap for i, j in product(range(wsize), range(hsize - 1))}

    for k in range(0, height - 1):
        new1, new2 = step(prev1, next1), step(prev2, next2)

        for (i, j), func in new1.items():
            x = x0 + 2 * scale * j
            y = y0 + scale + 2 * scale * i
            z = 62 - k * scale

            func(vxl, x, y, z)

        for (i, j), func in new2.items():
            x = x0 + scale + 2 * scale * j
            y = y0 + 2 * scale * i
            z = 62 - k * scale

            func(vxl, x, y, z)

        prev1, prev2 = new1, new2

    return vxl

def on_environment_generation(dirname, seed):
    weather = StaticWeather(t = 35, φ = 0.65)
    weather.clear_sky_fog = fog

    xmin, _, ymin, _ = boundary(0, 0)
    _, xmax, _, ymax = boundary(wsize - 1, hsize - 1)

    return Environment(
        default  = Dirt,
        build    = WetSand,
        water    = Water,
        size     = Box(xmin = xmin, xmax = xmax, ymin = ymin, ymax = ymax),
        weather  = weather,
        palette  = {make_color(*concrete): Concrete},
        defaults = defaults()
    )

def get_spawn_location(connection):
    protocol = connection.protocol

    if connection.team is protocol.blue_team:
        xmin, xmax, ymin, ymax = boundary(0, 0)

    if connection.team is protocol.green_team:
        xmin, xmax, ymin, ymax = boundary(wsize - 1, hsize - 1)

    x, y = randint(xmin + 1, xmax - 2), randint(ymin + 1, ymax - 2)
    return x, y, protocol.map.get_z(x, y, randint(0, 62))

from pyspades.constants import BLUE_FLAG, GREEN_FLAG, BLUE_BASE, GREEN_BASE

def get_entity_location(team, eid):
    M = team.protocol.map

    if eid == BLUE_BASE:
        x, y = center(0, 0)
        return x + scale, y + scale, 63

    elif eid == GREEN_BASE:
        x, y = center(wsize - 1, hsize - 1)
        return x - scale, y - scale, 63

    elif eid == BLUE_FLAG:
        x, y = center(2, 2)
        return x, y, M.get_z(x, y, randint(0, 62))

    elif eid == GREEN_FLAG:
        x, y = center(wsize - 3, hsize - 3)
        return x, y, M.get_z(x, y, randint(0, 62))
