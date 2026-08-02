# Copyright © 2011 triplefox
# Copyright © 2017 1AmYF
# Copyright © 2021, 2023–2024, 2026 rzrn

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

from pyspades.constants import CTF_MODE

from horseradish.commands import command
from horseradish.config import config

tdm_section    = config.section("tdm")
tdm_kill_limit = tdm_section.option("kill_limit", 500).get()

@command("score", "tdmscore")
def c_score(connection):
    """
    Report the current TDM score
    /score
    """
    return connection.protocol.get_kill_count()

def apply_script(protocol, connection, config):
    class TDMConnection(connection):
        def on_spawn(self, pos):
            self.send_chat(self.explain_game_mode())
            self.send_chat(self.protocol.get_kill_count())
            return connection.on_spawn(self, pos)

        def on_kill(self, killer, type, grenade):
            if connection.on_kill(self, killer, type, grenade) is False:
                return False

            self.protocol.check_end_game(killer)

        def on_flag_capture(self):
            connection.on_flag_capture(self)
            self.protocol.check_end_game(self)

        def explain_game_mode(self):
            return "Team Deathmatch: kill the opposing team"

    class TDMProtocol(protocol):
        game_mode = CTF_MODE

        def get_kill_count(self):
            kills = self.team_1.kills + self.team_2.kills

            return "{team_1} vs {team_2}: {rem} left. Playing to {total} kills".format(
                team_1 = self.team_1.kills,
                team_2 = self.team_2.kills,
                rem    = tdm_kill_limit - kills,
                total  = tdm_kill_limit
            )

        def check_end_game(self, player):
            if tdm_kill_limit <= self.team_1.kills + self.team_2.kills:
                if self.team_1.kills > self.team_2.kills:
                    self.send_chat(
                        "{} wins, {} : {}".format(self.team1_name, self.team_1.kills, self.team_2.kills)
                    )
                elif self.team_2.kills > self.team_1.kills:
                    self.send_chat(
                        "{} wins, {} : {}".format(self.team2_name, self.team_2.kills, self.team_1.kills)
                    )
                else:
                    self.send_chat("Draw!")

                self.reset_game(player)
                protocol.on_game_end(self)

    return TDMProtocol, TDMConnection
