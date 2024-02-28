from dataclasses import dataclass
from typing import Callable
from math import pi, atan

from pyspades.constants import RIFLE_WEAPON, SMG_WEAPON, SHOTGUN_WEAPON

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

default = 'default'
build   = 'build'

@dataclass
class Material:
    ricochet   : float
    density    : float
    strength   : float
    deflecting : float
    durability : float
    absorption : float

Dirt     = Material(ricochet = 0.3,  deflecting = 75, durability = 1.0,  strength = 2500,   density = 1200, absorption = 1e+15)
Sand     = Material(ricochet = 0.4,  deflecting = 83, durability = 1.0,  strength = 1500,   density = 1600, absorption = 1e+15)
Wood     = Material(ricochet = 0.75, deflecting = 80, durability = 3.0,  strength = 2.1e+6, density = 800,  absorption = 50e+3)
Concrete = Material(ricochet = 0.4,  deflecting = 75, durability = 5.0,  strength = 5e+6,   density = 2400, absorption = 100e+3)
Asphalt  = Material(ricochet = 0.6,  deflecting = 78, durability = 6.0,  strength = 1.2e+6, density = 2400, absorption = 80e+3)
Steel    = Material(ricochet = 0.80, deflecting = 77, durability = 10.0, strength = 500e+6, density = 7850, absorption = 150e+3)
Glass    = Material(ricochet = 0.0,  deflecting = 0,  durability = 0.3,  strength = 7e+6,   density = 2500, absorption = 500)
Plastic  = Material(ricochet = 0.1,  deflecting = 85, durability = 0.5,  strength = 1e+5,   density = 300,  absorption = 50e+3)
Grass    = Material(ricochet = 0.0,  deflecting = 0,  durability = 1.5,  strength = 100,    density = 50,   absorption = 1e+15)

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

@dataclass
class Gun:
    name               : str   # Name
    ammo               : type  # Ammunition container constructor
    round              : Round # Ammunition type used by weapon
    delay              : float # Time between shots
    reload_time        : float # Time between reloading and being able to shoot again
    spread             : float
    velocity_deviation : float

mm   = lambda s: s / 1000
gram = lambda m: m / 1000
yard = lambda s: s * 0.9144
inch = lambda s: s * 0.0254
Cone = lambda H, d: atan(0.5 * d / H)

R127x108mm = Round(900, gram(50.00), 150.0000, mm(12.70),  1)
R762x54mm  = Round(850, gram(10.00), 146.9415, mm(07.62),  1)
Parabellum = Round(600, gram(08.03), 104.7573, mm(09.00),  1)
Shot       = Round(457, gram(38.00),   5.0817, mm(18.40), 15)

Rifle = Gun(
    name               = "Rifle",
    ammo               = Magazines(5, 10),
    round              = R762x54mm,
    delay              = 0.50,
    reload_time        = 2.5,
    spread             = 0,
    velocity_deviation = 0.05
)

SMG = Gun(
    name               = "SMG",
    ammo               = Magazines(4, 30),
    round              = Parabellum,
    delay              = 0.11,
    reload_time        = 2.5,
    spread             = 0,
    velocity_deviation = 0.05
)

Shotgun = Gun(
    name               = "Shotgun",
    ammo               = Heap(6, 48),
    round              = Shot,
    delay              = 1.00,
    reload_time        = 0.5,
    spread             = Cone(yard(25), inch(40)),
    velocity_deviation = 0.10
)

guns = {RIFLE_WEAPON: Rifle, SMG_WEAPON: SMG, SHOTGUN_WEAPON: Shotgun}

@dataclass
class Part:
    hp       : int  = 100
    bleeding : bool = False
    fracture : bool = False
    splint   : bool = False

    def hit(self, value):
        if value <= 0: return
        self.hp = max(0, self.hp - value)
