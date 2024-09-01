from math import inf

from twisted.internet import reactor

from pyspades.world import Grenade
from pyspades.constants import *

from milsim.simulator import cone
import milsim.blast as blast
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

class GrenadeLauncher(UnderbarrelItem):
    name = "Grenade Launcher"

    def __init__(self):
        UnderbarrelItem.__init__(self)
        self.grenade = None

    def on_press(self, player):
        if o := self.grenade:
            self.grenade = None

            wo = player.world_object

            r = wo.position.copy()

            fuse = 1.0
            if loc := wo.cast_ray(256):
                d = (r - Vertex3(*loc)).length()
                fuse = d / o.muzzle

            v = wo.orientation.normal().copy()
            v *= o.muzzle / 32

            player.protocol.world.create_object(
                Grenade, fuse, r, None, v, o.on_explosion(player)
            )
            blast.effect(player.protocol, player.player_id, r, v, fuse)

    @property
    def mass(self):
        return 1.36 + getattr(self.grenade, 'mass', 0)

class GrenadeCartridge(Item):
    def apply(self, player):
        w = player.weapon_object

        if isinstance(w.item_underbarrel, GrenadeLauncher):
            player.inventory.remove(self)

            if o := w.item_underbarrel.grenade:
                player.inventory.push(o)

            w.item_underbarrel.grenade = self

class GrenadeItem(GrenadeCartridge):
    name   = "Grenade"
    mass   = 0.230
    muzzle = 120

    def on_explosion(self, player):
        return player.grenade_exploded

class FlashbangItem(GrenadeCartridge):
    name   = "Flashbang"
    mass   = 0.200
    muzzle = 120

    def on_explosion(self, player):
        return player.flashbang_exploded

class ABCWeapon(Tool):
    name        = NotImplemented
    delay       = NotImplemented
    reload_time = NotImplemented

    def __init__(self, player):
        self.player           = player
        self.item_underbarrel = None

        self.reset()

    @property
    def mass(self):
        return self._mass + self.magazine.mass + getattr(self.item_underbarrel, 'mass', 0)

    def reload(self):
        if self.reloading:
            return

        if self.magazine.can_reload(self.player.inventory):
            self.weapon_reload_timer = reactor.seconds()
            self.reloading = True

    def is_empty(self, tolerance = 0):
        return self.magazine.current() <= 0

    def update(self, t):
        if self.reloading:
            if t - self.weapon_reload_timer >= self.reload_time:
                self.weapon_reload_timer = t

                self.magazine, self.reloading = self.magazine.reload(self.player.inventory)

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

            sim = self.player.protocol.simulator

            for i in range(cartridge.pellets):
                u = toMeters3(o.velocity)
                v = n * gauss(mu = cartridge.muzzle, sigma = cartridge.muzzle * cartridge.deviation)
                sim.add(self.player, r, u + cone(v, cartridge.grouping), t, cartridge)

            self.player.sendWeaponReloadPacket()

    def reset(self):
        if o := self.item_underbarrel:
            if o.persistent:
                self.player.get_drop_inventory().push(o)

        self.item_underbarrel = None

        self.last_shot = -inf
        self.reloading = False
        self.restock()
