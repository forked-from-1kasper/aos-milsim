from collections import Counter
from itertools import chain
from math import ceil

from time import monotonic

from pyspades.constants import ERROR_BANNED, ERROR_UNDEFINED
from pyspades.common import prettify_timespan

from piqueserver.commands import command, player_only, get_player, join_arguments
from piqueserver.config import config, cast_duration
from piqueserver.utils import timeparse

voteban_config = config.section('voteban')

voteban_duration        = voteban_config.option('ban_duration', default = "30min", cast = cast_duration).get()
voteban_revoke_timeout  = voteban_config.option('revoke_timeout', default = "2min", cast = cast_duration).get()
voteban_percentage      = voteban_config.option('percentage', 51).get()
voteban_percentage_team = voteban_config.option('percentage_team', 75).get()

def format_reason(ws):
    if len(ws) > 0:
        return "Reason: {}".format(' '.join(ws))
    else:
        return None

class VotebanResults(Counter):
    def __init__(self, percentage, players):
        votes = dict()

        for player in players:
            addr, port = player.address

            # this way votes from the same address are not counted twice
            vs = votes[addr] = votes.get(addr) or set()
            vs.update(player.voteban)

        for vs in votes.values():
            self.update(vs)

        ratio = percentage / 100.0

        self.percentage = percentage
        self.threshold  = max(2, ceil(len(votes) * ratio))

    def against(self, addr):
        return self.get(addr, 0)

    def successful(self, addr):
        return self.threshold <= self.get(addr, 0)

def voteban_vetos(protocol):
    return set(
        chain.from_iterable(
            player.vetos for player in protocol.connections.values()
        )
    )

def voteban_results(protocol):
    total  = VotebanResults(voteban_percentage,      protocol.connections.values())
    team_1 = VotebanResults(voteban_percentage_team, protocol.team_1.get_players())
    team_2 = VotebanResults(voteban_percentage_team, protocol.team_2.get_players())

    return total, team_1, team_2

def voteban_revoke(player):
    retval = len(player.vetos)

    player.voteban.clear()
    player.vetos.clear()

    return retval

def scan_for_bans(protocol, total, team_1, team_2):
    vetos = voteban_vetos(protocol)

    revoked = 0

    for player in protocol.connections.values():
        addr, port = player.address

        if addr in vetos:
            continue

        if addr in protocol.bans:
            revoked += voteban_revoke(player)
            continue

        if total.successful(addr):
            reason = "voteban {:.0f} %".format(total.percentage)
        elif team_1.successful(addr):
            reason = "voteban {:.0f} % ({})".format(team_1.percentage, protocol.team_1.name)
        elif team_2.successful(addr):
            reason = "voteban {:.0f} % ({})".format(team_2.percentage, protocol.team_2.name)
        else:
            continue

        for player2 in protocol.connections.values():
            player2.voteban.discard(addr)

        revoked += player.ban(reason, voteban_duration)

    return revoked

def check_voteban_end(protocol):
    total, team_1, team_2 = voteban_results(protocol)

    while scan_for_bans(protocol, total, team_1, team_2) > 0:
        pass

def have_privs(connection, target = None):
    protocol = connection.protocol

    if isinstance(connection, protocol.connection_class):
        # /voteveto effectively disables moderator permissions
        if connection.vetoed():
            return "Permission denied: you are under /voteveto"

        if connection.suspected():
            if isinstance(target, protocol.connection_class):
                if not target.suspected(investigator = connection.address[0]):
                    return "Permission denied: someone voted against you, but no one voted against {}".format(target.name)
            else:
                return "Permission denied: someone voted against you"

@command('votestatus', 'vs')
def c_votestatus(connection, nickname):
    """
    Print current voting results
    /votestatus <player>
    """

    protocol = connection.protocol
    player = get_player(protocol, nickname)

    addr, port = player.address

    if addr in protocol.bans:
        return "{} is banned".format(player.name)

    total, team_1, team_2 = voteban_results(protocol)

    votes_total  = total.against(addr)
    votes_team_1 = team_1.against(addr)
    votes_team_2 = team_2.against(addr)

    return "{}: {}/{}, {}/{} ({}), {}/{} ({}) {}".format(
        player.name,  votes_total,      total.threshold,
        votes_team_1, team_1.threshold, protocol.team_1.name,
        votes_team_2, team_2.threshold, protocol.team_2.name,
        "VETO" if player.vetoed() else ""
    )

@command('revokevote', 'rvo', admin_only = True)
def c_revokevote(connection, nickname, *ws):
    """
    Revoke votes against a given player
    /revokevote <player> [reason]
    """

    if errmsg := have_privs(connection):
        return errmsg

    protocol = connection.protocol
    player = get_player(protocol, nickname)

    t = monotonic()
    dt = t - player.voteban_last_revoke

    if dt < voteban_revoke_timeout:
        return "Wait {:.2f} seconds".format(voteban_revoke_timeout - dt)

    addr, port = player.address

    revaddrs = set()

    for player2 in protocol.connections.values():
        if addr in player2.voteban:
            player2.voteban.remove(addr)
            revaddrs.add(player2.address[0])

    revoked = len(revaddrs)

    if revoked <= 0:
        return "No one voted against {} yet".format(player.name)
    else:
        player.voteban_last_revoke = t

        protocol.broadcast_message(
            "{} revoked {} vote(s) against {}".format(
                connection.name, revoked, player.name
            ),
            format_reason(ws)
        )

