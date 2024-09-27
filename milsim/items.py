from math import degrees, fmod, acos

from pyspades.common import Vertex3

from milsim.common import toMeters, dot, xOy, azimuth, needle
from milsim.types import Item

class Kettlebell(Item):
    def __init__(self, mass):
        Item.__init__(self)
        self.mass = mass

    @property
    def name(self):
        return f"Kettlebell ({self.mass:.0f} kg)"

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

        if player.body.bleeding():
            return "To stop venous bleeding use /bandage /b"
        else:
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
