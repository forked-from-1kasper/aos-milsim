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

ite = lambda b, v1, v2: v1 if b else v2

from milsimlib.types.ammo_object import CartridgeBox, Magazine, BoxMagazine, TubularMagazine

from milsimlib.types.biology import (
    ABCMap, Linear, ABCLimb, Torso, Head, Arm, Leg, Body,
    left_adj, right_adj, torso_n, head_n, arm_n, leg_n,
    randbool, logit, logistic
)

from milsimlib.types.cartridge import Cartridge, OgiveBullet, G1, G7, Shotshell

from milsimlib.types.environment import Box, Weather, StaticWeather, Environment

from milsimlib.types.inventory import Inventory, ItemEntity

from milsimlib.types.item_object import Item

from milsimlib.types.tile_entity import TileEntity

from milsimlib.types.tool_object import Tool, SpadeTool, BlockTool, GrenadeTool
