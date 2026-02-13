# Copyright © 2024–2026 rzrn

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.

# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

from math import inf

from pyspades.constants import UPDATE_FREQUENCY
from pyspades.common import Vertex3
from pyspades.world import Grenade

from milsimlib.blast import HighExplosive, HEGrenadeObject, FlashbangObject, sendGrenadePacket
from milsimlib.weapon import UnderbarrelItem
from milsimlib.common import format_item
from milsimlib.types import Item

class GrenadeLauncher(UnderbarrelItem):
    basename = "M203 Grenade Launcher"

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
                o.grenade_class, player.protocol, player.player_id, inf, r, v
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

            return "Loaded {}".format(format_item(self))
        else:
            return "No grenade launcher to load"

class M433GrenadeObject(HEGrenadeObject):
    high_explosive = HighExplosive(0.040, 1000, 1700, 0.2 / 1000, 7.0e-5, 0.46)

class GrenadeItem(GrenadeCartridge):
    name          = "M433 Grenade"
    mass          = 0.230
    muzzle        = 120
    grenade_class = M433GrenadeObject

class FlashbangItem(GrenadeCartridge):
    name          = "Flashbang"
    mass          = 0.200
    muzzle        = 120
    grenade_class = FlashbangObject
