from piqueserver.commands import command, join_arguments
from piqueserver.config import config

from random import randint
from time import time
from math import inf

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