from horseradish.commands import command, player_only
from pyspades import contained as loaders

from pyspades.common import Vertex3

from pyspades.constants import *

class WorldUpdate256:
    def __init__(self, offset):
        self.offset = 0

    def write(self, writer):
        writer.writeUInt8LE(2)

        for i in range(128):
            writer.writeFloat32LE(126 + (i % 64) * 2.1 + self.offset)
            writer.writeFloat32LE(254 + i // 64)
            writer.writeFloat32LE(56)
            writer.writeFloat32LE(1)
            writer.writeFloat32LE(0)
            writer.writeFloat32LE(0)

class WorldUpdate076:
    def __init__(self, offset):
        self.offset = 0

    def write(self, writer):
        writer.writeUInt8LE(2)

        for i in range(1, 25):
            writer.writeUInt8LE(i)
            writer.writeFloat32LE(126 + (i % 64) * 2.1 + self.offset)
            writer.writeFloat32LE(254 + i // 64)
            writer.writeFloat32LE(56)
            writer.writeFloat32LE(1)
            writer.writeFloat32LE(0)
            writer.writeFloat32LE(0)

@command(admin_only = True)
def set_hp(connection, argval):
    contained          = loaders.SetHP()
    contained.hp       = int(argval)
    contained.not_fall = False

    connection.send_contained(contained)

@command(admin_only = True)
def test256(conn):
    for i in range(1, 128):
        name = 'Deuce%d' % i

        contained1 = loaders.ExistingPlayer()
        contained1.player_id = i
        contained1.name      = name
        conn.send_contained(contained1)

        contained2 = loaders.CreatePlayer()
        contained2.player_id = i
        contained2.name      = name
        conn.send_contained(contained2)

    conn.send_contained(WorldUpdate256(0))

    for i in range(1, 128):
        contained3 = loaders.InputData()
        contained3.player_id = i
        contained3.up        = 1
        contained3.down      = 0
        contained3.left      = 0
        contained3.right     = 0
        contained3.jump      = 0
        contained3.crouch    = 0
        contained3.sneak     = 0
        contained3.sprint    = 0
        conn.send_contained(contained3)
    return "OK"

@command(admin_only = True)
def test24(conn):
    for i in range(1, 25):
        name = 'Deuce%d' % i

        contained1 = loaders.ExistingPlayer()
        contained1.player_id = i
        contained1.name      = name
        conn.send_contained(contained1)

        contained2 = loaders.CreatePlayer()
        contained2.player_id = i
        contained2.name      = name
        conn.send_contained(contained2)

    conn.send_contained(WorldUpdate076(0))

    for i in range(1, 25):
        contained3 = loaders.InputData()
        contained3.player_id = i
        contained3.up        = 1
        contained3.down      = 0
        contained3.left      = 0
        contained3.right     = 0
        contained3.jump      = 0
        contained3.crouch    = 0
        contained3.sneak     = 0
        contained3.sprint    = 0
        conn.send_contained(contained3)

    return "OK"

@command(admin_only = True)
@player_only
def takeflag(conn):
    if conn.team is None or conn.team is conn.team.spectator:
        return

    conn.team.flag.player = conn

    contained1 = loaders.CreatePlayer()
    contained1.player_id = conn.player_id
    contained1.name = conn.name
    contained1.team = conn.team.other.id
    contained1.x = conn.world_object.position.x
    contained1.y = conn.world_object.position.y
    contained1.z = conn.world_object.position.z
    contained1.z = conn.weapon

    conn.protocol.broadcast_contained(contained1)

    contained2 = loaders.IntelPickup()
    contained2.player_id = conn.player_id

    conn.protocol.broadcast_contained(contained2)

    contained3 = loaders.CreatePlayer()
    contained3.player_id = conn.player_id
    contained3.name = conn.name
    contained3.team = conn.team.id
    contained3.x = conn.world_object.position.x
    contained3.y = conn.world_object.position.y
    contained3.z = conn.world_object.position.z
    contained3.z = conn.weapon

    conn.protocol.broadcast_contained(contained3)

    conn.world_object.set_orientation(1, 0, 0)

@command(admin_only = True)
@player_only
def dropflag(conn):
    if conn.team is None or conn.team is conn.team.spectator:
        return

    x, y, z = conn.protocol.map.get_safe_coords(*conn.world_object.position.get())
    z = conn.protocol.map.get_z(x, y, z)

    conn.team.flag.player = None
    conn.team.flag.set(x, y, z)

    contained1 = loaders.CreatePlayer()
    contained1.player_id = conn.player_id
    contained1.name = conn.name
    contained1.team = conn.team.other.id
    contained1.x = conn.world_object.position.x
    contained1.y = conn.world_object.position.y
    contained1.z = conn.world_object.position.z
    contained1.z = conn.weapon

    conn.protocol.broadcast_contained(contained1)

    contained2 = loaders.IntelDrop()
    contained2.player_id = conn.player_id
    contained2.x = x
    contained2.y = y
    contained2.z = z

    conn.protocol.broadcast_contained(contained2)

    contained3 = loaders.CreatePlayer()
    contained3.player_id = conn.player_id
    contained3.name = conn.name
    contained3.team = conn.team.id
    contained3.x = conn.world_object.position.x
    contained3.y = conn.world_object.position.y
    contained3.z = conn.world_object.position.z
    contained3.z = conn.weapon

    conn.protocol.broadcast_contained(contained3)

@command(admin_only = True)
@player_only
def testlongnade(conn):
    contained = loaders.GrenadePacket()
    contained.player_id = conn.player_id
    contained.value = 45
    contained.position = conn.world_object.position.get()
    contained.velocity = (0, 0, 0)

    conn.protocol.broadcast_contained(contained)

@command()
@player_only
def testerror(conn):
    contained = loaders.ChatMessage()
    contained.player_id = 35

    if EXTENSION_CHATTYPE in conn.proto_extensions:
        contained.chat_type = CHAT_ERROR
        contained.value     = "ERROR"
    else:
        contained.chat_type = CHAT_SYSTEM
        contained.value     = "!% ERROR"

    conn.protocol.broadcast_contained(contained)

@command()
@player_only
def testbeep(conn):
    contained = loaders.ChatMessage()
    contained.player_id = 35

    if EXTENSION_CHATTYPE in conn.proto_extensions:
        contained.chat_type = CHAT_ERROR
        contained.value     = ""
    else:
        contained.chat_type = CHAT_SYSTEM
        contained.value     = "!% "

    conn.protocol.broadcast_contained(contained)

@command(admin_only = True)
@player_only
def nickname(conn, nickname):
    conn.protocol.broadcast_chat("{} is now known as {}".format(conn.name, nickname))

    conn.name = nickname

    contained = loaders.CreatePlayer()
    contained.player_id = conn.player_id
    contained.name = conn.name
    contained.team = conn.team.id
    contained.x = conn.world_object.position.x
    contained.y = conn.world_object.position.y
    contained.z = conn.world_object.position.z
    contained.z = conn.weapon

    conn.protocol.broadcast_contained(contained)

@command(admin_only = True)
def go256(conn, val):
    offset = float(val)
    conn.send_contained(WorldUpdate256(offset))

from horseradish.commands import get_player

@command()
@player_only
def d_capture(player, argval):
    target = get_player(player.protocol, argval)

    contained           = loaders.IntelCapture()
    contained.player_id = target.player_id

    player.send_contained(contained)

@command(admin_only = True)
def kill1(connection, nickname):
    protocol = connection.protocol
    get_player(protocol, nickname).kill(by = connection)

@command(admin_only = True)
def block(connection, duration):
    from time import sleep

    duration = float(duration)
    sleep(duration)

    return "OK"

from pyspades.common import make_color
import asyncio

@command(admin_only = True)
def testblitz(connection):
    contained = loaders.FogColor()

    contained.color = make_color(255, 255, 255)
    connection.send_contained(contained)

    contained.color = make_color(*connection.protocol.fog_color)
    asyncio.get_running_loop().call_later(0.1, connection.send_contained, contained)

@command(admin_only = True)
def testpush(connection):
    connection.world_object.velocity.x += 10.0
    connection.protocol.update_network()

PACKET_EXT_BASE = 0x40

class PlayerPropertiesV1:
    ext_id = 0
    ext_version = 1
    id = PACKET_EXT_BASE + ext_id

    def __init__(self):
        self.player_id = None
        self.health = None
        self.blocks = None
        self.grenades = None
        self.ammo_clip = None
        self.ammo_reserved = None
        self.score = None

    def write(self, writer):
        writer.writeUInt8LE(self.id)
        writer.writeUInt8LE(0)
        writer.writeUInt8LE(self.player_id)
        writer.writeUInt8LE(self.health)
        writer.writeUInt8LE(self.blocks)
        writer.writeUInt8LE(self.grenades)
        writer.writeUInt8LE(self.ammo_clip)
        writer.writeUInt8LE(self.ammo_reserved)
        writer.writeUInt32LE(self.score)

@command(admin_only = True)
@player_only
def blocks256(connection):
    contained = PlayerPropertiesV1()

    contained.player_id = connection.player_id
    contained.health = connection.hp
    contained.blocks = 255
    contained.grenades = connection.grenades
    contained.ammo_clip = connection.weapon_object.magazine.current()
    contained.ammo_reserved = connection.weapon_object.reserved()
    contained.score = connection.kills

    connection.send_contained(contained)

def newSetColor(player_id, color):
    contained           = loaders.SetColor()
    contained.player_id = player_id
    contained.value     = color

    return contained

from pyspades.common import get_color

@command()
@player_only
def set_color(connection, argval):
    color = int(argval, base = 16)
    connection.color = get_color(color)
    connection.protocol.broadcast_contained(
        newSetColor(connection.player_id, color)
    )

from math import pi

from pyspades.constants import BUILD_BLOCK, DESTROY_BLOCK

@command(admin_only = True)
@player_only
def paint(connection):
    protocol = connection.protocol

    if wo := connection.world_object:
        if loc := wo.cast_ray(128):
            protocol.map.set_point(*loc, connection.color)

            contained = loaders.BlockAction()

            x, y, z = loc

            contained.x = x
            contained.y = y
            contained.z = z

            contained.player_id = connection.player_id

            contained.value = DESTROY_BLOCK
            protocol.broadcast_contained(contained, save = True)

            contained.value = BUILD_BLOCK
            protocol.broadcast_contained(contained, save = True)

def apply_script(protocol, connection, config):
    return protocol, connection
