from itertools import product

from pyspades.common import make_color

from milsim.types import StaticWeather
from milsim.vxl import VxlData
from milsim.maptools import *

name        = "PinpointCompact"
version     = "1.0"
author      = "Siegmentation Fault"
description = "Miniature version of the famous 'Pinpoint' map originally by izzy"

rgen = RNG(self.seed)
huef = rgen.uniform(0.0, 1.0)

water    = rgen.hsvi(0.5, 0.7, hue = huef)
concrete = rgen.hsvi(0.0, 0.3, hue = huef)
fog      = rgen.hsvi(0.1, 0.4, hue = huef)

def on_map_generation(dirname, seed):
    vxl = VxlData()

    for x, y in product(range(512), range(512)):
        vxl.set_point(x, y, 63, water)

    for Δx, Δy in product(range(0, 64), range(-32, 33)):
        vxl.set_point(256 - 64 - Δx, 256 + Δy, 62, concrete)
        vxl.set_point(256 + 64 + Δx, 256 + Δy, 62, concrete)

    for Δx in range(64):
        for Δy in range(Δx // 2 + 1):
            vxl.set_point(256 - Δx, 256 + Δy, 62, concrete)
            vxl.set_point(256 - Δx, 256 - Δy, 62, concrete)
            vxl.set_point(256 + Δx, 256 + Δy, 62, concrete)
            vxl.set_point(256 + Δx, 256 - Δy, 62, concrete)

    vxl.set_point(256, 256, 62, concrete)

    return vxl

def on_environment_generation(dirname, seed):
    weather = StaticWeather()
    weather.clear_sky_fog = fog

    return Environment(
        default  = Dirt,
        build    = Sand,
        water    = Water,
        weather  = weather,
        palette  = {make_color(*concrete): Concrete}
    )

get_entity_location = Entity(
    blue_flag  = (256 - 64, 256, 60),
    green_flag = (256 + 64, 256, 60),
    blue_base  = (256 - 96, 256, 60),
    green_base = (256 + 96, 256, 60),
)

get_spawn_location = Team(
    blue  = Rectangle(x1 = 256 - 96 - 16, x2 = 256 - 96 + 16, y1 = 256 - 32, y2 = 256 + 32),
    green = Rectangle(x1 = 256 + 96 - 16, x2 = 256 + 96 + 16, y1 = 256 - 32, y2 = 256 + 32)
)
