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

from time import monotonic
from random import gauss

impl = lambda P, Q: not P or Q

class Tool:
    def on_tool_used(self):
        pass

    def on_tool_equipped(self, o):
        pass

    def on_tool_unequipped(self, o):
        pass

    def on_lmb_press(self):
        pass

    def on_lmb_hold(self, t, dt):
        pass

    def on_lmb_release(self):
        pass

    def on_sneak_press(self):
        pass

    def on_sneak_hold(self, t, dt):
        pass

    def on_sneak_release(self):
        pass

    def on_rmb_press(self):
        pass

    def on_rmb_hold(self, t, dt):
        pass

    def on_rmb_release(self):
        pass

def dig(player, mu, dt, x, y, z):
    if wo := player.world_object:
        if wo.dead: return

        sigma = 0.01 if wo.crouch else 0.05
        value = max(0, gauss(mu = mu, sigma = sigma) * dt)

        player.protocol.engine.dig(player.player_id, x, y, z, value)

class SpadeTool(Tool):
    mass = 0.750

    def __init__(self, player):
        self.player = player

    def enabled(self):
        arml, armr = self.player.body.arml, self.player.body.armr
        return impl(arml.fractured, arml.splint) and \
               impl(armr.fractured, armr.splint)

    def on_lmb_hold(self, t, dt):
        if self.enabled():
            if loc := self.player.world_object.cast_ray(4.0):
                dig(self.player, dt, self.player.lmb_spade_speed, *loc)

    def on_rmb_hold(self, t, dt):
        if self.enabled():
            if loc := self.player.world_object.cast_ray(4.0):
                x, y, z = loc

                mu = self.player.rmb_spade_speed
                dig(self.player, dt, mu, x, y, z - 1)
                dig(self.player, dt, mu, x, y, z)
                dig(self.player, dt, mu, x, y, z + 1)

class BlockTool(Tool):
    mass = 0

    def __init__(self, player):
        self.player = player

    def enabled(self):
        return self.player.blocks > 0

class GrenadeTool(Tool):
    mass = 0

    def __init__(self, player):
        self.unpin_time = 0
        self.player = player

    def on_lmb_press(self):
        self.unpin_time = monotonic()

    def on_lmb_release(self):
        self.unpin_time = 0

    def on_tool_used(self):
        self.unpin_time = 0

    def on_tool_equipped(self, o):
        if self.player.world_object.primary_fire:
            self.unpin_time = monotonic()
        else:
            self.unpin_time = 0

    def on_tool_unequipped(self, o):
        self.unpin_time = 0
