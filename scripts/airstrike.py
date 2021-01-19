from pyspades.contained import GrenadePacket
from piqueserver.commands import command
from twisted.internet import reactor
from pyspades.common import Vertex3
from pyspades.world import Grenade
from random import randint, random
from functools import partial
from math import floor

AIRBOMB = "airbomb"
BOMBER_SPEED = 1
BOMBING_DELAY = 2
AIRBOMB_DELAY = 3
AIRBOMB_RADIUS = 10
AIRSTRIKE_PASSES = 50

shift = lambda val: val + randint(-AIRBOMB_RADIUS, AIRBOMB_RADIUS)

def explosion_effect(conn, x, y, z):
    if conn.player_id not in conn.protocol.players: return

    pack = GrenadePacket()
    pack.value = 0
    pack.player_id = conn.player_id

    pack.position = (x, y, z)
    pack.velocity = (0, 0, 0)
    conn.protocol.broadcast_contained(pack)

def airbomb_explode(conn, grenade):
    if conn.player_id not in conn.protocol.players: return
    conn.grenade_exploded(grenade)

    pos = grenade.position
    x, y, z = floor(pos.x), floor(pos.y), floor(pos.z)

    for i in range(AIRSTRIKE_PASSES):
        x1, y1 = shift(x), shift(y)
        z1 = conn.protocol.map.get_z(x1, y1)
        conn.grenade_destroy(x1, y1, z1)

        reactor.callLater(random(), lambda: explosion_effect(conn, x1, y1, z1))

def drop_airbomb(conn, x, y, vx, vy):
    if conn.player_id not in conn.protocol.players: return

    pos = Vertex3(x, y, 0)
    vel = Vertex3(vx, vy, 0)

    orientation = None

    grenade = conn.protocol.world.create_object(
        Grenade, AIRBOMB_DELAY, pos, orientation, vel,
        partial(airbomb_explode, conn)
    )
    grenade.name = AIRBOMB

    pack = GrenadePacket()
    pack.value = AIRBOMB_DELAY
    pack.player_id = conn.player_id
    pack.position = pos.get()
    pack.velocity = vel.get()
    conn.protocol.broadcast_contained(pack)

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
    loc = conn.world_object.cast_ray(90)
    if not loc: return

    x, y, _ = loc
    vx, vy, _ = conn.world_object.orientation.get()

    ux, uy = BOMBER_SPEED * vx, BOMBER_SPEED * vy

    do_bombing(conn, x - ux * AIRBOMB_DELAY, y - uy * AIRBOMB_DELAY, ux, uy, 7)

def apply_script(protocol, connection, config):
    return protocol, connection