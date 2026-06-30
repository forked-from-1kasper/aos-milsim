# Copyright © 2011–2012 Mathias Kaerlev
# Copyright © 2017–2019, 2021 NotAFile
# Copyright © 2019–2020 Jipok
# Copyright © 2021 MuffinTastic
# Copyright © 2022–2024 DryByte
# Copyright © 2024–2026 rzrn

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

from random import choice, uniform
from time import monotonic
from math import floor

from pyspades.packet import register_packet_handler
from pyspades.collision import collision_3d
from pyspades import contained as loaders
from pyspades.player import check_nan
from pyspades.world import cube_line
from pyspades.common import Vertex3

from pyspades.constants import (
    SPADE_TOOL, BLOCK_TOOL, GRENADE_TOOL, MELEE, MELEE_KILL,
    BUILD_BLOCK, DESTROY_BLOCK, MAX_BLOCK_DISTANCE
)

from piqueserver.player import FeatureConnection

from milsimlib.common import ilen, clamp

SHOVEL_GUARANTEED_DAMAGE = 50

@register_packet_handler(loaders.SetTool)
def on_tool_change_recieved(self, contained):
    if self.dead(): return

    if self.tool == contained.value:
        return

    if self.on_tool_set_attempt(contained.value) == False:
        # Reset tool back for the player.
        self.send_contained(self.newSetTool())
        # Needed to keep server synchronized with the player’s UI.
        self.last_tool_update = monotonic()
    else:
        self.set_tool(contained.value, sender = self)

@register_packet_handler(loaders.WeaponInput)
def on_weapon_input_recieved(self, contained):
    if self.dead(): return

    primary   = contained.primary
    secondary = contained.secondary

    if self.world_object.primary_fire != primary:
        if primary:
            self.tool_object.on_lmb_press()
        else:
            self.tool_object.on_lmb_release()

        self.world_object.primary_fire = primary

    if self.world_object.secondary_fire != secondary:
        if secondary:
            self.tool_object.on_rmb_press()
        else:
            self.tool_object.on_rmb_release()

        if secondary and self.tool == BLOCK_TOOL:
            position = self.world_object.position
            self.line_build_start_pos = position.copy()
            self.on_line_build_start()

        self.world_object.secondary_fire = secondary

    if self.filter_weapon_input:
        return

    contained.player_id = self.player_id
    self.protocol.broadcast_contained(contained, sender = self)

@register_packet_handler(loaders.HitPacket)
def on_hit_recieved(self, contained):
    if self.dead(): return

    if contained.value == MELEE and self.tool == SPADE_TOOL and self.spade_object.enabled():
        if player := self.protocol.players.get(contained.player_id):
            if player.dead(): return

            if self.team is player.team and self.spade_friendly_fire is False:
                return

            x, y, z = player.world_object.position.get()
            if not self.world_object.can_see(x, y, z):
                return

            damage = floor(uniform(SHOVEL_GUARANTEED_DAMAGE, 100))

            player.hit(
                damage, limb = choice(player.body.keys()),
                venous = True, hit_by = self, kill_type = MELEE_KILL
            )

@register_packet_handler(loaders.ExistingPlayer)
@register_packet_handler(loaders.ShortPlayerData)
def on_new_player_recieved(self, contained):
    if contained.team not in self.protocol.teams:
        return

    if self.name is None:
        FeatureConnection.on_new_player_recieved(self, contained)
    else:
        self.set_weapon(contained.weapon, local = True)
        self.set_team(self.protocol.teams[contained.team])

@register_packet_handler(loaders.ChangeTeam)
def on_team_change_recieved(self, contained):
    if contained.team not in self.protocol.teams:
        return

    FeatureConnection.on_team_change_recieved(self, contained)

def handle_block_line(self, x1, y1, z1, x2, y2, z2):
    if self.line_build_start_pos is None:
        return

    if self.on_tool_rapid_hack(BLOCK_TOOL):
        return

    M = self.protocol.map

    # Coordinates are out of bounds.
    if not M.is_valid_position(x1, y1, z1):
        return

    if not M.is_valid_position(x2, y2, z2):
        return

    v1 = self.line_build_start_pos

    # Ensure that the player was within tolerance of the location that the line build started at.
    if not collision_3d(v1.x, v1.y, v1.z, x1, y1, z1, MAX_BLOCK_DISTANCE):
        return

    v2 = self.world_object.position

    # Ensure that the player is currently within tolerance of the location that the line build ended at.
    if not collision_3d(v2.x, v2.y, v2.z, x2, y2, z2, MAX_BLOCK_DISTANCE):
        return

    # Check if block can be placed in that location.
    if not M.has_neighbors(x1, y1, z1):
        return

    if not M.has_neighbors(x2, y2, z2):
        return

    locs = [(x, y, z) for x, y, z in cube_line(x1, y1, z1, x2, y2, z2) if not M.get_solid(x, y, z)]

    if self.on_line_build_attempt(locs) is False:
        return

    for x, y, z in locs:
        if not M.build_point(x, y, z, self.color):
            break

    self.on_line_build(locs)

    contained = loaders.BlockLine()
    contained.player_id = self.player_id
    contained.x1, contained.y1, contained.z1 = x1, y1, z1
    contained.x2, contained.y2, contained.z2 = x2, y2, z2

    self.protocol.broadcast_contained(contained, save = True)
    self.protocol.update_entities()

    for x, y, z in locs:
        self.protocol.on_block_build(x, y, z)

