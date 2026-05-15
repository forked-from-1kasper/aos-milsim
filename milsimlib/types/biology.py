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

from math import exp, log, inf, floor, prod
from random import random, gauss

from pyspades.constants import SPADE_TOOL

from milsimlib.grammar import Adjective, RegularNoun
from milsimlib.constants import Limb

randbool = lambda prob: random() <= prob

logit    = lambda t: -log(1 / t - 1)
logistic = lambda t: 1 / (1 + exp(-t))

class ABCMap:
    def __call__(self, v):
        raise NotImplementedError

class Linear(ABCMap):
    def __init__(self, x1, x2, y1 = logit(0.01), y2 = logit(0.99)):
        self.v1 = min(x1, x2)
        self.v2 = max(x1, x2)

        self.w1 = min(y1, y2)
        self.w2 = max(y1, y2)

    def __call__(self, v):
        t = (v - self.v1) / (self.v2 - self.v1)
        return self.w1 + t * (self.w2 - self.w1)

class ABCLimb:
    bone_hit_probability   = None
    fracture_ked_threshold = None
    fracture_ked_fifty     = None
    damage                 = ABCMap()

    def __init__(self, abbrev, np):
        self.abbrev, self.np = abbrev, np

        self.reset()

    def ofEnergyAndArea(self, E, A):
        damage, venous, arterial, fractured = 0, False, False, False

        if E > 0:
            # [1] A survey of computational models for blast induced human injuries for security and defence applications,
            #     G. Solomos, M. Larcher, G. Valsamos, V. Karlos, F. Casadei, 2020
            # [2] Model for risk evaluation for fragment debris after a grenade detonation,
            #     G. Lund, 2021.

            a, b = -28.42, 2.94 # TODO: take N-layer uniform into consideration

            e = E / A # energy density or energy per area, J/m²
            Y = a + b * log(e / 5)

            if random() <= logistic(Y):
                if randbool(self.arterial_density):
                    arterial = True
                else:
                    venous = True

                # We use lognormal model based on energy density:
                #   P = P(fracture) = (1 + erf([log(e) − μ]/σ√2))/2,
                # taking the hypothesis (based on intuitive considerations) that, within
                # reasonable limits, fragments with the same energy density result in similar
                # damage to bones. Thus, velocity-based lognormal model as in [3] can be rewritten
                # into energy-density-based model.
                # [3] Mapping the Risk of Fracture of the Tibia From Penetrating Fragments,
                #     T.-T. N. Nguyen, D. Carpanen, I. A. Rankin, A. Ramasamy,
                #     J. Breeze, W. G. Proud, J. C. Clasper, S. D. Masouros.
                # We see that for P(e₅₀) = 1/2 we have μ = log(e₅₀).
                # Further, for the threshold probability Pₜₕ and energy density eₜₕ we calculate:
                #    Pₜₕ = (1 + erf(log(eₜₕ/e₅₀)/σ√2))/2
                #  ↔ 2Pₜₕ − 1 = erf(log(eₜₕ/e₅₀)/σ√2)
                #  ↔ log(eₜₕ/e₅₀)/σ√2 = erf⁻¹(2Pₜₕ − 1)
                #  ↔ σ = log(eₜₕ/e₅₀)/[erf⁻¹(2Pₜₕ − 1)√2] = α · log(eₜₕ/e₅₀).
                # We take Pₜₕ = 0.01, so α ≈ −0.4299.

                if random() <= self.bone_hit_probability:
                    # We can, in principle, to make some geometric test of the intesection
                    # of a bullet’s path with an AABB of bone, but since a bullet usually
                    # behaves unpredictably after entering the body, a simple probability
                    # test seems more natural. Moreover, a fracture can occur even without
                    # the bullet hitting the bone, but as the effect of the temporary cavity.

                    α = -0.4299

                    eth, e50 = self.fracture_ked_threshold, self.fracture_ked_fifty
                    fractured = gauss(mu = log(e50), sigma = α * log(eth / e50)) <= log(e)

            damage = 100 * logistic(self.damage(E))

        return damage, venous, arterial, fractured

    def hit(self, value):
        if value <= 0: return
        self.hp = max(0, self.hp - value)

    def reset(self):
        self.hp        = 100
        self.venous    = False
        self.arterial  = False
        self.fractured = False
        self.splint    = False

    def on_fracture(self, player):
        pass

