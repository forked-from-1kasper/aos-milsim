"""
Free for All: shoot anyone
"""
# Free for all script written by Yourself
# Modified by Siegmentation Fault

from pyspades.constants import (
    TEAM_CHANGE_KILL, CLASS_CHANGE_KILL
)
from piqueserver.commands import command
from pyspades.constants import CTF_MODE
from twisted.internet import reactor
from dataclasses import dataclass
from itertools import islice
from random import randint

fst = lambda xs: xs[0]
snd = lambda xs: xs[1]

IGNORE_IN_TOP = [TEAM_CHANGE_KILL, CLASS_CHANGE_KILL]
TOP_FREQUENCY = 120
TOP_SIZE = 3

# If ALWAYS_ENABLED is False, free for all can still be enabled in the map
# metadata by setting the key 'free_for_all' to True in the extensions
# dictionary
ALWAYS_ENABLED = True

# If WATER_SPAWNS is True, then players can spawn in water
WATER_SPAWNS = False

HIDE_POS = (0, 0, 63)

def show_score(item):
    idx, (name, score) = item
    return "%d) %s (%d kills, %d deaths)" % (idx, name, score.kills, score.deaths)

def game_top(protocol):
    nicknames = sorted(
        protocol.scores.items(),
        key = lambda item: snd(item).value(),
        reverse = True
    )
    top = enumerate(nicknames[:TOP_SIZE], start=1)

    if len(nicknames) > 0:
        return "Top players\n" + "\n".join(map(show_score, top))
    else:
        return "No players today."

@command('scores')
def scores(conn, *args):
    return game_top(conn.protocol)

@dataclass
class Score:
    kills  : int = 0
    deaths : int = 0

    def value(self):
        return (self.kills, -self.deaths)

def apply_script(protocol, connection, config):
    class FreeForAllProtocol(protocol):
        game_mode = CTF_MODE
        free_for_all = False
        old_friendly_fire = None

        def __init__(self, *arg, **kw):
            self.scores = {}
            self.send_top(True)
            return protocol.__init__(self, *arg, **kw)

        def on_map_change(self, map):
            self.scores = {}

            extensions = self.map_info.extensions

            self.spawn_borders_x = extensions.get('spawn_borders_x', (0, 511))
            self.spawn_borders_y = extensions.get('spawn_borders_y', (0, 511))

            if ALWAYS_ENABLED:
                self.free_for_all = True
            else:
                if 'free_for_all' in extensions:
                    self.free_for_all = extensions['free_for_all']
                else:
                    self.free_for_all = False
            if self.free_for_all:
                self.old_friendly_fire = self.friendly_fire
                self.friendly_fire = True
            else:
                if self.old_friendly_fire is not None:
                    self.friendly_fire = self.old_friendly_fire
                    self.old_friendly_fire = None

            return protocol.on_map_change(self, map)

        def on_base_spawn(self, x, y, z, base, entity_id):
            if self.free_for_all:
                return HIDE_POS
            return protocol.on_base_spawn(self, x, y, z, base, entity_id)

        def on_flag_spawn(self, x, y, z, flag, entity_id):
            if self.free_for_all:
                return HIDE_POS
            return protocol.on_flag_spawn(self, x, y, z, flag, entity_id)

        def send_top(self, init=False):
            if not init:
                for line in reversed(game_top(self).split('\n')):
                    self.broadcast_chat(line)
            reactor.callLater(TOP_FREQUENCY, self.send_top)

    class FreeForAllConnection(connection):
        score_hack = False

        def on_spawn_location(self, pos):
            if not self.score_hack and self.protocol.free_for_all:
                while True:
                    x = randint(*self.protocol.spawn_borders_x)
                    y = randint(*self.protocol.spawn_borders_y)
                    z = self.protocol.map.get_z(x, y)
                    if z != 63 or WATER_SPAWNS:
                        break
                # Magic numbers taken from server.py spawn function
                z -= 2.4
                x += 0.5
                y += 0.5
                return (x, y, z)
            return connection.on_spawn_location(self, pos)

        def on_refill(self):
            if self.protocol.free_for_all:
                return False
            return connection.on_refill(self)

        def on_flag_take(self):
            if self.protocol.free_for_all:
                return False
            return connection.on_flag_take(self)

        def on_login(self, name):
            if name not in self.protocol.scores:
                self.protocol.scores[name] = Score()
            return connection.on_login(self, name)

        def on_kill(self, by, reason, grenade):
            if by is not None and self.name != by.name:
                self.protocol.scores[by.name].kills += 1
            if reason not in IGNORE_IN_TOP:
                self.protocol.scores[self.name].deaths += 1

            # Switch teams to add score hack
            if by is not None and by.team is self.team and self is not by:
                self.score_hack = True
                pos = self.world_object.position
                self.set_team(self.team.other)
                self.spawn((pos.x, pos.y, pos.z))
                self.score_hack = False
            return connection.on_kill(self, by, reason, grenade)

    return FreeForAllProtocol, FreeForAllConnection

# x : from 238 to 270
# y : from 99 to 424