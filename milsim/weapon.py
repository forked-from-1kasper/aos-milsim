from math import inf

from twisted.internet import reactor

from pyspades.world import Grenade
from pyspades.constants import *

from milsim.engine import cone
from milsim.common import *

class UnderbarrelItem(Item):
    def on_press(self, player):
        pass

    def on_hold(self, player, t, dt):
        pass

    def on_release(self, player):
        pass

    def apply(self, player):
        player.inventory.remove(self)

        if o := player.weapon_object.item_underbarrel:
            player.inventory.push(o)

        player.weapon_object.item_underbarrel = self

class ABCWeapon(Tool):
    name        = NotImplemented
    delay       = NotImplemented
    reload_time = NotImplemented

    def __init__(self, player):
        self.weapon_reload_timer = -inf
        self.player              = player
        self.item_underbarrel    = None

        self.reset()

    def reserve(self):
        raise NotImplementedError

    def restock(self):
        raise NotImplementedError

    def refill(self):
        raise NotImplementedError

    @property
    def mass(self):
        return self._mass + self.magazine.mass + getattr(self.item_underbarrel, 'mass', 0)

    def is_empty(self, tolerance = 0):
        return self.magazine.current() <= 0

    def reserved(self):
        return sum(map(lambda o: o.current(), self.reserve()))

    def can_reload(self):
        return 0 < self.reserved() and self.magazine.current() < self.magazine.capacity

    def reload(self):
        if self.reloading:
            return

        if self.can_reload():
            self.weapon_reload_timer = reactor.seconds()
            self.reloading = True

    def update(self, t):
        if self.reloading and t - self.weapon_reload_timer >= self.reload_time:
            self.weapon_reload_timer = t

            succ, self.reloading = self.magazine.reload(self.reserve())

            if succ is not None:
                i = self.player.inventory
                i.remove(succ)
                i.append(self.magazine)

                self.magazine = succ

            self.player.on_reload_complete()
            self.player.sendWeaponReloadPacket()

    def on_sneak_press(self):
        if self.player.world_object.secondary_fire:
            if o := self.item_underbarrel:
                o.on_press(self.player)

    def on_rmb_press(self):
        if self.player.world_object.sneak:
            if o := self.item_underbarrel:
                o.on_press(self.player)

    def on_sneak_hold(self, t, dt):
        if self.player.world_object.secondary_fire:
            if o := self.item_underbarrel:
                o.on_hold(self.player, t, dt)

    def on_sneak_release(self):
        if o := self.item_underbarrel:
            o.on_release(self.player)

    def on_rmb_release(self):
        if o := self.item_underbarrel:
            o.on_release(self.player)

    def on_lmb_press(self):
        if self.magazine.continuous:
            self.reloading = False

            self.player.on_reload_complete()
            self.player.sendWeaponReloadPacket()

    def on_lmb_hold(self, t, dt):
        P = self.is_empty()
        Q = self.reloading
        R = t - self.last_shot < self.delay

        if P or Q or R:
            return

        if cartridge := self.magazine.eject():
            self.last_shot = t

            o = self.player.world_object
            n = o.orientation.normal()
            r = self.player.eye() + n * 1.2

            engine = self.player.protocol.engine

            for i in range(cartridge.pellets):
                u = toMeters3(o.velocity * 32)
                v = n * gauss(mu = cartridge.muzzle, sigma = cartridge.muzzle * cartridge.deviation)
                engine.add(self.player.player_id, r, u + cone(v, cartridge.grouping), t, cartridge)

            self.player.sendWeaponReloadPacket()

    def reset(self):
        if o := self.item_underbarrel:
            if o.persistent:
                self.player.get_drop_inventory().push(o)

        self.last_shot = -inf
        self.reloading = False
        self.restock()
        self.clear()

    def clear(self):
        self.item_underbarrel = None

    def format_ammo(self):
        return None