@command('voteveto', 'veto', 'vv', admin_only = True)
@player_only
def c_veto(connection, *w):
    """
    Veto ban against a given player
    /voteveto <player>
    """

    if errmsg := have_privs(connection):
        return errmsg

    protocol = connection.protocol

    nickname, *ws = w
    player = get_player(protocol, nickname)

    addr, port = player.address

    if addr is connection.address[0]:
        return "You can't veto yourself"
    elif addr in protocol.bans:
        return "{} is banned".format(player.name)
    elif addr in connection.vetos:
        return "You already vetoed {}'s ban".format(player.name)
    else:
        connection.vetos.add(addr)

        protocol.broadcast_message(
            "{} vetoed {}'s ban".format(
                connection.name, player.name
            ),
            format_reason(ws)
        )

@command('voteunveto', 'unveto', 'vuv', admin_only = True)
@player_only
def c_unveto(connection, *w):
    """
    Cancel ban veto against a given player
    /voteunvento <player>
    """

    protocol = connection.protocol

    nickname, *ws = w
    player = get_player(protocol, nickname)

    if errmsg := have_privs(connection, player):
        return errmsg

    addr, port = player.address

    if addr in protocol.bans:
        return "{} is banned".format(player.name)
    elif addr in connection.vetos:
        connection.vetos.remove(addr)

        protocol.broadcast_message(
            "{} cancelled his veto on {}'s ban".format(
                connection.name, player.name
            ),
            format_reason(ws)
        )

        check_voteban_end(protocol)
    else:
        return "You didn't veto {}'s ban".format(player.name)

@command('voteban', 'vb')
@player_only
def c_voteban(connection, *w):
    """
    Vote against a given player
    /voteban <player> [reason]
    """

    if len(w) <= 0: return "Target player is required"

    nickname, *ws = w

    protocol = connection.protocol
    player = get_player(protocol, nickname)

    addr, port = player.address

    if addr in protocol.bans:
        return "{} is already banned".format(player.name)
    elif addr in connection.voteban:
        return "You already voted against {}".format(player.name)
    else:
        connection.voteban.add(addr)

        protocol.broadcast_message(
            "{} voted AGAINST {}".format(
                connection.name, player.name
            ),
            format_reason(ws)
        )

        check_voteban_end(protocol)

@command('votepardon', 'vp')
@player_only
def c_votepardon(connection, *w):
    """
    Revoke your vote against given player
    /votepardon <player> [reason]
    """

    if len(w) <= 0: return "Target player is required"

    nickname, *ws = w

    protocol = connection.protocol
    player = get_player(protocol, nickname)

    addr, port = player.address

    if addr in connection.voteban:
        connection.voteban.remove(addr)

        protocol.broadcast_message(
            "{} took back his vote against {}".format(
                connection.name, player.name
            ),
            format_reason(ws)
        )
    else:
        return "You didn't vote against {}".format(player.name)

@command('votekick', 'vk')
def c_votekick(connection, *w, **kw):
    """
    The same as the /voteban
    /votekick <player> [reason]
    """

    return c_voteban(connection, *w, **kw)

@command('y')
def c_yes(connection, *w, **kw):
    """
    Placeholder for backward compatibility
    /y
    """

    return "Use /voteban <player> instead"

@command('cancel')
def cancel_votekick(connection, *w, **kw):
    """
    Placeholder for backward compatibility
    /cancel
    """

    return "Use /votepardon <player> instead"

@command(admin_only = True)
def kick(connection, nickname, *ws):
    """
    Kick a given player
    /kick <player> [reason]
    """

    reason = join_arguments(ws)
    player = get_player(connection.protocol, nickname)

    if errmsg := have_privs(connection, player):
        return errmsg

    player.kick(reason = reason)

@command(admin_only = True)
def disconnect(connection, nickname):
    """
    Silently disconnect a given player
    /disconnect <player>
    """

    player = get_player(connection.protocol, nickname)

    if errmsg := have_privs(connection, player):
        return errmsg

    player.disconnect(ERROR_UNDEFINED)

@command(admin_only = True)
def ban(connection, nickname, timestr, *ws):
    """
    Ban a given player forever or for a limited amount of time
    /ban <player> <duration> [reason]
    """

    duration = timeparse(timestr)
    reason   = join_arguments(ws)
    player   = get_player(connection.protocol, nickname)

    if errmsg := have_privs(connection, player):
        return errmsg

    player.ban(reason, duration)

