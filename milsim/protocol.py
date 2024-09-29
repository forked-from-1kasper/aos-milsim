from itertools import islice
from time import monotonic
from random import choice
import os

from twisted.internet import reactor, threads
from twisted.logger import Logger

import pyspades.contained as loaders
from pyspades.common import Vertex3
from pyspades.constants import *

from piqueserver.server import FeatureProtocol
from piqueserver.config import config

from milsim.packets import (
    TracerPacket, HitEffectPacket,
    hasTraceExtension, hasHitEffects,
    milsim_extensions
)

from milsim.items import Kettlebell, CompassItem, ProtractorItem, RangefinderItem
from milsim.underbarrel import GrenadeLauncher, GrenadeItem, FlashbangItem
from milsim.weapon import ABCWeapon, Rifle, SMG, Shotgun, HEIMagazine
from milsim.builtin import Buckshot0000, Buckshot00, Bullet
from milsim.vxl import onDeleteQueue, deleteQueueClear
from milsim.map import MapInfo, check_rotation
from milsim.constants import Limb, HitEffect
from milsim.types import CartridgeBox
from milsim.engine import Engine
from milsim.common import *

log = Logger()

class MilsimProtocol(FeatureProtocol):
    WeaponTool  = ABCWeapon
    SpadeTool   = SpadeTool
    BlockTool   = BlockTool
    GrenadeTool = GrenadeTool

    def __init__(self, *w, **kw):
        self.map_dir = os.path.join(config.config_dir, 'maps')

        self.environment = None
        self.engine      = Engine(self)
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
        self.engine.update(self.environment)

        self.set_fog_color(self.environment.weather.fog())

    def on_environment_change(self, o):
        self.engine.clear()

        self.environment    = o
        self.build_material = o.build

        o.apply(self.engine)

        self.update_weather()

    def on_engine_update(self):
        t = reactor.seconds()
        dt = t - self.time

        if self.environment is not None:
            if self.environment.weather.update(dt):
                self.update_weather()

        self.engine.step(self.time, t)
        self.time = t

    def on_block_build(self, x, y, z):
        self.engine[x, y, z] = self.build_material

        if e := self.get_tile_entity(x, y, z + 1):
            e.on_pressure()

    def on_block_destroy(self, x, y, z):
        del self.engine[x, y, z]

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
                    CartridgeBox(Buckshot0000, 60),
                    CartridgeBox(Buckshot00, 60),
                    CartridgeBox(Bullet, 50),
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
        self.on_engine_update()

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