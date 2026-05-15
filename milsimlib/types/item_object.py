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

def digits(n, base = 10):
    while n > 0:
        rem = (n - 1) % base
        n = (n - rem) // base
        yield rem

from string import ascii_uppercase
def encode(n, key = ascii_uppercase):
    ds = digits(n, base = len(key))
    return "".join(map(key.__getitem__, ds))[::-1]

from itertools import count

class Item:
    idpool = None

    @staticmethod
    def reset():
        Item.idpool = map(encode, count(1))

    def __init__(self):
        self.id = next(Item.idpool)
        self.persistent = True

    def mark_renewable(self):
        self.persistent = False

        return self

    def apply(self, player):
        pass

    def mass(self):
        raise NotImplementedError

    @property
    def name(self):
        raise NotImplementedError
