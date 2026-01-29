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

from itertools import count, filterfalse

class IDPool(set):
    def __init__(self, protocol):
        self.protocol = protocol
        super().__init__()

    def pop(self):
        ID = next(filterfalse(self.__contains__, count()))
        self.add(ID)
        return ID

    def put_back(self, ID):
        self.remove(ID)

def apply_script(protocol, connection, config):
    class IDPoolProtocol(protocol):
        def __init__(self, *w, **kw):
            protocol.__init__(self, *w, **kw)
            self.player_ids = IDPool(self)

    return IDPoolProtocol, connection