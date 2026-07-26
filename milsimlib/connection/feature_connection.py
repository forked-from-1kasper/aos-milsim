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

from time import monotonic
from math import isfinite

import asyncio

from pyspades import contained as loaders
from pyspades.common import Vertex3

from pyspades.constants import (
    SPADE_TOOL, BLOCK_TOOL, WEAPON_TOOL, GRENADE_TOOL,
    WEAPON_KILL, FALL_KILL, TEAM_CHANGE_KILL, CLASS_CHANGE_KILL
)

from milsimlib.types import randbool, logistic
from milsimlib.constants import Limb
from milsimlib.common import clamp

from milsimlib.grammar import (
    RegularNoun, Verb3, Verb4, VerbNP, VerbNPPP,
    PerfectAspect, Possessive, Adjective,
    you_pr, an_sg, np_vp_pres, SG
)
from milsimlib.types import arm_n, leg_n, left_adj, right_adj

feel_v    = Verb3(bare = "feel", ving = "feeling", ved = "felt", v3sg = "feels")
break_v   = Verb4(bare = "break", ving = "breaking", ved = "broken", v3sg = "breaks", vpast = "broke")
rib_n     = RegularNoun("rib")
pain_n    = RegularNoun("pain")
acute_adj = Adjective("acute")
dull_adj  = Adjective("dull")

pain_np       = an_sg(pain_n)
dull_pain_np  = dull_adj(pain_np)
acute_pain_np = acute_adj(pain_np)
feel_in_vp    = VerbNPPP(feel_v, "in")
break_vp      = VerbNP(break_v)

your_det = Possessive(you_pr, SG)

limb_fracture_np = {
    Limb.torso: your_det(rib_n),
    Limb.arml:  left_adj(your_det(arm_n)),
    Limb.armr:  right_adj(your_det(arm_n)),
    Limb.legl:  left_adj(your_det(leg_n)),
    Limb.legr:  right_adj(your_det(leg_n))
}

def set_tool(self, tool, sender = None):
    self.tool             = tool
    self.last_tool_update = monotonic()

    if tool == SPADE_TOOL:
        tool_object = self.spade_object
    if tool == BLOCK_TOOL:
        tool_object = self.block_object
    if tool == WEAPON_TOOL:
        tool_object = self.weapon_object
    if tool == GRENADE_TOOL:
        tool_object = self.grenade_object

    self.tool_object.on_tool_unequipped(tool_object)
    tool_object.on_tool_equipped(tool_object)

    self.tool_object = tool_object

    self.world_object.set_weapon(tool == WEAPON_TOOL)
    self.on_tool_changed(tool)

    if self.filter_visibility_data or self.filter_animation_data:
        return

    self.protocol.broadcast_contained(self.newSetTool(), sender = sender, save = True)

def set_weapon(self, weapon, local = False, no_kill = False):
    if weapon_class := self.protocol.get_weapon(weapon):
        self.weapon        = weapon
        self.weapon_object = weapon_class(self)

        if not local:
            contained           = loaders.ChangeWeapon()
            contained.player_id = self.player_id
            contained.weapon    = weapon

            self.protocol.broadcast_contained(contained, save = True)
            if not no_kill: self.kill(kill_type = CLASS_CHANGE_KILL)

def set_team(self, team):
    if team is self.team:
        return

    old_team, self.team = self.team, team
    self.on_team_changed(old_team)

    if old_team.spectator or True:
        x, y, z = self.get_spawn_location()

        contained           = loaders.CreatePlayer()
        contained.x         = x + 0.5
        contained.y         = y + 0.5
        contained.z         = z - 2.4
        contained.player_id = self.player_id
        contained.weapon    = self.weapon
        contained.name      = self.name
        contained.team      = self.team.id

        self.protocol.broadcast_contained(contained, save = True)

    self.kill(kill_type = TEAM_CHANGE_KILL)

def get_respawn_time(self):
    if self.respawn_time is None:
        return 0

    if self.team.spectator:
        return 0

    if self.protocol.respawn_waves:
        offset = self.last_death_time % self.respawn_time
        return self.respawn_time - offset

    if self.last_killer is self:
        return self.respawn_time
    elif self.last_death_type == TEAM_CHANGE_KILL or self.last_death_type == CLASS_CHANGE_KILL:
        return self.respawn_time
    else:
        return clamp(0, self.respawn_time, self.last_death_time - self.last_spawn_time)

def reset(self):
    if player_id := self.player_id:
        self.protocol.engine.on_despawn(player_id)

    if defer := self.spawn_call:
        self.spawn_call = None
        defer.cancel()

    if wo := self.world_object:
        self.world_object = None

        wo.delete()

    if team := self.team:
        self.team = None

        self.on_team_changed(team)

    self.on_reset()

    self.kills = 0
    self.name  = None
    self.hp    = None

