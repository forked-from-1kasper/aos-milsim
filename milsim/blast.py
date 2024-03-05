from random import choice, uniform, gauss
from math import sqrt, pi, sin, cos

from twisted.internet import reactor

from pyspades.constants import (TORSO, HEAD, ARMS, LEGS, GRENADE_KILL)
from pyspades.collision import distance_3d_vector
from pyspades.world import Grenade, Character
from pyspades.contained import GrenadePacket
from pyspades.common import Vertex3

parts = [TORSO, HEAD, ARMS, LEGS]

def dummy(*args, **kwargs):
    pass

def effect(conn, position, velocity, fuse):
    if conn.player_id not in conn.protocol.players: return

    contained           = GrenadePacket()
    contained.player_id = conn.player_id
    contained.value     = fuse
    contained.position  = position.get()
    contained.velocity  = velocity.get()

    conn.protocol.broadcast_contained(contained)

def damage(obj, pos, inner, outer):
    if not obj.can_see(pos.x, pos.y, pos.z):
        return 0

    dist = distance_3d_vector(obj.position, pos)

    if dist >= outer: return 0
    if dist <= inner: return 100

    t = (outer - dist) / (outer - inner)
    return 100 * sqrt(t)

class Fragment:
    def __init__(self):
        self.mass    = uniform(1 / 1000, 5 / 1000)
        self.area    = 0.01 * 0.01
        self.drag    = 0.5
        self.grenade = True

def explode(inner, outer, conn, pos):
    timestamp = reactor.seconds()

    for i in range(1, 15):
        speed = uniform(210, 220)

        α = uniform(0, pi)
        β = uniform(0, 2 * pi)

        v = Vertex3(
            sin(α) * cos(β),
            sin(α) * sin(β),
            cos(α)
        ) * speed

        conn.protocol.sim.add(conn, pos, v, timestamp, Fragment())

    for _, player in conn.protocol.players.items():
        if not player or not player.hp or not player.world_object: return

        D = damage(player.world_object, pos, inner, outer)
        if D <= 0: continue

        player.hit(
            D, part=choice(parts), venous=True,
            hit_by=conn, kill_type=GRENADE_KILL
        )
