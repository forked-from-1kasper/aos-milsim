from math import atan, atan2, tau, floor
from itertools import product
from random import random

from milsim.types import *

randbool = lambda prob: random() <= prob

mm    = lambda s: s / 1000
gram  = lambda m: m / 1000
yard  = lambda s: s * Yard
inch  = lambda s: s * Inch
pound = lambda m: m * Pound
grain = lambda m: m * Pound / 7000
TNT   = lambda m: m * 4.6e+6

isosceles = lambda H, d: atan(0.5 * d / H)

Dirt     = Material(name = "dirt",     ricochet = 0.3,  deflecting = 75, durability = 1.0,  strength = 2500,   density = 1200, absorption = 1e+15,  crumbly = True)
Sand     = Material(name = "sand",     ricochet = 0.4,  deflecting = 83, durability = 1.0,  strength = 1500,   density = 1600, absorption = 1e+15,  crumbly = True)
Wood     = Material(name = "wood",     ricochet = 0.75, deflecting = 80, durability = 3.0,  strength = 2.1e+6, density = 800,  absorption = 50e+3,  crumbly = False)
Concrete = Material(name = "concrete", ricochet = 0.4,  deflecting = 75, durability = 5.0,  strength = 5e+6,   density = 2400, absorption = 100e+3, crumbly = False)
Asphalt  = Material(name = "asphalt",  ricochet = 0.6,  deflecting = 78, durability = 6.0,  strength = 1.2e+6, density = 2400, absorption = 80e+3,  crumbly = False)
Stone    = Material(name = "stone",    ricochet = 0.5,  deflecting = 90, durability = 30.0, strength = 20e+6,  density = 2500, absorption = 5e+5,   crumbly = False)
Brick    = Material(name = "brick",    ricochet = 0.3,  deflecting = 76, durability = 7.0,  strength = 2e+6,   density = 1800, absorption = 80e+3,  crumbly = False)
Steel    = Material(name = "steel",    ricochet = 0.80, deflecting = 77, durability = 10.0, strength = 500e+6, density = 7850, absorption = 150e+3, crumbly = False)
Glass    = Material(name = "glass",    ricochet = 0.0,  deflecting = 0,  durability = 0.15, strength = 7e+6,   density = 2500, absorption = 500,    crumbly = False)
Plastic  = Material(name = "plastic",  ricochet = 0.1,  deflecting = 85, durability = 0.5,  strength = 1e+5,   density = 300,  absorption = 50e+3,  crumbly = True)
Grass    = Material(name = "grass",    ricochet = 0.0,  deflecting = 0,  durability = 1.5,  strength = 100,    density = 50,   absorption = 1e+4,   crumbly = True)
Water    = Material(name = "water",    ricochet = 0.7,  deflecting = 78, durability = 1e+6, strength = 1,      density = 1000, absorption = 1e+15,  crumbly = False)

Shot     = Ball(457.00, grain(82.000),  mm(9.65), 15, isosceles(yard(25), inch(40)))
Buckshot = Ball(396.24, grain(350.000), mm(8.38), 5,  isosceles(yard(25), inch(40)))
Bullet   = Ball(540.00, grain(109.375), mm(10.4), 1,  0)

R145x114mm = G1(1000, gram(67.00), 0.800, mm(14.50))
R127x108mm = G1(900,  gram(50.00), 0.732, mm(12.70))
R762x54mm  = G7(850,  gram(10.00), 0.187, mm(07.62))
Parabellum = G1(600,  gram(8.03),  0.212, mm(09.00))

grenade_zone = lambda x, y, z: product(range(x - 1, x + 2), range(y - 1, y + 2), range(z - 1, z + 2))

dot = lambda u, v: u.x * v.x + u.y * v.y + u.z * v.z
xOy = lambda v: Vertex3(v.x, v.y, 0)
xOz = lambda v: Vertex3(v.x, 0, v.z)
yOz = lambda v: Vertex3(0, v.y, v.z)

def clockwise(v1, v2):
    return atan2(v1.x * v2.y - v1.y * v2.x, v1.x * v2.x + v1.y * v2.y)

def azimuth(E, v):
    φ = clockwise(E.north, v)
    return φ if φ > 0 else φ + tau

def needle(φ):
    label = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
    N     = len(label)
    Δφ    = tau / N
    t     = (φ + Δφ / 2) / Δφ
    return label[floor(t) % N]
