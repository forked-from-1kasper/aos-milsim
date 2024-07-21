from typing import Dict, List, Callable, Tuple
from dataclasses import dataclass, field
from collections.abc import Iterable

from math import pi, exp, log, inf, floor, prod
from random import random, gauss
from enum import Enum

from pyspades.color import interpolate_rgb
from pyspades.constants import SPADE_TOOL
from pyspades.common import Vertex3

randbool = lambda prob: random() <= prob

ite = lambda b, v1, v2: v1 if b else v2

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
class Box:
    xmin : float = -inf
    xmax : float = +inf
    ymin : float = -inf
    ymax : float = +inf
    zmin : float = -inf
    zmax : float = +inf

    def inside(self, v):
        return self.xmin <= v.x <= self.xmax and \
               self.ymin <= v.y <= self.ymax and \
               self.zmin <= v.z <= self.zmax

class Weather:
    clear_sky_fog         = (128, 232, 255)
    complete_coverage_fog = (200, 200, 200)

    def update(self, dt):
        raise NotImplementedError

    def temperature(self) -> float:
        raise NotImplementedError

    def pressure(self) -> float:
        raise NotImplementedError

    def humidity(self) -> float:
        raise NotImplementedError

    def wind(self) -> Tuple[float, float]:
        raise NotImplementedError

    def cloudiness(self) -> float:
        return NotImplementedError

    def fog(self):
        return interpolate_rgb(
            self.clear_sky_fog,
            self.complete_coverage_fog,
            self.cloudiness()
        )

class StaticWeather(Weather):
    def __init__(self, t = 15, p = 101325, φ = 0.3, w = (0, 0), k = 0):
        self.t = t
        self.p = p
        self.φ = φ
        self.w = w
        self.k = k

    def update(self, dt):
        return False

    def temperature(self):
        return self.t

    def pressure(self):
        return self.p

    def humidity(self):
        return self.φ

    def wind(self):
        return self.w

    def cloudiness(self):
        return self.k

Vector3i = Tuple[int, int, int]

def void():
    yield from ()

@dataclass
class Environment:
    registry        : List[Material]
    default         : Material
    build           : Material
    water           : Material
    on_flag_capture : Callable = lambda player: None
    size            : Box = field(default_factory = Box)
    palette         : Dict[int, Material] = field(default_factory = dict)
    defaults        : Callable[[], Iterable[Tuple[Vector3i, Material]]] = void
    north           : Vertex3 = Vertex3(1, 0, 0)
    weather         : Weather = StaticWeather()

    def apply(self, sim):
        assert len(self.registry) > 0

        for M in self.registry:
            sim.register(M)

        sim.setDefaultMaterial(self.default)
        sim.setBuildMaterial(self.build)
        sim.setWaterMaterial(self.water)

        sim.applyPalette(self.palette)

        for (x, y, z), M in self.defaults():
            sim.set(x, y, z, M)

class Round:
    pass

@dataclass
class Bullet(Round):
    muzzle  : float
    mass    : float
    BC      : float
    caliber : float

    grenade = False
    pellets = 1
    spread  = 0

    def __post_init__(self):
        self.area = 0.25 * pi * self.caliber * self.caliber

        # http://www.x-ballistics.eu/cms/ballistics/how-to-calculate-the-trajectory/
        m = self.mass / Pound
        d = self.caliber / Inch
        i = m / (d * d)
        self.ballistic = i / self.BC

class G1(Bullet):
    model = 1

class G7(Bullet):
    model = 2

@dataclass
class Ball(Round):
    muzzle   : float
    mass     : float
    diameter : float
    pellets  : int
    spread   : float

    grenade   = False
    model     = 3
    ballistic = 0.0

    def __post_init__(self):
        self.area = 0.25 * pi * self.diameter * self.diameter

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

