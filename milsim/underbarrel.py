from math import inf

from pyspades.constants import UPDATE_FREQUENCY
from pyspades.common import Vertex3
from pyspades.world import Grenade

from milsim.blast import sendGrenadePacket
from milsim.weapon import UnderbarrelItem
from milsim.types import Item

class GrenadeLauncher(UnderbarrelItem):
    basename = "Grenade Launcher"

    def __init__(self):
        UnderbarrelItem.__init__(self)
        self.grenade = None

    def on_press(self, player):
        if o := self.grenade:
            self.grenade = None

            wo = player.world_object

            r = wo.position.copy()
            v = wo.orientation.normal().copy() * (o.muzzle / 32)

            go = player.protocol.world.create_object(
                Grenade, inf, r, None, v, o.on_explosion(player)
            )

            go.fuse, _, _, _ = go.get_next_collision(UPDATE_FREQUENCY)
            sendGrenadePacket(player.protocol, player.player_id, r, v, go.fuse)

    @property
    def name(self):
        if o := self.grenade:
            return "{} + {}".format(self.basename, o.name)
        else:
            return self.basename

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
