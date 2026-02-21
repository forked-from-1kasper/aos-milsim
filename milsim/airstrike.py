# Copyright © 2021, 2023–2026 rzrn

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.

# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

from random import randint, random, uniform
from dataclasses import dataclass
from math import floor, inf
from time import sleep

from twisted.internet import reactor

from pyspades.protocol import BaseProtocol
from pyspades.constants import WEAPON_TOOL
from pyspades.common import Vertex3
from pyspades.team import Team

from piqueserver.commands import command
from piqueserver.config import config

from milsimlib.blast import HighExplosive, sendGrenadePacket
from milsimlib.weapon import UnderbarrelItem

from milsimlib.common import alive_only
from milsimlib import ismilsim

section = config.section("airstrike")

airstrike_zoomv_time = section.option("zoomv_time", 2).get()
airstrike_delay      = section.option("delay", 7 * 60).get()
aitstrike_phase      = section.option("phase", 120).get()

BOMBS_COUNT   = 7
BOMBER_SPEED  = 10
BOMBING_DELAY = 2

AIRBOMB_DELAY  = 3
AIRBOMB_RADIUS = 10

AIRSTRIKE_PASSES        = 50
AIRSTRIKE_CAST_DISTANCE = 300

airbomb_high_explosive = HighExplosive(350.0, 10_000, 3000, 1 / 1000, 0.017, 0.50)

def airbomb_explode(protocol, player_id, x, y, z):
    if player := protocol.take_player(player_id):
        airbomb_high_explosive.explode(protocol, Vertex3(x, y, z), hit_by = player)

        for i in range(AIRSTRIKE_PASSES):
            X = x + randint(-AIRBOMB_RADIUS, AIRBOMB_RADIUS)
            Y = y + randint(-AIRBOMB_RADIUS, AIRBOMB_RADIUS)
            Z = protocol.map.get_z(X, Y)

            player.grenade_destroy(X, Y, Z)
            sendGrenadePacket(protocol, player.player_id, Vertex3(X, Y, Z), Vertex3(0, 0, 0), 0)

            sleep(uniform(0.0, 0.05))

def drop_airbomb(protocol, player_id, x, y):
    X = floor(x)
    Y = floor(y)
    Z = protocol.map.get_z(X, Y) - 2

    airbomb_explode(protocol, player_id, X, Y, Z)

def do_bombing(protocol, player_id, x, y, vx, vy, nbombs):
    for k in range(nbombs):
        sleep(BOMBING_DELAY)
        drop_airbomb(protocol, player_id, x, y)

        x += vx * BOMBING_DELAY
        y += vy * BOMBING_DELAY

def do_airstrike(name, connection):
    protocol = connection.protocol

    if wo := connection.world_object:
        if loc := wo.cast_ray(AIRSTRIKE_CAST_DISTANCE):
            protocol.broadcast_chat(
                "<{}> Coordinates recieved. Over.".format(name),
                global_message = False, team = connection.team
            )

            x, y, z = loc
            o = wo.orientation
            v = Vertex3(o.x, o.y, 0).normal() * BOMBER_SPEED

            reactor.callInThread(do_bombing, protocol, connection.player_id, x, y, v.x, v.y, BOMBS_COUNT)

@command(admin_only = True)
@alive_only
def gift(connection):
    do_airstrike("Panavia Tornado ECR", connection)

@command('airstrike', 'air')
@alive_only
def air(player, loc = None):
    """
    Report time before bomber's arrival
    /air
    """

    if loc is not None:
        return "To initiate an airstrike scope and then hold V. Use /air to check the readiness"

    if o := player.team.bomber:
        remaining = o.remaining()

        if remaining is not None:
            approx = round((remaining / 10 + 1) * 10)
            o.report("Will be ready in {} seconds".format(approx))
        else:
            o.report("Awaiting for coordinates")

class Laser(UnderbarrelItem):
    name = "Laser"
    mass = 0.500

    def __init__(self):
        UnderbarrelItem.__init__(self)
        self.timer = -inf

    def on_press(self, player):
        self.timer = 0

    def on_hold(self, player, t, dt):
        self.timer += dt

        if self.timer > airstrike_zoomv_time:
            self.timer = 0

            if o := player.team.bomber:
                o.point(player)

@dataclass
class Bomber:
    name     : str
    team     : Team
    protocol : BaseProtocol

    def __post_init__(self):
        self.init()

    def init(self, by_server = False):
        self.player_id   = None
        self.preparation = None
        self.call        = None
        self.ready       = False

        if by_server:
            self.preparation = reactor.callLater(aitstrike_phase, self.start)

    def point(self, connection):
        if not self.active() and self.ready:
            self.player_id = connection.player_id
            do_airstrike(self.name, connection)
            self.restart()

    def active(self):
        return self.call and self.call.active()

    def stop(self, player_id = None):
        if player_id is not None and player_id != self.player_id:
            return

        if self.call and self.call.active():
            self.call.cancel()

        self.call = None

    def start(self):
        if self.ready: return

        self.report("Air support is ready")
        self.preparation = None
        self.ready       = True

    def restart(self):
        self.stop()

        self.ready       = False
        self.preparation = reactor.callLater(airstrike_delay, self.start)

    def report(self, msg):
        self.protocol.broadcast_chat(
            "<{}> {}. Over.".format(self.name, msg),
            global_message = False, team = self.team
        )

    def remaining(self):
        if self.preparation:
            return self.preparation.getTime() - reactor.seconds()
        else:
            return None

def apply_script(protocol, connection, config):
    assert ismilsim(protocol, connection)

    class AirstrikeProtocol(protocol):
        def __init__(self, *w, **kw):
            protocol.__init__(self, *w, **kw)

            self.team_1.bomber         = Bomber("B-52",   self.team_1, self)
            self.team_2.bomber         = Bomber("Tu-22M", self.team_2, self)
            self.team_spectator.bomber = None

        def on_map_change(self, M):
            for team in self.team_1, self.team_2:
                bomber = team.bomber

                if bomber.preparation and bomber.preparation.active():
                    bomber.preparation.cancel()

                bomber.stop()
                bomber.init(by_server = True)

            protocol.on_map_change(self, M)

    class AirstrikeConnection(connection):
        def on_spawn(self, pos):
            connection.on_spawn(self, pos)

            self.weapon_object.item_underbarrel = Laser().mark_renewable()

    return AirstrikeProtocol, AirstrikeConnection
