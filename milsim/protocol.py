from twisted.internet import reactor
from random import choice

from pyspades.protocol import BaseProtocol
from pyspades import contained as loaders
from pyspades.common import Vertex3
from pyspades.constants import *

from milsim.packets import (
    TracerPacket, HitEffectPacket,
    hasTraceExtension, hasHitEffects,
    milsim_extensions
)
from milsim.simulator import Simulator
from milsim.weapon import ABCWeapon
from milsim.constants import Limb
from milsim.common import *

class DetachableMagazineItem:
    def restock(self):
        self.magazine = self.default_magazine()
        self.magazine.mark_renewable()

    def refill(self):
        i = self.player.inventory
        for k in range(self.default_magazine_count):
            i.append(self.default_magazine().mark_renewable())

class IntegralMagazineItem:
    def restock(self):
        self.magazine = self.default_magazine()
        self.magazine.mark_renewable()

        for k in range(self.magazine.capacity):
            self.magazine.push(self.default_cartridge)

    def refill(self):
        i = self.player.inventory
        i.append(CartridgeBox(self.default_cartridge, self.default_reserve).mark_renewable())

class RifleMagazine(BoxMagazine):
    _mass     = 0.227
    _name     = "AA762R02"
    capacity  = 10
    cartridge = R762x54mm

class Rifle(DetachableMagazineItem):
    _mass                  = 4.220
    name                   = "Rifle"
    delay                  = 0.50
    reload_time            = 2.5
    default_magazine       = RifleMagazine
    default_magazine_count = 6

class SMGMagazine(BoxMagazine):
    _mass     = 0.160
    _name     = "MP5MAG30"
    capacity  = 30
    cartridge = Parabellum

class SMG(DetachableMagazineItem):
    _mass                  = 3.600
    name                   = "SMG"
    delay                  = 0.11
    reload_time            = 2.5
    default_magazine       = SMGMagazine
    default_magazine_count = 4

class ShotgunMagazine(TubularMagazine):
    capacity  = 6
    cartridge = Shotshell

class Shotgun(IntegralMagazineItem):
    _mass             = 3.600
    name              = "Shotgun"
    delay             = 1.00
    reload_time       = 0.5
    default_magazine  = ShotgunMagazine
    default_cartridge = Buckshot1
    default_reserve   = 70

class MilsimProtocol:
    WeaponTool  = ABCWeapon
    SpadeTool   = SpadeTool
    BlockTool   = BlockTool
    GrenadeTool = GrenadeTool

    def __init__(self, *w, **kw):
        assert isinstance(self, BaseProtocol)

        self.environment = None
        self.simulator   = Simulator(self)
        self.time        = reactor.seconds()

        self.tile_entities = {}
        self.item_entities = {}

        self.team1_tent_inventory = Inventory()
        self.team2_tent_inventory = Inventory()

        self.rifle   = type('Rifle',   (Rifle,   self.WeaponTool), dict())
        self.smg     = type('SMG',     (SMG,     self.WeaponTool), dict())
        self.shotgun = type('Shotgun', (Shotgun, self.WeaponTool), dict())

        self.available_proto_extensions.extend(milsim_extensions)

    def get_weapon(self, weapon):
        if weapon == RIFLE_WEAPON:
            return self.rifle

        if weapon == SMG_WEAPON:
            return self.smg

        if weapon == SHOTGUN_WEAPON:
            return self.shotgun

    def living(self):
        for player in self.players.values():
            if player.alive():
                yield player

    def take_player(self, player_id):
        if player_id not in self.players:
            ids = list(self.players.keys())

            if len(ids) > 0:
                return self.players[choice(ids)]
        else:
            return self.players[player_id]

    def add_tile_entity(self, klass, *w, **kw):
        entity = klass(*w, **kw)
        self.tile_entities[entity.position] = entity

        return entity

    def get_tile_entity(self, x, y, z):
        return self.tile_entities.get((x, y, z))

    def remove_tile_entity(self, x, y, z):
        self.tile_entities.pop((x, y, z))

    def get_item_entity(self, x, y, z):
        return self.item_entities.get((x, y, z))

    def remove_item_entity(self, x, y, z):
        self.item_entities.pop((x, y, z))

    def new_item_entity(self, x, y, z):
        if o := self.item_entities.get((x, y, z)):
            return o
        else:
            o = ItemEntity(self, x, y, z)
            self.item_entities[(x, y, z)] = o

            return o

    def drop_item_entity(self, x, y, z1):
        if o := self.get_item_entity(x, y, z1):
            z2 = self.map.get_z(x, y, z1)
            if z1 == z2: return

            self.new_item_entity(x, y, z2).extend(o)
            self.remove_item_entity(x, y, z1)

    def clear_entities(self):
        self.tile_entities.clear()
        self.item_entities.clear()

        self.team1_tent_inventory.clear()
        self.team2_tent_inventory.clear()

    def update_weather(self):
        self.simulator.update(self.environment)
        self.set_fog_color(self.environment.weather.fog())

    def on_environment_change(self, o):
        self.simulator.wipe()

        if isinstance(o, Environment):
            self.environment = o
            o.apply(self.simulator)
            self.update_weather()
        else:
            raise TypeError("“environment” expected to be of the type milsim.types.Enviornment")

    def on_simulator_update(self):
        t = reactor.seconds()
        dt = t - self.time

        if self.environment is not None:
            if self.environment.weather.update(dt):
                self.update_weather()

        self.simulator.step(self.time, t)
        self.time = t

    def onTrace(self, index, x, y, z, value, origin):
        self.broadcast_contained(
            TracerPacket(index, Vertex3(x, y, z), value, origin = origin),
            rule = hasTraceExtension
        )

    def onHitEffect(self, x, y, z, X, Y, Z, target):
        self.broadcast_contained(
            HitEffectPacket(Vertex3(x, y, z), X, Y, Z, target),
            rule = hasHitEffects
        )

    def on_block_build(self, x, y, z):
        self.simulator.build(x, y, z)

        if e := self.get_tile_entity(x, y, z + 1):
            e.on_pressure()

    def on_block_destroy(self, x, y, z):
        self.simulator.destroy(x, y, z)

        if e := self.get_tile_entity(x, y, z):
            e.on_destroy()

        self.drop_item_entity(x, y, z)

    def onDestroy(self, pid, x, y, z):
        if pid not in self.players:
            return

        player = self.players[pid]

        count = self.map.destroy_point(x, y, z)

        if count:
            contained           = loaders.BlockAction()
            contained.x         = x
            contained.y         = y
            contained.z         = z
            contained.value     = DESTROY_BLOCK
            contained.player_id = pid

            self.broadcast_contained(contained, save = True)
            self.update_entities()

            player.on_block_removed(x, y, z)
            player.total_blocks_removed += count

    def onHit(self, thrower, target, index, E, A, grenade):
        if target not in self.players:
            return

        player    = self.players[target]
        hit_by    = self.players.get(thrower, player)
        limb      = Limb(index)
        kill_type = GRENADE_KILL if grenade else HEADSHOT_KILL if limb == Limb.head else WEAPON_KILL

        damage, venous, arterial, fractured = player.body[limb].ofEnergyAndArea(E, A)

        if damage > 0:
            player.hit(
                damage, limb = limb, hit_by = hit_by, kill_type = kill_type,
                venous = venous, arterial = arterial, fractured = fractured,
            )
