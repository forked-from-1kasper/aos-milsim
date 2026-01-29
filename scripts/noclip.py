# Copyright © 2024 rzrn

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.

# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

def apply_script(protocol, connection, config):
    class NoclipProtocol(protocol):
        def is_solid(self, x, y, z):
            return 0 <= z < 63 and self.map.get_solid(x, y, z)

    class NoclipConnection(connection):
        def is_stuck(self, x, y, z):
            protocol = self.protocol

            if self.world_object.crouch:
                return protocol.is_solid(x, y, z) or protocol.is_solid(x, y, z + 1)
            else:
                return protocol.is_solid(x, y, z) or protocol.is_solid(x, y, z + 1) or protocol.is_solid(x, y, z + 2)

        def check_speedhack(self, x2, y2, z2, distance = None):
            x1, y1, z1 = self.world_object.position.get()

            # TODO: is there any way to prevent tunnelling through walls?
            if self.is_stuck(x1, y1, z1) or self.is_stuck(x2, y2, z2):
                return False

            return connection.check_speedhack(self, x2, y2, z2, distance)

    return NoclipProtocol, NoclipConnection
