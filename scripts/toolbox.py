from itertools import product
from random import randint
from time import time
from math import inf

from piqueserver.commands import command, player_only, join_arguments
from piqueserver.config import config

from pyspades.common import get_color, make_color
from pyspades import contained as loaders
from pyspades.constants import *

def irange(a, b):
    return range(min(a, b), max(a, b) + 1)

def icube(u, v):
    x1, y1, z1 = u
    x2, y2, z2 = v

    return product(irange(x1, x2), irange(y1, y2), irange(z1, z2))

def cast_ray(connection, limit = 128):
    if o := connection.world_object:
        return o.cast_ray(limit)

@command('cast', admin_only = True)
@player_only
def cast(connection):
    """
    Prints the coordinates of the block under sight
    /cast
    """
    if loc := cast_ray(connection):
        return f"{loc}"

@command('/pos1', admin_only = True)
@player_only
def pos1(connection):
    """
    Selects the first block
    //pos1
    """
    if loc := cast_ray(connection):
        connection.pos1 = loc
        return "First position set to {}".format(loc)

@command('/pos2', admin_only = True)
@player_only
def pos2(connection):
    """
    Selects the second block
    //pos2
    """
    if loc := cast_ray(connection):
        connection.pos2 = loc
        return "Second position set to {}".format(loc)

@command('/sel', admin_only = True)
@player_only
def sel(connection):
    """
    Prints the coordinates of the selected blocks
    //sel
    """
    if connection.pos1 and connection.pos2:
        return "{} -> {}".format(connection.pos1, connection.pos2)
    else:
        return "No active selection"

def newSetColor(player_id, color):
    contained           = loaders.SetColor()
    contained.player_id = player_id
    contained.value     = make_color(*color)

    return contained

def sendBuildBlock(connection, color, region):
    protocol = connection.protocol
    M = protocol.map

    protocol.broadcast_contained(newSetColor(connection.player_id, color))

    contained           = loaders.BlockAction()
    contained.player_id = connection.player_id
    contained.value     = BUILD_BLOCK

    N = 0

    for x, y, z in region:
        contained.x = x
        contained.y = y
        contained.z = z

        protocol.broadcast_contained(contained)

        M.set_point(x, y, z, color)
        connection.on_block_build(x, y, z)

        N += 1

    protocol.broadcast_contained(newSetColor(connection.player_id, connection.color))

    return N

def sendDestroyBlock(connection, region):
    protocol = connection.protocol
    M = protocol.map

    contained           = loaders.BlockAction()
    contained.player_id = connection.player_id
    contained.value     = DESTROY_BLOCK

    N = 0

    for x, y, z in region:
        contained.x = x
        contained.y = y
        contained.z = z

        protocol.broadcast_contained(contained)

        M.destroy_point(x, y, z)
        connection.on_block_removed(x, y, z)

        N += 1

    return N

@command('/set', admin_only = True)
@player_only
def set_block(connection, argval = None):
    """
    Fill the selected region with the given color
    //set or //set RRGGBB
    """
    if argval is None:
        color = connection.color
    else:
        color = get_color(int(argval, 16))

    if connection.pos1 and connection.pos2:
        N = sendBuildBlock(connection, color, icube(connection.pos1, connection.pos2))
        return "Set {} block(s)".format(N)

@command('/del', admin_only = True)
@player_only
def del_block(connection):
    """
    Destroy selected region
    //del
    """

    if connection.pos1 and connection.pos2:
        N = sendDestroyBlock(connection, icube(connection.pos1, connection.pos2))
        return "Removed {} block(s)".format(N)

@command(admin_only = True)
@player_only
def elevate(connection):
    """
    Teleport to the maximum available height
    /elevate
    """
    if wo := connection.world_object:
        x, y, _ = connection.world_object.position.get()
        z = connection.protocol.map.get_z(x, y) - 3

        connection.set_location_safe((x, y, z))

@command(admin_only = True)
@player_only
def elevation(connection):
    """
    Returns the Z-coordinate of the first block underfoot
    /elevation
    """
    if wo := connection.world_object:
        x, y, z = wo.position.get()
        return f"z = {connection.protocol.map.get_z(x, y)}"

@command()
@player_only
def printcolor(connection):
    """
    Print the selected color
    /printcolor
    """

    if connection.color is not None:
        r, g, b = connection.color
        return f"#{r:02x}{g:02x}{b:02x}"

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
    Sends random data with a given packet id
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
    Print the information about server's discord
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
    Leaves a message to the server administrator
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
    Evaluates arbitrary Python code
    /eval <code>
    """

    try:
        return str(connection.eval(' '.join(w)))
    except Exception as exc:
        return connection.protocol.format_exception(exc)

@command('exec', admin_only = True)
def c_exec(connection, *w):
    """
    Executes arbitrary Python code
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

            self.pos1 = None
            self.pos2 = None

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