from math import degrees, fmod, acos

from pyspades.collision import distance_3d_vector
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

def is_reachable(player, target):
    wo1 = player.world_object
    wo2 = target.world_object

    if 1.5 < distance_3d_vector(wo1.position, wo2.position):
        return "{} is too far".format(target.name)

class BandageItem(Item):
    name = "Bandage"
    mass = 0.250

    def apply(self, player, nickname):
        target = player.get_player(nickname)
        if not target.alive(): return

        if errmsg := is_reachable(player, target):
            return errmsg

        for bodypart in target.body.values():
            if bodypart.arterial or bodypart.venous:
                player.inventory.remove(self)

                bodypart.venous = False

                if target is player:
                    return "You bandaged your {}".format(bodypart.label)
                else:
                    target.send_chat("{} bandaged your {}".format(player.name, bodypart.label))
                    return "You bandaged {}'s {}".format(target.name, bodypart.label)

        if target is player:
            return "You are not bleeding"
        else:
            return "{} is not bleeding".format(target.name)

class TourniquetItem(Item):
    name = "Tourniquet"
    mass = 0.050

    def apply(self, player, nickname):
        target = player.get_player(nickname)
        if not target.alive(): return

        if errmsg := is_reachable(player, target):
            return errmsg

        for bodypart in target.body.values():
            if bodypart.arterial:
                player.inventory.remove(self)

                bodypart.arterial = False

                if target is player:
                    return "You put a tourniquet on your {}".format(bodypart.label)
                else:
                    target.send_chat("{} put a tourniquet on your {}".format(player.name, bodypart.label))
                    return "You put a tourniquet on {}'s {}".format(target.name, bodypart.label)

        if target.body.bleeding():
            return "To stop venous bleeding use /bandage /b"
        elif target is player:
            return "You are not bleeding"
        else:
            return "{} is not bleeding".format(target.name)

class SplintItem(Item):
    name = "Splint"
    mass = 0.160

    def apply(self, player, nickname):
        target = player.get_player(nickname)
        if not target.alive(): return

        if errmsg := is_reachable(player, target):
            return errmsg

        for bodypart in target.body.values():
            if bodypart.fractured and not bodypart.splint:
                player.inventory.remove(self)

                bodypart.splint = True

                if target is player:
                    return "You put a splint on your {}".format(bodypart.label)
                else:
                    target.send_chat("{} put a split on your {}".format(player.name, bodypart.label))
                    return "You put a splint on {}'s {}".format(target.name, bodypart.label)

        if target is player:
            return "You have no fractures"
        else:
            return "{} has no fractures".format(target.name)

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
            return "Use /protractor again while facing the second point"
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
            return "Too far"

class HandgrenadeItem(Item):
    pass

class F1GrenadeItem(HandgrenadeItem):
    name = "F-1 Grenade"
    mass = 0.600

    def on_explosion(self, player):
        return player.grenade_exploded

class StunHandgrenadeItem(HandgrenadeItem):
    name = "M84 Stun Grenade"
    mass = 0.370

    def on_explosion(self, player):
        return player.flashbang_exploded
