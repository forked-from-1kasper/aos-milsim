from dataclasses import dataclass
from typing import Callable

from twisted.internet import reactor

from pyspades.constants import *
from milsim.common import *

@dataclass
class Weapon:
    on_reload : Callable

    def __post_init__(self):
        self.reloading = False
        self.shooting  = False
        self.ammo      = None

        self.reset()

    def restock(self):
        self.ammo.restock()

    def reset(self):
        self.ammo = self.Ammo()
        self.shooting = False

    def set_shoot(self, value : bool) -> None:
        if self.shooting != value:
            if value and self.ammo.continuous:
                self.reloading = False
                self.on_reload()

        self.shooting = value

    def reload(self):
        if self.ammo.full() or self.reloading:
            return

        self.weapon_reload_start = reactor.seconds()
        self.reloading = True

    def update(self, t):
        if self.reloading:
            if t - self.weapon_reload_start >= self.reload_time:
                self.weapon_reload_start = t
                self.reloading = self.ammo.reload()

                self.on_reload()

    def is_empty(self, tolerance = CLIP_TOLERANCE) -> bool:
        return self.ammo.current() <= 0

class Rifle(Weapon):
    name               = "Rifle"
    Ammo               = Magazines(6, 10)
    round              = R762x54mm
    delay              = 0.50
    reload_time        = 2.5
    velocity_deviation = 0.05

class SMG(Weapon):
    name               = "SMG"
    Ammo               = Magazines(5, 30)
    round              = Parabellum
    delay              = 0.11
    reload_time        = 2.5
    velocity_deviation = 0.05

class Shotgun(Weapon):
    name               = "Shotgun"
    Ammo               = Heap(6, 48)
    round              = Shot
    delay              = 1.00
    reload_time        = 0.5
    velocity_deviation = 0.10

weapons = {RIFLE_WEAPON: Rifle, SMG_WEAPON: SMG, SHOTGUN_WEAPON: Shotgun}
