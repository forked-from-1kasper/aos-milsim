"""
Team Deathmatch game mode.

Maintainer: Triplefox
"""

from pyspades.constants import *

from piqueserver.commands import command

HIDE_COORD = (0, 0, 0)


@command()
def score(connection):
    return connection.protocol.get_kill_count()


def apply_script(protocol, connection, config):
    class TDMConnection(connection):
        def on_spawn(self, pos):
            self.send_chat(self.explain_game_mode())
            self.send_chat(self.protocol.get_kill_count())
            return connection.on_spawn(self, pos)

        def on_flag_take(self):
            return False

        def on_kill(self, killer, type, grenade):
            result = connection.on_kill(self, killer, type, grenade)
            self.protocol.check_end_game(killer)
            return result

        def explain_game_mode(self):
            return 'Team Deathmatch: Kill the opposing team.'

    class TDMProtocol(protocol):
        game_mode = CTF_MODE
        kill_limit = config.get('kill_limit', 300)

        def on_flag_spawn(self, x, y, z, flag, entity_id):
            return HIDE_COORD

        def get_kill_count(self):
            kills = self.team_1.kills + self.team_2.kills
            return ("%s left. Playing to %s kills." %
                   (self.kill_limit - kills, self.kill_limit))

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
