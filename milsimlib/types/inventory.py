# Copyright © 2024–2026 rzrn

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

from collections import deque

class Inventory:
    def __init__(self):
        self.data = deque()

    def __iter__(self):
        return iter(self.data)

    def __getitem__(self, ID):
        return next(filter(lambda x: x.id == ID.upper(), self.data), None)

    def remove(self, o):
        self.data.remove(o)

    def remove_if(self, pred):
        self.data = deque(filter(lambda o: not pred(o), self.data))

    def clear(self):
        self.data.clear()

    def extend(self, it):
        self.data.extend(it)

    def push(self, o):
        self.data.appendleft(o)
        return o

    def append(self, *w):
        self.data.extend(w)

    def empty(self):
        return not bool(self.data)

class ItemEntity(Inventory):
    def __init__(self, protocol, x, y, z):
        Inventory.__init__(self)

        self.x, self.y, self.z = x, y, z
        self.protocol = protocol

    def remove_if_empty(self):
        if self.empty():
            self.protocol.remove_item_entity(
                self.x, self.y, self.z
            )

    def remove(self, o):
        Inventory.remove(self, o)
        self.remove_if_empty()

    def remove_if(self, pred):
        Inventory.remove_if(self, pred)
        self.remove_if_empty()

    def clear(self, pred):
        Inventory.clear(self)
        self.remove_if_empty()
