from random import choice, uniform
from itertools import product
from math import floor, inf

from twisted.internet import reactor

from pyspades.collision import collision_3d, vector_collision
from pyspades.packet import register_packet_handler
from pyspades import contained as loaders
from pyspades.world import cube_line
from pyspades.common import Vertex3
from pyspades.constants import *

from piqueserver.player import FeatureConnection

from milsim.common import grenade_zone, TNT, gram, BandageItem, TourniquetItem, SplintItem
from milsim.blast import sendGrenadePacket, explode, flashbang_effect
from milsim.types import Inventory, Body, randbool, logistic
from milsim.constants import Limb

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

class MilsimConnection(FeatureConnection):
    body_mass = 70

    def __init__(self, *w, **kw):
        FeatureConnection.__init__(self, *w, **kw)

        self.spade_object   = self.protocol.SpadeTool(self)
        self.block_object   = self.protocol.BlockTool(self)
        self.grenade_object = self.protocol.GrenadeTool(self)

        self.last_hp_update = -inf
        self.inventory      = Inventory()
        self.body           = Body()

        self.previous_floor_position = None

    def on_reload_complete(self):
        pass

    def on_flag_taken(self):
        pass

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

    def alive(self):
        return self.team is not None and not self.team.spectator and \
               self.world_object is not None and not self.world_object.dead

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
            Δz = 2 if o.crouch else 3
            return (
                floor(o.position.x),
                floor(o.position.y),
                floor(o.position.z) + Δz
            )

    def get_drop_inventory(self):
        if wo := self.world_object:
            x = floor(wo.position.x)
            y = floor(wo.position.y)
            z = floor(wo.position.z)

            return self.protocol.new_item_entity(
                x, y, self.protocol.map.get_z(x, y, z)
            )

    def get_available_inventory(self):
        if wo := self.world_object:
            x = floor(wo.position.x)
            y = floor(wo.position.y)
            z = floor(wo.position.z)

            for X, Y in product(range(x - 1, x + 2), range(y - 1, y + 2)):
                for Z in range(z, z + 4):
                    if self.protocol.map.get_solid(X, Y, Z):
                        if i := self.protocol.get_item_entity(X, Y, Z):
                            yield i

                        break

            if vector_collision(wo.position, self.protocol.team_1.base):
                yield self.protocol.team1_tent_inventory

            if vector_collision(wo.position, self.protocol.team_2.base):
                yield self.protocol.team2_tent_inventory

    def get_available_items(self):
        for i in self.get_available_inventory():
            for o in i: yield i, o

    def drop(self, ID):
        if o := self.inventory[ID]:
            if o.persistent:
                self.get_drop_inventory().push(o)

            self.inventory.remove(o)
            self.sendWeaponReloadPacket()

    def drop_inventory(self):
        if self.world_object is not None:
            self.get_drop_inventory().extend(
                filter(lambda o: o.persistent, self.inventory)
            )

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

    def on_position_update(self):
        if self.previous_floor_position is not None:
            r1, r2 = self.previous_floor_position, self.floor()

            M = self.protocol.map
            for x, y, z in cube_line(*r1, *r2):
                if M.get_solid(x, y, z):
                    if e := self.protocol.get_tile_entity(x, y, z):
                        e.on_pressure()

            self.previous_floor_position = r2

        FeatureConnection.on_position_update(self)

    def on_orientation_update(self, x, y, z):
        retval = FeatureConnection.on_orientation_update(self, x, y, z)

        if retval == False:
            return False

        torso = self.body.torso

        if torso.fractured and not torso.splint:
            torso.hit(torso.rotation_damage)

        return retval

    def on_animation_update(self, jump, crouch, sneak, sprint):
        retval = FeatureConnection.on_animation_update(self, jump, crouch, sneak, sprint)

        if retval is not None:
            jump, crouch, sneak, sprint = retval

        if self.world_object.sprint and not sprint:
            self.last_sprint = reactor.seconds()

        if self.world_object.sneak != sneak:
            if sneak:
                self.tool_object.on_sneak_press()
            else:
                self.tool_object.on_sneak_release()

        self.protocol.engine.set_animation(self.player_id, crouch)

        return retval

    def on_block_build(self, x, y, z):
        self.blocks = 50 # due to the limitations of protocol we simply assume that each player has unlimited blocks
        FeatureConnection.on_block_build(self, x, y, z)

    def on_line_build(self, points):
        self.blocks = 50
        FeatureConnection.on_line_build(self, points)

    def on_tool_set_attempt(self, tool):
        if self.body.arml.fractured or self.body.armr.fractured:
            return False
        else:
            return FeatureConnection.on_tool_set_attempt(self, tool)

    def on_grenade(self, fuse):
        if not self.spade_object.enabled():
            self.send_chat_error("How did you do that??")
            return False

        return FeatureConnection.on_grenade(self, fuse)

    def on_flag_capture(self):
        if map_on_flag_capture := self.protocol.map_info.on_flag_capture:
            map_on_flag_capture(self)

        FeatureConnection.on_flag_capture(self)

    def on_spawn(self, pos):
        self.previous_floor_position = self.floor()

        self.tool_object = self.weapon_object

        self.last_sprint      = -inf
        self.last_tool_update = -inf

        self.last_hp_update = reactor.seconds()
        self.body.reset()
        self.hp = 100

        self.sendWeaponReloadPacket()

        self.protocol.engine.on_spawn(self.player_id)
        FeatureConnection.on_spawn(self, pos)

    def on_kill(self, killer, kill_type, grenade):
        if FeatureConnection.on_kill(self, killer, kill_type, grenade) is False:
            return False

        self.protocol.engine.on_despawn(self.player_id)
        self.drop_inventory()

    def on_disconnect(self):
        if o := self.weapon_object:
            o.reset()

        self.drop_inventory()

        FeatureConnection.on_disconnect(self)

    def reset(self):
        if self.player_id is not None:
            self.protocol.engine.on_despawn(self.player_id)

        FeatureConnection.reset(self)

    def set_tool(self, tool):
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

        self.world_object.set_weapon(tool == WEAPON_TOOL)
        self.on_tool_changed(tool)

        if self.filter_visibility_data or self.filter_animation_data:
            return

        self.protocol.broadcast_contained(self.newSetTool(), save = True)

    def on_tool_rapid_hack(self, tool):
        t1, t2 = self.last_block, reactor.seconds()

        self.last_block = t2

        if self.rapid_hack_detect and t1 is not None and t2 - t1 < TOOL_INTERVAL[tool]:
            self.rapids.record_event(t2)

            if self.rapids.above_limit():
                self.on_hack_attempt('Rapid hack detected')
                return True

        return False

    def take_flag(self):
        if not self.alive(): return

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

    def grenade_explode(self, r):
        self.grenade_destroy(floor(r.x), floor(r.y), floor(r.z))
        explode(GRENADE_LETHAL_RADIUS, GRENADE_SAFETY_RADIUS, self, r)

    def grenade_exploded(self, grenade):
        if self.name is None:
            return

        self.grenade_explode(grenade.position)

    def flashbang_exploded(self, grenade):
        if self.name is None:
            return

        reactor.callInThread(
            flashbang_effect, self.protocol, self.player_id, grenade.position.copy()
        )

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

    def on_refill(self):
        self.inventory.append(
            BandageItem().mark_renewable(),
            BandageItem().mark_renewable(),
            BandageItem().mark_renewable(),
            TourniquetItem().mark_renewable(),
            TourniquetItem().mark_renewable(),
            SplintItem().mark_renewable()
        )

    def refill(self, local = False):
        for P in self.body.values():
            if P.fractured:
                P.splint = True

            P.arterial = False
            P.venous   = False

        self.grenades = 3
        self.blocks   = 50

        self.inventory.remove_if(lambda o: not o.persistent)
        self.weapon_object.refill()
        self.on_refill()

        if not local:
            self.send_contained(loaders.Restock())
            self.sendWeaponReloadPacket()

            hp = self.body.average()
            if hp != 100: # loaders.Restock() reverts hp to 100
                self.set_hp(hp, kill_type = MELEE_KILL)

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

    @register_packet_handler(loaders.SetTool)
    def on_tool_change_recieved(self, contained):
        if not self.hp: return

        if self.on_tool_set_attempt(contained.value) == False:
            # Reset it back for the player.
            self.send_contained(self.newSetTool())
        else:
            self.set_tool(contained.value)

    @register_packet_handler(loaders.WeaponInput)
    def on_weapon_input_recieved(self, contained):
        if not self.hp: return

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
        if not self.hp: return

        if contained.value == MELEE and self.spade_object.enabled():
            if player := self.protocol.players.get(contained.player_id):
                damage = floor(uniform(SHOVEL_GUARANTEED_DAMAGE, 100))

                player.hit(
                    damage, limb = choice(player.body.keys()),
                    venous = True, hit_by = self, kill_type = MELEE_KILL
                )

    @register_packet_handler(loaders.BlockLine)
    def on_block_line_recieved(self, contained):
        if not self.alive():
            return

        if self.line_build_start_pos is None:
            return

        if self.on_tool_rapid_hack(BLOCK_TOOL):
            return

        M = self.protocol.map

        x1, y1, z1 = contained.x1, contained.y1, contained.z1
        x2, y2, z2 = contained.x2, contained.y2, contained.z2

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

        if locs is None:
            return

        if len(locs) > self.blocks + BUILD_TOLERANCE:
            return

        if self.on_line_build_attempt(locs) is False:
            return

        for x, y, z in locs:
            if not M.build_point(x, y, z, self.color):
                break

        self.blocks -= len(locs)
        self.on_line_build(locs)

        contained.player_id = self.player_id
        self.protocol.broadcast_contained(contained, save = True)
        self.protocol.update_entities()

        for x, y, z in locs:
            self.protocol.on_block_build(x, y, z)

    @register_packet_handler(loaders.ExistingPlayer)
    @register_packet_handler(loaders.ShortPlayerData)
    def on_new_player_recieved(self, contained):
        if contained.team not in self.protocol.teams:
            return

        FeatureConnection.on_new_player_recieved(self, contained)

    @register_packet_handler(loaders.ChangeTeam)
    def on_team_change_recieved(self, contained):
        if contained.team not in self.protocol.teams:
            return

        FeatureConnection.on_team_change_recieved(self, contained)

    @register_packet_handler(loaders.BlockAction)
    def on_block_action_recieved(self, contained):
        # Everything else is handled server-side.
        if contained.value == BUILD_BLOCK:
            if self.protocol.map.get_solid(contained.x, contained.y, contained.z):
                return

            FeatureConnection.on_block_action_recieved(self, contained)

assert MilsimConnection.on_connect is FeatureConnection.on_connect