def respawn(self):
    if defer := self.spawn_call:
        defer.cancel()

    self.spawn_call = None

    respawn_time = self.get_respawn_time()

    if not isfinite(respawn_time):
        return
    elif respawn_time <= 0:
        self.spawn()
    else:
        self.spawn_call = asyncio.get_running_loop().call_later(respawn_time, self.spawn)

def kill(self, by = None, kill_type = WEAPON_KILL, grenade = None):
    if self.hp is None and kill_type != TEAM_CHANGE_KILL:
        return

    if self.on_kill(by, kill_type, grenade) is False:
        return

    if self.tool == GRENADE_TOOL and self.grenade_object.unpin_time > 0:
        dt = max(0, monotonic() - self.grenade_object.unpin_time)
        fuse = max(0, 3.0 - dt)

        self.grenade_object.unpin_time = 0
        self.create_grenade(self.world_object.position.copy(), Vertex3(), fuse)

    if o := self.weapon_object:
        o.reset()

    self.drop_flag()
    self.drop_inventory()

    self.protocol.engine.on_despawn(self.player_id)

    self.hp = None

    if wo := self.world_object:
        wo.dead = True

    self.last_killer     = by
    self.last_death_type = kill_type
    self.last_death_time = monotonic()

    if by is not None and by.team is not self.team:
        by.add_score(1)

    respawn_time = self.get_respawn_time()

    contained              = loaders.KillAction()
    contained.kill_type    = kill_type
    contained.player_id    = self.player_id
    contained.killer_id    = by.player_id if by is not None else self.player_id
    contained.respawn_time = respawn_time if isfinite(respawn_time) else 0

    self.protocol.broadcast_contained(contained, save = True)

    self.on_killed(by, kill_type, grenade)

    self.respawn()

def refill(self, local = False):
    self.inventory.remove_if(lambda o: not o.persistent)
    self.weapon_object.refill()
    self.on_refill()

    if local is False: self.sync()

def hit(self, value, hit_by = None, kill_type = WEAPON_KILL, limb = Limb.torso,
        venous = False, arterial = False, fractured = False):
    if hit_by is not None and hit_by.team is self.team:
        if self.protocol.friendly_fire is False:
            return

    P = self.body[limb]

    P.hit(value)

    if self.hp is not None and self.hp > 0:
        hp = self.body.average()

        if fractured and not P.fractured:
            self.body.pushl_message(
                np_vp_pres(
                    np = you_pr,
                    vp = PerfectAspect(break_vp(limb_fracture_np[limb]))
                )
            )

            P.on_fracture(self)

        if arterial and not P.arterial:
            feeling_np = acute_pain_np
        elif venous and not P.venous:
            feeling_np = dull_pain_np
        elif value > 5:
            feeling_np = pain_np
        else:
            feeling_np = None

        if feeling_np is not None:
            self.body.pushl_message(
                np_vp_pres(
                    np = you_pr,
                    vp = feel_in_vp(feeling_np, P.np(your_det))
                )
            )

        self.set_hp(hp, hit_by = hit_by, kill_type = kill_type)

        P.venous    = P.venous or venous
        P.arterial  = P.arterial or arterial
        P.fractured = P.fractured or fractured

def _on_fall(self, damage):
    if self.dead(): return

    retval = self.on_fall(damage)

    if retval is False: return

    if retval is not None:
        damage = retval

    if damage > 0:
        legl, legr = self.body.legl, self.body.legr

        P = not legl.fractured and randbool(logistic(legl.fall(damage)))

        if P: legl.fractured = True
        legl.hit(damage)

        Q = not legr.fractured and randbool(logistic(legr.fall(damage)))

        if Q: legr.fractured = True
        legr.hit(damage)

        if P and Q:
            self.body.pushl_message("You have broken your legs")
        elif P:
            self.body.pushl_message("You have broken your left leg")
        elif Q:
            self.body.pushl_message("You have broken your right leg")

        self.set_hp(self.body.average(), kill_type = FALL_KILL)

def take_flag(self):
    if self.dead(): return

    flag = self.team.other.flag

    # If the flag is already taken.
    if flag.player is not None:
        return

    # You cannot take the flag while standing under it.
    if self.world_object.position.z >= flag.z:
        return

    # You cannot take the flag without seeing it (for example, underground).
    if not self.world_object.can_see(flag.x, flag.y, flag.z - 0.5):
        return

    if self.on_flag_take() == False:
        return

    flag.player = self

    contained           = loaders.IntelPickup()
    contained.player_id = self.player_id
    self.protocol.broadcast_contained(contained, save = True)

    self.on_flag_taken()
