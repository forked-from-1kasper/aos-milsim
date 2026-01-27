from math import degrees, fmod, acos

from pyspades.collision import distance_3d_vector
from pyspades.common import Vertex3

from milsim.common import Success, Failure, toMeters, dot, xOy, azimuth, needle
from milsim.blast import HighExplosive, HEGrenadeObject, FlashbangObject
from milsim.types import Item

from milsim.grammar import (
    VerbNTR, VerbNP, VerbNPPP, ProgressiveAspect, Possessive,
    ProperNoun, RegularNoun, SemiregularVerb, RegularVerb,
    an_sg, no_pl, you_pr, have_v, not_adv, np_vp_pres, np_vp_past, SG
)

class Kettlebell(Item):
    def __init__(self, mass):
        Item.__init__(self)
        self.mass = mass

    @property
    def name(self):
        return "Kettlebell ({:.0f} kg)".format(self.mass)

def is_reachable(player, target):
    wo1, wo2 = player.world_object, target.world_object
    if 1.5 < distance_3d_vector(wo1.position, wo2.position):
        return "{} is too far".format(target.name)

class MedicalItem(Item):
    def apply(self, player, nickname):
        target = player.get_player(nickname)
        if not target.alive(): return

        if errmsg := is_reachable(player, target):
            return errmsg

        target_np = you_pr if target is player else ProperNoun(target.name)

        match self.treat(target):
            case Success(vp):
                player.inventory.remove(self)

                if target is not player:
                    target.send_chat(
                        np_vp_past(ProperNoun(player.name), vp(you_pr))
                    )

                return np_vp_past(you_pr, vp(target_np))

            case Failure(vp):
                return np_vp_pres(target_np, vp)

bleed_v   = SemiregularVerb(bare = "bleed", ving = "bleeding", ved = "bled", v3sg = "bleeds", vpast = "bled")
bandage_v = RegularVerb("bandage")

not_bleeding_vp = ProgressiveAspect(not_adv(VerbNTR(bleed_v)))
bandage_vp      = VerbNP(bandage_v)

class BandageItem(MedicalItem):
    name = "Bandage"
    mass = 0.250

    def treat(self, target):
        for bodypart in target.body.values():
            if bodypart.arterial or bodypart.venous:
                bodypart.venous = False
                return Success(
                    lambda np: bandage_vp(bodypart.np(Possessive(np, SG)))
                )

        return Failure(not_bleeding_vp)

apply_v      = RegularVerb("apply")
tourniquet_n = RegularNoun("tourniquet")

a_tourniquet_np = an_sg(tourniquet_n)
apply_on_vp     = VerbNPPP(apply_v, "on")

class TourniquetItem(MedicalItem):
    name = "Tourniquet"
    mass = 0.050

    def treat(self, target):
        for bodypart in target.body.values():
            if bodypart.arterial or bodypart.venous:
                bodypart.arterial = False
                return Success(
                    lambda np: apply_on_vp(
                        a_tourniquet_np, bodypart.np(Possessive(np, SG))
                    )
                )

        return Failure(not_bleeding_vp)

fracture_n = RegularNoun("fracture")
splint_v   = RegularVerb("splint")

splint_vp            = VerbNP(splint_v)
have_vp              = VerbNP(have_v)
have_no_fractures_vp = have_vp(no_pl(fracture_n))

class SplintItem(MedicalItem):
    name = "Splint"
    mass = 0.160

    def treat(self, target):
        for bodypart in target.body.values():
            if bodypart.fractured and not bodypart.splint:
                bodypart.splint = True
                return Success(
                    lambda np: splint_vp(bodypart.np(Possessive(np, SG)))
                )

        return Failure(have_no_fractures_vp)

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

class F1GrenadeObject(HEGrenadeObject):
    high_explosive = HighExplosive(0.184, 1000, 1500, 0.5 / 1000, 5.5e-5, 0.46)

class F1GrenadeItem(HandgrenadeItem):
    name          = "F-1 Grenade"
    mass          = 0.600
    grenade_class = F1GrenadeObject

class StunHandgrenadeItem(HandgrenadeItem):
    name          = "M84 Stun Grenade"
    mass          = 0.370
    grenade_class = FlashbangObject
