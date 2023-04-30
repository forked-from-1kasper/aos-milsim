from math import sqrt, floor
from random import choice

from twisted.internet.error import AlreadyCalled, AlreadyCancelled
from twisted.internet import reactor

from pyspades.constants import (
    TORSO, HEAD, ARMS, LEGS, GRENADE_KILL, CHAT_ALL
)
from pyspades.collision import distance_3d_vector
from pyspades.contained import GrenadePacket
from pyspades import contained as loaders
from pyspades.common import Vertex3

from piqueserver.commands import command
import scripts.blast as blast

BOOM_GUARANTEED_KILL_RADIUS = 17
BOOM_RADIUS = 40

BOOM_MESSAGE = "ALLAH AKBAR"
BOOM_LIMIT = 60

parts = [TORSO, HEAD, ARMS, LEGS]

@command('boom', 'a')
def boom(conn, *args):
    delay = 0
    if len(args) > 0:
        delay, *rest = args

        if not delay.isdigit():
            return "Usage: /boom [delay in seconds]"

        delay = int(delay)

    if delay < 0 or delay > BOOM_LIMIT:
        return "Delay should be non-negative and less than %d" % BOOM_LIMIT

    if conn.boom_call: return
    def callback():
        if not conn or not conn.world_object: return

        msg = loaders.ChatMessage()
        msg.player_id = conn.player_id
        msg.chat_type = CHAT_ALL
        msg.value = BOOM_MESSAGE

        conn.protocol.broadcast_contained(msg)

        pos = conn.world_object.position
        blast.effect(conn, pos - Vertex3(0, 0, 1.5), Vertex3(0, 0, 0), 0)

        blast.explode(BOOM_GUARANTEED_KILL_RADIUS, BOOM_RADIUS, conn, pos)
        conn.grenade_destroy(floor(pos.x), floor(pos.y), floor(pos.z + 3))

        conn.boom_call = None

    conn.boom_call = reactor.callLater(delay, callback)

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
