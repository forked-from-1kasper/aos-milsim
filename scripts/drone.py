from dataclasses import dataclass
from functools import partial
from enum import Enum, auto
from random import random
from math import floor

from twisted.internet import reactor

from pyspades.contained import GrenadePacket
from pyspades.protocol import BaseProtocol
from pyspades.common import Vertex3
from pyspades.world import Grenade
from pyspades.team import Team

from piqueserver.commands import command, get_player, CommandError
import scripts.blast as blast

MIN_FUSE = 3
MAX_FUSE = 5

class Status(Enum):
    inflight = auto()
    awaiting = auto()
    inwork   = auto()

DRONE_INIT_DELAY   = 10
DRONE_DELAY        = 240
DRONE_POLL_DELAY   = 2
DRONE_POLL_TIMEOUT = 60

class Ghost:
    def __init__(self):
        self.status   = None
        self.callback = None
        self.grenades = 0

    def init(self, by_server=False):
        pass

    def report(self, msg):
        pass

    def start(self):
        pass

    def stop(self):
        pass

    def track(self, player, target):
        pass

    def remaining(self):
        pass

@dataclass
class Drone:
    name     : str
    team     : Team
    protocol : BaseProtocol

    def __post_init__(self):
        self.init()

    def init(self, by_server=False):
        self.status   = Status.inflight
        self.callback = None
        self.target   = None
        self.grenades = 0
        self.passed   = 0

        if by_server:
            self.callback = reactor.callLater(DRONE_INIT_DELAY, self.start)

    def report(self, msg):
        self.protocol.broadcast_chat(
            "<%s> %s. Over." % (self.name, msg),
            global_message=False, team=self.team
        )

    def start(self):
        if self.status != Status.inflight:
            return

        self.arrive()

    def stop(self):
        if self.callback and self.callback.active():
            self.callback.cancel()
            self.callback = None

    def arrive(self):
        self.grenades = 3
        self.status = Status.awaiting
        self.report("Drone on the battlefield")

    def track(self, client, target):
        self.client = client
        self.target = target
        self.status = Status.inwork
        self.passed = 0

        self.report("Received. Watching for %s" % target.name)
        self.callback = reactor.callLater(DRONE_POLL_DELAY, self.ping)

    def ping(self):
        self.passed += DRONE_POLL_DELAY

        if self.passed > DRONE_POLL_TIMEOUT:
            self.report("Don’t see %s. Awaiting for further instructions" % self.target.name)

            self.status = Status.awaiting
            self.passed = 0
            self.target = None
            self.client = None

            return

        x, y, z = self.target.world_object.position.get()
        H = self.protocol.map.get_z(floor(x), floor(y))

        if z <= H:
            fuse = rand(MIN_FUSE, MAX_FUSE)

            position = Vertex3(x, y, 0)
            velocity = Vertex3(0, 0, 0)

            grenade = self.protocol.world.create_object(
                Grenade, fuse, position, None, velocity, self.client.grenade_exploded
            )
            grenade.name = 'grenade'

            blast.effect(self.client, position, velocity, fuse)

            self.grenades -= 1

            self.passed = 0
            self.target = None
            self.client = None

            if self.grenades > 0:
                self.status   = Status.awaiting
                self.callback = None
                self.report("Bombed out. Awaiting for further instructions")

            else:
                self.status   = Status.inflight
                self.callback = reactor.callLater(DRONE_DELAY, self.arrive)
                self.report("Bombed out. Will be ready in %s seconds" % DRONE_DELAY)
        else:
            self.callback = reactor.callLater(DRONE_POLL_DELAY, self.ping)

    def remaining(self):
        if self.callback:
            return self.callback.getTime() - reactor.seconds()
        else:
            return None

def rand(a, b):
    return a + random() * (b - a)

@command('drone', 'd')
def drone(conn, *args):
    if conn.player_id not in conn.protocol.players: return

    drone = conn.get_drone()

    if drone.status == Status.inflight:
        remaining = drone.remaining()
        if remaining:
            approx = (remaining // 5 + 1) * 5
            drone.report("Will be on the battlefield in %d seconds" % approx)

    if drone.status == Status.inwork:
        drone.report("Drone is busy")

    if drone.status == Status.awaiting:
        if len(args) > 0:
            player = get_player(conn.protocol, args[0], spectators=False)

            if player.team.id == conn.team.id:
                raise CommandError("Expected enemy’s nickname")

            drone.track(conn, player)
        else:
            conn.send_lines(["Usage: /drone <player>"], 'usage')

def apply_script(protocol, connection, config):
    class DroneProtocol(protocol):
        def __init__(self, *arg, **kw):
            protocol.__init__(self, *arg, **kw)
            self.drones = {
                self.team_spectator.id : Ghost(),
                self.team_1.id         : Drone("DJI Mavic 3",   self.team_1, self),
                self.team_2.id         : Drone("DJI Phantom 4", self.team_2, self)
            }

        def on_map_change(self, map):
            for drone in self.drones.values():
                drone.stop()
                drone.init(by_server=True)

            return protocol.on_map_change(self, map)

    class DroneConnection(connection):
        def get_drone(self):
            return self.protocol.drones[self.team.id]

    return DroneProtocol, DroneConnection