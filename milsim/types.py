from dataclasses import dataclass
from typing import Dict, List
from math import pi, exp, log

from pyspades.constants import TORSO, HEAD, ARMS, LEGS

ite = lambda b, v1, v2: v1 if b else v2

EXTENSION_BASE          = 0x40
EXTENSION_TRACE_BULLETS = 0x10
EXTENSION_HIT_EFFECTS   = 0x11

class TracerPacket:
    id = EXTENSION_BASE + EXTENSION_TRACE_BULLETS

    def __init__(self, index, position, value, origin = False):
        self.index    = index
        self.position = position
        self.value    = value
        self.origin   = origin

    def write(self, writer):
        writer.writeByte(self.id, True)
        writer.writeByte(self.index, False)
        writer.writeFloat(self.position.x, False)
        writer.writeFloat(self.position.y, False)
        writer.writeFloat(self.position.z, False)
        writer.writeFloat(self.value, False)
        writer.writeByte(0xFF if self.origin else 0x00, False)

def hasTraceExtension(conn):
    return EXTENSION_TRACE_BULLETS in conn.proto_extensions

class HitEffectPacket:
    id = EXTENSION_BASE + EXTENSION_HIT_EFFECTS

    def __init__(self, position, x, y, z, target):
        self.position = position
        self.x        = x
        self.y        = y
        self.z        = z
        self.target   = target

    def write(self, writer):
        writer.writeByte(self.id, True)

        writer.writeFloat(self.position.x, False)
        writer.writeFloat(self.position.y, False)
        writer.writeFloat(self.position.z, False)

        writer.writeInt(self.x, False, False)
        writer.writeInt(self.y, False, False)
        writer.writeInt(self.z, False, False)

        writer.writeByte(self.target, False)

def hasHitEffects(conn):
    return EXTENSION_HIT_EFFECTS in conn.proto_extensions

@dataclass
class Material:
    name       : str   # Material name.
    ricochet   : float # Conditional probability of ricochet.
    deflecting : float # Minimum angle required for a ricochet to occur (degree).
    durability : float # Average number of seconds to break material with a shovel.
    strength   : float # Material cavity strength (Pa).
    density    : float # Density of material (kg/m³).
    absorption : float # Amount of energy that material can absorb before breaking.
    crumbly    : bool  # Whether material can crumble.

@dataclass
class Voxel:
    material   : Material
    durability : float

@dataclass
class Environment:
    registry : List[Material]
    default  : Material
    build    : Material
    palette  : Dict[int, Material]

ρ      = 1.225 # Air density
factor = 0.5191

@dataclass
class Round:
    speed     : float
    mass      : float
    ballistic : float
    caliber   : float
    pellets   : int

    def __post_init__(self):
        self.grenade = False
        self.drag    = (factor * self.mass) / (self.ballistic * (self.caliber ** 2))
        self.area    = (pi / 4) * (self.caliber ** 2)
        self.k       = (ρ * self.drag * self.area) / (2 * self.mass)

class Ammo:
    def total(self):
        raise NotImplementedError

    def current(self):
        raise NotImplementedError

    def reserved(self):
        return self.total() - self.current()

@dataclass
class Gun:
    name               : str   # Name
    ammo               : type  # Ammunition container constructor
    round              : Round # Ammunition type used by weapon
    delay              : float # Time between shots
    reload_time        : float # Time between reloading and being able to shoot again
    spread             : float
    velocity_deviation : float

logit    = lambda t: -log(1 / t - 1)
logistic = lambda t: 1 / (1 + exp(-t))

class Linear:
    def __init__(self, x1, x2, y1 = logit(0.01), y2 = logit(0.99)):
        self.v1 = min(x1, x2)
        self.v2 = max(x1, x2)

        self.w1 = min(y1, y2)
        self.w2 = max(y1, y2)

    def __call__(self, v):
        t = (v - self.v1) / (self.v2 - self.v1)
        return self.w1 + t * (self.w2 - self.w1)

