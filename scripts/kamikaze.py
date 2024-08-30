from math import floor, inf, isinf, isnan
from random import choice

from twisted.internet.error import AlreadyCalled, AlreadyCancelled
from twisted.internet import reactor

from pyspades.constants import CHAT_ALL

from pyspades import contained as loaders
from pyspades.common import Vertex3

from piqueserver.commands import command, player_only
from piqueserver.config import config

import milsim.blast as blast

BOOM_GUARANTEED_KILL_RADIUS = 17
BOOM_RADIUS = 40

section = config.section("kamikaze")

kamikaze_message  = section.option("message", None).get()
kamikaze_max_fuse = section.option("max_fuse", 60).get()
kamikaze_delay    = section.option("delay", 15).get()

class Boom:
    protection = [
        "Don't try to die twice.",
        "Are you a zombie?",
        "Your death was not a fake."
    ]

    def __init__(self, conn):
        self.defer = None
        self.conn  = conn
        self.last  = -inf

    def alive(self):
        return self.conn and self.conn.ingame()

    def start(self, fuse):
        if self.defer:
            return

        if not self.alive():
            return choice(self.protection)

        if fuse < 0 or fuse > kamikaze_max_fuse:
            return "Delay should be non-negative and less than {}.".format(kamikaze_max_fuse)

        dt = reactor.seconds() - self.last

        if dt < kamikaze_delay:
            return "Wait {:.1f} seconds.".format(kamikaze_delay - dt)

        self.defer = reactor.callLater(fuse, self.callback)

    def stop(self):
        if self.defer:
            try:
                self.defer.cancel()
            except (AlreadyCalled, AlreadyCancelled):
                pass

            self.last  = reactor.seconds()
            self.defer = None

    def callback(self):
        self.last  = reactor.seconds()
        self.defer = None

        if self.alive() and kamikaze_message:
            contained           = loaders.ChatMessage()
            contained.player_id = self.conn.player_id
            contained.chat_type = CHAT_ALL
            contained.value     = kamikaze_message

            self.conn.protocol.broadcast_contained(contained)

        r = self.conn.world_object.position
        blast.effect(
            self.conn.protocol, self.conn.player_id,
            r - Vertex3(0, 0, 1.5), Vertex3(0, 0, 0), 0
        )

        self.conn.grenade_destroy(floor(r.x), floor(r.y), floor(r.z + 3))
        blast.explode(BOOM_GUARANTEED_KILL_RADIUS, BOOM_RADIUS, self.conn, r)

@command('boom', 'a')
@player_only
def boom(conn, fuse = 0):
    """
    Detonates the explosive belt after a given number of seconds.
    /boom [delay]
    """

    try:
        fuse = float(fuse)
    except ValueError:
        return "Usage: /boom [delay]"

    if isnan(fuse) or isinf(fuse):
        return "Are you a hacker?"

    return conn.boom.start(fuse)

def apply_script(protocol, connection, config):
    class KamikazeConnection(connection):
        def __init__(self, *w, **kw):
            connection.__init__(self, *w, **kw)
            self.boom = Boom(self)

        def on_spawn(self, pos):
            self.boom.stop()

            connection.on_spawn(self, pos)

        def on_team_changed(self, old_team):
            if self.team is None or self.team.spectator:
                self.boom.stop()

            connection.on_team_changed(self, old_team)

    return protocol, KamikazeConnection
