from itertools import product, islice
from math import floor, inf

from twisted.internet import reactor

from pyspades.packet import register_packet_handler
from pyspades import contained as loaders
from pyspades.world import cube_line
from pyspades.constants import *

from piqueserver.map import Map, MapNotFound

from milsim.connection import MilsimConnection
from milsim.protocol import MilsimProtocol

from milsim.vxl import VxlData, onDeleteQueue, deleteQueueClear
from milsim.common import *

def load_vxl(self, rot):
    try:
        fin = open(rot.get_map_filename(self.load_dir), 'rb')
    except OSError:
        raise MapNotFound(rot.name)

    self.data = VxlData(fin)
    fin.close()

Map.load_vxl = load_vxl # is there any better way to override this?

def apply_script(protocol, connection, config):
    class CombatProtocol(MilsimProtocol, protocol):
        def __init__(self, *w, **kw):
            protocol.__init__(self, *w, **kw)
            MilsimProtocol.__init__(self, *w, **kw)

            self.team_spectator.kills = 0 # bugfix

        def on_map_change(self, M):
            deleteQueueClear()
            self.clear_tile_entities()

            protocol.on_map_change(self, M)

            o = self.map_info.extensions.get('environment')
            MilsimProtocol.on_environment_change(self, o)

        def on_world_update(self):
            MilsimProtocol.on_simulator_update(self)

            for x, y, z in islice(onDeleteQueue(), 50):
                if e := self.get_tile_entity(x, y, z):
                    e.on_destroy()

            t = reactor.seconds()

            for player in self.players.values():
                if player.ingame():
                    dt = t - player.last_hp_update

                    player.body.update(dt)

                    if player.moving():
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
                            player.tool_object.on_lmb_hold(t, dt)

                        if player.world_object.secondary_fire:
                            player.tool_object.on_rmb_hold(t, dt)

                    hp = player.body.average()
                    if player.hp != hp:
                        player.set_hp(hp, kill_type = MELEE_KILL)

                    if not self.environment.size.inside(player.world_object.position):
                        player.kill()

                player.last_hp_update = t

            protocol.on_world_update(self)

        def broadcast_contained(self, contained, unsequenced = False, sender = None, team = None, save = False, rule = None):
            protocol.broadcast_contained(self, contained, unsequenced, sender, team, save, rule)

            if isinstance(contained, loaders.BlockAction):
                x, y, z = contained.x, contained.y, contained.z

                # This is intentionally not in `connection.on_block_build`, so that `protocol.on_block_build`
                # is called *after* the BlockAction packet has been sent.
                if contained.value == BUILD_BLOCK:
                    self.on_block_build(x, y, z)

                if contained.value == DESTROY_BLOCK:
                    self.on_block_destroy(x, y, z)

                if contained.value == SPADE_DESTROY:
                    for X, Y, Z in (x, y, z), (x, y, z - 1), (x, y, z + 1):
                        self.on_block_destroy(X, Y, Z)

                if contained.value == GRENADE_DESTROY:
                    for X, Y, Z in grenade_zone(x, y, z):
                        self.on_block_destroy(X, Y, Z)

    class CombatConnection(MilsimConnection, connection):
        def __init__(self, *w, **kw):
            connection.__init__(self, *w, **kw)
            MilsimConnection.__init__(self, *w, **kw)

            self.previous_position = None

        def on_block_build(self, x, y, z):
            self.blocks = 50 # due to the limitations of protocol we simply assume that each player has unlimited blocks
            connection.on_block_build(self, x, y, z)

        def on_line_build(self, points):
            self.blocks = 50
            connection.on_line_build(self, points)

        def on_spawn(self, pos):
            self.previous_position = self.world_object.position.copy()

            self.tool_object = self.weapon_object

            self.last_sprint      = -inf
            self.last_tool_update = -inf

            self.last_hp_update = reactor.seconds()
            self.hp             = 100
            self.body.reset()

            self.sendWeaponReload()

            connection.on_spawn(self, pos)

        def on_animation_update(self, jump, crouch, sneak, sprint):
            retval = connection.on_animation_update(self, jump, crouch, sneak, sprint)

            if retval is not None:
                jump, crouch, sneak, sprint = retval

            if self.world_object.sprint and not sprint:
                self.last_sprint = reactor.seconds()

            return retval

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
                return False
            else:
                return connection.on_tool_set_attempt(self, tool)

        def on_grenade(self, fuse):
            if not self.spade_object.enabled():
                self.send_chat_error("How did you do that??")
                return False

            return connection.on_grenade(self, fuse)

        def on_flag_capture(self):
            self.protocol.environment.on_flag_capture(self)
            connection.on_flag_capture(self)

        def on_position_update(self):
            if self.previous_position is not None:
                r1 = self.previous_position.get()
                r2 = self.world_object.position.get()

                M = self.protocol.map
                for x, y, z in cube_line(*r1, *r2):
                    for Δz in range(4):
                        if M.get_solid(x, y, z + Δz):
                            if e := self.protocol.get_tile_entity(x, y, z + Δz):
                                e.on_pressure()

                            break

                self.previous_position = self.world_object.position.copy()

            connection.on_position_update(self)

        @register_packet_handler(loaders.ExistingPlayer)
        @register_packet_handler(loaders.ShortPlayerData)
        def on_new_player_recieved(self, contained):
            if contained.team not in self.protocol.teams:
                return

            connection.on_new_player_recieved(self, contained)

        @register_packet_handler(loaders.ChangeTeam)
        def on_team_change_recieved(self, contained):
            if contained.team not in self.protocol.teams:
                return

            connection.on_team_change_recieved(self, contained)

        @register_packet_handler(loaders.BlockAction)
        def on_block_action_recieved(self, contained):
            # Everything else is handled server-side.
            if contained.value == BUILD_BLOCK:
                if self.protocol.map.get_solid(contained.x, contained.y, contained.z):
                    return

                connection.on_block_action_recieved(self, contained)

    return CombatProtocol, CombatConnection
