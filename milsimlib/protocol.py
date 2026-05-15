# Copyright © 2024–2026 rzrn

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.

# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

from itertools import islice
from time import monotonic
from random import choice
import os

from twisted.internet import threads
from twisted.logger import Logger

from pyspades.collision import distance_3d_vector
import pyspades.contained as loaders
from pyspades.common import Vertex3

from pyspades.constants import (
    RIFLE_WEAPON, SMG_WEAPON, SHOTGUN_WEAPON,
    WEAPON_KILL, HEADSHOT_KILL, MELEE_KILL, GRENADE_KILL,
    BUILD_BLOCK, DESTROY_BLOCK, SPADE_DESTROY, GRENADE_DESTROY
)

from piqueserver.server import FeatureProtocol
from piqueserver.config import config

from milsimlib.packets import (
    TracerPacket, HitEffectPacket,
    hasTraceExtension, hasHitEffects,
    milsim_extensions
)

from milsimlib.weapon import ABCWeapon, Rifle, SMG, Shotgun, HEIMagazine
from milsimlib.vxl import onDeleteQueue, deleteQueueClear
from milsimlib.map import MapInfo, check_rotation
from milsimlib.constants import Limb, HitEffect
from milsimlib.engine import Engine, toMeters
from milsimlib.common import grenade_zone

from milsimlib.types import Item, ItemEntity, Inventory, SpadeTool, BlockTool, GrenadeTool

from milsimlib.items import (
    Kettlebell, CompassItem, ProtractorItem, RangefinderItem, StunHandgrenadeItem,
    PulsarRadioItem, LiantongxinRadioItem, DurobandRadioItem
)
from milsimlib.underbarrel import GrenadeLauncher, GrenadeItem, FlashbangItem
from milsimlib.builtin import Buckshot0000, Buckshot00, Bullet
from milsimlib.types import CartridgeBox

def milsim_default_tent_loadout(protocol, team):
    for k in range(90):
        yield from (
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
            HEIMagazine(),
            StunHandgrenadeItem()
        )

    if team is protocol.team_1:
        for k in range(24):
            yield PulsarRadioItem()

    if team is protocol.team_2:
        for k in range(24):
            yield LiantongxinRadioItem()

    for k in range(5):
        yield DurobandRadioItem()

    yield from (
        Kettlebell(1),
        Kettlebell(5),
        Kettlebell(10),
        Kettlebell(15),
        Kettlebell(30),
        Kettlebell(50)
    )

log = Logger()

