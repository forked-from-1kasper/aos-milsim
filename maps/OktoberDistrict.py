from itertools import product
from milsim.maptools import *

from milsim.weather.openmeteo import OpenMeteo

name        = "OktoberDistrict"
version     = "1.1"
author      = "Bubochka"
description = "Sgonyaem v magaz?"

palette = {
    0x8D6652: Brick,
    0x997A61: Brick,
    0x997059: Brick,
    0x9E6749: Brick,
    0x9E6343: Brick,
    0x7C6A5E: Concrete,
    0x9E8778: Steel,
    0x756766: Steel,
    0x363638: Asphalt,
    0x857E7E: Concrete,
    0x524B24: Grass,
    0x8B6927: Grass,
    0x8B5528: Grass,
    0x94714D: Plastic,
    0x94673B: Plastic,
    0x3C4B2D: Grass,
    0x323F25: Grass,
    0x945F61: Steel,
    0x945557: Steel,
    0x333333: Steel,
    0x4A5540: Grass,
    0x436947: Grass,
    0x546943: Grass,
    0x866864: Brick,
}

for rgba in 0x6D372E, 0x996B63, 0x884D42, 0x836252, 0x945C3E, 0xA38B78, 0x665630, 0xAA9C74, \
            0x7C6E44, 0x94834D, 0x948B6B, 0x5C5127, 0x888542, 0x4B5831, 0x6E834C, 0x5C727A, \
            0x0066FF, 0x2F3669, 0x001DFF, 0x454549, 0x483A53, 0x884266, 0x6B4F5D, 0x946B6D, \
            0x816658, 0x554840, 0x9C3036, 0xD1BBAF, 0x9C6E70, 0x2C4B2C, 0x615149, 0x9E745E, \
            0x99705B, 0x000000, 0x5C727A, 0x728994, 0x617881, 0x6B584B, 0x6B5F4B, 0x695243, \
            0x7E7294, 0x995E55, 0x839983, 0x839199, 0x949983, 0x996E61, 0x997469, 0x996658, \
            0x554136:
    palette[rgba] = Wood

get_entity_location = Entity(
    blue_flag  = (182, 273, 14),
    green_flag = (327, 273, 14),
    blue_base  = (181, 281, 56),
    green_base = (328, 281, 56)
)

get_spawn_location = Team(
    blue  = Bitmap(x1 = 186, y1 = 268, x2 = 177, y2 = 292, zs = [56, 50, 44]),
    green = Bitmap(x1 = 323, y1 = 268, x2 = 332, y2 = 292, zs = [56, 50, 44])
)

def on_environment_generation(dirname, seed):
    return Environment(
        registry = [Wood, Concrete, Steel, Asphalt, Plastic, Grass, Dirt, Sand, Water, Brick],
        default  = Dirt,
        build    = Sand,
        water    = Water,
        palette  = palette,
        size     = Box(xmin = 160, xmax = 356, ymin = 142, ymax = 370),
        weather  = OpenMeteo(53.902735, 27.555696) # Minsk
    )

on_map_generation = VXL("OktoberDistrict.vxl")
