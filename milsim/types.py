from typing import Dict, List, Callable, Tuple
from dataclasses import dataclass, field
from collections.abc import Iterable
from collections import deque

from math import pi, exp, log, inf, floor, prod
from random import random, gauss

from pyspades.color import interpolate_rgb
from pyspades.constants import SPADE_TOOL
from pyspades.common import Vertex3

from milsim.constants import Pound, Inch, Limb

randbool = lambda prob: random() <= prob

ite = lambda b, v1, v2: v1 if b else v2

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

@dataclass
class Cartridge:
    name      : str
    muzzle    : float
    effmass   : float
    totmass   : float
    grouping  : float
    deviation : float

    grenade = False

@dataclass
class Bullet(Cartridge):
    BC      : float
    caliber : float

    pellets = 1

    def __post_init__(self):
        self.area = 0.25 * pi * self.caliber * self.caliber

        # http://www.x-ballistics.eu/cms/ballistics/how-to-calculate-the-trajectory/
        m = self.effmass / Pound
        d = self.caliber / Inch
        i = m / (d * d)
        self.ballistic = i / self.BC

class G1(Bullet):
    model = 1

class G7(Bullet):
    model = 2

@dataclass
class Shotshell(Cartridge):
    diameter : float
    pellets  : int

    model     = 3
    ballistic = 0.0

    def __post_init__(self):
        self.area = 0.25 * pi * self.diameter * self.diameter

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

def digits(n, base = 10):
    if n == 0:
        yield 0
    while n > 0:
        yield n % base
        n //= base

from string import ascii_uppercase

def encode(n, key = ascii_uppercase):
    return "".join(map(key.__getitem__, digits(n, base = len(key))))

from itertools import count
itemidpool = map(encode, count())

class Item:
    def __init__(self):
        self.id = next(itemidpool)
        self.persistent = True

    def mark_renewable(self):
        self.persistent = False

    def apply(self, player):
        pass

    def mass(self):
        raise NotImplementedError

    def print(self):
        return self.name

class CartridgeBox(Item):
    def __init__(self, o, capacity = 0):
        Item.__init__(self)

        self.object   = o
        self.capacity = capacity

    def pop(self):
        if self.capacity > 0:
            self.capacity -= 1
            return self.object

    @property
    def mass(self):
        return self.capacity * self.object.totmass

    def print(self):
        return f"{self.object.name} Box ({self.capacity})"

class Inventory:
    def __init__(self):
        self.data = deque()

    def __iter__(self):
        return iter(self.data)

    def __getitem__(self, ID):
        return next(filter(lambda x: x.id == ID.upper(), self.data), None)

    def find(self, typ):
        return next(filter(lambda x: isinstance(x, typ), self.data), None)

    def remove(self, o):
        self.data.remove(o)

    def remove_if(self, pred):
        self.data = deque(filter(lambda o: not pred(o), self.data))

    def pop(self, typ):
        if o := self.find(typ):
            self.data.remove(o)
            return o

    def clear(self):
        self.data.clear()

    def extend(self, it):
        self.data.extend(it)

    def push(self, o):
        self.data.append(o)
        return o

    def empty(self):
        return not bool(self.data)

class ItemEntity(Inventory):
    def __init__(self, protocol, x, y, z):
        Inventory.__init__(self)

        self.x, self.y, self.z = x, y, z
        self.protocol = protocol

    def remove_if_empty(self):
        if self.empty():
            self.protocol.remove_item_entity(
                self.x, self.y, self.z
            )

    def remove(self, o):
        Inventory.remove(self, o)
        self.remove_if_empty()

    def remove_if(self, pred):
        Inventory.remove_if(self, pred)
        self.remove_if_empty()

    def pop(self, typ):
        o = Inventory.remove(self, typ)
        self.remove_if_empty()

        return o

    def clear(self, pred):
        Inventory.clear(self)
        self.remove_if_empty()

class Magazine(Item):
    capacity = NotImplemented

    @property
    def mass(self):
        raise NotImplementedError

    def current(self):
        raise NotImplementedError

    def reserved(self, i):
        raise NotImplementedError

    def can_reload(self, i):
        return 0 < self.reserved(i) and self.current() < self.capacity

def icons(x, xs):
    yield x
    yield from xs