@register_packet_handler(loaders.BlockLine)
def on_block_line_recieved(self, contained):
    if self.dead(): return

    x1, y1, z1 = contained.x1, contained.y1, contained.z1
    x2, y2, z2 = contained.x2, contained.y2, contained.z2

    blocks = self.blocks

    if self.spade_object.enabled():
        self.handle_block_line(x1, y1, z1, x2, y2, z2)

    self.blocks = max(0, blocks - len(cube_line(x1, y1, z1, x2, y2, z2)))
    if self.blocks <= 0:
        self.sync()

@register_packet_handler(loaders.BlockAction)
def on_block_action_recieved(self, contained):
    if self.dead(): return

    if self.tool == SPADE_TOOL and contained.value == DESTROY_BLOCK:
        if self.client_info.get("client") == "OpenSpades":
            # OpenSpades behavior differs here from that one of voxlap and BetterSpades:
            # 1. The latter send `BlockAction` only once on the second hit on the block
            #    and add one block regardless of the server’s response.
            # 2. The former sends `BlockAction` on the second and all subsequent hits
            #    and add one block only when `BlockAction` from the server arrives.
            # Because of this `self.blocks` is sometimes lower than the value shown on the client for OpenSpades,
            # but we are actually interested only in making sure that this value is never *higher* than the client one.
            # In particular, I don’t know which logic does OpenSpades follow when the player uses spade + RMB.
            pass
        else:
            self.blocks = min(50, self.blocks + 1)

    # Everything else is handled server-side.
    if contained.value != BUILD_BLOCK:
        return

    if self.protocol.map.get_solid(contained.x, contained.y, contained.z):
        return

    blocks = self.blocks

    if self.spade_object.enabled():
        FeatureConnection.on_block_action_recieved(self, contained)

    self.blocks = max(0, blocks - 1)

    if self.blocks <= 0:
        self.sync()

def handle_grenade_packet(self, x, y, z, vx, vy, vz, value):
    if self.tool != GRENADE_TOOL:
        return

    if check_nan(x, y, z, vx, vy, vz, value):
        return

    if not self.check_speedhack(x, y, z):
        x, y, z = self.world_object.position.get()

    fuse = clamp(0.0, 3.0, value)

    if self.on_grenade(fuse) is False:
        return

    r = Vertex3(x, y, z)
    u = Vertex3(vx, vy, vz) - self.world_object.velocity
    v = u.normal() * min(u.length(), 2.0) + self.world_object.velocity

    if check_nan(v.length()):
        return

    if self.create_grenade(r, v, fuse, sender = self) is not None:
        self.grenade_object.on_tool_used()

def create_grenade(self, r, v, fuse, sender = None):
    if o := next(self.handgrenades(), None):
        self.inventory.remove(o)

        grenade = self.protocol.world.create_object(
            o.grenade_class, self.protocol, self.player_id, fuse, r, v
        )
        grenade.team = self.team

        self.on_grenade_thrown(grenade)

        if not self.filter_visibility_data:
            contained           = loaders.GrenadePacket()
            contained.player_id = self.player_id
            contained.value     = fuse
            contained.position  = r.get()
            contained.velocity  = v.get()

            self.protocol.broadcast_contained(contained, sender = sender)

        return grenade

from milsimlib.grammar import RegularNoun, Verb3, Cardinal, VerbNTR, PassiveVoice, np_vp_pres

leave_v    = Verb3(bare = "leave", ving = "leaving", ved = "left", v3sg = "leaves")
grenade_n  = RegularNoun("grenade")
be_left_vp = PassiveVoice(VerbNTR(leave_v))

@register_packet_handler(loaders.GrenadePacket)
def on_grenade_recieved(self, contained):
    if self.dead(): return

    self.grenades = max(0, self.grenades - 1)

    x, y, z = contained.position
    vx, vy, vz = contained.velocity

    self.handle_grenade_packet(x, y, z, vx, vy, vz, contained.value)

    rem = ilen(self.handgrenades())
    self.send_chat(np_vp_pres(Cardinal(rem, grenade_n), be_left_vp))

    if self.grenades <= 0 or rem <= 0:
        self.sync()
