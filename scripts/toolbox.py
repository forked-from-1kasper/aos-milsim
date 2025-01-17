from random import randint
from time import time
from math import inf

from piqueserver.commands import command, player_only, join_arguments
from piqueserver.config import config

from pyspades import contained as loaders
from pyspades.constants import *

def randbyte():
    return randint(0, 255)

class StressPacket:
    def __init__(self, pid = None, length = None):
        self.id     = randint(0, 60) if pid is None else pid
        self.length = randint(0, 4096) if length is None else length

    def write(self, writer):
        writer.writeByte(self.id, True)

        for i in range(self.length):
            writer.writeByte(randbyte(), False)

@command()
@player_only
def stress(connection, pid = None, length = None):
    """
    Send random data with a given packet id
    /stress [packet id] [packet length]
    """

    try:
        if pid is not None:
            pid = int(pid)
    except ValueError:
        return "Packet id expected to be an integer"

    try:
        if length is not None:
            length = int(length)

            if length < 0:
                raise ValueError
    except ValueError:
        return "Packet length expected to be a positive integer"

    connection.send_contained(StressPacket(pid, length))

discord     = config.section("discord")
invite      = discord.option("invite", "<no invite>").get()
description = discord.option("description", "Discord").get()

@command()
def discord(connection):
    """
    Information on where to find administrators in Discord
    /discord
    """

    return "{}: {}".format(description, invite)

mailbox   = config.section("mailbox")
mailfile  = mailbox.option("file", "mailbox.txt").get()
maildelay = mailbox.option("delay", 90).get()

@command('mail', 'admin')
@player_only
def mail(connection, *w):
    """
    Leave a message to the server administrator even if he is offline
    /mail <your message>
    """

    message = join_arguments(w).strip()

    if len(message) <= 0:
        return "Do not send empty messages (admins can see your IP)"

    ip, port = connection.address

    timestamp = time()

    dt = timestamp - getattr(connection, 'lastmail', -inf)

    if dt < maildelay:
        return "Do not write too often: wait {:.1f} seconds".format(maildelay - dt)

    with open(mailfile, 'a') as fout:
        fmtd = "{timestamp:.2f}: {nickname} ({ip}): {message}\n".format(
            timestamp = timestamp,
            nickname  = connection.name,
            ip        = ip,
            message   = message
        )

        fout.write(fmtd)
        connection.lastmail = timestamp

        return "Message sent"

@command('eval', admin_only = True)
def c_eval(connection, *w):
    """
    Evaluate arbitrary Python code
    /eval <code>
    """

    try:
        return str(connection.eval(' '.join(w)))
    except Exception as exc:
        return connection.protocol.format_exception(exc)

@command('exec', admin_only = True)
def c_exec(connection, *w):
    """
    Execute arbitrary Python code
    /exec <code>
    """

    try:
        connection.exec(' '.join(w))
    except Exception as exc:
        return connection.protocol.format_exception(exc)

from gc import collect
@command(admin_only = True)
def gc(connection):
    """
    Run the garbage collector
    /gc
    """

    return str(collect())

@command()
def say(connection, *w):
    """
    Say something in chat
    /say <text>
    """

    protocol = connection.protocol

    contained       = loaders.ChatMessage()
    contained.value = ' '.join(w)

    if isinstance(connection, protocol.connection_class):
        contained.player_id = connection.player_id
        contained.chat_type = CHAT_ALL
    else:
        contained.chat_type = CHAT_SYSTEM

    protocol.broadcast_contained(contained)

@command('showrotation', 'shr')
def show_rotation(connection, argval = None):
    """
    Scroll through the current map rotation
    /shr [page number | query] or /shr * or /showrotation
    """

    maps = connection.protocol.get_map_rotation()

    page_size = 5
    total = len(maps) // page_size + 1

    if argval == "*":
        return ", ".join(maps)

    npage = None

    if argval is None:
        npage = getattr(connection, 'show_rotation_page', 0)
    elif argval.isdigit():
        npage = max(1, min(total, int(argval))) - 1
    else:
        query = argval.lower()

        out = (i for i, map_name in enumerate(maps) if query in map_name.lower())

        if i := next(out, None):
            npage = i // page_size
        else:
            return "'{}' map not found".format(query)

    connection.show_rotation_page = (npage + 1) % total

    i1, i2 = npage * page_size, (npage + 1) * page_size
    return "{}/{}) {}".format(npage + 1, total, ", ".join(maps[i1 : i2]))

def apply_script(protocol, connection, config):
    from piqueserver.console import ConsoleInput

    class ToolboxConnection(connection):
        def __init__(self, *w, **kw):
            connection.__init__(self, *w, **kw)

            self.variables = dict(connection = self, protocol = self.protocol)

        def eval(self, expr):
            return eval(expr, globals(), self.variables)

        def exec(self, stmt):
            exec(stmt, globals(), self.variables)

        def on_connect(self):
            self.chat_limiter._seconds = 1

            connection.on_connect(self)

        def existing_player_sent(self):
            return self.name is not None and self.team is not None

        def on_login(self, name):
            self.protocol.update_master()

            connection.on_login(self, name)

        # TODO: this *should* be fixed in the piqueserver itself
        def on_reset(self):
            self.kills = 0

            connection.on_reset(self)

    class ToolboxProtocol(protocol):
        def __init__(self, *w, **kw):
            protocol.__init__(self, *w, **kw)

            ConsoleInput.variables = dict(connection = None, protocol = self)
            ConsoleInput.eval      = self.connection_class.eval
            ConsoleInput.exec      = self.connection_class.exec

        def format_exception(self, exc):
            return "{}: {}".format(type(exc).__name__, exc)

        def get_player_count(self):
            return sum(connection.existing_player_sent() for connection in self.connections.values())

    return ToolboxProtocol, ToolboxConnection