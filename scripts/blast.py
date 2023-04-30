from random import choice
from math import sqrt

from pyspades.constants import (TORSO, HEAD, ARMS, LEGS, GRENADE_KILL)
from pyspades.collision import distance_3d_vector
from pyspades.world import Grenade, Character
from pyspades.contained import GrenadePacket

parts = [TORSO, HEAD, ARMS, LEGS]

def dummy(*args, **kwargs):
    pass

def effect(conn, position, velocity, fuse):
    if conn.player_id not in conn.protocol.players: return
    pack = GrenadePacket()

    pack.player_id = conn.player_id
    pack.value = fuse

    pack.position = position.get()
    pack.velocity = velocity.get()
    conn.protocol.broadcast_contained(pack)

def damage(inner, outer, obj, pos1, pos2):
    if not obj.can_see(pos2.x, pos2.y, pos2.z): return 0
    dist = distance_3d_vector(pos1, pos2)

    if dist >= outer: return 0
    if dist <= inner: return 100

    return sqrt(outer - dist) * (100 / sqrt(outer - inner))

def explode(inner, outer, conn, pos):
    # because grenade.hit_test is private, we’re creating dummy object to perform fast raycast
    geist = conn.protocol.world.create_object(Character, pos, None, dummy)

    for _, player in conn.protocol.players.items():
        if not player or not player.hp or not player.world_object: return

        D = damage(inner, outer, geist, pos, player.world_object.position)
        if D <= 0: continue

        player.hit(
            D, part=choice(parts), bleeding=True,
            hit_by=conn, kill_type=GRENADE_KILL
        )

    geist.delete()