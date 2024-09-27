from itertools import product

from pyspades.common import make_color

from milsim.types import StaticWeather
from milsim.vxl import VxlData
from milsim.maptools import *

name        = "pinline2"
version     = "1.0"
author      = "Siegmentation Fault"
description = "Automatically generated version of the 'pinline' map by izzy/danke"

rgen = RNG(self.seed)
huef = rgen.uniform(0.0, 1.0)

water    = rgen.hsvi(0.5, 0.7, hue = huef)
concrete = rgen.hsvi(0.0, 0.3, hue = huef)
fog      = rgen.hsvi(0.1, 0.4, hue = huef)

def on_map_generation(dirname, seed):
    vxl = VxlData()

    for x, y in product(range(512), range(512)):
        vxl.set_point(x, y, 63, water)

    for x, y in product(range(64, 512 - 64), (255, 256)):
        vxl.set_point(x, y, 62, concrete)

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
    blue_flag  = (256 - 64,  256, 60),
    green_flag = (256 + 64,  256, 60),
    blue_base  = (256 - 128, 256, 60),
    green_base = (256 + 128, 256, 60),
)

get_spawn_location = Team(
    blue  = Rectangle(x1 = 256 - 128, x2 = 256 - 128 - 32, y1 = 255, y2 = 257),
    green = Rectangle(x1 = 256 + 128, x2 = 256 + 128 + 32, y1 = 255, y2 = 257)
)
