from itertools import islice
from time import monotonic
from random import choice
import os

from twisted.internet import reactor, threads
from twisted.logger import Logger

from pyspades import contained as loaders
from pyspades.common import Vertex3
from pyspades.constants import *

from piqueserver.server import FeatureProtocol
from piqueserver.config import config

from milsim.packets import (
    TracerPacket, HitEffectPacket,
    hasTraceExtension, hasHitEffects,
    milsim_extensions
)

from milsim.weapon import GrenadeLauncher, GrenadeItem, FlashbangItem
from milsim.vxl import onDeleteQueue, deleteQueueClear
from milsim.blast import sendGrenadePacket, explode
from milsim.map import MapInfo, check_rotation
from milsim.constants import Limb, HitEffect
from milsim.simulator import Simulator
from milsim.weapon import ABCWeapon
from milsim.common import *

def icons(x, xs):
    yield x
    yield from xs

class DetachableMagazineItem:
    def reserve(self):
        return filter(
            lambda o: isinstance(o, self.magazine_class),
            self.player.inventory
        )

    def restock(self):
        self.magazine = self.default_magazine()
        self.magazine.mark_renewable()

    def refill(self):
        i = self.player.inventory
        for k in range(self.default_magazine_count):
            i.append(self.default_magazine().mark_renewable())

    def format_ammo(self):
        it = icons(
            "{}*".format(self.magazine.current()),
            map(lambda o: "{}".format(o.current()), self.reserve())
        )

        return "Magazines: {}".format(", ".join(it))

class IntegralMagazineItem:
    def reserve(self):
        return filter(
            lambda o: isinstance(o, CartridgeBox) and
                      isinstance(o.object, self.cartridge_class),
            self.player.inventory
        )

    def restock(self):
        self.magazine = self.default_magazine()
        self.magazine.mark_renewable()

        for k in range(self.magazine.capacity):
            self.magazine.push(self.default_cartridge)

    def refill(self):
        i = self.player.inventory
        i.append(CartridgeBox(self.default_cartridge, self.default_reserve).mark_renewable())

Buckshot1 = Shotshell(name = "0000 Buckshot", muzzle = 457.00, effmass = grain(82.000),  totmass = gram(150.00), grouping = isosceles(yard(25), inch(40)), deviation = 0.10, diameter = mm(9.65), pellets = 15)
Buckshot2 = Shotshell(name = "00 Buckshot",   muzzle = 396.24, effmass = grain(350.000), totmass = gram(170.00), grouping = isosceles(yard(25), inch(40)), deviation = 0.10, diameter = mm(8.38), pellets = 5)
Bullet    = Shotshell(name = "Bullet",        muzzle = 540.00, effmass = grain(109.375), totmass = gram(20.00),  grouping = 0,                             deviation = 0.10, diameter = mm(10.4), pellets = 1)

class G7HEI(G7):
    def explode(self, protocol, player_id, r):
        if player := protocol.players.get(player_id):
            sendGrenadePacket(protocol, player_id, r, Vertex3(1, 0, 0), -1)
            explode(4, 20, player, r)

            return True

    def on_block_hit(self, protocol, r, v, X, Y, Z, thrower, E, A):
        return self.explode(protocol, thrower, r)

    def on_player_hit(self, protocol, r, v, X, Y, Z, thrower, E, A, target, limb_index):
        return self.explode(protocol, thrower, r)

R145x114mm = G1(name = "R145x114mm", muzzle = 1000, effmass = gram(67.00), totmass = gram(191.00), grouping = MOA(0.7), deviation = 0.03, BC = 0.800, caliber = mm(14.50))
R127x108mm = G1(name = "R127x108mm", muzzle = 900,  effmass = gram(50.00), totmass = gram(130.00), grouping = MOA(0.7), deviation = 0.03, BC = 0.732, caliber = mm(12.70))
R762x54mm  = G7(name = "R762x54mm",  muzzle = 850,  effmass = gram(10.00), totmass = gram(22.00),  grouping = MOA(0.7), deviation = 0.03, BC = 0.187, caliber = mm(07.62))
Parabellum = G1(name = "Parabellum", muzzle = 600,  effmass = gram(8.03),  totmass = gram(12.00),  grouping = MOA(2.5), deviation = 0.05, BC = 0.212, caliber = mm(09.00))

HEI762x54mm = G7HEI(name = "HEI762x54mm", muzzle = 820, effmass = gram(160.00), totmass = gram(250.00), grouping = MOA(2.0), deviation = 0.07, BC = 0.190, caliber = mm(07.62))

class RifleMagazine(BoxMagazine):
    pass

class R762Magazine(RifleMagazine):
    _mass     = 0.227
    _name     = "AA762R02"
    capacity  = 10
    cartridge = R762x54mm

class HEIMagazine(RifleMagazine):
    _mass     = 0.150
    _name     = "AA762HEI"
    capacity  = 5
    cartridge = HEI762x54mm

class Rifle(DetachableMagazineItem):
    _mass                  = 4.220
    name                   = "Rifle"
    delay                  = 0.50
    reload_time            = 2.5
    magazine_class         = RifleMagazine
    default_magazine       = R762Magazine
    default_magazine_count = 5

class SMGMagazine(BoxMagazine):
    pass

class ParabellumMagazine(SMGMagazine):
    _mass     = 0.160
    _name     = "MP5MAG30"
    capacity  = 30
    cartridge = Parabellum

class SMG(DetachableMagazineItem):
    _mass                  = 3.600
    name                   = "SMG"
    delay                  = 0.11
    reload_time            = 2.5
    magazine_class         = SMGMagazine
    default_magazine       = ParabellumMagazine
    default_magazine_count = 4

class ShotgunMagazine(TubularMagazine):
    capacity = 6

