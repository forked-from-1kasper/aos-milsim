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

import asyncio

from pyspades.protocol import BaseProtocol
from pyspades.constants import WEAPON_TOOL
from pyspades.common import Vertex3

from piqueserver.commands import command
from piqueserver.config import config

from milsimlib.items import (
    RadioChannel, civil_radio_channel,
    military_radio_channel_1, military_radio_channel_2
)
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

async def airbomb_explode(protocol, player_id, x, y, z):
    if player := protocol.take_player(player_id):
        airbomb_high_explosive.explode(protocol, Vertex3(x, y, z), hit_by = player)

        for i in range(AIRSTRIKE_PASSES):
            X = x + randint(-AIRBOMB_RADIUS, AIRBOMB_RADIUS)
            Y = y + randint(-AIRBOMB_RADIUS, AIRBOMB_RADIUS)
            Z = protocol.map.get_z(X, Y)

            player.grenade_destroy(X, Y, Z)
            sendGrenadePacket(protocol, player.player_id, Vertex3(X, Y, Z), Vertex3(0, 0, 0), 0)

            await asyncio.sleep(uniform(0.0, 0.05))

async def drop_airbomb(protocol, player_id, x, y):
    X = floor(x)
    Y = floor(y)
    Z = protocol.map.get_z(X, Y) - 2

    await airbomb_explode(protocol, player_id, X, Y, Z)

async def do_bombing(protocol, player_id, x, y, vx, vy, nbombs):
    for k in range(nbombs):
        await asyncio.sleep(BOMBING_DELAY)
        await drop_airbomb(protocol, player_id, x, y)

        x += vx * BOMBING_DELAY
        y += vy * BOMBING_DELAY

def do_airstrike(name, radio_channel, connection):
    protocol = connection.protocol

    if wo := connection.world_object:
        if loc := wo.cast_ray(AIRSTRIKE_CAST_DISTANCE):
            radio_channel.broadcast_chat(
                protocol, "<{}> Coordinates recieved. Over.".format(name)
            )

            x, y, z = loc

            o = wo.orientation
            v = Vertex3(o.x, o.y, 0).normal() * BOMBER_SPEED

            return protocol.create_map_task(
                do_bombing(protocol, connection.player_id, x, y, v.x, v.y, BOMBS_COUNT)
            )

@command(admin_only = True)
@alive_only
def gift(connection):
    do_airstrike("Panavia Tornado ECR", civil_radio_channel, connection)

@command('airstrike', 'air')
@alive_only
def air(player, loc = None):
    """
    Report time before bomber's arrival
    /air
    """

    if loc is not None:
        return "To initiate an airstrike scope and then hold V. Use /air to check the readiness"

    if o := player.get_bomber():
        remaining = o.remaining()

        if remaining is not None:
            approx = round((remaining / 10 + 1) * 10)
            o.broadcast_report("Will be ready in {} seconds".format(approx))
        else:
            o.broadcast_report("Awaiting for coordinates")
    else:
        return "You haven't equipped an appropriate radio"

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

            if o := player.get_bomber():
                o.point(player)

@dataclass
class Bomber:
    name          : str
    radio_channel : RadioChannel
    protocol      : BaseProtocol

    def __post_init__(self):
        self.init()

    def init(self, by_server = False):
        self.player_id   = None
        self.preparation = None
        self.ready       = False

        if by_server:
            self.preparation = asyncio.get_running_loop().call_later(aitstrike_phase, self.start)

    def point(self, connection):
        if self.ready is True:
            self.player_id = connection.player_id
            do_airstrike(self.name, self.radio_channel, connection)
            self.restart()

    def stop(self, player_id = None):
        if player_id is not None and player_id != self.player_id:
            return

    def start(self):
        if self.ready: return

        self.preparation = None
        self.ready       = True

        self.broadcast_report("Air support is ready")

    def restart(self):
        self.ready       = False
        self.preparation = asyncio.get_running_loop().call_later(airstrike_delay, self.start)

    def broadcast_report(self, mesg):
        self.radio_channel.broadcast_chat(
            self.protocol, "<{}> {}. Over.".format(self.name, mesg)
        )

    def remaining(self):
        if self.preparation:
            return self.preparation.when() - asyncio.get_running_loop().time()
        else:
            return None

def apply_script(protocol, connection, config):
    assert ismilsim(protocol, connection)

    class AirstrikeProtocol(protocol):
        def __init__(self, *w, **kw):
            protocol.__init__(self, *w, **kw)

            self.bomber_1 = Bomber("B-52",   military_radio_channel_1, self)
            self.bomber_2 = Bomber("Tu-22M", military_radio_channel_2, self)

        def on_map_change(self, M):
            for bomber in self.bomber_1, self.bomber_2:
                if bomber.preparation is not None:
                    bomber.preparation.cancel()

                bomber.stop()
                bomber.init(by_server = True)

            protocol.on_map_change(self, M)

    class AirstrikeConnection(connection):
        def on_spawn(self, pos):
            connection.on_spawn(self, pos)

            self.weapon_object.item_underbarrel = Laser().mark_renewable()

        def get_bomber(self):
            if wt := self.handheld_radio_item:
                if wt.radio_channel is military_radio_channel_1:
                    return self.protocol.bomber_1

                if wt.radio_channel is military_radio_channel_2:
                    return self.protocol.bomber_2

    return AirstrikeProtocol, AirstrikeConnection
