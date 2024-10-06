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

    class ToolboxProtocol(protocol):
        def __init__(self, *w, **kw):
            protocol.__init__(self, *w, **kw)

            ConsoleInput.variables = dict(connection = None, protocol = self)
            ConsoleInput.eval      = self.connection_class.eval
            ConsoleInput.exec      = self.connection_class.exec

        def format_exception(self, exc):
            return "{}: {}".format(type(exc).__name__, exc)

    return ToolboxProtocol, ToolboxConnection