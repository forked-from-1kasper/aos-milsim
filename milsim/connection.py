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

from math import log10, floor, copysign, isfinite
from random import choice, uniform
from itertools import product
from time import monotonic

from twisted.internet import reactor
from twisted.logger import Logger

from piqueserver.commands import get_player

from pyspades.collision import distance_3d_vector, collision_3d, vector_collision
from pyspades.packet import register_packet_handler
from pyspades.world import Character, cube_line
from pyspades import contained as loaders
from pyspades.player import check_nan
from pyspades.common import Vertex3
from pyspades.constants import *

from piqueserver.player import FeatureConnection

from milsim.common import grenade_zone, TNT, gram, ilen, iempty, floor3, clamp
from milsim.blast import sendGrenadePacket, flashbang_effect
from milsim.types import Inventory, Body, randbool, logistic
from milsim.engine import WorldObject, toMeters
from milsim.items import HandgrenadeItem
from milsim.constants import Limb

from milsim.grammar import (
    RegularNoun, Verb3, Verb4, Cardinal, VerbNTR, VerbNP, VerbNPPP, PassiveVoice,
    PerfectAspect, Possessive, Adjective, you_pr, an_sg, np_vp_pres, SG
)
from milsim.types import arm_n, leg_n, left_adj, right_adj

feel_v    = Verb3(bare = "feel", ving = "feeling", ved = "felt", v3sg = "feels")
break_v   = Verb4(bare = "break", ving = "breaking", ved = "broken", v3sg = "breaks", vpast = "broke")
leave_v   = Verb3(bare = "leave", ving = "leaving", ved = "left", v3sg = "leaves")
rib_n     = RegularNoun("rib")
grenade_n = RegularNoun("grenade")
pain_n    = RegularNoun("pain")
acute_adj = Adjective("acute")
dull_adj  = Adjective("dull")

pain_np       = an_sg(pain_n)
dull_pain_np  = dull_adj(pain_np)
acute_pain_np = acute_adj(pain_np)
be_left_vp    = PassiveVoice(VerbNTR(leave_v))
feel_in_vp    = VerbNPPP(feel_v, "in")
break_vp      = VerbNP(break_v)

SHOVEL_GUARANTEED_DAMAGE = 50

your_det = Possessive(you_pr, SG)

limb_fracture_np = {
    Limb.torso: your_det(rib_n),
    Limb.arml:  left_adj(your_det(arm_n)),
    Limb.armr:  right_adj(your_det(arm_n)),
    Limb.legl:  left_adj(your_det(leg_n)),
    Limb.legr:  right_adj(your_det(leg_n))
}

bleeding_warning = "You're bleeding"

from milsim.items import BandageItem, TourniquetItem, SplintItem, F1GrenadeItem

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

log = Logger()

