from random import randint, random
from dataclasses import dataclass
from math import floor

from twisted.internet import reactor

from pyspades.protocol import BaseProtocol
from pyspades.constants import WEAPON_TOOL
from piqueserver.config import config
from pyspades.common import Vertex3
from pyspades.team import Team

from piqueserver.commands import command, player_only
import milsim.blast as blast

section = config.section("airstrike")

class Option:
    zoomv_time = section.option("zoomv_time", 2).get()
    delay      = section.option("delay", 7 * 60).get()
    phase      = section.option("phase", 120).get()

BOMBS_COUNT   = 7
BOMBER_SPEED  = 10
BOMBING_DELAY = 2

AIRBOMB_DELAY                  = 3
AIRBOMB_RADIUS                 = 10
AIRBOMB_SAFE_DISTANCE          = 150
AIRBOMB_GUARANTEED_KILL_RADIUS = 40

AIRSTRIKE_PASSES        = 50
AIRSTRIKE_CAST_DISTANCE = 300

shift = lambda val: val + randint(-AIRBOMB_RADIUS, AIRBOMB_RADIUS)

def dummy(*args, **kwargs):
    pass

def airbomb_explode(protocol, player_id, pos):
    if player := protocol.take_player(player_id):
        x, y, z = floor(pos.x), floor(pos.y), floor(pos.z)

        blast.explode(AIRBOMB_GUARANTEED_KILL_RADIUS, AIRBOMB_SAFE_DISTANCE, player, pos)

        for i in range(AIRSTRIKE_PASSES):
            X, Y = shift(x), shift(y)
            Z = protocol.map.get_z(X, Y)

            if player.grenade_destroy(X, Y, Z):
                reactor.callLater(random(), blast.effect, protocol, player.player_id, Vertex3(X, Y, Z), Vertex3(0, 0, 0), 0)

def drop_airbomb(protocol, player_id, x, y, vx, vy):
    pos = Vertex3(x, y, protocol.map.get_z(x, y) - 2)
    reactor.callLater(AIRBOMB_DELAY, airbomb_explode, protocol, player_id, pos)

def do_bombing(protocol, player_id, x, y, vx, vy, bombs):
    if bombs <= 0: return

    drop_airbomb(protocol, player_id, floor(x), floor(y), vx, vy)

    x1 = x + vx * BOMBING_DELAY
    y1 = y + vy * BOMBING_DELAY

    if bombs > 1:
        reactor.callLater(
            BOMBING_DELAY, do_bombing, protocol, player_id, x1, y1, vx, vy, bombs - 1
        )

def do_airstrike(name, conn, callback):
    if conn.player_id not in conn.protocol.players:
        return

    if loc := conn.world_object.cast_ray(AIRSTRIKE_CAST_DISTANCE):
        conn.protocol.broadcast_chat(
            "<%s> Coordinates recieved. Over." % name,
            global_message=False, team=conn.team
        )

        x, y, _ = loc
        orientation = conn.world_object.orientation
        v = Vertex3(orientation.x, orientation.y, 0).normal() * BOMBER_SPEED

        do_bombing(conn.protocol, conn.player_id, x, y, v.x, v.y, BOMBS_COUNT)
        callback()

@command(admin_only = True)
@player_only
def gift(conn):
    do_airstrike("Panavia Tornado ECR", conn, dummy)

@command('air')
def air(conn):
    """
    Report time before bomber's arrival.
    /air
    """

    bomber = conn.get_bomber()
    remaining = bomber.remaining()

    if remaining:
        approx = (remaining // 10 + 1) * 10
        bomber.report("Will be ready in %d seconds" % approx)
    else:
        bomber.report("Awaiting for coordinates")

class Ghost:
    def __init__(self):
        self.call = None
        self.ready = False
        self.player_id = None
        self.preparation = None

    def init(self, by_server = False):
        pass

    def point(self, conn):
        pass

    def active(self):
        pass

    def stop(self, player_id = None):
        pass

    def start(self):
        pass

    def restart(self):
        pass

    def report(self, msg):
        pass

    def remaining(self):
        pass

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
            self.preparation = reactor.callLater(Option.phase, self.start)

    def point(self, conn):
        if not self.active() and self.ready:
            self.player_id = conn.player_id
            self.call = reactor.callLater(
                Option.zoomv_time, do_airstrike, self.name, conn, self.restart
            )

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
        self.preparation = reactor.callLater(Option.delay, self.start)

    def report(self, msg):
        self.protocol.broadcast_chat(
            "<%s> %s. Over." % (self.name, msg),
            global_message=False, team=self.team
        )

    def remaining(self):
        if self.preparation:
            return self.preparation.getTime() - reactor.seconds()
        else:
            return None

def apply_script(protocol, connection, config):
    class AirstrikeWeaponTool(protocol.WeaponTool):
        def on_rmb_press(self):
            protocol.WeaponTool.on_rmb_press(self)

            if self.player.world_object.sneak:
                self.player.send_airstrike()

        def on_rmb_release(self):
            protocol.WeaponTool.on_rmb_release(self)

            self.player.cancel_airstrike()

    class AirstrikeProtocol(protocol):
        WeaponTool = AirstrikeWeaponTool

        def __init__(self, *w, **kw):
            protocol.__init__(self, *w, **kw)
            self.bombers = {
                self.team_spectator.id : Ghost(),
                self.team_1.id         : Bomber("B-52",   self.team_1, self),
                self.team_2.id         : Bomber("Tu-22M", self.team_2, self)
            }

        def on_map_change(self, M):
            for bomber in self.bombers.values():
                if bomber.preparation and bomber.preparation.active():
                    bomber.preparation.cancel()
                bomber.stop()
                bomber.init(by_server = True)

            return protocol.on_map_change(self, M)

    class AirstrikeConnection(connection):
        def get_bomber(self):
            return self.protocol.bombers[self.team.id]

        def send_airstrike(self):
            obj     = self.world_object
            walking = obj.up or obj.down or obj.left or obj.right

            if not walking: self.get_bomber().point(self)

        def cancel_airstrike(self):
            self.get_bomber().stop(player_id = self.player_id)

        def on_kill(self, killer, kill_type, grenade):
            self.cancel_airstrike()
            return connection.on_kill(self, killer, kill_type, grenade)

        def on_walk_update(self, up, down, left, right):
            if self.get_bomber().active() and (up or down or left or right):
                self.cancel_airstrike()
            return connection.on_walk_update(self, up, down, left, right)

        def on_animation_update(self, jump, crouch, sneak, sprint):
            if self.world_object.secondary_fire and self.tool == WEAPON_TOOL:
                if sneak and not self.get_bomber().active():
                    self.send_airstrike()
                elif not sneak and self.get_bomber().active():
                    self.cancel_airstrike()

            return connection.on_animation_update(self, jump, crouch, sneak, sprint)

        def on_tool_changed(self, tool):
            if tool != WEAPON_TOOL: self.cancel_airstrike()

            return connection.on_tool_changed(self, tool)

    return AirstrikeProtocol, AirstrikeConnection
