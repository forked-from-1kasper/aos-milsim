# Copyright © 2012 Youself
# Copyright © 2021, 2026 rzrn

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

from dataclasses import dataclass
from itertools import islice
from random import randint
from math import inf

import asyncio

from pyspades.constants import CTF_MODE, TEAM_CHANGE_KILL, CLASS_CHANGE_KILL
from horseradish.commands import command
from horseradish.config import config

ffa_section       = config.section("ffa")
ffa_top_size      = ffa_section.option("top_size", 3).get()
ffa_top_frequency = ffa_section.option("top_frequency", 120).get()

def game_top(protocol):
    nicknames = sorted(
        protocol.scores.items(),
        key = lambda item: item[1].value(),
        reverse = True
    )

    top = enumerate(nicknames[:ffa_top_size], start = 1)

    if len(nicknames) > 0:
        return "Top players\n" + "\n".join(
            "{}) {} ({} kills, {} deaths)".format(
                no, nickname, value.kills, value.deaths
            )
            for no, (nickname, value) in top
        )
    else:
        return "No players today"

@command("scores", "score")
def c_scores(connnection):
    """
    Report the current score table
    /scores
    """
    return game_top(connnection.protocol)

@dataclass
class Score:
    kills  : int = 0
    deaths : int = 0

    def value(self):
        return (self.kills, -self.deaths)

def apply_script(protocol, connection, config):
    class FreeForAllProtocol(protocol):
        game_mode    = CTF_MODE
        free_for_all = True
        hide_coord   = (inf, inf, 128)

        def __init__(self, *w, **kw):
            self.scores = {}
            protocol.__init__(self, *w, **kw)

        async def on_event_loop_start(self):
            await protocol.on_event_loop_start(self)
            self.create_task(self.send_top_loop())

        def on_map_change(self, map):
            self.scores = {}

            extensions = self.map_info.extensions

            self.spawn_borders_x = extensions.get('spawn_borders_x', (0, 511))
            self.spawn_borders_y = extensions.get('spawn_borders_y', (0, 511))

            self.friendly_fire = True

            return protocol.on_map_change(self, map)

        def on_base_spawn(self, x, y, z, base, entity_id):
            return self.hide_coord

        def on_flag_spawn(self, x, y, z, flag, entity_id):
            return self.hide_coord

        async def send_top_loop(self):
            while True:
                await asyncio.sleep(ffa_top_frequency)

                for line in reversed(game_top(self).split('\n')):
                    self.broadcast_chat(line)

    class FreeForAllConnection(connection):
        score_hack = False

        def on_spawn_location(self, pos):
            if not self.score_hack and self.protocol.free_for_all:
                while True:
                    x = randint(*self.protocol.spawn_borders_x)
                    y = randint(*self.protocol.spawn_borders_y)
                    z = self.protocol.map.get_z(x, y)

                    if z < 63: break

                # Magic numbers taken from server.py spawn function
                z -= 2.4
                x += 0.5
                y += 0.5
                return x, y, z

            return connection.on_spawn_location(self, pos)

        def on_refill(self):
            return False

        def on_flag_take(self):
            return False

        def on_login(self, name):
            if name not in self.protocol.scores:
                self.protocol.scores[name] = Score()

            connection.on_login(self, name)

        def on_kill(self, hit_by, kill_type, grenade):
            if hit_by is not None and self.name != hit_by.name:
                self.protocol.scores[hit_by.name].kills += 1

            if kill_type not in {TEAM_CHANGE_KILL, CLASS_CHANGE_KILL}:
                self.protocol.scores[self.name].deaths += 1

            # Switch teams to add score hack
            if hit_by is not None and hit_by.team is self.team and self is not hit_by:
                self.score_hack = True
                self.set_team(self.team.other)
                self.spawn(self.world_object.position.get())
                self.score_hack = False

            return connection.on_kill(self, hit_by, kill_type, grenade)

    return FreeForAllProtocol, FreeForAllConnection
