from piqueserver.commands import command, join_arguments
from piqueserver.config import config

from pyspades import contained as loaders
from pyspades.constants import *

from itertools import product
from random import randint
from time import time
from math import inf

def edge(a, b):
    return range(min(a, b), max(a, b) + 1)

def cube(u, v):
    x1, y1, z1 = u
    x2, y2, z2 = v

    return product(edge(x1, x2), edge(y1, y2), edge(z1, z2))

def cast_ray(conn):
    if not conn.world_object: return
    return conn.world_object.cast_ray(128)

@command('/pos1', admin_only=True)
def pos1(conn, *args):
    if loc := cast_ray(conn):
        conn.pos1 = loc
        return "First position set to {}".format(loc)

@command('/pos2', admin_only=True)
def pos2(conn, *args):
    if loc := cast_ray(conn):
        conn.pos2 = loc
        return "Second position set to {}".format(loc)

@command('/sel', admin_only=True)
def sel(conn, *args):
    if conn.pos1 and conn.pos2:
        return "{} -> {}".format(conn.pos1, conn.pos2)
    else:
        return "No active selection."

def blockAction(conn, value, pos1, pos2):
    contained           = loaders.BlockAction()
    contained.player_id = conn.player_id
    contained.value     = value

    N = 0

    for (x, y, z) in cube(pos1, pos2):
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

@command('/set', admin_only=True)
def set(conn, *args):
    if not (conn.pos1 and conn.pos2): return

    value = DESTROY_BLOCK if len(args) >= 1 and args[0] == "0" else BUILD_BLOCK
    return blockAction(conn, value, conn.pos1, conn.pos2)

@command(admin_only=True)
def elevate(conn, *args):
    if not conn.hp: return

    x, y, _ = conn.world_object.position.get()
    z = conn.protocol.map.get_z(x, y) - 3

    conn.set_location_safe((x, y, z))

@command('position', 'pos')
def position(conn, *args):
    return str(conn.world_object.position)

@command()
def printcolor(conn, *args):
    if conn.color is not None:
        r, g, b = conn.color
        return f"#{r:02x}{g:02x}{b:02x}"

def randbyte():
    return randint(0, 255)

class StressPacket:
    def __init__(self, id = None):
        self.id = id

    def write(self, writer):
        if self.id is not None:
            writer.writeByte(self.id, True)
        else:
            writer.writeByte(randbyte(), False)

        for i in range(randint(0, 4096)):
            writer.writeByte(randbyte(), False)

@command()
def stress(conn, *args):
    if len(args) > 0:
        id, *rest = args

        try:
            id = int(id)
        except ValueError:
            return "Usage: /stress [packet id]"

        conn.send_contained(StressPacket(id))
    else:
        conn.send_contained(StressPacket())

discord     = config.section("discord")
invite      = discord.option("invite", "<no invite>").get()
description = discord.option("description", "Discord").get()

@command()
def discord(conn, *args):
    return "%s: %s" % (description, invite)

mailbox   = config.section("mailbox")
mailfile  = mailbox.option("file", "mailbox.txt").get()
maildelay = mailbox.option("delay", 90).get()

@command()
def mail(conn, *args):
    message = join_arguments(args)

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

def apply_script(protocol, connection, config):
    class ToolboxConnection(connection):
        def on_connect(self):
            self.pos1 = None
            self.pos2 = None

            self.lastmail = -inf

            self.chat_limiter._seconds = 0
            return connection.on_connect(self)

        def on_flag_take(self):
            flag = self.team.other.flag

            if self.world_object.position.z >= flag.z:
                return False

            if not self.world_object.can_see(flag.x, flag.y, flag.z - 0.5):
                return False

            return connection.on_flag_take(self)

    return protocol, ToolboxConnection