from twisted.internet import reactor

from pyspades import contained as loaders
from pyspades.common import Vertex3
from pyspades.constants import *

from milsim.simulator import Simulator
from milsim.common import *

class ABCSimulatorManager:
    def __new__(Klass, *w, **kw):
        raise NotImplementedError

    def __init__(self):
        self.environment = None
        self.simulator   = Simulator(self)
        self.time        = reactor.seconds()

    def updateWeather(self):
        self.simulator.update(self.environment)
        self.set_fog_color(self.environment.weather.fog())

    def onWipe(self, o):
        self.simulator.wipe()

        if isinstance(o, Environment):
            self.environment = o
            o.apply(self.simulator)
            self.updateWeather()
        else:
            raise TypeError("“environment” expected to be of the type milsim.types.Enviornment")

    def onTick(self):
        t = reactor.seconds()
        dt = t - self.time

        if self.environment is not None:
            if self.environment.weather.update(dt):
                self.updateWeather()

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
