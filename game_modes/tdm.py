# Copyright © 2011 triplefox
# Copyright © 2017 1AmYF
# Copyright © 2021, 2023–2024 rzrn

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

from pyspades.constants import *

from piqueserver.commands import command

WIN_POINTS = 500
INTEL_POINTS = 10

@command()
def score(connection):
    return connection.protocol.get_kill_count()

def apply_script(protocol, connection, config):
    class TDMConnection(connection):
        intel_points = config.get('intel_points', INTEL_POINTS)

        def on_spawn(self, pos):
            self.send_chat(self.explain_game_mode())
            self.send_chat(self.protocol.get_kill_count())
            return connection.on_spawn(self, pos)

        def on_kill(self, killer, type, grenade):
            result = connection.on_kill(self, killer, type, grenade)
            self.protocol.check_end_game(killer)
            return result

        def on_flag_capture(self):
            result = connection.on_flag_capture(self)
            self.team.kills += self.intel_points
            self.protocol.check_end_game(self)
            return result

        def explain_game_mode(self):
            return 'Team Deathmatch: kill the opposing team.'

    class TDMProtocol(protocol):
        game_mode = CTF_MODE
        kill_limit = config.get('kill_limit', WIN_POINTS)

        def get_kill_count(self):
            kills = self.team_1.kills + self.team_2.kills
            return "%d vs %d: %s left. Playing to %s kills." % (
                self.team_1.kills,
                self.team_2.kills,
                self.kill_limit - kills,
                self.kill_limit
            )

        def check_end_game(self, player):
            if self.team_1.kills + self.team_2.kills >= self.kill_limit:
                if self.team_1.kills > self.team_2.kills:
                    self.send_chat("%s Wins, %s : %s" %
                                   (self.team1_name, self.team_1.kills, self.team_2.kills))
                elif self.team_2.kills > self.team_1.kills:
                    self.send_chat("%s Wins, %s : %s" %
                                   (self.team2_name, self.team_2.kills, self.team_1.kills))
                else:
                    self.send_chat("Draw!")

                self.reset_game(player)
                protocol.on_game_end(self)

    return TDMProtocol, TDMConnection
