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

from dataclasses import dataclass
from math import pi, nan

from milsimlib.constants import Pound, Inch

@dataclass
class Cartridge:
    name      : str   # Projectile name
    muzzle    : float # Muzzle velocity (m/s)
    effmass   : float # Mass of the bullet (kg)
    totmass   : float # Mass of the cartridge (kg)
    grouping  : float # Standard deviation of the group size (rad)
    deviation : float # Standard deviation of the bullet speed in fractions of the muzzle velocity

    on_block_hit  = None
    on_player_hit = None
    grenade       = False

@dataclass
class OgiveBullet(Cartridge):
    BC      : float # Ballistic coefficient
    caliber : float # Caliber (m)

    pellets = 1

    def __post_init__(self):
        self.area = 0.25 * pi * self.caliber * self.caliber

        # http://www.x-ballistics.eu/cms/ballistics/how-to-calculate-the-trajectory/
        m = self.effmass / Pound
        d = self.caliber / Inch
        i = m / (d * d)
        self.ballistic = i / self.BC

class G1(OgiveBullet):
    model = 1

class G7(OgiveBullet):
    model = 2

@dataclass
class Shotshell(Cartridge):
    diameter : float # Pellet diameter (m)
    pellets  : int   # Number of pellets in the single shell

    model     = 3
    ballistic = nan

    def __post_init__(self):
        self.area = 0.25 * pi * self.diameter * self.diameter
