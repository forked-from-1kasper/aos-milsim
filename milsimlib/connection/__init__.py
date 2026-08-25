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

from pyspades import contained as loaders
from pyspades.world import Character

from horseradish.player import FeatureConnection

from milsimlib.types import Inventory, Body
from milsimlib.engine import WorldObject

from milsimlib.items import BandageItem, TourniquetItem, SplintItem, F1GrenadeItem

def milsim_default_loadout(self):
    yield BandageItem()
    yield BandageItem()
    yield BandageItem()

    yield TourniquetItem()
    yield TourniquetItem()

    yield SplintItem()

    yield F1GrenadeItem()
    yield F1GrenadeItem()
    yield F1GrenadeItem()

class MilsimConnection(FeatureConnection):
    world_object_class = WorldObject

    default_loadout = milsim_default_loadout

    blocks_refill_threshold = 5

    bleeding_spread_modifier    = 4.5
    fracture_spread_modifier    = 9.5
    suppression_spread_modifier = 7.0

    lmb_spade_speed = 1.0
    rmb_spade_speed = 0.7

    last_killer     = None
    last_death_type = None
    last_death_time = 0
    last_spawn_time = 0

    body_mass = 70

    def __init__(self, *w, **kw):
        FeatureConnection.__init__(self, *w, **kw)

        self.spade_object   = self.protocol.SpadeTool(self)
        self.block_object   = self.protocol.BlockTool(self)
        self.grenade_object = self.protocol.GrenadeTool(self)

        self.handheld_radio_item = None

        self.inventory = Inventory()

        self.courage_value            = 1.0
        self.suppression_value        = 0.0
        self.suppression_warning_sent = False
        self.last_hp_update           = None
        self.body                     = Body()

        self.spade_friendly_fire = False

    # (1) Frequently used packets

    def newSetTool(self):
        contained           = loaders.SetTool()
        contained.player_id = self.player_id
        contained.value     = self.tool

        return contained

    def sendWeaponReloadPacket(self):
        contained              = loaders.WeaponReload()
        contained.player_id    = self.player_id
        contained.clip_ammo    = self.weapon_object.magazine.current()
        contained.reserve_ammo = self.weapon_object.reserved()
        self.send_contained(contained)

    # (2) Methods specific to `MilsimConnection`

    from milsimlib.connection.methods import (
        handgrenades, sync, alive, dead, moving, height, eye, floor, drop, drop_inventory,
        get_drop_inventory, get_available_inventory, get_available_items, get_spread_modifier,
        gear_mass, item_shown, get_player, grenade_destroy, grenade_exploded, flashbang_exploded,
        get_tool_object,
    )

    # (3) All `on_XXX_YYY` handlers, including the custom ones

    from milsimlib.connection.handlers import (
        on_animation_update,
        on_block_stepped,
        on_chat,
        on_chat_delivered,
        on_disconnect,
        on_flag_capture,
        on_flag_taken,
        on_killed,
        on_orientation_update,
        on_refill,
        on_reload_complete,
        on_spawn,
        on_tool_rapid_hack,
        on_tool_set_attempt,
    )

    # (4) Overridden `FeatureConnection` methods

    from milsimlib.connection.feature_connection import (
        set_tool, set_weapon, set_team, get_respawn_time,
        reset, respawn, kill, refill, hit, _on_fall, take_flag,
    )

    # (5) Overridden packets handlers

    from milsimlib.connection.packet_handler import (
        create_grenade,
        handle_block_line,
        handle_grenade_packet,
        on_block_action_recieved,
        on_block_line_recieved,
        on_grenade_recieved,
        on_hit_recieved,
        on_new_player_recieved,
        on_team_change_recieved,
        on_tool_change_recieved,
        on_weapon_input_recieved,
    )

assert FeatureConnection.world_object_class is Character
assert MilsimConnection.on_connect is FeatureConnection.on_connect
