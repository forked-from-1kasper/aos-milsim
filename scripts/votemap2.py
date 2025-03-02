from operator import itemgetter
from collections import Counter
from math import ceil
import random

from pyspades.common import prettify_timespan

from piqueserver.commands import command, player_only
from piqueserver.config import config, cast_duration

votemap_config = config.section('votemap')
votemap_ratio = votemap_config.option('percentage', 60).get() / 100.0

votemap_extension_time = votemap_config.option(
    'extension_time', default = "15min", cast = lambda x: cast_duration(x) / 60
).get() # minutes

class VotemapCandidate:
    def __init__(self, label):
        self.name = "[{}]".format(label)

vote_extend_candidate = VotemapCandidate('Extend')
vote_skip_candidate = VotemapCandidate('Next Map')

def map_vote_iterator(protocol):
    for player in protocol.players.values():
        if map_vote := player.map_vote:
            yield map_vote

def map_vote_counter(protocol):
    return Counter(map_vote_iterator(protocol))

def map_vote_threshold(protocol):
    return ceil(len(protocol.players) * votemap_ratio)

def check_map_vote_end(protocol):
    vote_results = map_vote_counter(protocol)
    threshold = map_vote_threshold(protocol)

    if w := max(vote_results.items(), default = None, key = itemgetter(1)):
        map_vote, vote_count = w

        if threshold <= vote_count:
            for player in protocol.players.values():
                player.map_vote = None

            if map_vote is vote_extend_candidate:
                timelimit = protocol.set_time_limit(votemap_extension_time, True)

                protocol.broadcast_chat(
                    'Mapvote ended. Current map will continue for {}'.format(
                        prettify_timespan(timelimit * 60)
                    )
                )
            elif map_vote is vote_skip_candidate:
                # “protocol.advance_rotation” will take the next map
                # from “protocol.map_rotator” if `protocol.planned_map` was not chosen
                protocol.advance_rotation('Mapvote ended.')
            else:
                protocol.planned_map = map_vote
                protocol.advance_rotation('Mapvote ended.')

@command('vote')
@player_only
def c_vote(connection, *w):
    """
    (Re-)vote for a given map
    /vote <map name>
    """

    if len(w) <= 0: return "You can check available maps using /showrotation or /roll"

    protocol = connection.protocol

    query = " ".join(w).lower()

    for rot_info in protocol.maps:
        if query == rot_info.name.lower():
            if connection.map_vote is rot_info:
                return "You already voted for {}".format(rot_info.name)

            connection.map_vote = rot_info
            protocol.broadcast_chat(
                "{} voted for {}".format(connection.name, rot_info.name)
            )

            check_map_vote_end(protocol)

            return

    # It’s slightly inefficient to iterate twice, but
    # a) the loss of performance here can be neglected,
    # and b) this way we make sure that players can vote
    # for the map XXX even if there is map XXXYYY before
    # (that is, one that contains the former as a prefix).
    for rot_info in protocol.maps:
        if query in rot_info.name.lower():
            return "Did you mean '{}'?".format(rot_info.name)

    return "'{}' map not found".format(query)

@command('voteskip')
@player_only
def c_voteskip(connection, *w):
    """
    Vote to skip the current map
    /voteskip
    """

    protocol = connection.protocol

    if connection.map_vote is vote_skip_candidate:
        return "You already voted to skip the current map"

    connection.map_vote = vote_skip_candidate
    protocol.broadcast_chat(
        "{} voted to skip the current map".format(connection.name)
    )

    check_map_vote_end(protocol)

@command('voteextend')
@player_only
def c_voteextend(connection, *w):
    """
    Vote to extend the current map
    /voteextend
    """

    protocol = connection.protocol

    if connection.map_vote is vote_extend_candidate:
        return "You already voted to extend the current map"

    connection.map_vote = vote_extend_candidate
    protocol.broadcast_chat(
        "{} voted to extend the current map".format(connection.name)
    )

    check_map_vote_end(protocol)

@command('voteback')
@player_only
def c_voteback(connection, *w):
    """
    Take your map vote back
    /voteback
    """

    protocol = connection.protocol

    if map_vote := connection.map_vote:
        connection.map_vote = None
        protocol.broadcast_chat(
            "{} took back his vote for {}".format(connection.name, map_vote.name)
        )
    else:
        return "You haven't voted yet"

@command('votemap')
def c_votemap(connection):
    """
    Report current map voting results
    /votemap
    """

    protocol = connection.protocol

    vote_results = map_vote_counter(protocol)
    threshold = map_vote_threshold(protocol)

    if bool(vote_results):
        return ", ".join(
            "{} ({}/{})".format(map_vote.name, vote_count, threshold)
            for map_vote, vote_count in vote_results.most_common(5)
        )
    else:
        return "No one voted yet. Use /vote <map name>, /voteskip, or /voteextend to be the first"

@command('roll')
def c_roll(connection):
    """
    Print 5 random maps from rotation
    /roll
    """

    protocol = connection.protocol
    rotation = protocol.maps

    chosen = random.sample(rotation, min(len(rotation), 5))
    return " ".join(rot_info.name for rot_info in chosen)

def apply_script(protocol, connection, config):
    class VotemapConnection(connection):
        map_vote = None

        def on_disconnect(self):
            connection.on_disconnect(self)
            check_map_vote_end(self.protocol)

    class VotemapProtocol(protocol):
        def on_map_change(self, M):
            for player in self.players.values():
                # These votes where about the previous maps
                if player.map_vote is vote_extend_candidate:
                    player.map_vote = None

                if player.map_vote is vote_skip_candidate:
                    player.map_vote = None

            protocol.on_map_change(self, M)

    return VotemapProtocol, VotemapConnection