# Copyright © 2023–2024, 2026 rzrn

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

from dataclasses import dataclass
from math import floor, sqrt
from enum import Enum, auto

from twisted.internet import reactor

from pyspades.protocol import BaseProtocol
from pyspades.common import Vertex3
from pyspades.world import Grenade

from piqueserver.commands import command, get_player, CommandError
from piqueserver.config import config

from milsimlib.items import RadioChannel, military_radio_channel_1, military_radio_channel_2
from milsimlib.blast import HighExplosive, HEGrenadeObject, sendGrenadePacket

from milsimlib.common import alive_only
from milsimlib import ismilsim

section = config.section("drone")

drone_phase    = section.option("phase", 90).get()
drone_delay    = section.option("delay", 240).get()
drone_rate     = section.option("rate", 1).get()
drone_timeout  = section.option("timeout", 60).get()
drone_teamkill = section.option("teamkill", False).get()
drone_grenades = section.option("grenades", 5).get()

class M26GrenadeObject(HEGrenadeObject):
    high_explosive = HighExplosive(0.200, 1150, 1600, 0.2 / 1000, 2.0e-5, 0.46)

class Status(Enum):
    inflight = auto()
    awaiting = auto()
    inwork   = auto()

@dataclass
class Drone:
    name          : str
    radio_channel : RadioChannel
    protocol      : BaseProtocol

    def __post_init__(self):
        self.init()

    def init(self, by_server = False):
        self.status    = Status.inflight
        self.callback  = None
        self.player_id = None
        self.target_id = None
        self.grenades  = 0
        self.passed    = 0

        if by_server:
            self.callback = reactor.callLater(drone_phase, self.start)

    def broadcast_report(self, mesg):
        self.radio_channel.broadcast_chat(
            self.protocol, "<{}> {}. Over.".format(self.name, mesg)
        )

    def start(self):
        if self.status != Status.inflight:
            return

        self.arrive()

    def stop(self):
        if self.callback and self.callback.active():
            self.callback.cancel()
            self.callback = None

    def arrive(self):
        self.grenades = drone_grenades
        self.status = Status.awaiting
        self.broadcast_report("Drone on the battlefield")

    def track(self, player, target):
        self.player_id = player.player_id
        self.target_id = target.player_id
        self.status    = Status.inwork
        self.passed    = 0

        self.broadcast_report("Received. Watching for {}".format(target.name))
        self.callback = reactor.callLater(drone_rate, self.ping)

    def free(self):
        self.status    = Status.awaiting
        self.passed    = 0
        self.player_id = None
        self.target_id = None

    def ping(self):
        self.passed += drone_rate

        if self.target_id not in self.protocol.players:
            self.broadcast_report("Don't see the target. Awaiting for further instructions")
            return self.free()

        target = self.protocol.players[self.target_id]

        if self.passed > drone_timeout:
            self.broadcast_report("Don't see {}. Awaiting for further instructions".format(target.name))
            return self.free()

        if target.dead():
            self.callback = reactor.callLater(drone_rate, self.ping)
            return

        x, y, z = target.world_object.position.get()
        H = self.protocol.map.get_z(floor(x), floor(y))

        if z <= H:
            fuse = sqrt(z) / 4

            position = Vertex3(x, y, 0)
            velocity = Vertex3(0, 0, 0)

            if player := self.protocol.take_player(self.player_id):
                grenade = self.protocol.world.create_object(
                    M26GrenadeObject, self.protocol, player.player_id, fuse, position, velocity
                )
                grenade.name = 'grenade'

                sendGrenadePacket(self.protocol, player.player_id, position, velocity, fuse)

                self.grenades -= 1

                self.passed    = 0
                self.target_id = None
                self.player_id = None

                if self.grenades > 0:
                    self.status   = Status.awaiting
                    self.callback = None
                    self.broadcast_report("Bombed out. Awaiting for further instructions")
                else:
                    self.status   = Status.inflight
                    self.callback = reactor.callLater(drone_delay, self.arrive)
                    self.broadcast_report("Bombed out. Will be ready in {} seconds".format(drone_delay))
        else:
            self.callback = reactor.callLater(drone_rate, self.ping)

    def remaining(self):
        if self.callback is not None:
            return self.callback.getTime() - reactor.seconds()

@command('drone', 'd')
@alive_only
def drone(conn, nickname = None):
    """
    Commands the drone to follow the player
    /drone <player>
    """

    if drone := conn.get_drone():
        if drone.status == Status.inflight:
            if rem := drone.remaining():
                approx = (rem // 5 + 1) * 5
                drone.broadcast_report("Will be on the battlefield in {:.0f} seconds".format(approx))
        elif drone.status == Status.inwork:
            drone.broadcast_report("Drone is busy")
        elif nickname is None:
            return "Usage: /drone <player>"
        elif drone.status == Status.awaiting:
            player = get_player(conn.protocol, nickname, spectators = False)

            if player.team.id == conn.team.id and not drone_teamkill:
                raise CommandError("Expected enemy's nickname")

            drone.track(conn, player)
    else:
        return "You haven't equipped an appropriate radio"

def apply_script(protocol, connection, config):
    assert ismilsim(protocol, connection)

    class UAVProtocol(protocol):
        def __init__(self, *w, **kw):
            protocol.__init__(self, *w, **kw)

            self.drone_1 = Drone("AER Razor 1",         military_radio_channel_1, self)
            self.drone_2 = Drone("SHUO North Star 400", military_radio_channel_2, self)

        def on_map_change(self, M):
            for drone in self.drone_1, self.drone_2:
                drone.stop()
                drone.init(by_server = True)

            protocol.on_map_change(self, M)

    class UAVConnection(connection):
        def get_drone(self):
            if wt := self.handheld_radio_item:
                if wt.radio_channel is military_radio_channel_1:
                    return self.protocol.drone_1

                if wt.radio_channel is military_radio_channel_2:
                    return self.protocol.drone_2

    return UAVProtocol, UAVConnection