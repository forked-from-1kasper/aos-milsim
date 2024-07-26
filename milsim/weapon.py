from math import inf

from twisted.internet import reactor

from pyspades.constants import *

from milsim.simulator import cone
from milsim.common import *

class ABCWeapon(Tool):
    name        = NotImplemented
    Ammo        = type(NotImplemented)
    round       = NotImplemented
    delay       = NotImplemented
    reload_time = NotImplemented

    def __init__(self, player):
        self.player    = player
        self.last_shot = -inf
        self.reloading = False
        self.ammo      = self.Ammo()

        self.reset()

    def restock(self):
        self.ammo.restock()

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

                self.player.on_reload_complete()
                self.player.sendWeaponReload()

    def on_lmb_press(self):
        if self.ammo.continuous:
            self.reloading = False

            self.player.on_reload_complete()
            self.player.sendWeaponReload()

    def on_lmb_hold(self, t, dt):
        P = self.ammo.current() > 0
        Q = not self.reloading
        R = t - self.last_shot >= self.delay

        if P and Q and R:
            self.last_shot = t
            self.ammo.shoot(1)

            self.player.sendWeaponReload()

            o = self.player.world_object
            n = o.orientation.normal()
            r = self.player.eye() + n * 1.2

            sim = self.player.protocol.simulator

            for i in range(self.round.pellets):
                u = toMeters3(o.velocity)
                v = n * gauss(mu = self.round.muzzle, sigma = self.round.muzzle * self.round.deviation)
                sim.add(self.player, r, u + cone(v, self.round.grouping), t, self.round)

    def reset(self):
        pass
