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

from itertools import product

from pyspades.constants import GRENADE_DESTROY, SPADE_TOOL, BLOCK_TOOL, WEAPON_TOOL, GRENADE_TOOL
from pyspades.collision import vector_collision
from pyspades import contained as loaders
from pyspades.common import Vertex3

from milsimlib.common import grenade_zone, TNT, gram, iempty, floor3
from milsimlib.blast import flashbang_effect
from milsimlib.items import HandgrenadeItem

def get_spread_modifier(self):
    svth = self.protocol.suppression_threshold

    return max(
        self.suppression_spread_modifier * max(0, self.suppression_value - svth) / (1 - svth),
        self.bleeding_spread_modifier if self.body.bleeding() else 0.0,
        self.fracture_spread_modifier if self.body.fractured() else 0.0,
    )

def handgrenades(self):
    return filter(lambda o: isinstance(o, HandgrenadeItem), self.inventory)

def sync(self):
    if self.blocks <= self.blocks_refill_threshold or self.grenades <= 0 and not iempty(self.handgrenades()):
        self.blocks = 50 # due to the limitations of protocol we simply assume that each player has unlimited blocks
        self.grenades = 3 # this is what shown to player, not the actual count

        self.send_contained(loaders.Restock())

        if self.hp != 100:
            contained          = loaders.SetHP()
            contained.hp       = self.hp
            contained.source_x = 0
            contained.source_y = 0
            contained.source_z = 0
            contained.not_fall = False
            self.send_contained(contained)

    self.sendWeaponReloadPacket()

    if self.tool == GRENADE_TOOL and iempty(self.handgrenades()):
        # make GRENADE_TOOL unavailable to user
        if self.weapon_object.enabled():
            self.set_tool(WEAPON_TOOL)
        elif self.block_object.enabled():
            self.set_tool(BLOCK_TOOL)
        else:
            self.set_tool(SPADE_TOOL)

def alive(self):
    return self.team is not None and not self.team.spectator and \
           self.world_object is not None and not self.world_object.dead

def dead(self):
    return not self.alive()

def moving(self):
    return self.world_object.up or self.world_object.down or \
           self.world_object.left or self.world_object.right

def height(self):
    if o := self.world_object:
        return 1.05 if o.crouch else 1.1

def eye(self):
    if o := self.world_object:
        return Vertex3(o.position.x, o.position.y, o.position.z - self.height())

def floor(self):
    if o := self.world_object:
        x, y, z = floor3(o.position)

        Δz = 2 if o.crouch else 3
        return x, y, z + Δz

def get_drop_inventory(self):
    if wo := self.world_object:
        x, y, z = floor3(wo.position)

        return self.protocol.new_item_entity(
            x, y, self.protocol.map.get_z(x, y, z)
        )

def get_available_inventory(self):
    if wo := self.world_object:
        r = wo.position

        x, y, z = floor3(r)

        for X, Y in product(range(x - 1, x + 2), range(y - 1, y + 2)):
            if Z := self.protocol.map.get_z(X, Y, zmin = z, zmax = z + 4):
                if i := self.protocol.get_item_entity(X, Y, Z):
                    yield i

        for team in self.protocol.team_1, self.protocol.team_2:
            if team.base is None: continue

            if vector_collision(r, team.base):
                yield team.tent_inventory

def get_available_items(self):
    for i in self.get_available_inventory():
        for o in i: yield i, o

def drop(self, ID):
    if o := self.inventory[ID]:
        if o.persistent:
            self.get_drop_inventory().push(o)

        self.inventory.remove(o)
        self.sync()

        return o

def drop_inventory(self):
    if self.world_object is not None:
        di = self.get_drop_inventory()

        di.extend(filter(lambda o: o.persistent, self.inventory))

        if wt := self.handheld_radio_item:
            if wt.persistent:
                di.push(wt)

    self.handheld_radio_item = None
    self.inventory.clear()

def gear_mass(self):
    return (
        sum(map(lambda o: o.mass, self.inventory)) +
        self.spade_object.mass + self.block_object.mass +
        self.weapon_object.mass + self.grenade_object.mass
    )

def item_shown(self, t):
    P = not self.world_object.sprint
    Q = 0.5 <= t - self.last_sprint
    R = 0.5 <= t - self.last_tool_update

    return P and Q and R

import horseradish.commands

def get_player(self, nickname):
    if nickname is None:
        return self
    else:
        return horseradish.commands.get_player(
            self.protocol, nickname
        )

def grenade_destroy(self, x, y, z):
    if x < 0 or x > 512 or y < 0 or y > 512 or z < 0 or z > 63:
        return False

    if self.on_block_destroy(x, y, z, GRENADE_DESTROY) == False:
        return False

    for X, Y, Z in grenade_zone(x, y, z):
        self.protocol.engine.smash(self.player_id, X, Y, Z, TNT(gram(60)))

        if e := self.protocol.get_tile_entity(X, Y, Z):
            e.on_explosion()

    return True

def grenade_exploded(self, grenade):
    raise NotImplementedError("Use `HighExplosive.explode()` instead")

def flashbang_exploded(self, grenade):
    if self.name is None:
        return

    self.protocol.create_map_task(
        flashbang_effect(self.protocol, self.player_id, grenade.position.copy())
    )

def get_tool_object(self, tool):
    if tool == SPADE_TOOL:
        return self.spade_object

    if tool == BLOCK_TOOL:
        return self.block_object

    if tool == WEAPON_TOOL:
        return self.weapon_object

    if tool == GRENADE_TOOL:
        return self.grenade_object
