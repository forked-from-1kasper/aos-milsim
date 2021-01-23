from pyspades.constants import (
    TORSO, HEAD, ARMS, LEGS, GRENADE_KILL, WEAPON_TOOL
)
from pyspades.collision import distance_3d_vector
from pyspades.world import Grenade, Character
from pyspades.contained import GrenadePacket
from random import randint, random, choice
from pyspades.protocol import BaseProtocol
from piqueserver.commands import command
from twisted.internet import reactor
from pyspades.common import Vertex3
from dataclasses import dataclass
from pyspades.team import Team
from functools import partial
from math import floor, sqrt

AIRBOMB = "airbomb"

BOMBS_COUNT = 7
BOMBER_SPEED = 10
BOMBING_DELAY = 2

AIRBOMB_DELAY = 3
AIRBOMB_RADIUS = 10
AIRBOMB_SAFE_DISTANCE = 150
AIRBOMB_GUARANTEED_KILL_RADIUS = 40

ZOOMV_TIME = 2
AIRSTRIKE_DELAY = 7 * 60
AIRSTRIKE_PASSES = 50
AIRSTRIKE_INIT_DELAY = 120
AIRSTRIKE_CAST_DISTANCE = 300

parts = [TORSO, HEAD, ARMS, LEGS]
shift = lambda val: val + randint(-AIRBOMB_RADIUS, AIRBOMB_RADIUS)

def dummy(*args, **kwargs):
    pass

def explosion_effect(conn, x, y, z):
    if conn.player_id not in conn.protocol.players: return

    pack = GrenadePacket()
    pack.value = 0
    pack.player_id = conn.player_id

    pack.position = (x, y, z)
    pack.velocity = (0, 0, 0)
    conn.protocol.broadcast_contained(pack)

def calc_damage(conn, pos1, pos2):
    dist = distance_3d_vector(pos1, pos2)

    if dist >= AIRBOMB_SAFE_DISTANCE: return 0
    if dist <= AIRBOMB_GUARANTEED_KILL_RADIUS: return 100

    diff = AIRBOMB_SAFE_DISTANCE - AIRBOMB_GUARANTEED_KILL_RADIUS
    return sqrt(AIRBOMB_SAFE_DISTANCE - dist) * (100 / sqrt(diff))

def airbomb_explode(conn, pos):
    if conn.player_id not in conn.protocol.players: return

    x, y, z = floor(pos.x), floor(pos.y), floor(pos.z)

    for i in range(AIRSTRIKE_PASSES):
        x1, y1 = shift(x), shift(y)
        z1 = conn.protocol.map.get_z(x1, y1)
        conn.grenade_destroy(x1, y1, z1)

        reactor.callLater(random(), explosion_effect, conn, x1, y1, z1)

    # because grenade.hit_test is private
    char = conn.protocol.world.create_object(Character, pos, None, dummy)
    for _, player in conn.protocol.players.items():
        if not player or not player.hp or not player.world_object: return

        if not char.can_see(*player.world_object.position.get()): return
        damage = calc_damage(conn, pos, player.world_object.position)
        if damage == 0: continue

        player.hit(
            damage, part=choice(parts), bleeding=True,
            hit_by=conn, kill_type=GRENADE_KILL
        )

    char.delete()

def drop_airbomb(conn, x, y, vx, vy):
    if conn.player_id not in conn.protocol.players: return

    pos = Vertex3(x, y, conn.protocol.map.get_z(x, y))
    reactor.callLater(AIRBOMB_DELAY, airbomb_explode, conn, pos)

def do_bombing(conn, x, y, vx, vy, bombs):
    if conn.player_id not in conn.protocol.players: return

    if bombs <= 0: return
    drop_airbomb(conn, floor(x), floor(y), vx, vy)

    x1 = x + vx * BOMBING_DELAY
    y1 = y + vy * BOMBING_DELAY

    if bombs > 1:
        reactor.callLater(
            BOMBING_DELAY, do_bombing, conn, x1, y1, vx, vy, bombs - 1
        )