class MilsimConnection(FeatureConnection):
    world_object_class = WorldObject

    default_loadout = milsim_default_loadout

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
        if self.blocks <= 0 or self.grenades <= 0 and not iempty(self.handgrenades()):
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
                    di.push(di)

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

    def get_player(self, nickname):
        if nickname is None:
            return self
        else:
            return get_player(self.protocol, nickname)

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

        reactor.callInThread(
            flashbang_effect, self.protocol, self.player_id, grenade.position.copy()
        )

    # (3) All `on_XXX_YYY` handlers, including the custom ones

    def on_killed(self, killer, kill_type, grenade):
        pass

    def on_reload_complete(self):
        pass

    def on_flag_taken(self):
        pass

    def on_chat(self, value, is_global_message):
        if is_global_message is False:
            if self.handheld_radio_item is None:
                self.send_chat("You don't have an equipped radio")

                return False

        return FeatureConnection.on_chat(self, value, is_global_message)

    def on_chat_delivered(self, player, value, is_global_message):
        if self.deaf: return False

        if self.alive() and self.body.deaf: return False

        # We observe that attenuation α = α(f) is a monotonic function of a frequency `f`,
        # thus if a fixed frequency f = f₀ is getting attenuated below the background noise level,
        # so does any freqeuncy f > f₀. Cutting of everything above f = 1 kHz will drop many consonants,
        # therefore we take this frequency as a cutoff frequency.
        # [1] https://physics.stackexchange.com/questions/856827/looking-for-a-formula-to-realistically-model-sound-loudness-at-a-given-distance
        # [2] https://physics.stackexchange.com/questions/415409/how-far-can-a-shout-travel
        # [3] https://en.wikibooks.org/wiki/Engineering_Acoustics/Outdoor_Sound_Propagation

        if is_global_message:
            if self.dead(): # dead player can hear anyone anywhere
                return True # TODO: is this a good idea?

            if player.name is None or player.team.spectator: # spectators can be heard anywhere
                return True

            if player.dead(): # alive players can’t hear dead players
                return False

            d = toMeters(distance_3d_vector(self.world_object.position, player.world_object.position))

            d0 = 0.3 # Some arbitrary distance at which SPL₀ (initial sound pressure level) is measured (m).
            L0 = 80.0 if value.isupper() else 65.0 # SPL₀ (dB), where we interpret uppercase as shouting.

            if d < d0:
                L = L0
            else:
                α = self.protocol.attenuation_coefficient
                L = L0 - 20 * log10(d / d0) - α * d

            o = self.protocol.environment

            return L > o.ANL
        else:
            if wt := self.handheld_radio_item:
                return wt.team is player.handheld_radio_item.team
            else:
                return False

    def on_orientation_update(self, x, y, z):
        ε = 1e-9

        retval = FeatureConnection.on_orientation_update(self, x, y, z)

        if retval is False: return False

        if retval is not None: x, y, z = retval

        if -ε < x < ε: retval = copysign(ε, x), y, z

        torso = self.body.torso

        if torso.fractured and not torso.splint:
            torso.hit(torso.rotation_damage)

        return retval

    def on_animation_update(self, jump, crouch, sneak, sprint):
        retval = FeatureConnection.on_animation_update(self, jump, crouch, sneak, sprint)
        if retval is not None: jump, crouch, sneak, sprint = retval

        if self.world_object.sprint and not sprint:
            self.last_sprint = monotonic()

        if self.world_object.sneak != sneak:
            if sneak:
                self.tool_object.on_sneak_press()
            else:
                self.tool_object.on_sneak_release()

        if not self.world_object.jump and jump:
            for leg in self.body.legs():
                if leg.fractured:
                    leg.hit(leg.jump_damage)

        self.protocol.engine.set_animation(self.player_id, crouch)

        return retval

    def on_tool_set_attempt(self, tool):
        if self.body.arml.fractured or self.body.armr.fractured:
            return False

        if tool == GRENADE_TOOL and iempty(self.handgrenades()):
            return False

        return FeatureConnection.on_tool_set_attempt(self, tool)

    def on_flag_capture(self):
        if map_on_flag_capture := self.protocol.map_info.on_flag_capture:
            map_on_flag_capture(self)

        FeatureConnection.on_flag_capture(self)

    def on_client_info(self):
        log.info("{address} connected with {client}",
            address  = self.address[0],
            client   = self.client_string
        )

        FeatureConnection.on_client_info(self)

    def on_spawn(self, loc):
        FeatureConnection.on_spawn(self, loc)

        self.world_object.on_block_stepped = self.on_block_stepped

        self.last_spawn_time = monotonic()

        self.tool_object = self.weapon_object
        self.tool_object.on_tool_equipped(None)

        self.last_sprint      = 0
        self.last_tool_update = 0

        self.suppression_value        = 0.0
        self.suppression_warning_sent = False

        self.last_hp_update = monotonic()

        self.body.reset()

        self.hp       = 100
        self.blocks   = 50
        self.grenades = 3

        self.sendWeaponReloadPacket()

        self.protocol.engine.on_spawn(self.player_id)

        if isfinite(self.get_respawn_time()):
            pass
        else:
            self.kill() # if spawn is disabled

    def on_disconnect(self):
        if o := self.weapon_object:
            o.reset()

        self.drop_inventory()

        FeatureConnection.on_disconnect(self)

    def on_tool_rapid_hack(self, tool):
        t1, t2 = self.last_block, reactor.seconds()

        self.last_block = t2

        if self.rapid_hack_detect and t1 is not None and t2 - t1 < TOOL_INTERVAL[tool]:
            self.rapids.record_event(t2)

            if self.rapids.above_limit():
                self.on_hack_attempt('Rapid hack detected')
                return True

        return False

    def on_refill(self):
        self.inventory.extend(io.mark_renewable() for io in self.default_loadout())

    def on_block_stepped(self, x, y, z):
        M = self.protocol.map
        if M.get_solid(x, y, z):
            if e := self.protocol.get_tile_entity(x, y, z):
                e.on_pressure()

    # (4) Overridden `FeatureConnection` methods

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

            if defer.active():
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
            if defer.active():
                defer.cancel()

        self.spawn_call = None

        respawn_time = self.get_respawn_time()

        if not isfinite(respawn_time):
            return
        elif respawn_time <= 0:
            self.spawn()
        else:
            self.spawn_call = reactor.callLater(respawn_time, self.spawn)

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

        self.weapon_object.reset()

        self.drop_flag()
        self.drop_inventory()

        self.protocol.engine.on_despawn(self.player_id)

        self.hp = None

        self.world_object.dead = True

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
        for P in self.body.values():
            if P.fractured:
                P.splint = True

            P.arterial = False
            P.venous   = False

        self.inventory.remove_if(lambda o: not o.persistent)
        self.weapon_object.refill()
        self.on_refill()

        if not local: self.sync()

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

    # (5) Overridden packets handlers

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

assert FeatureConnection.world_object_class is Character
assert MilsimConnection.on_connect is FeatureConnection.on_connect