@dataclass
class Part:
    hp        : int  = 100
    venous    : bool = False
    arterial  : bool = False
    fractured : bool = False
    splint    : bool = False

    def hit(self, value):
        if value <= 0: return
        self.hp = max(0, self.hp - value)

    def reset(self):
        self.hp        = 100
        self.venous    = False
        self.arterial  = False
        self.fractured = False
        self.splint    = False

class Torso(Part):
    name             = "torso"
    bleeding_rate    = 0.7
    arterial_density = 0.4
    bleeding         = Linear(15, 70)
    fracture         = Linear(500, 1000)
    damage           = Linear(0, 1500)
    rotation_damage  = 0.1

class Head(Part):
    name             = "head"
    bleeding_rate    = 1.0
    arterial_density = 0.65
    bleeding         = Linear(10, 50)
    fracture         = Linear(40, 70)
    damage           = Linear(0, 500)

class Arms(Part):
    name               = "arms"
    bleeding_rate      = 0.35
    arterial_density   = 0.7
    bleeding           = Linear(15, 55)
    fracture           = Linear(450, 600)
    damage             = Linear(0, 3000)
    action_damage_rate = 0.25

class Legs(Part):
    name               = "legs"
    bleeding_rate      = 0.55
    arterial_density   = 0.75
    bleeding           = Linear(15, 60)
    fracture           = Linear(500, 650)
    damage             = Linear(0, 4000)
    fall               = Linear(1, 10)
    sprint_damage_rate = 10.0
    walk_damage_rate   = 5.0

class Body:
    arterial_rate = 2.0

    def __init__(self):
        self.torso = Torso()
        self.head  = Head()
        self.arms  = Arms()
        self.legs  = Legs()

    def __getitem__(self, k):
        if k == HEAD:  return self.head
        if k == TORSO: return self.torso
        if k == ARMS:  return self.arms
        if k == LEGS:  return self.legs

    def keys(self):
        return [TORSO, HEAD, ARMS, LEGS]

    def values(self):
        return [self.torso, self.head, self.arms, self.legs]

def Magazines(magazines : int, capacity : int) -> type:
    """
    magazines: Number of magazines
    capacity:  Number of rounds that fit in the weapon at once
    """

    class Implementation(Ammo):
        continuous = False

        def __init__(self):
            self.loaded = 0
            self.restock()

        def empty(self):
            return all(map(lambda c: c <= 0, self.container))

        def next(self):
            self.loaded += 1
            self.loaded %= magazines

        def reload(self):
            if self.empty():
                return False

            self.next()
            while self.container[self.loaded] <= 0:
                self.next()

            return False

        def full(self):
            return self.total() >= capacity * magazines

        def current(self):
            return self.container[self.loaded]

        def total(self):
            return sum(self.container)

        def shoot(self, amount):
            avail = self.container[self.loaded]
            self.container[self.loaded] = max(avail - amount, 0)

        def restock(self):
            self.container = [capacity] * magazines

        def info(self):
            show = lambda w: str(w[1]) + ite(self.loaded == w[0], "*", "")

            buff = ", ".join(map(show, enumerate(self.container)))
            return f"{magazines} magazines: {buff}"

    return Implementation

def Heap(capacity : int, stock : int) -> type:
    """
    capacity: Number of rounds that fit in the weapon at once
    stock:    Total number of rounds
    """

    class Implementation(Ammo):
        continuous = True

        def __init__(self):
            self.loaded = capacity
            self.restock()

        def reload(self):
            if self.loaded < capacity and self.remaining > 0:
                self.loaded    += 1
                self.remaining -= 1
                return True

            return False

        def full(self):
            return self.total() >= stock

        def current(self):
            return self.loaded

        def total(self):
            return self.remaining + self.loaded

        def shoot(self, amount):
            self.loaded = max(self.loaded - amount, 0)

        def restock(self):
            self.remaining = stock - self.loaded

        def info(self):
            noun = "rounds" if self.remaining != 1 else "round"
            return f"{self.remaining} {noun} in reserve"

    return Implementation
