from time import strftime, gmtime, time, monotonic
from twisted.internet import reactor

from piqueserver.commands import command, player_only, get_player
from piqueserver.player import FeatureConnection

from pyspades.player import ServerConnection
from pyspades import contained as loaders
from pyspades.constants import *

prohibited = {
    loaders.WeaponInput.id,
    loaders.HitPacket.id,
    loaders.GrenadePacket.id,
    loaders.BlockAction.id,
    loaders.BlockLine.id
}

@command()
def roles(connection, nickname):
    """
    List roles of the given player
    /roles <player>
    """

    player = get_player(connection.protocol, nickname)

    if bool(player.user_types):
        return "{}: {}".format(
            player.name, ", ".join(player.user_types)
        )
    else:
        return "{} has no roles".format(player.name)

@command(admin_only = True)
def disconnect(connection, nickname):
    """
    Silently disconnect a given player
    /disconnect <player>
    """

    get_player(connection.protocol, nickname).disconnect(ERROR_UNDEFINED)

@command(admin_only = True)
def hardban(connection, nickname):
    """
    Hardban a given player
    /hardban <player>
    """

    protocol = connection.protocol

    player = get_player(protocol, nickname)
    protocol.broadcast_chat(f'{connection.name} was hardbanned.')

    protocol.hard_bans.add(player.address[0])
    player.disconnect(ERROR_BANNED)

@command(admin_only = True)
def unban(connection, nickname):
    """
    Unban a given player
    /unban <player>
    """

    protocol = connection.protocol

    player = get_player(protocol, nickname)
    ip = player.address[0]

    if ip in protocol.bans:
        protocol.remove_ban(ip)
        return "{} unbanned".format(player.name)
    else:
        return "{} is not banned".format(player.name)

@command(admin_only = True)
def unbanip(connection, ip):
    """
    Unban an ip
    /unbanip <ip>
    """

    protocol = connection.protocol

    if ip in protocol.bans:
        protocol.remove_ban(ip)
        return "{} unbanned".format(ip)
    else:
        return "{} is not banned".format(ip)

@command()
def status(connection, nickname = None):
    """
    Print ban expiry date
    /status [player]
    """

    protocol = connection.protocol

    if nickname is not None:
        player = get_player(protocol, nickname)
    elif isinstance(connection, ServerConnection):
        player = connection
    else:
        return "Usage: /status [player]"

    ip = player.address[0]
    if ip in protocol.bans:
        name, reason, timestamp = protocol.bans[ip]
        reason = reason or ""

        if timestamp < time():
            protocol.remove_ban(ip)
            return f"Ban expired{reason}"
        elif timestamp is not None:
            expires = strftime("%b %d, %Y %H:%M:%S", gmtime(timestamp))
            return f"Banned until {expires}{reason}"
        else:
            return f"Permabanned{reason}"
    else:
        return "Not banned"

def apply_script(protocol, connection, config):
    extensions = [(EXTENSION_KICKREASON, 1)]

    class JailbanProtocol(protocol):
        def __init__(self, *w, **kw):
            protocol.__init__(self, *w, **kw)

            self.available_proto_extensions.extend(extensions)

        def save_bans(self):
            protocol.save_bans(self)

            for player in self.players.values():
                player.banned = player.address[0] in self.bans

    assert connection.on_connect is FeatureConnection.on_connect, (
        "“jailban” script is expected to be loaded before any other script that modifies `connection.on_connect`"
    )

    class JailbanConnection(connection):
        command_whitelist = {
            "status",
            "admin",
            "ping",
        }

        def __init__(self, *w, **kw):
            self.banned = False

            connection.__init__(self, *w, **kw)

        def on_connect(self):
            ServerConnection.on_connect(self)

            self.banned = self.address[0] in self.protocol.bans

        def on_command(self, command, parameters):
            if self.banned and command not in self.command_whitelist:
                if self.protocol.command_antispam:
                    self.command_limiter.record_event(monotonic())

                if not self.command_limiter.above_limit():
                    self.send_chat("Use /status to check your ban expiry date")

                return

            connection.on_command(self, command, parameters)

        def on_flag_take(self):
            if self.banned: return False

            return connection.on_flag_take(self)

        def ban(self, reason = None, duration = None):
            self.drop_flag()

            connection.ban(self, reason, duration)

        def kick(self, reason = None, silent = False):
            if silent:
                return # only `FeatureProtocol.add_ban` uses this
            else:
                message = "{} was kicked: {}".format(self.name, reason) if reason is not None else \
                          "{} was kicked".format(self.name)

                self.protocol.broadcast_chat(message, irc = True)

                if EXTENSION_KICKREASON in self.proto_extensions and reason is not None:
                    contained           = loaders.ChatMessage()
                    contained.player_id = 255
                    contained.chat_type = CHAT_SYSTEM
                    contained.value     = reason

                    self.send_contained(contained)

                self.peer.disconnect_later(ERROR_KICKED)

        def loader_received(self, loader):
            if self.banned and loader.dataLength > 0:
                if loader.data[0] in prohibited:
                    return

            return connection.loader_received(self, loader)

    return JailbanProtocol, JailbanConnection