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

from milsimlib.types.item_object import Item

class CartridgeBox(Item):
    def __init__(self, o, current = 0):
        Item.__init__(self)

        self.object   = o
        self._current = current

    def pop(self):
        if self._current > 0:
            self._current -= 1
            return self.object

    def current(self):
        return self._current

    @property
    def mass(self):
        return self._current * self.object.totmass

    @property
    def name(self):
        return f"{self.object.name} Box ({self._current})"

class Magazine(Item):
    capacity = NotImplemented

    @property
    def mass(self):
        raise NotImplementedError

    def current(self):
        raise NotImplementedError

class BoxMagazine(Magazine):
    continuous = False
    basemass   = NotImplemented
    basename   = NotImplemented
    cartridge  = NotImplemented

    def __init__(self):
        Magazine.__init__(self)

        self._current = self.capacity

    def reload(self, i):
        return next(filter(lambda o: o.current() > 0, i), None), False

    def current(self):
        return self._current

    def eject(self):
        if self._current > 0:
            self._current -= 1
            return self.cartridge

    @property
    def mass(self):
        return self.basemass + self._current * self.cartridge.totmass

    @property
    def name(self):
        return f"{self.basename} ({self._current})"

class TubularMagazine(Magazine):
    continuous = True
    cartridge  = NotImplemented

    def __init__(self):
        Magazine.__init__(self)

        self.container = deque()

    def push(self, o):
        self.container.appendleft(o)

    def reload(self, i):
        if self.capacity <= self.current():
            return None, False

        it = filter(lambda o: o.current() > 0, i)

        if o := next(it, None):
            self.push(o.pop())
            return None, True

        return None, False

    def current(self):
        return len(self.container)

    def eject(self):
        if bool(self.container):
            return self.container.popleft()

    @property
    def mass(self):
        return sum(map(lambda o: o.totmass, self.container))