@command(admin_only = True)
def mban(connection, nickname, *ws):
    """
    Ban a given player for a minute
    /mban <player> [reason]
    """

    reason = join_arguments(ws)
    player = get_player(connection.protocol, nickname)

    if errmsg := have_privs(connection, player):
        return errmsg

    player.ban(reason, 60)

@command(admin_only = True)
def hban(connection, nickname, *ws):
    """
    Ban a given player for an hour
    /hban <player> [reason]
    """

    reason = join_arguments(ws)
    player = get_player(connection.protocol, nickname)

    if errmsg := have_privs(connection, player):
        return errmsg

    player.ban(reason, 60 * 60)

@command(admin_only = True)
def dban(connection, nickname, *ws):
    """
    Ban a given player for one day
    /dban <player> [reason]
    """

    reason = join_arguments(ws)
    player = get_player(connection.protocol, nickname)

    if errmsg := have_privs(connection, player):
        return errmsg

    player.ban(reason, 24 * 60 * 60)

@command(admin_only = True)
def wban(connection, nickname, *ws):
    """
    Ban a given player for one week
    /wban <player> [reason]
    """

    reason = join_arguments(ws)
    player = get_player(connection.protocol, nickname)

    if errmsg := have_privs(connection, player):
        return errmsg

    player.ban(reason, 7 * 24 * 60 * 60)

@command(admin_only = True)
def pban(connection, nickname, *ws):
    """
    Ban a given player permanently
    /pban <player> [reason]
    """

    reason = join_arguments(ws)
    player = get_player(connection.protocol, nickname)

    if errmsg := have_privs(connection, player):
        return errmsg

    player.ban(reason)

@command(admin_only = True)
def banip(connection, addr, timestr, *ws):
    """
    Ban an ip
    /banip <ip> [duration] [reason]
    """

    duration = timeparse(timestr)
    reason   = join_arguments(ws)

    if errmsg := have_privs(connection):
        return errmsg

    try:
        connection.protocol.add_ban(addr, reason, duration)
    except ValueError:
        return 'Invalid address: {}'.format(addr)

    reason = ': ' + reason if reason is not None else ''

    return "{} banned for {}{}".format(
        addr, prettify_timespan(duration), reason
    )

@command(admin_only = True)
def hardban(connection, nickname, *ws):
    """
    Hardban a given player
    /hardban <player> [reason]
    """

    protocol = connection.protocol

    player = get_player(protocol, nickname)

    if errmsg := have_privs(connection, player):
        return errmsg

    protocol.broadcast_message(
        "{} was hardbanned by {}".format(
            player.name, connection.name
        ),
        format_reason(ws)
    )

    protocol.hard_bans.add(player.address[0])
    player.disconnect(ERROR_BANNED)

@command(admin_only = True)
def undoban(connection):
    """
    Undo last ban
    /undoban
    """

    if errmsg := have_privs(connection):
        return errmsg

    protocol = connection.protocol

    if len(protocol.bans) > 0:
        addr, _ = protocol.undo_last_ban()
        return "{} unbanned".format(addr)

@command(admin_only = True)
def unban(connection, nickname, *ws):
    """
    Unban a given player
    /unban <player> [reason]
    """

    if errmsg := have_privs(connection):
        return errmsg

    protocol = connection.protocol
    player = get_player(protocol, nickname)

    addr, port = player.address

    if addr in protocol.bans:
        protocol.remove_ban(addr)

        protocol.broadcast_message(
            "{} was unbanned by {}".format(player.name, connection.name),
            format_reason(ws)
        )
    else:
        return "{} is not banned".format(player.name)

@command(admin_only = True)
def unbanip(connection, addr):
    """
    Unban an ip
    /unbanip <ip>
    """

    if errmsg := have_privs(connection):
        return errmsg

    protocol = connection.protocol

    if addr in protocol.bans:
        protocol.remove_ban(addr)
        return "{} unbanned".format(addr)
    else:
        return "{} is not banned".format(addr)

def apply_script(protocol, connection, config):
    class VotebanProtocol(protocol):
        def broadcast_message(self, *ws, sep = ". "):
            self.broadcast_chat(sep.join(w for w in ws if w is not None))

    class VotebanConnection(connection):
        voteban_last_revoke = 0

        def __init__(self, *w, **kw):
            connection.__init__(self, *w, **kw)

            self.voteban = set()
            self.vetos = set()

        def on_connect(self):
            connection.on_connect(self)
            check_voteban_end(self.protocol)

        def on_disconnect(self):
            connection.on_disconnect(self)
            check_voteban_end(self.protocol)

        def on_team_changed(self, old_team):
            connection.on_team_changed(self, old_team)
            check_voteban_end(self.protocol)

        def ban(self, reason = None, duration = None):
            connection.ban(self, reason, duration)
            return voteban_revoke(self)

        def suspected(self, investigator = None):
            addr, port = self.address

            return any(
                addr in player.voteban
                for player in self.protocol.connections.values()
                if player.address[0] != investigator
            )

        def vetoed(self):
            addr, port = self.address

            return any(addr in player.vetos for player in self.protocol.connections.values())

    return VotebanProtocol, VotebanConnection