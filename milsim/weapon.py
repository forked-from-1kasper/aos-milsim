from dataclasses import dataclass
from typing import Callable
from random import gauss
from math import inf

from twisted.internet.error import AlreadyCalled, AlreadyCancelled
from twisted.internet import reactor

from pyspades.protocol import BaseConnection
from pyspades.constants import *

from milsim.simulator import cone
from milsim.common import Gun

@dataclass
class Weapon:
    conn            : BaseConnection
    gun             : Gun
    reload_callback : Callable

    def __post_init__(self):
        self.reloading   = False
        self.reload_call = None

        self.shooting    = False
        self.defer       = None

        self.ammo        = None
        self.last_shot   = -inf

        self.reset()

    def restock(self):
        self.ammo.restock()

    def reset(self):
        self.cease()
        self.ready()

        self.shooting  = False
        self.ammo      = self.gun.ammo()
        self.last_shot = -inf

    def set_shoot(self, value : bool) -> None:
        if self.shooting != value:
            if value:
                if self.ammo.continuous:
                    self.ready()

                if self.defer is None:
                    self.fire()
            else:
                self.cease()

        self.shooting = value

    def ready(self):
        if self.reload_call is not None:
            try:
                self.reload_call.cancel()
            except (AlreadyCalled, AlreadyCancelled):
                pass

        self.reloading = False

    def cease(self):
        if self.defer is not None:
            try:
                self.defer.cancel()
            except (AlreadyCalled, AlreadyCancelled):
                pass

            self.defer = None

    def fire(self):
        if not self.conn.world_object:
            return

        if self.conn.cannot_work():
            return

        timestamp = reactor.seconds()

        P = self.ammo.current() > 0
        Q = self.reloading and not self.ammo.continuous
        R = timestamp - self.last_shot >= self.gun.delay
        S = self.conn.world_object.sprint or timestamp - self.conn.last_sprint < 0.5
        T = timestamp - self.conn.last_tool_update < 0.5

        if P and not Q and R and not S and not T:
            self.last_shot = timestamp
            self.ammo.shoot(1)

            n = self.conn.world_object.orientation.normal()
            r = self.conn.eye() + n * 1.2

            for i in range(0, self.gun.round.pellets):
                v = n * gauss(mu = self.gun.round.speed, sigma = self.gun.round.speed * self.gun.velocity_deviation)
                self.conn.protocol.sim.add(self.conn, r, cone(v, self.gun.spread), timestamp, self.gun.round)

        self.defer = reactor.callLater(self.gun.delay, self.fire)

    def reload(self):
        if self.reloading: return

        self.reloading   = True
        self.reload_call = reactor.callLater(self.gun.reload_time, self.on_reload)

    def on_reload(self):
        self.reloading = False

        if self.ammo.continuous:
            if self.ammo.full() or self.shooting:
                return

        again = self.ammo.reload()
        self.reload_callback()

        if again: self.reload()

    def is_empty(self, tolerance=CLIP_TOLERANCE) -> bool:
        return self.ammo.current() <= 0
