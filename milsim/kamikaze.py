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

from math import floor, inf, isinf, isnan
from time import monotonic
from random import choice

import asyncio

from pyspades.constants import CHAT_ALL

from pyspades import contained as loaders
from pyspades.common import Vertex3

from piqueserver.commands import command, player_only
from piqueserver.config import config

from milsimlib.blast import HighExplosive, sendGrenadePacket
from milsimlib import ismilsim

section = config.section("kamikaze")

kamikaze_message  = section.option("message", None).get()
kamikaze_max_fuse = section.option("max_fuse", 60).get()
kamikaze_delay    = section.option("delay", 15).get()

class ExplosiveBelt:
    high_explosive = HighExplosive(4.5, 1500, 1700, 1 / 1000, 1.5e-4, 0.70)

    def __init__(self, connection):
        self.connection = connection
        self.defer      = None
        self.last       = -inf

    def alive(self):
        return self.connection and self.connection.alive()

    def start(self, fuse):
        if self.defer is not None:
            return

        if not self.alive():
            return

        if fuse < 0 or fuse > kamikaze_max_fuse:
            return "Delay should be non-negative and less than {}.".format(kamikaze_max_fuse)

        dt = monotonic() - self.last

        if dt < kamikaze_delay:
            return "Wait {:.1f} seconds.".format(kamikaze_delay - dt)

        self.defer = asyncio.get_running_loop().call_later(fuse, self.callback)

    def stop(self):
        if self.defer:
            self.defer.cancel()

            self.last  = monotonic()
            self.defer = None

    def callback(self):
        self.last  = monotonic()
        self.defer = None

        protocol = self.connection.protocol

        if self.alive() and kamikaze_message:
            contained           = loaders.ChatMessage()
            contained.player_id = self.connection.player_id
            contained.chat_type = CHAT_ALL
            contained.value     = kamikaze_message

            protocol.broadcast_contained(contained)

        r = self.connection.world_object.position
        sendGrenadePacket(
            protocol, self.connection.player_id,
            r - Vertex3(0, 0, 1.5), Vertex3(0, 0, 0), 0
        )

        self.connection.grenade_destroy(floor(r.x), floor(r.y), floor(r.z + 3))
        self.high_explosive.explode(protocol, r, hit_by = self.connection)

@command('boom', 'a', 'aa')
@player_only
def boom(player, fuse = 0):
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

    return player.belt.start(fuse)

def apply_script(protocol, connection, config):
    assert ismilsim(protocol, connection)

    class KamikazeConnection(connection):
        def __init__(self, *w, **kw):
            connection.__init__(self, *w, **kw)
            self.belt = ExplosiveBelt(self)

        def on_spawn(self, pos):
            self.belt.stop()

            connection.on_spawn(self, pos)

        def on_team_changed(self, old_team):
            if self.team is None or self.team.spectator:
                self.belt.stop()

            connection.on_team_changed(self, old_team)

    return protocol, KamikazeConnection