@dataclass
class ABCLimb:
    abbrev    : str
    label     : str

    hp        : int  = 100
    venous    : bool = False
    arterial  : bool = False
    fractured : bool = False
    splint    : bool = False

    bleeding = ABCMap()
    fracture = ABCMap()
    damage   = ABCMap()

    def ofEnergyAndArea(self, E, A):
        damage, venous, arterial, fractured = 0, False, False, False

        if E > 0:
            e = (E / A) / (100 * 100) # energy per area, J/cm²

            if randbool(logistic(self.bleeding(e))):
                if randbool(self.arterial_density):
                    arterial = True
                else:
                    venous = True

            fractured = randbool(logistic(self.fracture(E)))
            damage    = 100 * logistic(self.damage(E))

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
    venous_rate      = 0.7
    arterial_rate    = 2.8
    arterial_density = 0.4
    bleeding         = Linear(15, 70)
    fracture         = Linear(500, 1000)
    damage           = Linear(0, 1500)
    rotation_damage  = 0.1

class Head(ABCLimb):
    venous_rate      = 1.0
    arterial_rate    = 4.3
    arterial_density = 0.65
    bleeding         = Linear(10, 50)
    fracture         = Linear(40, 70)
    damage           = Linear(0, 500)

class Arm(ABCLimb):
    venous_rate        = 0.35
    arterial_rate      = 1.7
    arterial_density   = 0.7
    bleeding           = Linear(15, 55)
    fracture           = Linear(450, 600)
    damage             = Linear(0, 3000)
    action_damage_rate = 0.25

    def on_fracture(self, player):
        player.set_tool(SPADE_TOOL)

class Leg(ABCLimb):
    venous_rate        = 0.55
    arterial_rate      = 2.1
    arterial_density   = 0.75
    bleeding           = Linear(15, 60)
    fracture           = Linear(500, 650)
    damage             = Linear(0, 4000)
    fall               = Linear(1, 10)
    sprint_damage_rate = 7.5
    walk_damage_rate   = 3.5

class Body:
    def __init__(self):
        self.torso = Torso("torso", "torso")
        self.head  = Head("head", "head")
        self.arml  = Arm("arml", "left arm")
        self.armr  = Arm("armr", "right arm")
        self.legl  = Leg("legl", "left leg")
        self.legr  = Leg("legr", "right leg")

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

    def update(self, dt):
        for P in self.values():
            if P.arterial:
                P.hit(P.arterial_rate * dt)

            if P.venous:
                P.hit(P.venous_rate * dt)

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

class Tool:
    def lmb(self, t, dt):
        pass

    def rmb(self, t, dt):
        pass

def dig(player, mu, dt, x, y, z):
    if not player.world_object or player.world_object.dead: return

    sigma = 0.01 if player.world_object.crouch else 0.05
    value = max(0, gauss(mu = mu, sigma = sigma) * dt)

    protocol = player.protocol

    if protocol.simulator.dig(x, y, z, value):
        protocol.onDestroy(player.player_id, x, y, z)

class SpadeTool(Tool):
    def __init__(self, player):
        self.player = player

    def enabled(self):
        arml, armr = self.player.body.arml, self.player.body.armr
        return (not arml.fractured or arml.splint) and \
               (not armr.fractured or armr.splint)

    def lmb(self, t, dt):
        if self.enabled():
            loc = self.player.world_object.cast_ray(4.0)

            if loc is not None:
                dig(self.player, dt, 1.0, *loc)

    def rmb(self, t, dt):
        if self.enabled():
            loc = self.player.world_object.cast_ray(4.0)

            if loc is not None:
                x, y, z = loc
                dig(self.player, dt, 0.7, x, y, z - 1)
                dig(self.player, dt, 0.7, x, y, z)
                dig(self.player, dt, 0.7, x, y, z + 1)

class BlockTool(Tool):
    def __init__(self, player):
        self.player = player

class GrenadeTool(Tool):
    def __init__(self, player):
        self.player = player
