from time import strftime, gmtime, time, monotonic
from twisted.internet import reactor

from piqueserver.commands import command, get_player

from pyspades.constants import ERROR_UNDEFINED, ERROR_BANNED
from pyspades.player import ServerConnection
from pyspades import contained as loaders

prohibited = {
    loaders.WeaponInput.id,
    loaders.HitPacket.id,
    loaders.GrenadePacket.id,
    loaders.BlockAction.id,
    loaders.BlockLine.id
}

whitelist = {
    "status",
    "admin",
    "ping",
}

@command(admin_only = True)
def disconnect(conn, nickname):
    get_player(conn.protocol, nickname).disconnect(ERROR_UNDEFINED)

@command(admin_only = True)
def hardban(conn, nickname):
    protocol = conn.protocol

    player = get_player(protocol, nickname)
    protocol.broadcast_chat(f'{conn.name} was hardbanned.')

    protocol.hard_bans.add(player.address[0])
    player.disconnect(ERROR_BANNED)

@command()
def status(conn, nickname = None):
    protocol = conn.protocol

    player = get_player(protocol, nickname) if nickname is not None else conn

    ip = player.address[0]
    if ip in protocol.bans:
        name, reason, timestamp = protocol.bans[ip]

        if timestamp < time():
            protocol.remove_ban(ip)
            return f"Ban expired{reason}"
        else:
            if timestamp is not None:
                expires = strftime("%b %d, %Y %H:%M:%S", gmtime(timestamp))
                return f"Banned until {expires}{reason}"
            else:
                return f"Permabanned{reason}"
    else:
        return "Not banned"

def apply_script(protocol, connection, config):
    class JailbanProtocol(protocol):
        def save_bans(self):
            protocol.save_bans(self)

            for player in self.players.values():
                player.banned = player.address[0] in self.bans

    class JailbanConnection(connection):
        def __init__(self, *w, **kw):
            self.banned = False

            return connection.__init__(self, *w, **kw)

        def on_connect(self):
            ServerConnection.on_connect(self)
            self.banned = self.address[0] in self.protocol.bans

        def on_command(self, command, parameters):
            if self.banned and command not in whitelist:
                if self.protocol.command_antispam:
                    self.command_limiter.record_event(monotonic())

                if not self.command_limiter.above_limit():
                    self.send_chat("Use /status to check your ban expiry date.")

                return

            return connection.on_command(self, command, parameters)

        def kick(self, reason = None, silent = False):
            if silent:
                return # only `FeatureProtocol.add_ban` uses this
            else:
                return connection.kick(self, reason, silent)

        def loader_received(self, loader):
            if self.banned and loader.dataLength > 0:
                if loader.data[0] in prohibited:
                    return

            return connection.loader_received(self, loader)

    return JailbanProtocol, JailbanConnection