from dataclasses import dataclass
from typing import Callable
from math import inf

from twisted.internet import reactor

from pyspades.constants import *

from milsim.simulator import cone
from milsim.common import *

class Weapon(Tool):
    on_reload : Callable

    def __init__(self, player):
        self.player    = player
        self.last_shot = -inf

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
                self.player._on_reload()

        self.shooting = value

    def reload(self):
        if self.ammo.full() or self.reloading:
            return

        self.weapon_reload_start = reactor.seconds()
        self.reloading = True

    def is_empty(self, tolerance = CLIP_TOLERANCE) -> bool:
        return self.ammo.current() <= 0

    def update(self, t):
        if self.reloading:
            if t - self.weapon_reload_start >= self.reload_time:
                self.weapon_reload_start = t
                self.reloading = self.ammo.reload()

                self.player._on_reload()

    def lmb(self, t, dt):
        P = self.ammo.current() > 0
        Q = not self.reloading
        R = t - self.last_shot >= self.delay

        if P and Q and R:
            self.last_shot = t
            self.ammo.shoot(1)

            self.player.update_hud()

            o = self.player.world_object
            n = o.orientation.normal()
            r = self.player.eye() + n * 1.2

            sim = self.player.protocol.simulator

            for i in range(self.round.pellets):
                u = toMeters3(o.velocity)
                v = n * gauss(mu = self.round.muzzle, sigma = self.round.muzzle * self.round.deviation)
                sim.add(self.player, r, u + cone(v, self.round.grouping), t, self.round)

class Rifle(Weapon):
    name        = "Rifle"
    Ammo        = Magazines(6, 10)
    round       = R762x54mm
    delay       = 0.50
    reload_time = 2.5

class SMG(Weapon):
    name        = "SMG"
    Ammo        = Magazines(5, 30)
    round       = Parabellum
    delay       = 0.11
    reload_time = 2.5

class Shotgun(Weapon):
    name        = "Shotgun"
    Ammo        = Heap(6, 48)
    round       = Buckshot1
    delay       = 1.00
    reload_time = 0.5

weapons = {RIFLE_WEAPON: Rifle, SMG_WEAPON: SMG, SHOTGUN_WEAPON: Shotgun}