def do_airstrike(name, conn, callback):
    loc = conn.world_object.cast_ray(AIRSTRIKE_CAST_DISTANCE)
    if not loc: return

    conn.protocol.send_chat(
        "<%s> Coordinates recieved. Over." % name,
        global_message=False, team=conn.team
    )

    x, y, _ = loc
    orientation = conn.world_object.orientation
    v = Vertex3(orientation.x, orientation.y, 0).normal() * BOMBER_SPEED

    do_bombing(conn, x, y, v.x, v.y, BOMBS_COUNT)
    callback()

@command(admin_only=True)
def gift(conn, *args):
    do_airstrike("Panavia Tornado ECR", conn, dummy)

@dataclass
class Bomber:
    name     : str
    team     : Team
    protocol : BaseProtocol

    def __post_init__(self):
        self.init()

    def init(self, by_server=False):
        self.call = None
        self.ready = False
        self.player_id = None
        self.preparation = None

        if by_server:
            self.preparation = reactor.callLater(AIRSTRIKE_INIT_DELAY, self.start)

    def point(self, conn):
        if not self.active() and self.ready:
            self.player_id = conn.player_id
            self.call = reactor.callLater(
                ZOOMV_TIME, do_airstrike, self.name, conn, self.restart
            )

    def active(self):
        return self.call and self.call.active()

    def stop(self, player_id=None):
        if (player_id and player_id != self.player_id) or not player_id:
            return

        if self.call and self.call.active():
            self.call.cancel()
        self.call = None

    def start(self):
        if self.ready: return

        self.protocol.send_chat(
            "<%s> Air support is ready. Over." % self.name,
            global_message=False, team=self.team
        )
        self.ready = True

    def restart(self):
        self.stop()
        self.ready = False
        reactor.callLater(AIRSTRIKE_DELAY, self.start)

def apply_script(protocol, connection, config):
    class AirstrikeProtocol(protocol):
        def __init__(self, *arg, **kw):
            protocol.__init__(self, *arg, **kw)
            self.bombers = {
                self.team_1.id : Bomber("B-52",   self.team_1, self),
                self.team_2.id : Bomber("Tu-22M", self.team_2, self)
            }

        def on_map_change(self, map):
            for bomber in self.bombers.values():
                if bomber.preparation and bomber.preparation.active():
                    bomber.preparation.cancel()
                bomber.stop()
                bomber.init(by_server=True)

            return protocol.on_map_change(self, map)

    class AirstrikeConnection(connection):
        def get_bomber(self):
            return self.protocol.bombers[self.team.id]

        def send_airstrike(self):
            obj = self.world_object
            walking = obj.up or obj.down or obj.left or obj.right
            if not walking: self.get_bomber().point(self)

        def revert_airstrike(self):
            self.get_bomber().stop(player_id=self.player_id)

        def on_kill(self, killer, kill_type, grenade):
            self.revert_airstrike()
            return connection.on_kill(self, killer, kill_type, grenade)

        def on_walk_update(self, up, down, left, right):
            if self.get_bomber().active() and (up or down or left or right):
                self.revert_airstrike()
            return connection.on_walk_update(self, up, down, left, right)

        def on_secondary_fire_set(self, secondary):
            if self.tool == WEAPON_TOOL:
                if secondary:
                    if self.world_object.sneak:
                        self.send_airstrike()
                else:
                    self.revert_airstrike()

            return connection.on_secondary_fire_set(self, secondary)

        def on_animation_update(self, jump, crouch, sneak, sprint):
            if self.world_object.secondary_fire and self.tool == WEAPON_TOOL:
                if sneak and not self.get_bomber().active():
                    self.send_airstrike()
                elif not sneak and self.get_bomber().active():
                    self.revert_airstrike()

            return connection.on_animation_update(self, jump, crouch, sneak, sprint)

        def on_tool_set_attempt(self, tool):
            res = connection.on_tool_set_attempt(self, tool)
            if res and tool != WEAPON_TOOL:
                self.revert_airstrike()
            return res

    return AirstrikeProtocol, AirstrikeConnection