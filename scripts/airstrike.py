from pyspades.constants import (
    TORSO, HEAD, ARMS, LEGS, GRENADE_KILL
)
from pyspades.collision import distance_3d_vector
from pyspades.world import Grenade, Character
from pyspades.contained import GrenadePacket
from random import randint, random, choice
from piqueserver.commands import command
from twisted.internet import reactor
from pyspades.common import Vertex3
from functools import partial
from math import floor, sqrt

AIRBOMB = "airbomb"
BOMBS_COUNT = 7
BOMBER_SPEED = 10
BOMBING_DELAY = 2
AIRBOMB_DELAY = 3
AIRBOMB_RADIUS = 10
AIRSTRIKE_PASSES = 50
AIRBOMB_SAFE_DISTANCE = 150
AIRSTRIKE_CAST_DISTANCE = 300
AIRBOMB_GUARANTEED_KILL_RADIUS = 40

parts = [TORSO, HEAD, ARMS, LEGS]
shift = lambda val: val + randint(-AIRBOMB_RADIUS, AIRBOMB_RADIUS)

def dummy(damage):
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

        reactor.callLater(random(), lambda: explosion_effect(conn, x1, y1, z1))

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
    reactor.callLater(AIRBOMB_DELAY, lambda: airbomb_explode(conn, pos))

def do_bombing(conn, x, y, vx, vy, bombs):
    if conn.player_id not in conn.protocol.players: return

    if bombs <= 0: return
    drop_airbomb(conn, floor(x), floor(y), vx, vy)

    x1 = x + vx * BOMBING_DELAY
    y1 = y + vy * BOMBING_DELAY

    if bombs > 1:
        reactor.callLater(
            BOMBING_DELAY, lambda: do_bombing(conn, x1, y1, vx, vy, bombs - 1)
        )

@command(admin_only=True)
def airbomb(conn, *args):
    loc = conn.world_object.cast_ray(AIRSTRIKE_CAST_DISTANCE)
    if not loc: return

    x, y, _ = loc

    orientation = conn.world_object.orientation
    v = Vertex3(orientation.x, orientation.y, 0).normal() * BOMBER_SPEED

    do_bombing(conn, x, y, v.x, v.y, BOMBS_COUNT)

def apply_script(protocol, connection, config):
    return protocol, connection