class BoxMagazine(Magazine):
    continuous = False
    cartridge  = NotImplemented

    def __init__(self):
        Magazine.__init__(self)

        self._current = 0
        self.restock()

    def reload(self, i):
        if succ := i.pop(type(self)):
            i.push(self) # TODO: skip empty magazines
            return succ, False

        return self, False

    def current(self):
        return self._current

    def reserved(self, i):
        return sum(map(lambda o: o.current(), filter(lambda o: isinstance(o, type(self)), i)))

    def eject(self):
        if self._current > 0:
            self._current -= 1
            return self.cartridge

    def restock(self):
        self._current = self.capacity

    @property
    def mass(self):
        return self._mass + self._current * self.cartridge.totmass

    def info(self, i):
        res = filter(lambda o: isinstance(o, type(self)), i)
        return "Magazines: " + ", ".join(icons(
            str(self.current()) + "*",
            map(lambda o: str(o.current()), res)
        ))

    def print(self):
        return f"{self.name} ({self._current})"

class TubularMagazine(Magazine):
    continuous = True
    cartridge  = NotImplemented

    def __init__(self):
        Magazine.__init__(self)

        self.container = deque()

    def find(self, i):
        it = filter(
            lambda o: isinstance(o, CartridgeBox) and \
                      isinstance(o.object, self.cartridge) and \
                      o.capacity > 0,
            i
        )

        return next(it, None)

    def push(self, o):
        self.container.appendleft(o)

    def reload(self, i):
        if self.capacity <= self.current():
            return self, False

        if o := self.find(i):
            self.push(o.pop())
            return self, True

        return self, False

    def current(self):
        return len(self.container)

    def reserved(self, i):
        return sum(map(
            lambda o: o.capacity,
            filter(lambda o: isinstance(o, CartridgeBox) and \
                             isinstance(o.object, self.cartridge), i)
        ))

    def eject(self):
        if bool(self.container):
            return self.container.popleft()

    def restock(self):
        raise NotImplementedError

    @property
    def mass(self):
        return sum(map(lambda o: o.totmass, self.container))

    def info(self, i):
        rem = self.reserved(i)
        return f"{rem} round(s) in reserve"

class Tool:
    def on_lmb_press(self):
        pass

    def on_lmb_release(self):
        pass

    def on_sneak_press(self):
        pass

    def on_sneak_release(self):
        pass

    def on_rmb_press(self):
        pass

    def on_rmb_release(self):
        pass

    def on_lmb_hold(self, t, dt):
        pass

    def on_rmb_hold(self, t, dt):
        pass

    def on_sneak_hold(self, t, dt):
        pass

def dig(player, mu, dt, x, y, z):
    if not player.world_object or player.world_object.dead: return

    sigma = 0.01 if player.world_object.crouch else 0.05
    value = max(0, gauss(mu = mu, sigma = sigma) * dt)

    protocol = player.protocol

    if protocol.simulator.dig(x, y, z, value):
        protocol.onDestroy(player.player_id, x, y, z)

class SpadeTool(Tool):
    mass = 0.750

    def __init__(self, player):
        self.player = player

    def enabled(self):
        arml, armr = self.player.body.arml, self.player.body.armr
        return (not arml.fractured or arml.splint) and \
               (not armr.fractured or armr.splint)

    def on_lmb_hold(self, t, dt):
        if self.enabled():
            if loc := self.player.world_object.cast_ray(4.0):
                dig(self.player, dt, 1.0, *loc)

    def on_rmb_hold(self, t, dt):
        if self.enabled():
            if loc := self.player.world_object.cast_ray(4.0):
                x, y, z = loc
                dig(self.player, dt, 0.7, x, y, z - 1)
                dig(self.player, dt, 0.7, x, y, z)
                dig(self.player, dt, 0.7, x, y, z + 1)

class BlockTool(Tool):
    mass = 0

    def __init__(self, player):
        self.player = player

class GrenadeTool(Tool):
    def __init__(self, player):
        self.player = player

    @property
    def mass(self):
        return 0.600 * self.player.grenades

class TileEntity:
    def __init__(self, protocol, position):
        self.protocol = protocol
        self.position = position

    def on_explosion(self):
        pass

    def on_pressure(self):
        pass

    def on_destroy(self):
        self.protocol.remove_tile_entity(*self.position)
