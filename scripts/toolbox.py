from math import inf, fmod, tan, acos, pi, tau, degrees
from itertools import product
from random import randint
from time import time

from piqueserver.commands import command, join_arguments
from piqueserver.config import config

from pyspades.common import Vertex3
from pyspades import contained as loaders
from pyspades.constants import *

from milsim.common import dot, xOy, azimuth, needle
from milsim.simulator import toMeters

def edge(a, b):
    return range(min(a, b), max(a, b) + 1)

def cube(u, v):
    x1, y1, z1 = u
    x2, y2, z2 = v

    return product(edge(x1, x2), edge(y1, y2), edge(z1, z2))

def cast_ray(conn, limit = 128):
    if not conn.world_object: return None
    return conn.world_object.cast_ray(limit)

@command('cast', admin_only=True)
def cast(conn):
    if loc := cast_ray(conn):
        return f"{loc}"

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

@command(admin_only=True)
def get_z(conn):
    x, y, _ = conn.world_object.position.get()
    return f"z = {conn.protocol.map.get_z(x, y)}"

@command('position', 'pos')
def position(conn, *args):
    """
    Print the current position on the map
    /position
    """
    return str(conn.world_object.position)

@command()
def printcolor(conn, *args):
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
def mail(conn, *args):
    """
    Leaves a message to the server administrator
    /mail <your message>
    """

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

@command()
def rangefinder(conn):
    """
    Measures the distance between the player and a given point
    /rangefinder
    """

    error = 2.0

    if loc := cast_ray(conn, limit = 1024):
        # this number is a little wrong, but anyway we’ll truncate the result
        d = conn.world_object.position.distance(Vertex3(*loc))
        m = toMeters(d)
        M = m - fmod(m, error)

        if m < error:
            return "< %.0f m" % error
        else:
            return "%.0f m" % M
    else:
        return "Too far."

@command()
def protractor(conn):
    """
    Measures the angle between the player and two specified points
    /protractor
    """

    if conn.world_object is not None:
        if conn.protractor is None:
            conn.protractor = conn.world_object.orientation.normal().copy()
            return "Use /protractor again while facing the second point."
        else:
            t = dot(conn.world_object.orientation.normal(), conn.protractor)
            θ = degrees(acos(t))

            conn.protractor = None
            return "%.2f deg" % θ

@command()
def compass(conn):
    """
    Prints the current azimuth
    /compass
    """

    if conn.world_object is not None:
        o = xOy(conn.world_object.orientation)
        φ = azimuth(conn.protocol.environment, o)
        θ = degrees(φ)
        return "%.0f deg, %s" % (θ, needle(φ))

def apply_script(protocol, connection, config):
    class ToolboxConnection(connection):
        def __init__(self, *w, **kw):
            self.protractor = None
            return connection.__init__(self, *w, **kw)

        def on_connect(self):
            self.pos1 = None
            self.pos2 = None

            self.lastmail = -inf

            self.chat_limiter._seconds = 1
            return connection.on_connect(self)

    return protocol, ToolboxConnection