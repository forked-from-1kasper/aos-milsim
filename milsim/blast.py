from math import sqrt, pi, sin, cos
from random import choice, uniform
from time import sleep

from pyspades.collision import distance_3d_vector
from pyspades.constants import GRENADE_KILL

from pyspades.contained import GrenadePacket
from pyspades.common import Vertex3

from milsim.vxl import can_see

def sendGrenadePacket(protocol, player_id, position, velocity, fuse):
    contained           = GrenadePacket()
    contained.player_id = player_id
    contained.value     = fuse
    contained.position  = position.get()
    contained.velocity  = velocity.get()

    protocol.broadcast_contained(contained)

def flashbang_effect(protocol, player_id, position):
    for i in range(50):
        sleep(uniform(0.05, 0.25))

        r = position.copy()
        r.x += uniform(-5.0, 5.0)
        r.y += uniform(-5.0, 5.0)
        r.z += uniform(-5.0, 5.0)

        sendGrenadePacket(protocol, player_id, r, Vertex3(0, 0, 0), 0.0)

def damage(M, o, r, inner, outer):
    x0, y0, z0 = o.position.x, o.position.y, min(62.9, o.position.z)
    x1, y1, z1 = r.x, r.y, min(62.9, r.z)

    if not can_see(M, x0, y0, z0, x1, y1, z1):
        return 0

    dist = distance_3d_vector(o.position, r)

    if dist >= outer: return 0
    if dist <= inner: return 100

    t = (outer - dist) / (outer - inner)
    return 100 * sqrt(t)

def explode(inner, outer, connection, r):
    protocol = connection.protocol

    for player in protocol.living():
        D = damage(protocol.map, player.world_object, r, inner, outer)
        if D > 0:
            player.hit(
                D, limb = choice(player.body.keys()), venous = True,
                hit_by = connection, kill_type = GRENADE_KILL
            )
