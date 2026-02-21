# Copyright © 2012 triplefox
# Copyright © 2017 Samuel Walladge
# Copyright © 2021 Jipok
# Copyright © 2024 rzrn

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

from piqueserver.commands import command

from milsimlib import MilsimProtocol, MilsimConnection
from milsimlib.map import check_map

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
def load_map(connection, map_name = None):
    """
    Instantly switches map to the specified
    /loadmap <mapname>
    """
    protocol = connection.protocol

    map_name = map_name or protocol.map_info.name

    if rot_info := check_map(map_name, protocol.map_dir):
        protocol.planned_map = rot_info
        protocol.advance_rotation()
    else:
        return 'Map {} not found'.format(map_name)

def apply_script(protocol, connection, config):
    # Scripts listed before are intentionally ignored.
    return MilsimProtocol, MilsimConnection
