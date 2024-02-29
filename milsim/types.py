from dataclasses import dataclass
from typing import Dict
from math import pi

EXTENSION_BASE          = 0x40
EXTENSION_TRACE_BULLETS = 0x10

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

@dataclass
class Material:
    ricochet   : float # Conditional probability of ricochet.
    deflecting : float # Minimum angle required for a ricochet to occur (degree).
    durability : float # Average number of seconds to break material with a shovel.
    strength   : float # Material cavity strength (Pa).
    density    : float # Density of material (kg/m³).
    absorption : float # Amount of energy that material can absorb before breaking.
    crumbly    : bool  # Whether material can crumble.

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

@dataclass
class Part:
    hp       : int  = 100
    bleeding : bool = False
    fracture : bool = False
    splint   : bool = False

    def hit(self, value):
        if value <= 0: return
        self.hp = max(0, self.hp - value)

@dataclass
class Environment:
    color   : Dict[int, Material]
    default : Material
    build   : Material

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
            buff = ", ".join(map(str, self.container))
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
