from piqueserver.commands import command

from milsim.connection import MilsimConnection
from milsim.protocol import MilsimProtocol
from milsim.map import check_map

@command()
def seed(connection):
    """
    Return the map's seed
    /seed
    """
    return str(connection.protocol.map_info.seed)

@command('map', admin_only = True)
def change_planned_map(connection, map_name):
    """
    Set the next map to be loaded after current game ends and inform everyone of it
    /map <mapname>
    """
    nickname = connection.name
    protocol = connection.protocol

    if rot_info := check_map(map_name, protocol.map_dir):
        protocol.planned_map = rot_info
        protocol.broadcast_chat(
            '{} changed next map to {}'.format(nickname, map_name),
            irc = True
        )
    else:
        return 'Map {} not found'.format(map_name)

@command('loadmap', admin_only = True)
def load_map(connection, map_name):
    """
    Instantly switches map to the specified
    /loadmap <mapname>
    """
    protocol = connection.protocol

    if rot_info := check_map(map_name, protocol.map_dir):
        protocol.planned_map = rot_info
        protocol.advance_rotation()
    else:
        return 'Map {} not found'.format(map_name)

def apply_script(protocol, connection, config):
    return MilsimProtocol, MilsimConnection
