from collections import deque

from pyspades.common import Vertex3

from piqueserver.commands import command, player_only

from milsim.common import alive_only, apply_item, has_item, take_item, take_items
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

class Charge(Explosive):
    on_explosion = Explosive.explode
    on_destroy   = Explosive.explode

class ExplosiveItem(Item):
    def apply(self, player):
        if loc := player.world_object.cast_ray(7):
            x, y, z = loc

            if z >= 63: return "{} cannot be placed on water".format(self.name)
            return self.spawn(player, x, y, z)
        else:
            return "{} cannot be placed that far away from you".format(self.name)

    def spawn(self, player, x, y, z):
        player.inventory.remove(self)

        protocol = player.protocol
        protocol.add_tile_entity(
            self.tileEntityClass, protocol, (x, y, z), player.player_id
        )

        return "{} placed at ({}, {}, {})".format(self.name, x, y, z)

class LandmineItem(ExplosiveItem):
    tileEntityClass = Landmine
    name            = "Landmine"
    mass            = 0.550

    def spawn(self, player, x, y, z):
        if e := player.protocol.get_tile_entity(x, y, z):
            if isinstance(e, LandmineItem):
                player.inventory.remove(self)
                e.explode()

                return
            else:
                return "{} cannot be placed here".format(self.name)

        return ExplosiveItem.spawn(self, player, x, y, z)

class DetonatorItem(Item):
    mass  = 0.150
    limit = 4

    def __init__(self):
        Item.__init__(self)
        self.targets = []

    @property
    def name(self):
        return "Detonator ({})".format(len(self.targets))

    def add(self, x, y, z):
        self.targets.append((x, y, z))

    def available(self):
        return len(self.targets) < self.limit

    def apply(self, player):
        protocol = player.protocol

        for x, y, z in self.targets:
            if e := protocol.get_tile_entity(x, y, z):
                if isinstance(e, Charge):
                    e.explode()

        self.targets = []

class ChargeItem(ExplosiveItem):
    tileEntityClass = Charge
    name            = "Charge"
    mass            = 0.700

    def spawn(self, player, x, y, z):
        if player.protocol.get_tile_entity(x, y, z) is not None:
            return "{} cannot be placed here".format(self.name)

        it = filter(
            lambda o: isinstance(o, DetonatorItem) and o.available(),
            player.inventory
        )

        if o := next(it, None):
            o.add(x, y, z)
            return ExplosiveItem.spawn(self, player, x, y, z)
        else:
            return "You don't have an available detonator"

@command('mine', 'm')
@alive_only
def use_landmine(conn):
    """
    Put a mine on the given block
    /m or /mine
    """
    return apply_item(LandmineItem, conn, errmsg = "You do not have mines")

@command('charge', 'c')
@alive_only
def use_charge(conn):
    """
    Put a charge on the given block
    /c or /charge
    """
    return apply_item(ChargeItem, conn, errmsg = "You do not have charges")

@command('detonate', 'de')
@alive_only
def use_detonator(conn):
    """
    Activate a detonator
    /de or /detonate
    """
    return apply_item(DetonatorItem, conn, errmsg = "You do not have a detonator")

@command('takecharge', 'tc')
@alive_only
def take_charge(conn, n):
    """
    Try to take a given number of charges and a detonator
    /tc [n] or /takecharge
    """
    n = int(n)

    if n <= 0: return "Invalid number of charges"

    if not has_item(conn, DetonatorItem):
        take_item(conn, DetonatorItem)

    take_items(conn, ChargeItem, n, 5)

def apply_script(protocol, connection, config):
    class MineGrenadeTool(protocol.GrenadeTool):
        def on_rmb_press(self):
            protocol.GrenadeTool.on_rmb_press(self)

            if reply := apply_item(ExplosiveItem, self.player, errmsg = "You do not have explosives"):
                self.player.send_chat(reply)

    class MineProtocol(protocol):
        GrenadeTool = MineGrenadeTool

        def on_map_change(self, M):
            protocol.on_map_change(self, M)

            for i in self.team1_tent_inventory, self.team2_tent_inventory:
                for k in range(100):
                    i.append(
                        LandmineItem(),
                        DetonatorItem(),
                        ChargeItem(),
                        ChargeItem()
                    )

    class MineConnection(connection):
        def on_refill(self):
            connection.on_refill(self)

            for k in range(2):
                self.inventory.append(LandmineItem().mark_renewable())

    return MineProtocol, MineConnection