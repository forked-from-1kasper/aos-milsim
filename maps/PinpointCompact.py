from random import Random as RNG
from colorsys import hsv_to_rgb
from itertools import product

from milsim.types import StaticWeather
from milsim.vxl import VxlData
from milsim.maptools import *

name    = 'PinpointCompact'
version = '1.0'
author  = 'Siegmentation Fault'

byte = lambda x: int(x * 255)

def BGRA(color):
    r, g, b = color
    return r << 16 | g << 8 | b

def gen_color(rgen, hue, minsat = 0.5, maxsat = 1.0):
    r, g, b = hsv_to_rgb(hue, rgen.uniform(minsat, maxsat), 1.0)
    return byte(r), byte(g), byte(b)

def gen_palette(rgen):
    hue = rgen.uniform(0.0, 1.0)

    water    = gen_color(rgen, hue, minsat = 0.5, maxsat = 0.7)
    concrete = gen_color(rgen, hue, minsat = 0.0, maxsat = 0.3)
    fog      = gen_color(rgen, hue, minsat = 0.1, maxsat = 0.4)

    return water, concrete, fog

def on_map_generation(dirname, seed):
    rgen = RNG(seed)
    water, concrete, fog = gen_palette(rgen)

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

    rgen = RNG(seed)
    water, concrete, fog = gen_palette(rgen)

    weather.clear_sky_fog = fog

    palette = dict()
    palette[BGRA(concrete)] = Concrete

    return Environment(
        registry = [Concrete, Dirt, Sand, Water],
        default  = Dirt,
        build    = Sand,
        water    = Water,
        weather  = weather,
        palette  = palette
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
