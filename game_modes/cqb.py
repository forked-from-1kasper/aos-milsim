# Copyright © 2026 rzrn

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

from math import inf

from pyspades.contained import IntelCapture
from pyspades.constants import CTF_MODE

from piqueserver.commands import command, player_only
from piqueserver.config import config

from milsim.grammar import RegularNoun, CompoundNoun, SemiregularVerb, Cardinal, VerbNTR, np_vp_past
from milsim.connection import MilsimConnection

cqb_section              = config.section("cqb")
cqb_respawn_tickets      = cqb_section.option("respawn_tickets", 64).get()
cqb_flag_capture_tickets = cqb_section.option("flag_capture_tickets", 5).get()

remain_v         = SemiregularVerb(bare = "remain", ving = "remaining", ved = "remained", v3sg = "remains", vpast = "remained")
ticket_n         = RegularNoun("ticket")
respawn_ticket_n = CompoundNoun("respawn", ticket_n)

remain_vp = VerbNTR(remain_v)

def get_team_respawn_notice(team):
    if team.available_tickets is None:
        return

    return np_vp_past(Cardinal(team.available_tickets, respawn_ticket_n), remain_vp)

def is_team_defeated(team):
    available_tickets = team.available_tickets

    if available_tickets is None:
        return False

    if available_tickets <= 0:
        return all(player.dead() for player in team.get_players())
    else:
        return False

def announce_game_end(protocol, winner = None):
    if winner is None:
        for player in protocol.players.values():
            player.send_chat_error("The game ended in a draw")
    else:
        contained           = IntelCapture()
        contained.player_id = winner.player_id
        contained.winning   = True

        protocol.broadcast_contained(contained, save = True)

@command("tickets", "showtickets")
@player_only
def c_tickets(connection):
    """
    Report the current number of respawn tickets
    /tickets
    """
    return get_team_respawn_notice(connection.team)

def apply_script(protocol, connection, config):
    """
    [1] A fixed number `cqb_respawn_tickets` of respawn tickets is assigned to each team.
    [2] Capturing the flag gives `cqb_flag_capture_tickets` more tickets to your team.
    [3] A team that has no living players and no respawn tickets available is considered defeated.
    [4] A team wins iff it is not defeated and the opposing team is.

    This game mode is much like TDM, but, unlike TDM, what’s important is not the number
    of kills in itself, but the number of respawns. This approach suits `aos-milsim` more,
    because it encourages players to save their lives: e.g., you can’t circumvent bleeding
    by simply issuing `/kill`, as this will waste your team’s respawn tickets. The other
    common problem with TDM is that players often die not immediately but after a few
    seconds due to bleeding, so the kill doesn’t count.
    """

    # We rely on the ability to return `inf` from `get_respawn_time()` here.
    assert issubclass(connection, MilsimConnection)

    class CQBProtocol(protocol):
        game_mode = CTF_MODE

        def __init__(self, *w, **kw):
            protocol.__init__(self, *w, **kw)

            for team in self.team_1, self.team_2, self.team_spectator:
                team.available_tickets = None

        def on_map_change(self, M):
            self.max_score = 0

            self.team_1.available_tickets = cqb_respawn_tickets
            self.team_2.available_tickets = cqb_respawn_tickets

            protocol.on_map_change(self, M)

        def check_game_end(self):
            team_1_is_defeated = is_team_defeated(self.team_1)
            team_2_is_defeated = is_team_defeated(self.team_2)

            if team_1_is_defeated and team_2_is_defeated:
                player = None
            elif team_1_is_defeated:
                player = next(self.team_2.get_players(), None)
            elif team_2_is_defeated:
                player = next(self.team_1.get_players(), None)
            else:
                return # Neither team is defeated, the game continues.

            announce_game_end(self, winner = player)

            self.on_game_end()

    class CQBConnection(connection):
        def has_available_tickets(self):
            available_tickets = self.team.available_tickets

            if available_tickets is None:
                return True

            return available_tickets > 0

        def get_respawn_time(self):
            if self.has_available_tickets():
                return connection.get_respawn_time(self)
            else:
                return inf

        def on_spawn(self, loc):
            connection.on_spawn(self, loc)

            self.team.available_tickets = max(self.team.available_tickets - 1, 0)

            if mesg := get_team_respawn_notice(self.team):
                self.send_chat(mesg)

        def on_flag_capture(self):
            connection.on_flag_capture(self)

            self.team.available_tickets += cqb_flag_capture_tickets

        def on_killed(self, killer, type, grenade):
            connection.on_killed(self, killer, type, grenade)

            self.protocol.check_game_end()

    return CQBProtocol, CQBConnection
