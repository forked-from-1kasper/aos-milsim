from math import degrees, acos, atan, atan2, tau, floor, fmod
from itertools import product

from milsim.simulator import toMeters
from milsim.types import *

from milsim.constants import Pound, Yard, Inch

toMeters3 = lambda v: Vertex3(toMeters(v.x), toMeters(v.y), toMeters(v.z))

mm    = lambda s: s / 1000
gram  = lambda m: m / 1000
yard  = lambda s: s * Yard
inch  = lambda s: s * Inch
pound = lambda m: m * Pound
grain = lambda m: m * Pound / 7000
TNT   = lambda m: m * 4.6e+6
MOA   = lambda x: x * tau / 360 / 60

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

Buckshot1 = Shotshell(name = "Buckshot1", muzzle = 457.00, effmass = grain(82.000),  totmass = gram(150.00), grouping = isosceles(yard(25), inch(40)), deviation = 0.10, diameter = mm(9.65), pellets = 15)
Buckshot2 = Shotshell(name = "Buckshot2", muzzle = 396.24, effmass = grain(350.000), totmass = gram(170.00), grouping = isosceles(yard(25), inch(40)), deviation = 0.10, diameter = mm(8.38), pellets = 5)
Bullet    = Shotshell(name = "Bullet",    muzzle = 540.00, effmass = grain(109.375), totmass = gram(20.00),  grouping = 0,                             deviation = 0.10, diameter = mm(10.4), pellets = 1)

R145x114mm = G1(name = "R145x114mm", muzzle = 1000, effmass = gram(67.00), totmass = gram(191.00), grouping = MOA(0.7), deviation = 0.03, BC = 0.800, caliber = mm(14.50))
R127x108mm = G1(name = "R127x108mm", muzzle = 900,  effmass = gram(50.00), totmass = gram(130.00), grouping = MOA(0.7), deviation = 0.03, BC = 0.732, caliber = mm(12.70))
R762x54mm  = G7(name = "R762x54mm",  muzzle = 850,  effmass = gram(10.00), totmass = gram(22.00),  grouping = MOA(0.7), deviation = 0.03, BC = 0.187, caliber = mm(07.62))
Parabellum = G1(name = "Parabellum", muzzle = 600,  effmass = gram(8.03),  totmass = gram(12.00),  grouping = MOA(2.5), deviation = 0.05, BC = 0.212, caliber = mm(09.00))

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

class Kettlebell(Item):
    def __init__(self, mass):
        Item.__init__(self)
        self.mass = mass

    def print(self):
        return f"Kettlebell ({self.mass:.3f} kg)"

class BandageItem(Item):
    name = "Bandage"
    mass = 0.250

    def apply(self, player):
        for P in player.body.values():
            if P.arterial or P.venous:
                player.inventory.remove(self)
                P.venous = False

                return f"You have bandaged your {P.label}"

        return "You are not bleeding"

class TourniquetItem(Item):
    name = "Tourniquet"
    mass = 0.050

    def apply(self, player):
        for P in player.body.values():
            if P.arterial:
                player.inventory.remove(self)
                P.arterial = False

                return f"You put a tourniquet on your {P.label}"

        return "You are not bleeding"

class SplintItem(Item):
    name = "Splint"
    mass = 0.160

    def apply(self, player):
        for P in player.body.values():
            if P.fractured:
                player.inventory.remove(self)
                P.splint = True

                return f"You put a splint on your {P.label}"

        return "You have no fractures"

class CompassItem(Item):
    name = "Compass"
    mass = 0.050

    def apply(self, player):
        o = xOy(player.world_object.orientation)
        φ = azimuth(player.protocol.environment, o)
        θ = degrees(φ)
        return "{:.0f} deg, {}".format(θ, needle(φ))

class ProtractorItem(Item):
    name = "Protractor"
    mass = 0.150

    def __init__(self):
        Item.__init__(self)
        self.origin = None

    def apply(self, player):
        o = player.world_object.orientation

        if o.length() < 1e-4:
            return

        if self.origin is None:
            self.origin = o.normal().copy()
            return "Use /protractor again while facing the second point."
        else:
            t = dot(o.normal(), self.origin)
            θ = degrees(acos(t))

            self.origin = None
            return "{:.2f} deg".format(θ)

class RangefinderItem(Item):
    name  = "Rangefinder"
    mass  = 0.300
    error = 2.0

    def apply(self, player):
        wo = player.world_object

        if loc := wo.cast_ray(1024):
            # this number is a little wrong, but anyway we’ll truncate the result
            d = wo.position.distance(Vertex3(*loc))
            m = toMeters(d)
            M = m - fmod(m, self.error)

            if m < self.error:
                return "< {:.0f} m".format(self.error)
            else:
                return "{:.0f} m".format(M)
        else:
            return "Too far."
