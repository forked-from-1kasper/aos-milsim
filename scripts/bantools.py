from time import strftime, gmtime, time, monotonic

from twisted.internet import reactor
from twisted.logger import Logger

from piqueserver.commands import _alias_map, command, player_only, get_player
from piqueserver.player import FeatureConnection
from piqueserver.server import FeatureProtocol

from pyspades.player import ServerConnection, parse_command
from pyspades.packet import register_packet_handler
from pyspades.common import escape_control_codes
from pyspades import contained as loaders
from pyspades.constants import *

prohibited = {
    loaders.WeaponInput.id,
    loaders.HitPacket.id,
    loaders.GrenadePacket.id,
    loaders.BlockAction.id,
    loaders.BlockLine.id
}

log = Logger()

@command()
def say(connection, *w):
    """
    Say something in chat
    /say <text>
    """

    protocol = connection.protocol

    value = ' '.join(w)

    if isinstance(connection, protocol.connection_class):
        connection.broadcast_chat(value)
    else:
        contained           = loaders.ChatMessage()
        contained.chat_type = CHAT_SYSTEM
        contained.value     = value

        protocol.broadcast_contained(contained)

@command('pm', 'priv', 'privmsg')
def c_privmsg(connection, nickname, *w):
    """
    Send a private message to a given player
    /pm <player> <message>
    """

    protocol = connection.protocol

    player = get_player(connection.protocol, nickname)

    value = ' '.join(w)

    if len(value) <= 0: return "Message not specified"

    if isinstance(connection, protocol.connection_class):
        connection.send_chat(
            "YOU -> {} (PRIVATE): {}".format(player.name, value)
        )

        if connection.address[0] in player.ignore_list:
            return

    player.send_chat(
        "{} -> YOU (PRIVATE): {}".format(connection.name, value)
    )

@command('togglelimbo', 'tli')
@player_only
def c_togglelimbo(connection):
    """
    Toggle receiving messages from players in limbo
    /togglelimbo
    """

    connection.ignore_limbo = not connection.ignore_limbo

    if connection.ignore_limbo:
        return "You are no longer receiving messages from limbo"
    else:
        return "You are receiving messages from limbo again"

@command('ignore', 'ign')
@player_only
def c_ignore(connection, nickname):
    """
    Ignore player
    /ignore <player>
    """

    player = get_player(connection.protocol, nickname)
    ip, port = player.address

    if ip in connection.ignore_list:
        return "You are already ignoring {}".format(player.name)
    else:
        connection.ignore_list.add(ip)
        return "You are now ignoring {}".format(player.name)

@command('unignore', 'uni')
@player_only
def c_unignore(connection, nickname):
    """
    Stop ignoring the given player
    /unignore <player>
    """

    player = get_player(connection.protocol, nickname)
    ip, port = player.address

    if ip in connection.ignore_list:
        connection.ignore_list.remove(ip)
        return "You are no longer ignoring {}".format(player.name)
    else:
        return "You are not ignoring {}".format(player.name)

@command('listroles', 'roles', 'lsr')
def c_roles(connection, nickname):
    """
    List roles of the given player
    /listroles <player>
    """

    player = get_player(connection.protocol, nickname)

    if bool(player.user_types):
        return "{}: {}".format(
            player.name, ", ".join(player.user_types)
        )
    else:
        return "{} has no roles".format(player.name)

@command()
def status(connection, nickname = None):
    """
    Print ban expiry date
    /status [player]
    """

    protocol = connection.protocol

    if nickname is not None:
        player = get_player(protocol, nickname)
    elif isinstance(connection, protocol.connection_class):
        player = connection
    else:
        return "Usage: /status [player]"

    ip = player.address[0]
    if ip in protocol.bans:
        name, reason, timestamp = protocol.bans[ip]
        reason = reason or ""

        if timestamp < time():
            protocol.remove_ban(ip)
            return "Ban expired{}".format(reason)
        elif timestamp is not None:
            expires = strftime("%b %d, %Y %H:%M:%S", gmtime(timestamp))
            return "Banned until {}{}".format(expires, reason)
        else:
            return "Permabanned{}".format(reason)
    else:
        return "{} is not banned".format(player.name)

message_maximum_length = 108

