from operator import itemgetter
from collections import Counter
from math import ceil

from piqueserver.commands import command, player_only
from piqueserver.config import config

votemap_config = config.section('votemap')
votemap_ratio = votemap_config.option('percentage', 60).get() / 100.0

class VoteSkipCandidate:
    name = '[Next Map]'

vote_skip_candidate = VoteSkipCandidate()

def get_vote_rotation_info(vote):
    if vote is vote_skip_candidate:
        return None # “protocol.advance_rotation” will take the next map from “protocol.map_rotator”
    else:
        return vote

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

            protocol.planned_map = get_vote_rotation_info(map_vote)
            protocol.advance_rotation('Mapvote ended.')

@command('vote')
@player_only
def c_vote(connection, *w):
    """
    (Re-)vote for a given map
    /vote <map name>
    """

    if len(w) <= 0: return "You can check available maps using /showrotation"

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
        return "No one voted yet. Use /vote <map name> or /voteskip to be the first"

def apply_script(protocol, connection, config):
    class VotemapConnection(connection):
        map_vote = None

        def on_disconnect(self):
            connection.on_disconnect(self)
            check_map_vote_end(self.protocol)

    return protocol, VotemapConnection