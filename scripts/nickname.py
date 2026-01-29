# Copyright © 2024, 2026 rzrn

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

TSV = lambda it: map(lambda x: tuple(x.rstrip("\n").split('\t')), it)
ordinal = lambda k, v: (ord(k), v)

# https://github.com/anyascii/anyascii
with open("extra/anyascii/anyascii.tsv", "r") as fin:
    anyascii = dict(map(lambda w: ordinal(*w), TSV(fin)))

deuce = lambda x: "Deuce" if len(x) <= 0 else x
valid = lambda c: 0x20 <= ord(c) <= 0x7E and c != '%' and c != '#'
clean = lambda x: deuce(''.join(filter(valid, x.translate(anyascii).strip())))

def candidates(name):
    yield name

    for i in count(1):
        yield name + str(i)

def apply_script(protocol, connection, config):
    class NicknameProtocol(protocol):
        def get_name(self, text):
            taken = set(player.name for player in self.players.values())
            return next(filterfalse(taken.__contains__, candidates(clean(text))))

    return NicknameProtocol, connection