message_translation_table = {
    0x00 : '␀', 0x01 : '␁', 0x02 : '␂', 0x03 : '␃',
    0x04 : '␄', 0x05 : '␅', 0x06 : '␆', 0x07 : '␇',
    0x08 : '␈', 0x09 : '␉', 0x0A : ' ', 0x0B : '␋',
    0x0C : '␌', 0x0D : ' ', 0x0E : '␎', 0x0F : '␏',
    0x10 : '␐', 0x11 : '␑', 0x12 : '␒', 0x13 : '␓',
    0x14 : '␔', 0x15 : '␕', 0x16 : '␖', 0x17 : '␗',
    0x18 : '␘', 0x19 : '␙', 0x1A : '␚', 0x1B : '␛',
    0x1C : '␜', 0x1D : '␝', 0x1E : '␞', 0x1F : '␟',
    0x7F : '␡'
}

def sanitize_message(text):
    return text.translate(message_translation_table)[:message_maximum_length]

def apply_script(protocol, connection, config):
    extensions = [(EXTENSION_KICKREASON, 1)]

    assert protocol.broadcast_chat is FeatureProtocol.broadcast_chat, (
        "“bantools” script is expected to be loaded before any other script that modifies `protocol.broadcast_chat`"
    )

    class BantoolsProtocol(protocol):
        def __init__(self, *w, **kw):
            protocol.__init__(self, *w, **kw)

            self.available_proto_extensions.extend(extensions)

        def save_bans(self):
            protocol.save_bans(self)

            for player in self.connections.values():
                player.banned = player.address[0] in self.bans

        def broadcast_chat(self, value, global_message = True, sender = None, team = None, irc = False):
            if irc: self.irc_say("* {}".format(value))

            for player in self.connections.values():
                if player is sender:
                    continue

                if player.deaf:
                    continue

                if team is not None and player.team is not team:
                    continue

                player.send_chat(value, global_message)

    assert connection.on_connect is FeatureConnection.on_connect, (
        "“bantools” script is expected to be loaded before any other script that modifies `connection.on_connect`"
    )

    class BantoolsConnection(connection):
        command_whitelist = {
            "status",
            "admin",
            "ping",
            "pm"
        }

        def __init__(self, *w, **kw):
            self.banned = False

            self.ignore_list  = set()
            self.ignore_limbo = False

            connection.__init__(self, *w, **kw)

        def on_connect(self):
            ServerConnection.on_connect(self)

            self.banned = self.address[0] in self.protocol.bans

        def on_command(self, command, parameters):
            if self.banned and _alias_map.get(command, command) not in self.command_whitelist:
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

        def broadcast_chat(self, value, team = None):
            contained           = loaders.ChatMessage()
            contained.player_id = self.player_id
            contained.chat_type = CHAT_ALL if team is None else CHAT_TEAM
            contained.value     = value

            ip, port = self.address

            for player in self.protocol.connections.values():
                if player.player_id is None:
                    continue

                if player.deaf:
                    continue

                if ip in player.ignore_list:
                    continue

                if team is None or team is player.team:
                    player.send_contained(contained)

        @register_packet_handler(loaders.ChatMessage)
        def on_chat_message_recieved(self, contained):
            value = sanitize_message(contained.value)

            if message_maximum_length < len(contained.value):
                log.info(
                    "TOO LONG MESSAGE ({chars} chars) FROM {name} (#{id})",
                    chars = len(contained.value),
                    name  = self.name or "Anonymous",
                    id    = self.player_id
                )

            if value.startswith('/'):
                self.on_command(*parse_command(value[1:]))

            elif self.name is None:
                contained           = loaders.ChatMessage()
                contained.chat_type = CHAT_SYSTEM
                contained.value     = "Anonymous: {}".format(value)

                for player in self.protocol.connections.values():
                    if player.player_id is None:
                        continue

                    if player.deaf:
                        continue

                    if player.ignore_limbo:
                        continue

                    player.send_contained(contained)

                log.info("{{Anonymous}} {value}", value = escape_control_codes(value))

            else:
                is_global_message = contained.chat_type == CHAT_ALL

                retval = self.on_chat(value, is_global_message)
                if retval == False:
                    return
                elif retval is not None:
                    value = retval

                self.broadcast_chat(value, team = None if is_global_message else self.team)
                self.on_chat_sent(value, is_global_message)

    return BantoolsProtocol, BantoolsConnection