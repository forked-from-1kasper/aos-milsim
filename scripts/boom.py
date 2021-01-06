from pyspades.constants import (
    TORSO, HEAD, ARMS, LEGS, GRENADE_KILL
)
from twisted.internet.error import AlreadyCalled, AlreadyCancelled
from pyspades.collision import distance_3d_vector
from pyspades.contained import GrenadePacket
from piqueserver.commands import command
from twisted.internet import reactor
from pyspades.common import Vertex3
from math import sqrt, floor
from random import choice

BOOM_GUARANTEED_KILL_RADIUS = 17
BOOM_RADIUS = 40
BOOM_DELAY = 5

parts = [TORSO, HEAD, ARMS, LEGS]

def effect(conn):
    pack = GrenadePacket()
    pack.value = 0
    pack.player_id = conn.player_id

    pos = conn.world_object.position - Vertex3(0, 0, 1.5)
    pack.position = pos.get()
    pack.velocity = (0, 0, 0)
    conn.protocol.broadcast_contained(pack)

def calc_damage(conn, pos1, pos2):
    if not conn.world_object.can_see(pos2.x, pos2.y, pos2.z): return 0
    dist = distance_3d_vector(pos1, pos2)

    if dist >= BOOM_RADIUS: return 0
    if dist <= BOOM_GUARANTEED_KILL_RADIUS: return 100

    diff = BOOM_RADIUS - BOOM_GUARANTEED_KILL_RADIUS
    return sqrt(BOOM_RADIUS - dist) * (100 / sqrt(diff))

@command()
def boom(conn, *args):
    if conn.boom_call: return
    def callback():
        if not conn: return
        effect(conn)

        pos = conn.world_object.position
        x, y, z = floor(pos.x), floor(pos.y), floor(pos.z) + 3
        conn.grenade_destroy(x, y, z)

        for _, player in conn.protocol.players.items():
            if not player or not player.hp or not player.world_object: return

            damage = calc_damage(
                conn, conn.world_object.position,
                player.world_object.position
            )
            if damage == 0: continue

            player.hit(
                damage, part=choice(parts), bleeding=True,
                hit_by=conn, kill_type=GRENADE_KILL
            )

        conn.boom_call = None

    conn.boom_call = reactor.callLater(BOOM_DELAY, callback)

def apply_script(protocol, connection, config):
    class BoomConnection(connection):
        def on_join(self):
            self.boom_call = None
            return connection.on_join(self)

        def on_kill(self, killer, kill_type, grenade):
            if self.boom_call:
                try:
                    self.boom_call.cancel()
                except (AlreadyCalled, AlreadyCancelled):
                    pass
                self.boom_call = None
            return connection.on_kill(self, killer, kill_type, grenade)

    return protocol, BoomConnection