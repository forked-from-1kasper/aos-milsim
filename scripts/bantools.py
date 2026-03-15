# Copyright © 2011–2012 Mathias Kaerlev
# Copyright © 2022–2024 DryByte
# Copyright © 2024–2026 rzrn

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

from time import strftime, gmtime, time, monotonic

from twisted.internet import reactor
from twisted.logger import Logger

from piqueserver.commands import CommandError, _alias_map, command, player_only, get_player
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
def kill(connection, value = None):
    """
    Kill yourself or a given player
    /kill [target]
    """

    protocol = connection.protocol

    player = connection if value is None else get_player(protocol, value)

    if player.name is None or player.world_object is None or player.team is None:
        return

    if player.hp is None or player.world_object.dead:
        return

    if player.team.spectator:
        return

    P = connection.rights.kill or connection.admin
    Q = player.banned
    R = player is connection

    if P or Q or R:
        player.kill()

        if player is connection:
            protocol.broadcast_chat("{} suicided".format(connection.name))
        else:
            protocol.broadcast_chat("{} killed {}".format(connection.name or "Anonymous", player.name))
    else:
        return "You can't kill {}".format(player.name)

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

@command('teamdup')
@player_only
def c_teamdup(connection):
    """
    Duplicate the last message sent in team chat to global chat
    /teamdup
    """

    if mesg := connection.last_teamchat_message:
        connection.broadcast_chat(mesg, is_global_message = True)
        connection.last_teamchat_message = None
    else:
        return "There's nothing to duplicate"

def get_connection(protocol, argval):
    if argval.startswith('#'):
        player_id = int(argval[1:])

        for connection in protocol.connections.values():
            if connection.player_id == player_id:
                return connection

        raise CommandError("Invalid Player")
    else:
        return get_player(protocol, argval)

def format_nickname(connection):
    return connection.name or "#{}".format(connection.player_id)

@command('pm', 'priv', 'privmsg', 'msg', 'w')
def c_privmsg(connection, argval, *w):
    """
    Send a private message to a given player
    /pm <player> <message>
    """

    protocol = connection.protocol

    player = get_connection(protocol, argval)

    value = ' '.join(w)

    if len(value) <= 0: return "Message not specified"

    if isinstance(connection, protocol.connection_class):
        connection.send_chat(
            "YOU -> {} (PRIVATE): {}".format(format_nickname(player), value)
        )

        if connection.address[0] in player.ignore_list:
            return

    player.send_chat(
        "{} -> YOU (PRIVATE): {}".format(format_nickname(connection), value)
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
def c_ignore(connection, argval):
    """
    Ignore player
    /ignore <player>
    """

    protocol = connection.protocol

    if isinstance(connection, protocol.connection_class) is False:
        return "Only players can use this command"

    player = get_connection(connection.protocol, argval)
    addr, port = player.address

    if addr in connection.ignore_list:
        return "You are already ignoring {}".format(format_nickname(player))
    else:
        connection.ignore_list.add(addr)
        return "You are now ignoring {}".format(format_nickname(player))

@command('unignore', 'uni')
def c_unignore(connection, argval):
    """
    Stop ignoring the given player
    /unignore <player>
    """

    protocol = connection.protocol

    if isinstance(connection, protocol.connection_class) is False:
        return "Only players can use this command"

    player = get_connection(protocol, argval)
    addr, port = player.address

    if addr in connection.ignore_list:
        connection.ignore_list.remove(addr)
        return "You are no longer ignoring {}".format(format_nickname(player))
    else:
        return "You are not ignoring {}".format(format_nickname(player))

@command()
def status(connection, nickname = None):
    """
    Print ban expiry date
    /status [player]
    """

    protocol = connection.protocol

    if nickname is not None:
        player = get_connection(protocol, nickname)
    elif isinstance(connection, protocol.connection_class):
        player = connection
    else:
        return "Usage: /status [player]"

    addr = player.address[0]
    if addr in protocol.bans:
        name, reason, timestamp = protocol.bans[addr]
        reason = reason or ""

        if timestamp < time():
            protocol.remove_ban(addr)
            return "Ban expired{}".format(reason)
        elif timestamp is not None:
            expires = strftime("%b %d, %Y %H:%M:%S", gmtime(timestamp))
            return "Banned until {}{}".format(expires, reason)
        else:
            return "Permabanned{}".format(reason)
    else:
        return "{} is not banned".format(format_nickname(player))

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
                past, pres = player.banned, player.address[0] in self.bans

                if past is True and pres is False: player.send_chat_error("You've been unbanned")
                if past is False and pres is True: player.send_chat_error("You've been banned")

                player.banned = pres

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

            self.last_teamchat_message = None

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

            contained           = loaders.WeaponInput()
            contained.primary   = False
            contained.secondary = False
            contained.player_id = self.player_id

            self.protocol.broadcast_contained(contained, sender = self, save = True)

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

        def on_chat_delivered(self, player, value, is_global_message):
            addr, port = player.address
            if addr in self.ignore_list:
                return False

            if player.name is None and self.ignore_limbo:
                return False

            return connection.on_chat_delivered(self, player, value, is_global_message)

        def broadcast_chat(self, value, is_global_message = True):
            contained           = loaders.ChatMessage()
            contained.player_id = self.player_id
            contained.chat_type = CHAT_ALL if is_global_message else CHAT_TEAM
            contained.value     = value

            addr, port = self.address

            for player in self.protocol.connections.values():
                if player.player_id is None:
                    continue

                if player.on_chat_delivered(self, value, is_global_message) is False:
                    continue

                player.send_contained(contained)

        @register_packet_handler(loaders.ChatMessage)
        def on_chat_message_recieved(self, contained):
            value = sanitize_message(contained.value)

            is_global_message = contained.chat_type == CHAT_ALL
            team = None if is_global_message else self.team

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

                addr, port = self.address

                for player in self.protocol.connections.values():
                    if player.player_id is None:
                        continue

                    if player.on_chat_delivered(self, value, is_global_message) is False:
                        continue

                    player.send_contained(contained)

                log.info("{{Anonymous}} {value}", value = escape_control_codes(value))

            else:
                retval = self.on_chat(value, is_global_message)

                if retval is False:
                    return
                elif retval is not None:
                    value = retval

                self.broadcast_chat(value, is_global_message)
                self.on_chat_sent(value, is_global_message)

                self.last_teamchat_message = None if is_global_message else value

    return BantoolsProtocol, BantoolsConnection