class Shotgun(IntegralMagazineItem):
    _mass             = 3.600
    name              = "Shotgun"
    delay             = 1.00
    reload_time       = 0.5
    cartridge_class   = Shotshell
    default_magazine  = ShotgunMagazine
    default_cartridge = Buckshot1
    default_reserve   = 70

log = Logger()

class MilsimProtocol(FeatureProtocol):
    WeaponTool  = ABCWeapon
    SpadeTool   = SpadeTool
    BlockTool   = BlockTool
    GrenadeTool = GrenadeTool

    def __init__(self, *w, **kw):
        self.map_dir = os.path.join(config.config_dir, 'maps')

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

        FeatureProtocol.__init__(self, *w, **kw)

        self.team_spectator.kills = 0 # bugfix
        self.available_proto_extensions.extend(milsim_extensions)

    def set_map_rotation(self, maps):
        self.maps = check_rotation(maps, self.map_dir)
        self.map_rotator = self.map_rotator_type(self.maps)

    def make_map(self, rot_info):
        return threads.deferToThread(MapInfo, rot_info, self.map_dir)

    def on_connect(self, peer):
        log.info("{address} connected", address = peer.address)
        FeatureProtocol.on_connect(self, peer)

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

        self.environment = o
        o.apply(self.simulator)
        self.update_weather()

    def on_simulator_update(self):
        t = reactor.seconds()
        dt = t - self.time

        if self.environment is not None:
            if self.environment.weather.update(dt):
                self.update_weather()

        self.simulator.step(self.time, t)
        self.time = t

    def on_block_build(self, x, y, z):
        self.simulator.build(x, y, z)

        if e := self.get_tile_entity(x, y, z + 1):
            e.on_pressure()

    def on_block_destroy(self, x, y, z):
        self.simulator.destroy(x, y, z)

        if e := self.get_tile_entity(x, y, z):
            e.on_destroy()

        self.drop_item_entity(x, y, z)

    def on_map_change(self, M):
        deleteQueueClear()

        for player in self.players.values():
            player.weapon_object.clear()
            player.inventory.clear()

        self.clear_entities()
        Item.reset()

        FeatureProtocol.on_map_change(self, M)

        for i in self.team1_tent_inventory, self.team2_tent_inventory:
            for k in range(90):
                i.append(
                    GrenadeLauncher(),
                    GrenadeItem(),
                    GrenadeItem(),
                    GrenadeItem(),
                    FlashbangItem(),
                    CompassItem(),
                    ProtractorItem(),
                    RangefinderItem(),
                    CartridgeBox(Bullet, 50),
                    CartridgeBox(Buckshot1, 60),
                    CartridgeBox(Buckshot2, 60),
                    HEIMagazine()
                )

            i.append(
                Kettlebell(1),
                Kettlebell(5),
                Kettlebell(10),
                Kettlebell(15),
                Kettlebell(30),
                Kettlebell(50)
            )

        t1 = monotonic()
        self.on_environment_change(self.map_info.environment)
        t2 = monotonic()

        log.info("Environment loading took {duration:.2f} s", duration = t2 - t1)

    def on_world_update(self):
        self.on_simulator_update()

        for x, y, z in islice(onDeleteQueue(), 50):
            if e := self.get_tile_entity(x, y, z):
                e.on_destroy()

            self.drop_item_entity(x, y, z)

        t = reactor.seconds()

        for player in self.living():
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

                if player.world_object.sneak:
                    player.tool_object.on_sneak_hold(t, dt)

            hp = player.body.average()
            if player.hp != hp:
                player.set_hp(hp, kill_type = MELEE_KILL)

            if not self.environment.size.inside(player.world_object.position):
                player.kill()

            player.last_hp_update = t

        FeatureProtocol.on_world_update(self)

    def broadcast_contained(self, contained, unsequenced = False, sender = None, team = None, save = False, rule = None):
        FeatureProtocol.broadcast_contained(self, contained, unsequenced, sender, team, save, rule)

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

    def onTrace(self, index, x, y, z, value, origin):
        self.broadcast_contained(
            TracerPacket(index, Vertex3(x, y, z), value, origin = origin),
            rule = hasTraceExtension
        )

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

    def onBlockHit(self, o, x, y, z, vx, vy, vz, X, Y, Z, thrower, E, A):
        self.broadcast_contained(
            HitEffectPacket(x, y, z, X, Y, Z, HitEffect.block),
            rule = hasHitEffects
        )

        if callable(o.on_block_hit):
            return o.on_block_hit(
                self, Vertex3(x, y, z), Vertex3(vx, vy, vz), X, Y, Z, thrower, E, A
            )

    def onPlayerHit(self, o, x, y, z, vx, vy, vz, X, Y, Z, thrower, E, A, target, limb_index):
        player    = self.players.get(target)
        hit_by    = self.players.get(thrower, player)
        limb      = Limb(limb_index)
        kill_type = GRENADE_KILL if o.grenade else HEADSHOT_KILL if limb == Limb.head else WEAPON_KILL

        if player is None: return

        damage, venous, arterial, fractured = player.body[limb].ofEnergyAndArea(E, A)

        if damage > 0:
            player.hit(
                damage, limb = limb, hit_by = hit_by, kill_type = kill_type,
                venous = venous, arterial = arterial, fractured = fractured,
            )

            self.broadcast_contained(
                HitEffectPacket(x, y, z, X, Y, Z, HitEffect.headshot if limb == Limb.head else HitEffect.player),
                rule = hasHitEffects
            )

            if callable(o.on_player_hit):
                return o.on_player_hit(
                    self, Vertex3(x, y, z), Vertex3(vx, vy, vz), X, Y, Z, thrower, E, A, target, limb
                )

        return True