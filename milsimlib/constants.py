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

from enum import Enum

Pound = 0.45359237
Yard  = 0.9144
Inch  = 0.0254

class Limb(Enum):
    head  = 0
    torso = 1
    arml  = 2
    armr  = 3
    legl  = 4
    legr  = 5

class HitEffect:
    block    = 0
    headshot = 1
    player   = 2
