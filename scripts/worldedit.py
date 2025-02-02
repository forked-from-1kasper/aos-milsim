from itertools import product

from piqueserver.commands import command, player_only

from pyspades.constants import BUILD_BLOCK, DESTROY_BLOCK
from pyspades.common import get_color, make_color
from pyspades import contained as loaders

def irange(a, b):
    return range(min(a, b), max(a, b) + 1)

def icube(u, v):
    x1, y1, z1 = u
    x2, y2, z2 = v

    return product(irange(x1, x2), irange(y1, y2), irange(z1, z2))

def cast_ray(connection, limit = 128):
    if o := connection.world_object:
        return o.cast_ray(limit)

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

        connection.set_location((x, y, z))

@command(admin_only = True)
@player_only
def elevation(connection):
    """
    Return the Z-coordinate of the first block underfoot
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

def apply_script(protocol, connection, config):
    connection.pos1 = None
    connection.pos2 = None

    return protocol, connection
