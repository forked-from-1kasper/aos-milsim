from random import randint, random, uniform
from dataclasses import dataclass
from math import floor, inf
from time import sleep

from twisted.internet import reactor

from pyspades.protocol import BaseProtocol
from pyspades.constants import WEAPON_TOOL
from piqueserver.config import config
from pyspades.common import Vertex3
from pyspades.team import Team

from milsim.blast import sendGrenadePacket, explode
from milsim.weapon import UnderbarrelItem
from piqueserver.commands import command
from milsim.common import alive_only

section = config.section("airstrike")

airstrike_zoomv_time = section.option("zoomv_time", 2).get()
airstrike_delay      = section.option("delay", 7 * 60).get()
aitstrike_phase      = section.option("phase", 120).get()

BOMBS_COUNT   = 7
BOMBER_SPEED  = 10
BOMBING_DELAY = 2

AIRBOMB_DELAY                  = 3
AIRBOMB_RADIUS                 = 10
AIRBOMB_SAFE_DISTANCE          = 150
AIRBOMB_GUARANTEED_KILL_RADIUS = 40

AIRSTRIKE_PASSES        = 50
AIRSTRIKE_CAST_DISTANCE = 300

def airbomb_explode(protocol, player_id, x, y, z):
    if player := protocol.take_player(player_id):
        explode(AIRBOMB_GUARANTEED_KILL_RADIUS, AIRBOMB_SAFE_DISTANCE, player, Vertex3(x, y, z))

        for i in range(AIRSTRIKE_PASSES):
            X = x + randint(-AIRBOMB_RADIUS, AIRBOMB_RADIUS)
            Y = y + randint(-AIRBOMB_RADIUS, AIRBOMB_RADIUS)
            Z = protocol.map.get_z(X, Y)

            player.grenade_destroy(X, Y, Z)
            sendGrenadePacket(protocol, player.player_id, Vertex3(X, Y, Z), Vertex3(0, 0, 0), 0)

            sleep(uniform(0.0, 0.05))

def drop_airbomb(protocol, player_id, x, y):
    X = floor(x)
    Y = floor(y)
    Z = protocol.map.get_z(X, Y) - 2

    airbomb_explode(protocol, player_id, X, Y, Z)

def do_bombing(protocol, player_id, x, y, vx, vy, nbombs):
    for k in range(nbombs):
        sleep(BOMBING_DELAY)
        drop_airbomb(protocol, player_id, x, y)

        x += vx * BOMBING_DELAY
        y += vy * BOMBING_DELAY

def do_airstrike(name, connection):
    protocol = connection.protocol

    if wo := connection.world_object:
        if loc := wo.cast_ray(AIRSTRIKE_CAST_DISTANCE):
            protocol.broadcast_chat(
                "<{}> Coordinates recieved. Over.".format(name),
                global_message = False, team = connection.team
            )

            x, y, z = loc
            o = wo.orientation
            v = Vertex3(o.x, o.y, 0).normal() * BOMBER_SPEED

            reactor.callInThread(do_bombing, protocol, connection.player_id, x, y, v.x, v.y, BOMBS_COUNT)

@command(admin_only = True)
@alive_only
def gift(connection):
    do_airstrike("Panavia Tornado ECR", connection)

@command()
@alive_only
def air(player):
    """
    Report time before bomber's arrival
    /air
    """

    if o := player.get_bomber():
        remaining = o.remaining()

        if remaining is not None:
            approx = round((remaining / 10 + 1) * 10)
            o.report("Will be ready in {} seconds".format(approx))
        else:
            o.report("Awaiting for coordinates")

class Laser(UnderbarrelItem):
    name = "Laser"
    mass = 0.500

    def __init__(self):
        UnderbarrelItem.__init__(self)
        self.timer = -inf

    def on_press(self, player):
        self.timer = 0

    def on_hold(self, player, t, dt):
        self.timer += dt

        if self.timer > airstrike_zoomv_time:
            self.timer = 0

            if o := player.get_bomber():
                o.point(player)

@dataclass
class Bomber:
    name     : str
    team     : Team
    protocol : BaseProtocol

    def __post_init__(self):
        self.init()

    def init(self, by_server = False):
        self.player_id   = None
        self.preparation = None
        self.call        = None
        self.ready       = False

        if by_server:
            self.preparation = reactor.callLater(aitstrike_phase, self.start)

    def point(self, conn):
        if not self.active() and self.ready:
            self.player_id = conn.player_id
            do_airstrike(self.name, conn)
            self.restart()

    def active(self):
        return self.call and self.call.active()

    def stop(self, player_id = None):
        if (player_id and player_id != self.player_id) or not player_id:
            return

        if self.call and self.call.active():
            self.call.cancel()
        self.call = None

    def start(self):
        if self.ready: return

        self.report("Air support is ready")
        self.preparation = None
        self.ready       = True

    def restart(self):
        self.stop()

        self.ready       = False
        self.preparation = reactor.callLater(airstrike_delay, self.start)

    def report(self, msg):
        self.protocol.broadcast_chat(
            "<{}> {}. Over.".format(self.name, msg),
            global_message = False, team = self.team
        )

    def remaining(self):
        if self.preparation:
            return self.preparation.getTime() - reactor.seconds()
        else:
            return None

def apply_script(protocol, connection, config):
    class AirstrikeProtocol(protocol):
        def __init__(self, *w, **kw):
            protocol.__init__(self, *w, **kw)
            self.bombers = {
                self.team_1.id : Bomber("B-52",   self.team_1, self),
                self.team_2.id : Bomber("Tu-22M", self.team_2, self)
            }

        def on_map_change(self, M):
            for bomber in self.bombers.values():
                if bomber.preparation and bomber.preparation.active():
                    bomber.preparation.cancel()
                bomber.stop()
                bomber.init(by_server = True)

            protocol.on_map_change(self, M)

    class AirstrikeConnection(connection):
        def get_bomber(self):
            return self.protocol.bombers.get(self.team.id)

        def on_spawn(self, pos):
            connection.on_spawn(self, pos)

            self.weapon_object.item_underbarrel = Laser().mark_renewable()

    return AirstrikeProtocol, AirstrikeConnection