class Torso(ABCLimb):
    venous_rate            = 0.7
    arterial_rate          = 2.8
    arterial_density       = 0.4
    bone_hit_probability   = 0.35
    fracture_ked_threshold = 1.00e+06
    fracture_ked_fifty     = 1.75e+06
    damage                 = Linear(0, 1500)
    rotation_damage        = 0.1

class Head(ABCLimb):
    venous_rate          = 1.0
    arterial_rate        = 4.3
    arterial_density     = 0.65
    bone_hit_probability = -inf
    damage               = Linear(0, 500)

class Arm(ABCLimb):
    venous_rate            = 0.35
    arterial_rate          = 1.7
    arterial_density       = 0.7
    bone_hit_probability   = 0.50
    fracture_ked_threshold = 1.50e+06
    fracture_ked_fifty     = 2.50e+06
    damage                 = Linear(0, 3000)
    action_damage_rate     = 0.25

    def on_fracture(self, player):
        player.set_tool(SPADE_TOOL)

class Leg(ABCLimb):
    venous_rate            = 0.55
    arterial_rate          = 2.1
    arterial_density       = 0.75
    bleeding               = Linear(15, 60)
    bone_hit_probability   = 0.45
    fracture_ked_threshold = 3.00e+06
    fracture_ked_fifty     = 4.25e+06
    damage                 = Linear(0, 4000)
    fall                   = Linear(1, 10)
    sprint_damage_rate     = 7.5
    walk_damage_rate       = 3.5
    jump_damage            = 9.0

left_adj, right_adj = Adjective("left"), Adjective("right")

torso_n = RegularNoun("torso")
head_n  = RegularNoun("head")
arm_n   = RegularNoun("arm")
leg_n   = RegularNoun("leg")

class Body:
    def __init__(self):
        self.torso = Torso("torso", lambda det: det(torso_n))
        self.head  = Head("head", lambda det: det(head_n))
        self.arml  = Arm("arml", lambda det: left_adj(det(arm_n)))
        self.armr  = Arm("armr", lambda det: right_adj(det(arm_n)))
        self.legl  = Leg("legl", lambda det: left_adj(det(leg_n)))
        self.legr  = Leg("legr", lambda det: right_adj(det(leg_n)))

        self.message_queue = deque()

        self.reset()

    def __getitem__(self, k):
        if k == Limb.torso: return self.torso
        if k == Limb.head:  return self.head
        if k == Limb.arml:  return self.arml
        if k == Limb.armr:  return self.armr
        if k == Limb.legl:  return self.legl
        if k == Limb.legr:  return self.legr

    def keys(self):
        return list(Limb)

    def arms(self):
        yield self.arml
        yield self.armr

    def legs(self):
        yield self.legl
        yield self.legr

    def values(self):
        yield self.torso
        yield self.head
        yield self.arml
        yield self.armr
        yield self.legl
        yield self.legr

    def average(self):
        avg = prod(map(lambda P: P.hp / 100, self.values()))
        return floor(100 * avg)

    def bleeding(self):
        return any(map(lambda P: P.venous or P.arterial, self.values()))

    def fractured(self):
        return any(map(lambda P: P.fractured, self.values()))

    def reset(self):
        for P in self.values():
            P.reset()

        self.message_queue.clear()

        self.deaf = False

    def update(self, dt):
        for P in self.values():
            if P.arterial:
                P.hit(P.arterial_rate * dt)

            if P.venous:
                P.hit(P.venous_rate * dt)

    def take_message(self):
        if bool(self.message_queue):
            return self.message_queue.popleft()

    def pushl_message(self, mesg):
        self.message_queue.appendleft(mesg)

    def pushr_message(self, mesg):
        self.message_queue.append(mesg)
