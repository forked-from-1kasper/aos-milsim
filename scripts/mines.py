from pyspades.collision import distance_3d_vector
from pyspades.contained import GrenadePacket
from piqueserver.commands import command
from pyspades.common import Vertex3
from pyspades.world import Grenade
from dataclasses import dataclass

MINE_ACTIVATE_DISTANCE = 3
MINE_SET_DISTANCE = 7
MINE = "mine"

@dataclass
class Mine:
    player_id : int
    def explode(self, protocol, pos):
        if self.player_id not in protocol.players:
            return
        player = protocol.players[self.player_id]

        x, y, z = pos

        loc = Vertex3(x, y, z - 0.5)
        vel = Vertex3(0, 0, 0)
        fuse = 0.1
        orientation = None

        grenade = protocol.world.create_object(
            Grenade, fuse, loc, orientation,
            vel, player.grenade_exploded
        )
        grenade.name = MINE

        pack = GrenadePacket()
        pack.value = fuse
        pack.player_id = self.player_id
        pack.position = loc.get()
        pack.velocity = vel.get()
        protocol.broadcast_contained(pack)

@command('mine', 'm')
def mine(conn, *args):
    loc = conn.world_object.cast_ray(MINE_SET_DISTANCE)
    if not loc:
        return "You can’t place a mine so far away from yourself."
    else:
        if loc in conn.protocol.mines:
            conn.protocol.explode(loc)

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
                self.mines[pos].explode(self, pos)
                del self.mines[pos]

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
                touched = []
                for pos, mine in self.protocol.mines.items():
                    x, y, z = pos
                    dist = distance_3d_vector(
                        pos0, Vertex3(x, y, z)
                    )
                    if dist <= MINE_ACTIVATE_DISTANCE:
                        touched.append(pos)

                for pos in touched:
                    self.protocol.explode(pos)
            except RuntimeError:
                pass

        def check_mine_by_pos(self, x, y, z):
            for pos, mine in self.protocol.mines.items():
                if pos == (x, y, z):
                    self.protocol.explode(pos)
                    break

        def on_position_update(self):
            self.check_mine(self.world_object.position)
            return connection.on_position_update(self)

        def on_block_destroy(self, x, y, z, mode):
            if connection.on_block_destroy(self, x, y, z, mode) == False:
                return False
            else:
                self.check_mine_by_pos(x, y, z)
                return True

        def on_block_removed(self, x, y, z):
            if connection.on_block_removed(self, x, y, z) == False:
                return False
            else:
                self.check_mine_by_pos(x, y, z)
                return True

        def grenade_destroy(self, x, y, z):
            if connection.grenade_destroy(self, x, y, z) == False:
                return False
            else:
                self.check_mine(Vertex3(x, y, z))
                return True

        def on_block_build(self, x, y, z):
            self.check_mine_by_pos(x, y, z + 1)
            return connection.on_block_build(self, x, y, z)

        def on_line_build(self, points):
            for (x, y, z) in points:
                self.check_mine_by_pos(x, y, z + 1)
            return connection.on_line_build(self, points)

    return MineProtocol, MineConnection