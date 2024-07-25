from pyspades.common import Vertex3

from piqueserver.commands import command, player_only

from milsim.types import TileEntity
import milsim.blast as blast

class Explosive(TileEntity):
    Δx = +0.5
    Δy = +0.5
    Δz = -0.5

    def __init__(self, protocol, position, player_id):
        self.player_id = player_id
        TileEntity.__init__(self, protocol, position)

    def explode(self):
        self.protocol.remove_tile_entity(*self.position)

        if player := self.protocol.take_player(self.player_id):
            x, y, z = self.position
            loc = Vertex3(x + self.Δx, y + self.Δy, z + self.Δz)

            player.grenade_explode(loc)
            blast.effect(self.protocol, player.player_id, loc, Vertex3(0, 0, 0), 0)

class Landmine(Explosive):
    Δz = -1.0

    on_pressure = Explosive.explode
    on_destroy  = Explosive.explode

@command('mine', 'm')
@player_only
def set_mine(conn):
    if not conn.ingame(): return

    loc = conn.world_object.cast_ray(10)
    if loc is None: return "You can't place a mine so far away from yourself."

    x, y, z = loc
    if z >= 63: return "You can't place a mine on water"

    if conn.mines > 0:
        conn.mines -= 1

        if e := conn.protocol.get_tile_entity(x, y, z):
            e.on_pressure()
            return

        conn.protocol.add_tile_entity(Landmine, conn.protocol, loc, conn.player_id)
        return "Mine placed at {}".format(loc)
    else:
        return "You do not have mines."

@command('givemine', 'gm', admin_only = True)
@player_only
def givemine(conn):
    conn.mines += 1
    return "You got a mine."

@command('checkmines', 'cm')
@player_only
def checkmines(conn):
    if conn.ingame():
        return "You have {} mine(s).".format(conn.mines)

def apply_script(protocol, connection, config):
    class MineGrenadeTool(protocol.GrenadeTool):
        def on_rmb_press(self):
            protocol.GrenadeTool.on_rmb_press(self)

            if reply := set_mine(self.player):
                self.player.send_chat(reply)

    class MineProtocol(protocol):
        GrenadeTool = MineGrenadeTool

    class MineConnection(connection):
        def __init__(self, *w, **kw):
            self.mines = 0
            return connection.__init__(self, *w, **kw)

        def on_spawn(self, pos):
            self.mines = 2
            return connection.on_spawn(self, pos)

        def refill(self, local = False):
            self.mines = 2
            return connection.refill(self, local)

    return MineProtocol, MineConnection