class MilsimProtocol(FeatureProtocol):
    suppression_rate_min   = 12.0
    suppression_rate_max   = 60.0
    suppression_threshold  = 0.5
    suppression_per_joule  = 0.15 / 1000
    suppression_near_range = 1.0
    suppression_far_range  = 20.0

    default_tent_loadout = milsim_default_tent_loadout

    WeaponTool  = ABCWeapon
    SpadeTool   = SpadeTool
    BlockTool   = BlockTool
    GrenadeTool = GrenadeTool

    def __init__(self, *w, **kw):
        self.map_dir = os.path.join(config.config_dir, 'maps')

        self.environment = None
        self.engine      = Engine(self)
        self.time        = monotonic()

        self.tile_entities = {}
        self.item_entities = {}

        self.rifle   = type('Rifle',   (Rifle,   self.WeaponTool), dict())
        self.smg     = type('SMG',     (SMG,     self.WeaponTool), dict())
        self.shotgun = type('Shotgun', (Shotgun, self.WeaponTool), dict())

        FeatureProtocol.__init__(self, *w, **kw)

        for team in self.team_1, self.team_2:
            team.tent_inventory = Inventory()

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
        if player := self.players.get(player_id):
            return player
        else:
            ids = list(self.players.keys())
            if len(ids) <= 0: return

            return self.players[choice(ids)]

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

            self.remove_item_entity(x, y, z1)
            self.new_item_entity(x, y, z2).extend(o)

    def clear_entities(self):
        self.tile_entities.clear()
        self.item_entities.clear()

    def update_weather(self):
        self.engine.update(self.environment)

        self.set_fog_color(self.environment.weather.fog())

        # See `milsim/connection/handlers.py` for more information.
        self.attenuation_coefficient = self.engine.attcoeff(1000.0) # Hz

    def on_environment_change(self, o):
        self.engine.clear()

        self.environment    = o
        self.build_material = o.build

        o.apply(self.engine)

        self.update_weather()

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

        for team in self.team_1, self.team_2:
            team.tent_inventory.clear()

            team.tent_inventory.extend(
                self.default_tent_loadout(team)
            )

        FeatureProtocol.on_map_change(self, M)

        t1 = monotonic()
        self.on_environment_change(self.map_info.environment)
        t2 = monotonic()

        log.info("Environment loading took {duration:.2f} s", duration = t2 - t1)

    def on_world_update(self):
        t = monotonic()
        dt = t - self.time

        if o := self.environment:
            if o.weather.update(dt):
                self.update_weather()

        self.engine.step(self.time, t)

        for x, y, z in islice(onDeleteQueue(), 50):
            if e := self.get_tile_entity(x, y, z):
                e.on_destroy()

            self.drop_item_entity(x, y, z)

        τ1, τ2 = self.suppression_rate_min, self.suppression_rate_max

        for player in self.living():
            if self.environment.size.inside(player.world_object.position) is False:
                player.kill()
                continue

            τ = τ2 + (τ1 - τ2) * player.courage_value
            player.suppression_value = τ * player.suppression_value / (τ + dt)

            if player.suppression_warning_sent:
                if player.suppression_value < 0.5:
                    player.suppression_warning_sent = False
            else:
                if player.suppression_value > 0.7:
                    player.suppression_warning_sent = True

                    player.body.pushl_message("You feel getting suppressed")

            player.body.update(dt)

            for leg in player.body.legs():
                if leg.fractured and not player.world_object.airborne:
                    if player.world_object.sprint:
                        leg.hit(leg.sprint_damage_rate * dt)
                    elif player.moving():
                        if not leg.splint: leg.hit(leg.walk_damage_rate * dt)

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

            if t - player.last_hp_update > 1.0:
                player.last_hp_update = t

                if mesg := player.body.take_message():
                    player.send_chat_status(mesg)

                hp = player.body.average()
                if player.hp != hp: player.set_hp(hp, kill_type = MELEE_KILL)

        self.time = t

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

    def onDestroy(self, player_id, x, y, z):
        player = self.players.get(player_id)

        if player is None:
            return

        count = self.map.destroy_point(x, y, z)

        if count > 0:
            contained           = loaders.BlockAction()
            contained.x         = x
            contained.y         = y
            contained.z         = z
            contained.value     = DESTROY_BLOCK
            contained.player_id = player_id

            self.broadcast_contained(contained, save = True)
            self.update_entities()

            player.on_block_removed(x, y, z)
            player.total_blocks_removed += count

    def onBlockHit(self, o, x, y, z, vx, vy, vz, X, Y, Z, thrower_id, E, A):
        self.broadcast_contained(
            HitEffectPacket(x, y, z, X, Y, Z, HitEffect.block),
            rule = hasHitEffects
        )

        r = Vertex3(x, y, z)
        v = Vertex3(vx, vy, vz)

        if callable(o.on_block_hit):
            return o.on_block_hit(self, r, v, X, Y, Z, thrower_id, E, A)

        svpj, d1, d2 = self.suppression_per_joule, self.suppression_near_range, self.suppression_far_range

        for player in self.living():
            if player.player_id == thrower_id: continue

            d = toMeters(distance_3d_vector(r, player.world_object.position))

            if d < d2:
                Δsv = svpj * E / max(d1 * d1, d * d)
                player.suppression_value = min(player.suppression_value + Δsv, 1.0)

    def onPlayerHit(self, o, x, y, z, vx, vy, vz, X, Y, Z, thrower_id, E, A, target_id, limb_index):
        player    = self.players.get(target_id)
        hit_by    = self.players.get(thrower_id, player)
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
                    self, Vertex3(x, y, z), Vertex3(vx, vy, vz), X, Y, Z, thrower_id, E, A, target_id, limb
                )

        return True