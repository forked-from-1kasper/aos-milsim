from pyspades.common import Vertex3
from pyspades.world import Grenade

from milsim.blast import sendGrenadePacket
from milsim.weapon import UnderbarrelItem
from milsim.types import Item

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
            sendGrenadePacket(player.protocol, player.player_id, r, v, fuse)

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
