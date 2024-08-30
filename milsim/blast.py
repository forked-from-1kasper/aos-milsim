from math import sqrt, pi, sin, cos
from random import choice, uniform

from twisted.internet import reactor

from pyspades.collision import distance_3d_vector
from pyspades.constants import GRENADE_KILL

from pyspades.contained import GrenadePacket
from pyspades.common import Vertex3

def dummy(*args, **kwargs):
    pass

def effect(protocol, player_id, position, velocity, fuse):
    contained           = GrenadePacket()
    contained.player_id = player_id
    contained.value     = fuse
    contained.position  = position.get()
    contained.velocity  = velocity.get()

    protocol.broadcast_contained(contained)

def damage(o, pos, inner, outer):
    if not o.can_see(pos.x, pos.y, pos.z):
        return 0

    dist = distance_3d_vector(o.position, pos)

    if dist >= outer: return 0
    if dist <= inner: return 100

    t = (outer - dist) / (outer - inner)
    return 100 * sqrt(t)

class Fragment:
    grenade = True
    model   = 0

    def __init__(self):
        self.effmass   = uniform(1 / 1000, 5 / 1000)
        self.area      = 0.01 * 0.01
        self.ballistic = 1.0

def explode(inner, outer, conn, pos):
    timestamp = reactor.seconds()

    for i in range(1, 15):
        speed = uniform(210, 220)

        α = uniform(0, pi)
        β = uniform(0, 2 * pi)

        v = Vertex3(sin(α) * cos(β), sin(α) * sin(β), cos(α)) * speed
        conn.protocol.simulator.add(conn, pos, v, timestamp, Fragment())

    for player in conn.protocol.players.values():
        if player.ingame():
            D = damage(player.world_object, pos, inner, outer)
            if D > 0:
                player.hit(
                    D, limb = choice(player.body.keys()), venous = True,
                    hit_by = conn, kill_type = GRENADE_KILL
                )
