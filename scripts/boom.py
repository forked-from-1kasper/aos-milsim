from math import sqrt, floor, inf, isinf, isnan
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
from piqueserver.config import config

import milsim.blast as blast

BOOM_GUARANTEED_KILL_RADIUS = 17
BOOM_RADIUS = 40

section = config.section("boom")

class Config:
    message  = section.option("message", None).get()
    max_fuse = section.option("max_fuse", 60).get()
    delay    = section.option("delay", 30).get()

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
        return self.conn and self.conn.world_object and not self.conn.world_object.dead

    def start(self, fuse):
        if self.defer:
            return

        if not self.alive():
            if self.conn and not self.conn.world_object:
                return

            return choice(self.protection)

        if fuse < 0 or fuse > Config.max_fuse:
            return "Delay should be non-negative and less than %d." % Config.max_fuse

        dt = reactor.seconds() - self.last

        if dt < Config.delay:
            return "Wait %.1f seconds." % (Config.delay - dt)

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

        if not self.alive():
            return

        if Config.message:
            msg           = loaders.ChatMessage()
            msg.player_id = self.conn.player_id
            msg.chat_type = CHAT_ALL
            msg.value     = Config.message

            self.conn.protocol.broadcast_contained(msg)

        pos = self.conn.world_object.position
        blast.effect(self.conn, pos - Vertex3(0, 0, 1.5), Vertex3(0, 0, 0), 0)

        blast.explode(BOOM_GUARANTEED_KILL_RADIUS, BOOM_RADIUS, self.conn, pos)
        self.conn.grenade_destroy(floor(pos.x), floor(pos.y), floor(pos.z + 3))

@command('boom', 'a')
def boom(conn, *args):
    fuse = 0
    if len(args) > 0:
        fuse, *rest = args

        try:
            fuse = float(fuse)
        except ValueError:
            return "Usage: /boom [delay in seconds]"

        if isnan(fuse) or isinf(fuse):
            return "Are you a hacker?"

    return conn.boom.start(fuse)

def apply_script(protocol, connection, config):
    class BoomConnection(connection):
        def on_join(self):
            self.boom = Boom(self)
            return connection.on_join(self)

        def on_kill(self, killer, kill_type, grenade):
            self.boom.stop()
            return connection.on_kill(self, killer, kill_type, grenade)

        def on_team_changed(self, old_team):
            self.boom.stop() # Just to be sure
            return connection.on_team_changed(self, old_team)

    return protocol, BoomConnection
