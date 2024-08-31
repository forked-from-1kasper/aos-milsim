from itertools import product
from random import randint
from time import time
from math import inf

from piqueserver.commands import command, player_only, join_arguments
from piqueserver.config import config

from pyspades import contained as loaders
from pyspades.constants import *

def edge(a, b):
    return range(min(a, b), max(a, b) + 1)

def cube(u, v):
    x1, y1, z1 = u
    x2, y2, z2 = v

    return product(edge(x1, x2), edge(y1, y2), edge(z1, z2))

def cast_ray(conn, limit = 128):
    if o := conn.world_object:
        return o.cast_ray(limit)

@command('cast', admin_only = True)
@player_only
def cast(conn):
    """
    Prints the coordinates of the block under sight
    /cast
    """
    if loc := cast_ray(conn):
        return f"{loc}"

@command('/pos1', admin_only = True)
@player_only
def pos1(conn):
    """
    Selects the first block
    //pos1
    """
    if loc := cast_ray(conn):
        conn.pos1 = loc
        return "First position set to {}".format(loc)

@command('/pos2', admin_only = True)
@player_only
def pos2(conn):
    """
    Selects the second block
    //pos2
    """
    if loc := cast_ray(conn):
        conn.pos2 = loc
        return "Second position set to {}".format(loc)

@command('/sel', admin_only = True)
@player_only
def sel(conn):
    """
    Prints the coordinates of the selected blocks
    //sel
    """
    if conn.pos1 and conn.pos2:
        return "{} -> {}".format(conn.pos1, conn.pos2)
    else:
        return "No active selection."

def blockAction(conn, value, pos1, pos2):
    contained           = loaders.BlockAction()
    contained.player_id = conn.player_id
    contained.value     = value

    N = 0

    for x, y, z in cube(pos1, pos2):
        contained.x = x
        contained.y = y
        contained.z = z

        if value == DESTROY_BLOCK:
            if conn.protocol.map.destroy_point(x, y, z):
                conn.protocol.broadcast_contained(contained)
                conn.on_block_removed(x, y, z)

                N += 1

        if value == BUILD_BLOCK:
            conn.protocol.map.set_point(x, y, z, conn.color)
            conn.protocol.broadcast_contained(contained)
            conn.on_block_build(x, y, z)

            N += 1

    return "Set {} blocks.".format(N)

@command('/set', admin_only = True)
@player_only
def set_block(conn, action = "1"):
    """
    Destroys or builds in the selected region
    //set (0|1)
    """
    if not (conn.pos1 and conn.pos2): return

    value = DESTROY_BLOCK if action == "0" else BUILD_BLOCK
    return blockAction(conn, value, conn.pos1, conn.pos2)

@command(admin_only = True)
@player_only
def elevate(conn):
    """
    Teleports to the maximum available height
    /elevate
    """
    if not conn.hp: return

    x, y, _ = conn.world_object.position.get()
    z = conn.protocol.map.get_z(x, y) - 3

    conn.set_location_safe((x, y, z))

@command(admin_only = True)
@player_only
def get_z(conn):
    """
    Returns the Z-coordinate of the first block underfoot
    /get_z
    """
    x, y, _ = conn.world_object.position.get()
    return f"z = {conn.protocol.map.get_z(x, y)}"

@command()
@player_only
def printcolor(conn):
    """
    Print the selected color
    /printcolor
    """

    if conn.color is not None:
        r, g, b = conn.color
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
def stress(conn, pid = None, length = None):
    """
    Sends random data with a given packet id.
    /stress [packet id] [packet length]
    """

    try:
        if pid is not None:
            pid = int(pid)
    except ValueError:
        return "Packet id expected to be an integer."

    try:
        if length is not None:
            length = int(length)

            if length < 0:
                raise ValueError
    except ValueError:
        return "Packet length expected to be a positive integer."

    conn.send_contained(StressPacket(pid, length))

discord     = config.section("discord")
invite      = discord.option("invite", "<no invite>").get()
description = discord.option("description", "Discord").get()

@command()
def discord(conn):
    """
    Print the information about server's discord.
    /discord
    """

    return "%s: %s" % (description, invite)

mailbox   = config.section("mailbox")
mailfile  = mailbox.option("file", "mailbox.txt").get()
maildelay = mailbox.option("delay", 90).get()

@command('mail', 'admin')
@player_only
def mail(conn, *w):
    """
    Leaves a message to the server administrator
    /mail <your message>
    """

    message = join_arguments(w)

    if not message:
        return "Do not send empty messages (admins can see your IP)."

    ip, port = conn.address

    timestamp = time()

    dt = timestamp - conn.lastmail
    if dt < maildelay:
        return "Do not write too often: wait %.1f seconds." % (maildelay - dt)

    with open(mailfile, 'a') as fout:
        fout.write("%.2f: %s (%s): %s\n" % (timestamp, conn.name, ip, message))
        conn.lastmail = timestamp
        return "Message sent."

@command('eval', admin_only = True)
def c_eval(conn, *w):
    """
    Evaluates arbitrary Python code
    /eval <code>
    """

    return str(eval(' '.join(w), globals(), locals()))

def apply_script(protocol, connection, config):
    class ToolboxConnection(connection):
        def on_connect(self):
            self.chat_limiter._seconds = 1
            self.lastmail = -inf

            connection.on_connect(self)

    return protocol, ToolboxConnection