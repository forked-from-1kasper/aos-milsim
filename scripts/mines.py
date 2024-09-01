from pyspades.common import Vertex3

from piqueserver.commands import command, player_only

from milsim.common import alive_only, apply_item
from milsim.types import TileEntity, Item
from milsim.blast import sendGrenadePacket

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
            sendGrenadePacket(self.protocol, player.player_id, loc, Vertex3(0, 0, 0), 0)

class Landmine(Explosive):
    Δz = -1.0

    on_pressure  = Explosive.explode
    on_explosion = Explosive.explode
    on_destroy   = Explosive.explode

class LandmineItem(Item):
    name = "Landmine"
    mass = 0.550

    def apply(self, player):
        if loc := player.world_object.cast_ray(10):
            protocol = player.protocol

            x, y, z = loc

            if z >= 63: return "You can't place a mine on water"

            player.inventory.remove(self)

            if e := protocol.get_tile_entity(x, y, z):
                e.on_pressure()
                return

            protocol.add_tile_entity(Landmine, protocol, loc, player.player_id)
            return "Mine placed at {}".format(loc)
        else:
            return "You can't place a mine so far away from yourself"

@command('mine', 'm')
@alive_only
def use_landmine(conn):
    """
    Puts a mine on the given block
    /mine
    """
    return apply_item(LandmineItem, conn, errmsg = "You do not have mines")

@command('givemine', 'gm', admin_only = True)
@player_only
def givemine(conn):
    conn.inventory.push(LandmineItem())
    return "You got a mine"

def apply_script(protocol, connection, config):
    class MineGrenadeTool(protocol.GrenadeTool):
        def on_rmb_press(self):
            protocol.GrenadeTool.on_rmb_press(self)

            if reply := use_landmine(self.player):
                self.player.send_chat(reply)

    class MineProtocol(protocol):
        GrenadeTool = MineGrenadeTool

        def on_map_change(self, M):
            protocol.on_map_change(self, M)

            for i in self.team1_tent_inventory, self.team2_tent_inventory:
                for k in range(30):
                    i.append(LandmineItem())

    class MineConnection(connection):
        def on_refill(self):
            connection.on_refill(self)

            for k in range(2):
                self.inventory.append(LandmineItem().mark_renewable())

    return MineProtocol, MineConnection