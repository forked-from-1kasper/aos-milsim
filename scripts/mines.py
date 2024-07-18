from itertools import product, islice
from dataclasses import dataclass
from random import choice
from math import floor

from twisted.internet import reactor

from pyspades.packet import register_packet_handler
from pyspades.constants import BUILD_BLOCK
from pyspades import contained as loaders
from pyspades.world import cube_line
from pyspades.common import Vertex3

from piqueserver.map import Map, MapNotFound
from piqueserver.commands import command
from piqueserver.config import config

from milsim.vxl import VxlData, onDeleteQueue, deleteQueueClear
from milsim.common import grenade_zone
import milsim.blast as blast

def load_vxl(self, rot):
    try:
        fin = open(rot.get_map_filename(self.load_dir), 'rb')
    except OSError:
        raise MapNotFound(rot.name)

    self.data = VxlData(fin)
    fin.close()

Map.load_vxl = load_vxl # is there any better way to override this?

class TileEntity:
    def __init__(self, protocol, position):
        self.protocol = protocol
        self.position = position

    def on_pressure(self):
        pass

    def on_destroy(self):
        self.protocol.remove_tile_entity(*self.position)

class DummyEntitiy(TileEntity):
    def __init__(self):
        pass

    def on_destroy(self):
        pass

dummy = DummyEntitiy()

class Explosive(TileEntity):
    def __init__(self, protocol, position, player_id):
        self.player_id = player_id
        TileEntity.__init__(self, protocol, position)

    def explode(self):
        self.protocol.remove_tile_entity(*self.position)

        if self.player_id not in self.protocol.players:
            ids = list(self.protocol.players.keys())
            if len(ids) > 0:
                self.player_id = choice(ids)
            else:
                return

        player = self.protocol.players[self.player_id]

        x, y, z = self.position
        loc = Vertex3(x + 0.5, y + 0.5, z - 0.5)

        player.grenade_explode(loc)
        blast.effect(player, loc, Vertex3(0, 0, 0), 0)

class Landmine(Explosive):
    on_pressure = Explosive.explode
    on_destroy  = Explosive.explode

@command('mine', 'm')
def mine(conn):
    if not conn.world_object or conn.world_object.dead: return

    loc = conn.world_object.cast_ray(10)

    if not loc: return "You can't place a mine so far away from yourself."

    x, y, z = loc
    if z >= 63: return "You can't place a mine on water"

    if conn.mines > 0:
        conn.mines -= 1

        entity = conn.protocol.get_tile_entity(x, y, z)

        if entity is not dummy:
            entity.on_pressure()
            return

        conn.protocol.add_tile_entity(Landmine, conn.protocol, loc, conn.player_id)
        return "Mine placed at {}".format(loc)
    else:
        return "You do not have mines."

@command('givemine', 'gm', admin_only = True)
def givemine(conn):
    conn.mines += 1
    return "You got a mine."

@command('checkmines', 'cm')
def checkmines(conn):
    if not conn.world_object or conn.world_object.dead: return
    return "You have {} mine(s).".format(conn.mines)

def apply_script(protocol, connection, config):
    class MineProtocol(protocol):
        def __init__(self, *w, **kw):
            self.tile_entities = {}

            return protocol.__init__(self, *w, **kw)

        def add_tile_entity(self, klass, *w, **kw):
            entity = klass(*w, **kw)
            self.tile_entities[entity.position] = entity

            return entity

        def get_tile_entity(self, x, y, z):
            return self.tile_entities.get((x, y, z), dummy)

        def remove_tile_entity(self, x, y, z):
            self.tile_entities.pop((x, y, z))

        def on_map_change(self, M):
            self.tile_entities.clear()
            deleteQueueClear()

            return protocol.on_map_change(self, M)

        def on_world_update(self):
            for x, y, z in islice(onDeleteQueue(), 50):
                self.get_tile_entity(x, y, z).on_destroy()

            return protocol.on_world_update(self)

        def broadcast_contained(self, contained, unsequenced = False, sender = None, team = None, save = False, rule = None):
            protocol.broadcast_contained(self, contained, unsequenced, sender, team, save, rule)

            if isinstance(contained, loaders.BlockAction):
                # This is intentionally not in `on_block_build`.
                if contained.value == BUILD_BLOCK:
                    self.get_tile_entity(contained.x, contained.y, contained.z + 1).on_pressure()

            if isinstance(contained, loaders.BlockLine):
                locs = cube_line(
                    contained.x1, contained.y1, contained.z1,
                    contained.x2, contained.y2, contained.z2
                )

                for x, y, z in locs:
                    self.get_tile_entity(x, y, z + 1).on_pressure()

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
                    self.protocol.get_tile_entity(x + Δx, y + Δy, z).on_pressure()

        def on_position_update(self):
            if self.previous_position is not None:
                r1 = self.previous_position.get()
                r2 = self.world_object.position.get()

                M = self.protocol.map
                for x, y, z in cube_line(*r1, *r2):
                    for Δz in range(4):
                        if M.get_solid(x, y, z + Δz):
                            self.protocol.get_tile_entity(x, y, z + Δz).on_pressure()
                            break

                self.previous_position = self.world_object.position.copy()

            return connection.on_position_update(self)

        def on_block_removed(self, x, y, z):
            connection.on_block_removed(self, x, y, z)
            self.protocol.get_tile_entity(x, y, z).on_destroy()

        def grenade_destroy(self, x, y, z):
            retval = connection.grenade_destroy(self, x, y, z)

            if retval != False:
                for X, Y, Z in grenade_zone(x, y, z):
                    self.protocol.get_tile_entity(X, Y, Z).on_destroy()

            return retval

    return MineProtocol, MineConnection