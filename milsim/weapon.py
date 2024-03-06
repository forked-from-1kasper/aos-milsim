from dataclasses import dataclass
from typing import Callable
from random import gauss
from math import inf

from twisted.internet.error import AlreadyCalled, AlreadyCancelled
from twisted.internet import reactor

from pyspades.protocol import BaseConnection
from pyspades.constants import *

from milsim.common import Gun

@dataclass
class Weapon:
    conn            : BaseConnection
    gun             : Gun
    reload_callback : Callable

    def __post_init__(self):
        self.reloading = False
        self.shooting  = False
        self.ammo      = None

        self.reset()

    def restock(self):
        self.ammo.restock()

    def reset(self):
        self.ammo = self.gun.ammo()
        self.shooting = False

    def set_shoot(self, value : bool) -> None:
        if self.shooting != value:
            if value and self.ammo.continuous:
                self.reloading = False
                self.reload_callback()

        self.shooting = value

    def reload(self):
        if self.ammo.full() or self.reloading:
            return

        self.weapon_reload_start = reactor.seconds()
        self.reloading = True

    def update(self, t):
        if self.reloading:
            if t - self.weapon_reload_start >= self.gun.reload_time:
                self.weapon_reload_start = t
                self.reloading = self.ammo.reload()

                self.reload_callback()

    def is_empty(self, tolerance = CLIP_TOLERANCE) -> bool:
        return self.ammo.current() <= 0
