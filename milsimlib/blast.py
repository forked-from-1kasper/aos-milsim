# Copyright © 2023–2026 rzrn

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

from math import floor, sqrt, cbrt, pi, sin, cos, exp, log, erf
from random import choice, uniform, binomialvariate, gauss
from dataclasses import dataclass

import asyncio

from pyspades.collision import distance_3d_vector
from pyspades.constants import GRENADE_KILL

from pyspades.contained import GrenadePacket
from pyspades.common import Vertex3
from pyspades.world import Grenade

from milsimlib.engine import toMeters
from milsimlib.constants import Limb
from milsimlib.vxl import can_see

class HEGrenadeObject(Grenade):
    @property
    def high_explosive(self):
        raise NotImplementedError

    def initialize(self, protocol, player_id, fuse, r, v):
        Grenade.initialize(self, fuse, r, None, v, type(self).explode)

        self.player_id = player_id
        self.protocol  = protocol

    def explode(self):
        if player := self.protocol.take_player(self.player_id):
            x, y, z = self.position.get()
            player.grenade_destroy(floor(x), floor(y), floor(z))

            self.high_explosive.explode(self.protocol, self.position, hit_by = player)

class FlashbangObject(Grenade):
    def initialize(self, protocol, player_id, fuse, r, v):
        Grenade.initialize(self, fuse, r, None, v, type(self).explode)

        self.player_id = player_id
        self.protocol  = protocol

    def explode(self):
        if player := self.protocol.take_player(self.player_id):
            player.flashbang_exploded(self)

def sendGrenadePacket(protocol, player_id, position, velocity, fuse):
    contained           = GrenadePacket()
    contained.player_id = player_id
    contained.value     = fuse
    contained.position  = position.get()
    contained.velocity  = velocity.get()

    protocol.broadcast_contained(contained)

async def flashbang_effect(protocol, player_id, position):
    for i in range(50):
        await asyncio.sleep(uniform(0.05, 0.25))

        r = position.copy()
        r.x += uniform(-5.0, 5.0)
        r.y += uniform(-5.0, 5.0)
        r.z += uniform(-5.0, 5.0)

        sendGrenadePacket(protocol, player_id, r, Vertex3(0, 0, 0), 0.0)

def applyDamage(hit_by, player, limb, E, A):
    damage, venous, arterial, fractured = player.body[limb].ofEnergyAndArea(E, A)

    if damage > 0:
        player.hit(
            damage, limb = limb, hit_by = hit_by, kill_type = GRENADE_KILL,
            venous = venous, arterial = arterial, fractured = fractured,
        )

@dataclass
class HighExplosive:
    TNTe    : float # TNT equivalent of a charge (kg)
    fragnum : int   # Average number of fragments
    speed   : float # Mean initial speed of fragments (m/s)
    mass    : float # Mean mass of fragments (kg)
    area    : float # Mean cross sectional area of fragments (m²)
    drag    : float # Mean drag coefficient of fragments (1)

    def explode(self, protocol, r, hit_by = None):
        for player in protocol.living():
            self.applyTotalDamage(r, player, hit_by = hit_by)

    def applyTotalDamage(self, r, player, hit_by = None):
        protocol = player.protocol

        wo = player.world_object
        x0, y0, z0 = wo.position.x, wo.position.y, min(62.9, wo.position.z)
        x1, y1, z1 = r.x, r.y, min(62.9, r.z)

        d = toMeters(distance_3d_vector(r, wo.position))
        Z = d * protocol.engine.hccoeff(self.TNTe)

        Δp = protocol.engine.opvalue(Z)
        ΔI = protocol.engine.opimpulse(Z)
        Δt = protocol.engine.opduration(Z) * cbrt(self.TNTe)

        # Estimate of Man’s Tolerance to the Direct Effects of Air Blast,
        # I. G. Bowen, E. R. Fletcher, D. R. Richmond, October 1968

        # (1) Lung hemorrhage
        if can_see(protocol.map, x0, y0, z0, x1, y1, z1):
            p = protocol.engine.pressure

            if wo.crouch:
                Δpᵉᶠᶠ = Δp
            else:
                Δpᵉᶠᶠ = 3.5 * Δp * (Δp + 2 * p) / (Δp + 7 * p)

            a, b, c = 0.004345, 1.064, 0.1788
            pSW50 = 424_028 # 61.5 psi, square-wave pressure resulting in 50 % fatalities with p = p0
            p0 = 101_325 # 14.7 psi, standard atmosphere

            P = Δpᵉᶠᶠ * p0 / p # Scaled peak overpressure (Pa)
            T = Δt * cbrt(70 / player.body_mass) * sqrt(p / p0) # Scaled duration (s)

            p50 = pSW50 * (a * pow(T, -b) + 1) # 50-percent fatalities overpressure for a given T (Pa)
            Y1 = log(P / p50) / c + 5 # Death probability (probit units)

            if gauss(mu = 5) <= Y1:
                player.kill(by = hit_by, kill_type = GRENADE_KILL)
                return

        # A survey of computational models for blast induced human injuries for security and defence applications,
        # G. Solomos, M. Larcher, G. Valsamos, V. Karlos, F. Casadei, 2020

        # (2) Skull fracture due to the head impact on a hard surface
        Y2 = 5 - 8.49 * log(2430 / Δp + 4.0e+8 / (Δp * ΔI))

        if gauss(mu = 5) <= Y2:
            player.kill(by = hit_by, kill_type = GRENADE_KILL)
            return

        # (3) Whole body impact
        Y3 = 5 - 2.44 * log(7380 / Δp + 1.3e+9 / (Δp * ΔI))

        if gauss(mu = 5) <= Y3:
            player.kill(by = hit_by, kill_type = GRENADE_KILL)
            return

        # (4) Eardrum rupture
        Y4 = -12.6 + 1.524 * log(Δp)

        if gauss(mu = 5) <= Y4:
            player.body.pushl_message("You feel pain in your ears")
            player.body.deaf = True

        # (5) Fragment debris
        r1 = Vertex3(r.x, r.y, r.z - 1) # TODO: figure out why do we need to “− 1”
        r2 = player.eye()

        v = protocol.engine.cast(self.drag, self.mass, self.area, self.speed, r1, r2)
        K = 0.5 * self.mass * v * v

        if v <= 0: return

        Etot, Ntot = 4 * pi, self.fragnum
        Ehd, Eto, Ell, Elr, Ear, Eal = protocol.engine.exposed(player.player_id, r)

        Nhd = binomialvariate(Ntot, Ehd / Etot)
        Nto = binomialvariate(Ntot, Eto / Etot)
        Nll = binomialvariate(Ntot, Ell / Etot)
        Nlr = binomialvariate(Ntot, Elr / Etot)
        Nar = binomialvariate(Ntot, Ear / Etot)
        Nal = binomialvariate(Ntot, Eal / Etot)

        # for the moment, we just multiply energy by the number of fragments
        if Nhd > 0: applyDamage(hit_by, player, Limb.head,  Nhd * K, self.area)
        if Nto > 0: applyDamage(hit_by, player, Limb.torso, Nto * K, self.area)
        if Nll > 0: applyDamage(hit_by, player, Limb.legl,  Nll * K, self.area)
        if Nlr > 0: applyDamage(hit_by, player, Limb.legr,  Nlr * K, self.area)
        if Nar > 0: applyDamage(hit_by, player, Limb.armr,  Nar * K, self.area)
        if Nal > 0: applyDamage(hit_by, player, Limb.arml,  Nal * K, self.area)
