from twisted.internet import reactor

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

class Rifle:
    name        = "Rifle"
    Ammo        = Magazines(6, 10)
    round       = R762x54mm
    delay       = 0.50
    reload_time = 2.5

class SMG:
    name        = "SMG"
    Ammo        = Magazines(5, 30)
    round       = Parabellum
    delay       = 0.11
    reload_time = 2.5

class Shotgun:
    name        = "Shotgun"
    Ammo        = Heap(6, 48)
    round       = Buckshot1
    delay       = 1.00
    reload_time = 0.5

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

    def clear_tile_entities(self):
        self.tile_entities.clear()

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
