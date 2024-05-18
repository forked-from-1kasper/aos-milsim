from dataclasses import dataclass
from itertools import product
from random import choice
from math import floor

from twisted.internet import reactor

from pyspades.packet import register_packet_handler
from pyspades.constants import BUILD_BLOCK
from pyspades import contained as loaders
from pyspades.world import cube_line
from pyspades.common import Vertex3

from piqueserver.commands import command
from piqueserver.config import config

from milsim.common import grenade_zone
import milsim.blast as blast

section = config.section("mines")

setup_distance = section.option("setup_distance", 13).get()

@dataclass
class Mine:
    player_id : int

    def explode(self, protocol, pos):
        if self.player_id not in protocol.players:
            ids = list(protocol.players.keys())
            if len(ids) > 0:
                self.player_id = choice(ids)
            else:
                return

        player = protocol.players[self.player_id]

        x, y, z = pos
        loc = Vertex3(x + 0.5, y + 0.5, z - 0.5)

        player.grenade_explode(loc)
        blast.effect(player, loc, Vertex3(0, 0, 0), 0)

@command('mine', 'm')
def mine(conn):
    if not conn.world_object or conn.world_object.dead: return

    loc = conn.world_object.cast_ray(setup_distance)

    if not loc:
        return "You can't place a mine so far away from yourself."
    else:
        if loc in conn.protocol.mines:
            conn.mines -= 1
            conn.protocol.explode(*loc)
            return

        _, _, z = loc
        if z == 63:
            return "You can't place a mine on water"

        if conn.mines > 0:
            conn.protocol.mines[loc] = Mine(conn.player_id)
            conn.mines -= 1
            return "Mine placed at %s" % str(loc)
        else:
            return "You do not have mines."

@command('givemine', 'gm', admin_only = True)
def givemine(conn):
    conn.mines += 1
    return "You got a mine."

@command('checkmines', 'cm')
def checkmines(conn):
    if not conn.world_object or conn.world_object.dead: return

    return "You have %d mine(s)." % conn.mines

def apply_script(protocol, connection, config):
    class MineProtocol(protocol):
        def __init__(self, *args, **kw):
            self.dirty = False

            self.mines = {}
            return protocol.__init__(self, *args, **kw)

        def on_map_change(self, M):
            self.mines = {}
            return protocol.on_map_change(self, M)

        def explode(self, x, y, z):
            r = (x, y, z)

            if r in self.mines:
                self.mines.pop(r).explode(self, r)

        def on_world_update(self):
            if self.dirty:
                flying = []

                for r in self.mines.keys():
                    if not self.map.get_solid(*r):
                        flying.append(r)

                for x, y, z in flying:
                    self.explode(x, y, z)

                self.dirty = False

            return protocol.on_world_update(self)

        def broadcast_contained(self, contained, unsequenced = False, sender = None, team = None, save = False, rule = None):
            protocol.broadcast_contained(self, contained, unsequenced, sender, team, save, rule)

            if isinstance(contained, loaders.BlockAction):
                # This is intentionally not in `on_block_build`.
                if contained.value == BUILD_BLOCK:
                    self.explode(contained.x, contained.y, contained.z + 1)

            if isinstance(contained, loaders.BlockLine):
                locs = cube_line(
                    contained.x1, contained.y1, contained.z1,
                    contained.x2, contained.y2, contained.z2
                )

                for x, y, z in locs:
                    self.explode(x, y, z + 1)

    class MineConnection(connection):
        def __init__(self, *w, **kw):
            self.previous_position = None
            self.mines = 0
            return connection.__init__(self, *w, **kw)

        def on_spawn(self, pos):
            self.previous_position = self.world_object.position.copy()
            self.mines = 2
            return connection.on_spawn(self, pos)

        def on_kill(self, killer, kill_type, grenade):
            self.previous_position = None
            return connection.on_kill(self, killer, kill_type, grenade)

        def refill(self, local = False):
            self.mines = 2
            return connection.refill(self, local)

        def take_flag(self):
            flag = self.team.other.flag
            x, y, z = floor(flag.x), floor(flag.y), floor(flag.z)

            connection.take_flag(self)

            if flag.player is not None: # when the flag was actually taken
                for Δx, Δy in product(range(-1, 2), range(-1, 2)):
                    self.protocol.explode(x + Δx, y + Δy, z)

        def on_position_update(self):
            if self.previous_position is not None:
                r1 = self.previous_position.get()
                r2 = self.world_object.position.get()

                for x, y, z in cube_line(*r1, *r2):
                    self.protocol.explode(x, y, self.protocol.map.get_z(x, y, z))

                self.previous_position = self.world_object.position.copy()

            return connection.on_position_update(self)

        def on_block_removed(self, x, y, z):
            connection.on_block_removed(self, x, y, z)

            self.protocol.explode(x, y, z)
            self.protocol.dirty = True

        def grenade_destroy(self, x, y, z):
            retval = connection.grenade_destroy(self, x, y, z)

            if retval != False:
                for X, Y, Z in grenade_zone(x, y, z):
                    self.protocol.explode(X, Y, Z)

            return retval

    return MineProtocol, MineConnection