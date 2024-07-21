from random import choice, uniform
from math import floor, inf

from twisted.internet import reactor

from pyspades.packet import register_packet_handler
from pyspades import contained as loaders
from pyspades.common import Vertex3
from pyspades.constants import *

import milsim.blast as blast

from milsim.manager.simulator import ABCSimulatorManager
from milsim.weapon import weapons
from milsim.common import *

WARNING_ON_KILL = "/b for bandage, /t for tourniquet, /s for splint"

GRENADE_LETHAL_RADIUS = 4
GRENADE_SAFETY_RADIUS = 30

SHOVEL_GUARANTEED_DAMAGE = 50

fracture_warning = {
    Limb.torso: "You broke your spine.",
    Limb.head:  "You broke your neck.",
    Limb.arml:  "You broke your left arm.",
    Limb.armr:  "You broke your right arm.",
    Limb.legl:  "You broke your left leg.",
    Limb.legr:  "You broke your right leg."
}

bleeding_warning = "You're bleeding."

def SetTool(conn):
    contained           = loaders.SetTool()
    contained.player_id = conn.player_id
    contained.value     = conn.tool

    return contained

def apply_script(protocol, connection, config):
    milsim_extensions = [(EXTENSION_TRACE_BULLETS, 1), (EXTENSION_HIT_EFFECTS, 1)]

    class CombatProtocol(protocol, ABCSimulatorManager):
        def __init__(self, *w, **kw):
            protocol.__init__(self, *w, **kw)
            ABCSimulatorManager.__init__(self)

            self.available_proto_extensions.extend(milsim_extensions)
            self.team_spectator.kills = 0 # bugfix

        def on_map_change(self, M):
            retval = protocol.on_map_change(self, M)
            self.onWipe(self.map_info.extensions.get('environment'))

            return retval

        def on_world_update(self):
            self.onTick()

            t = reactor.seconds()

            for player in self.players.values():
                P = player.team is not None and not player.team.spectator
                Q = player.world_object is not None and not player.world_object.dead

                if P and Q and player.last_hp_update is not None:
                    dt = t - player.last_hp_update

                    player.body.update(dt)

                    moving = player.world_object.up or player.world_object.down or \
                             player.world_object.left or player.world_object.right

                    if moving:
                        for leg in player.body.legs():
                            if leg.fractured:
                                if player.world_object.sprint:
                                    leg.hit(leg.sprint_damage_rate * dt)
                                elif not leg.splint:
                                    leg.hit(leg.walk_damage_rate * dt)

                    for arm in player.body.arms():
                        if player.world_object.primary_fire and arm.fractured:
                            arm.hit(arm.action_damage_rate * dt)

                    player.weapon_object.update(t)

                    if player.item_shown(t):
                        if player.world_object.primary_fire:
                            player.tool_object.lmb(t, dt)

                        if player.world_object.secondary_fire:
                            player.tool_object.rmb(t, dt)

                    hp = player.body.average()
                    if player.hp != hp:
                        player.set_hp(hp, kill_type = MELEE_KILL)

                    if not self.environment.size.inside(player.world_object.position):
                        player.kill()

                player.last_hp_update = t

            protocol.on_world_update(self)

    class CombatConnection(connection):
        def __init__(self, *w, **kw):
            self.spade_object   = SpadeTool(self)
            self.block_object   = BlockTool(self)
            self.grenade_object = GrenadeTool(self)

            self.last_hp_update = None
            self.body = Body()

            connection.__init__(self, *w, **kw)

        def height(self):
            if self.world_object:
                return 1.05 if self.world_object.crouch else 1.1

        def eye(self):
            if o := self.world_object:
                dt = reactor.seconds() - self.last_position_update

                return Vertex3(
                    o.position.x + o.velocity.x * dt,
                    o.position.y + o.velocity.y * dt,
                    o.position.z + o.velocity.z * dt - self.height(),
                )

        def item_shown(self, t):
            P = not self.world_object.sprint
            Q = t - self.last_sprint >= 0.5
            R = t - self.last_tool_update >= 0.5
            return P and Q and R

        def set_tool(self, tool):
            old_tool              = self.tool
            self.tool             = tool
            self.last_tool_update = reactor.seconds()

            if tool == SPADE_TOOL:
                self.tool_object = self.spade_object
            if tool == BLOCK_TOOL:
                self.tool_object = self.block_object
            if tool == WEAPON_TOOL:
                self.tool_object = self.weapon_object
            if tool == GRENADE_TOOL:
                self.tool_object = self.grenade_object

            if old_tool == WEAPON_TOOL:
                self.weapon_object.set_shoot(False)

            if self.tool == WEAPON_TOOL:
                self.on_shoot_set(self.world_object.primary_fire)
                self.weapon_object.set_shoot(self.world_object.primary_fire)

            self.world_object.set_weapon(self.tool == WEAPON_TOOL)
            self.on_tool_changed(self.tool)

            if self.filter_visibility_data or self.filter_animation_data:
                return

            self.protocol.broadcast_contained(SetTool(self), save = True)

        def reset_health(self):
            self.last_hp_update = reactor.seconds()
            self.hp             = 100

            self.body.reset()

        def refill(self, local = False):
            for P in self.body.values():
                if P.fractured:
                    P.splint = True

                P.arterial = False
                P.venous   = False

            self.grenades   = 3
            self.blocks     = 50
            self.bandage    = 3
            self.tourniquet = 2
            self.splint     = 1

            self.weapon_object.restock()

            if not local:
                self.send_contained(loaders.Restock())
                self.update_hud()

                hp = self.body.average()
                if hp != 100: # loaders.Restock() reverts hp to 100
                    self.set_hp(hp, kill_type = MELEE_KILL)

        def update_hud(self):
            weapon_reload              = loaders.WeaponReload()
            weapon_reload.player_id    = self.player_id
            weapon_reload.clip_ammo    = self.weapon_object.ammo.current()
            weapon_reload.reserve_ammo = self.weapon_object.ammo.reserved()
            self.send_contained(weapon_reload)

        def hit(self, value, hit_by = None, kill_type = WEAPON_KILL, limb = Limb.torso,
                venous = False, arterial = False, fractured = False):
            if hit_by is not None:
                if self.team is hit_by.team:
                    if kill_type == MELEE_KILL: return
                    if not self.protocol.friendly_fire: return

            P = self.body[limb]

            P.hit(value)

            if self.hp is not None and self.hp > 0:
                hp = self.body.average()

                if hp > 0:
                    if fractured and not P.fractured:
                        self.send_chat_status(fracture_warning[limb])
                    elif (venous or arterial) and not self.body.bleeding():
                        self.send_chat_status(bleeding_warning)

                if fractured and not P.fractured:
                    P.on_fracture(self)

                self.set_hp(hp, hit_by = hit_by, kill_type = kill_type)
                P.venous    = P.venous or venous
                P.arterial  = P.arterial or arterial
                P.fractured = P.fractured or fractured

        def grenade_destroy(self, x, y, z):
            if x < 0 or x > 512 or y < 0 or y > 512 or z < 0 or z > 63:
                return False

            if self.on_block_destroy(x, y, z, GRENADE_DESTROY) == False:
                return False

            for X, Y, Z in grenade_zone(x, y, z):
                if self.protocol.simulator.smash(X, Y, Z, TNT(gram(60))):
                    self.protocol.onDestroy(self.player_id, X, Y, Z)

            return True

        def grenade_explode(self, r):
            if self.grenade_destroy(floor(r.x), floor(r.y), floor(r.z)):
                blast.explode(GRENADE_LETHAL_RADIUS, GRENADE_SAFETY_RADIUS, self, r)

        def grenade_exploded(self, grenade):
            if self.name is None:
                return

            self.grenade_explode(grenade.position)

        def set_weapon(self, weapon, local = False, no_kill = False):
            if weapon not in weapons: return

            self.weapon        = weapon
            self.weapon_object = weapons[weapon](self)

            if not local:
                contained           = loaders.ChangeWeapon()
                contained.player_id = self.player_id
                contained.weapon    = weapon

                self.protocol.broadcast_contained(contained, save=True)
                if not no_kill: self.kill(kill_type=CLASS_CHANGE_KILL)

        def _on_reload(self):
            if not self.weapon_object.ammo.continuous:
                self.send_chat(self.weapon_object.ammo.info())

            self.update_hud()

        def _on_fall(self, damage):
            if not self.hp: return

            retval = self.on_fall(damage)

            if retval is False: return

            if retval is not None:
                damage = retval

            if damage > 0:
                legl, legr = self.body.legl, self.body.legr

                legl.hit(damage)
                legr.hit(damage)

                if randbool(logistic(legl.fall(damage))):
                    legl.fractured = True
                    legr.fractured = True
                    self.send_chat_status("You broke your legs.")

                self.set_hp(self.body.average(), kill_type = FALL_KILL)

        def on_block_build(self, x, y, z):
            self.blocks = 50 # due to the limitations of protocol we simply assume that each player has unlimited blocks

            self.protocol.simulator.build(x, y, z)
            return connection.on_block_build(self, x, y, z)

        def on_line_build(self, points):
            for x, y, z in points:
                self.protocol.simulator.build(x, y, z)

            return connection.on_line_build(self, points)

        def on_block_removed(self, x, y, z):
            self.protocol.simulator.destroy(x, y, z)
            return connection.on_block_removed(self, x, y, z)

        def on_spawn(self, pos):
            self.tool_object = self.weapon_object

            self.last_sprint      = -inf
            self.last_tool_update = -inf

            self.reset_health()
            self.update_hud()

            return connection.on_spawn(self, pos)

        def on_kill(self, killer, kill_type, grenade):
            if kill_type != TEAM_CHANGE_KILL and kill_type != CLASS_CHANGE_KILL:
                self.send_chat(WARNING_ON_KILL)

            return connection.on_kill(self, killer, kill_type, grenade)

        def on_animation_update(self, jump, crouch, sneak, sprint):
            if self.world_object.sprint and not sprint:
                self.last_sprint = reactor.seconds()

            return connection.on_animation_update(self, jump, crouch, sneak, sprint)

        def on_orientation_update(self, x, y, z):
            retval = connection.on_orientation_update(self, x, y, z)

            if retval == False:
                return False

            torso = self.body.torso

            if torso.fractured and not torso.splint:
                torso.hit(torso.rotation_damage)

            return retval

        def on_tool_set_attempt(self, tool):
            if self.body.arml.fractured or self.body.armr.fractured:
                self.send_contained(SetTool(self))

                return False
            else:
                return connection.on_tool_set_attempt(self, tool)

        def on_grenade(self, fuse):
            if not self.spade_object.enabled():
                self.send_chat_error("How did you do that??")
                return False

            return connection.on_grenade(self, fuse)

        def on_block_destroy(self, x, y, z, mode):
            if self.tool == WEAPON_TOOL or self.tool == SPADE_TOOL:
                if mode == DESTROY_BLOCK:
                    return False

            if mode == SPADE_DESTROY:
                return False

            return connection.on_block_destroy(self, x, y, z, mode)

        def on_flag_take(self):
            flag = self.team.other.flag

            # You cannot take the flag while standing under it.
            if self.world_object.position.z >= flag.z:
                return False

            # You cannot take the flag without seeing it (for example, underground).
            if not self.world_object.can_see(flag.x, flag.y, flag.z - 0.5):
                return False

            return connection.on_flag_take(self)

        def on_flag_capture(self):
            self.protocol.environment.on_flag_capture(self)
            return connection.on_flag_capture(self)

        @register_packet_handler(loaders.SetTool)
        def on_tool_change_recieved(self, contained):
            if not self.hp: return

            if self.on_tool_set_attempt(contained.value) == False:
                return

            self.set_tool(contained.value)

        @register_packet_handler(loaders.ExistingPlayer)
        @register_packet_handler(loaders.ShortPlayerData)
        def on_new_player_recieved(self, contained):
            if contained.team not in self.protocol.teams:
                return

            return connection.on_new_player_recieved(self, contained)

        @register_packet_handler(loaders.ChangeTeam)
        def on_team_change_recieved(self, contained):
            if contained.team not in self.protocol.teams:
                return

            return connection.on_team_change_recieved(self, contained)

        @register_packet_handler(loaders.HitPacket)
        def on_hit_recieved(self, contained):
            if not self.hp: return

            if contained.value == MELEE and self.spade_object.enabled():
                player = self.protocol.players.get(contained.player_id)

                if player is not None:
                    damage = floor(uniform(SHOVEL_GUARANTEED_DAMAGE, 100))

                    player.hit(
                        damage, limb = choice(player.body.keys()),
                        venous = True, hit_by = self, kill_type = MELEE_KILL
                    )

    return CombatProtocol, CombatConnection
