from dataclasses import dataclass

from pyspades.collision import distance_3d_vector
from pyspades.common import Vertex3

from piqueserver.commands import command
from piqueserver.config import config

from milsim.common import grenade_zone
import milsim.blast as blast

section = config.section("mines")

class Option:
    activation_distance = section.option("activation_distance", 3.5).get()
    setup_distance      = section.option("setup_distance", 13).get()

def down(pos):
    x, y, z = pos
    return (x, y, z + 1)

@dataclass
class Mine:
    player_id : int

    def explode(self, protocol, pos):
        if self.player_id not in protocol.players:
            return
        player = protocol.players[self.player_id]

        x, y, z = pos

        loc = Vertex3(x + 0.5, y + 0.5, z - 0.5)

        player.grenade_explode(loc)
        blast.effect(player, loc, Vertex3(0, 0, 0), 0)

@command('mine', 'm')
def mine(conn, *args):
    loc = conn.world_object.cast_ray(Option.setup_distance)

    if not loc:
        return "You can't place a mine so far away from yourself."
    else:
        if loc in conn.protocol.mines:
            conn.protocol.explode(loc)

        _, _, z = loc
        if z == 63:
            return "You can't place a mine on water"

        if conn.mines > 0:
            conn.protocol.mines[loc] = Mine(conn.player_id)
            conn.mines -= 1
            return "Mine placed at %s" % str(loc)
        else:
            return "You do not have mines."

@command('givemine', 'gm', admin_only=True)
def givemine(conn, *args):
    conn.mines += 1
    return "You got a mine."

@command('checkmines', 'cm')
def checkmines(conn, *args):
    return "You have %d mine(s)." % conn.mines

def apply_script(protocol, connection, config):
    class MineProtocol(protocol):
        def __init__(self, *arg, **kw):
            self.mines = {}
            return protocol.__init__(self, *arg, **kw)

        def explode(self, pos):
            if pos in self.mines:
                mine = self.mines.pop(pos)
                mine.explode(self, pos)

        def on_map_change(self, map):
            self.mines = {}
            return protocol.on_map_change(self, map)

    class MineConnection(connection):
        def on_spawn(self, pos):
            self.mines = 2
            return connection.on_spawn(self, pos)

        def refill(self, local=False):
            self.mines = 2
            return connection.refill(self, local)

        def check_mine(self, pos0):
            try:
                affected = []
                for pos, mine in self.protocol.mines.items():
                    x, y, z = pos
                    dist = distance_3d_vector(pos0, Vertex3(x, y, z))

                    if dist <= Option.activation_distance:
                        affected.append(pos)

                for pos in affected:
                    self.protocol.explode(pos)

            except RuntimeError:
                pass

        def check_mine_by_pos(self, positions):
            affected = []
            for pos, mine in self.protocol.mines.items():
                if pos in positions or not self.protocol.map.get_solid(*pos):
                    affected.append(pos)

            for pos in affected:
                self.protocol.explode(pos)

        def on_position_update(self):
            self.check_mine(self.world_object.position)
            return connection.on_position_update(self)

        def on_block_removed(self, x, y, z):
            self.check_mine_by_pos([(x, y, z)])
            connection.on_block_removed(self, x, y, z)

        def grenade_destroy(self, x, y, z):
            if connection.grenade_destroy(self, x, y, z) == False:
                return False
            else:
                self.check_mine_by_pos(grenade_zone(x, y, z))
                self.check_mine(Vertex3(x, y, z))
                return True

        def on_block_build(self, x, y, z):
            self.check_mine_by_pos([(x, y, z + 1)])
            return connection.on_block_build(self, x, y, z)

        def on_line_build(self, points):
            self.check_mine_by_pos(map(down, points))
            return connection.on_line_build(self, points)

    return MineProtocol, MineConnection