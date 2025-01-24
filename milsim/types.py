from typing import Dict, List, Callable, Tuple
from dataclasses import dataclass, field
from collections.abc import Iterable
from collections import deque

from math import pi, exp, log, inf, nan, floor, prod, sin, cos
from random import random, gauss

from pyspades.color import interpolate_rgb
from pyspades.constants import SPADE_TOOL
from pyspades.common import Vertex3

from milsim.constants import Pound, Inch, Limb
from milsim.engine import Material

randbool = lambda prob: random() <= prob

impl = lambda P, Q: not P or Q
ite = lambda b, v1, v2: v1 if b else v2

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
    default  : Material
    build    : Material
    water    : Material
    size     : Box = field(default_factory = Box)
    palette  : Dict[int, Material] = field(default_factory = dict)
    defaults : Iterable[Tuple[Vector3i, Material]] = field(default_factory = void)
    north    : Vertex3 = Vertex3(1, 0, 0)
    weather  : Weather = field(default_factory = StaticWeather)

    def apply(self, o):
        o.default = self.default
        o.water   = self.water

        o.apply(self.palette)

        for (x, y, z), M in self.defaults:
            o[x, y, z] = M

    def ofPolar(self, r, θ):
        n = self.north
        x = n.x * cos(θ) - n.y * sin(θ)
        y = n.x * sin(θ) + n.y * cos(θ)

        return Vertex3(r * x, r * y, 0)

    @property
    def temperature(self):
        return self.weather.temperature()

    @property
    def pressure(self):
        return self.weather.pressure()

    @property
    def humidity(self):
        return self.weather.humidity()

    @property
    def wind(self):
        v, d = self.weather.wind()
        return self.ofPolar(v, d)

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
    while n > 0:
        rem = (n - 1) % base
        n = (n - rem) // base
        yield rem

from string import ascii_uppercase
def encode(n, key = ascii_uppercase):
    ds = digits(n, base = len(key))
    return "".join(map(key.__getitem__, ds))[::-1]

from itertools import count

class Item:
    idpool = None

    @staticmethod
    def reset():
        Item.idpool = map(encode, count(1))

    def __init__(self):
        self.id = next(Item.idpool)
        self.persistent = True

    def mark_renewable(self):
        self.persistent = False

        return self

    def apply(self, player):
        pass

    def mass(self):
        raise NotImplementedError

    @property
    def name(self):
        raise NotImplementedError

class CartridgeBox(Item):
    def __init__(self, o, current = 0):
        Item.__init__(self)

        self.object   = o
        self._current = current

    def pop(self):
        if self._current > 0:
            self._current -= 1
            return self.object

    def current(self):
        return self._current

    @property
    def mass(self):
        return self._current * self.object.totmass

    @property
    def name(self):
        return f"{self.object.name} Box ({self._current})"

class Inventory:
    def __init__(self):
        self.data = deque()

    def __iter__(self):
        return iter(self.data)

    def __getitem__(self, ID):
        return next(filter(lambda x: x.id == ID.upper(), self.data), None)

    def remove(self, o):
        self.data.remove(o)

    def remove_if(self, pred):
        self.data = deque(filter(lambda o: not pred(o), self.data))

    def clear(self):
        self.data.clear()

    def extend(self, it):
        self.data.extend(it)

    def push(self, o):
        self.data.appendleft(o)
        return o

    def append(self, *w):
        self.data.extend(w)

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

class BoxMagazine(Magazine):
    continuous = False
    basemass   = NotImplemented
    basename   = NotImplemented
    cartridge  = NotImplemented

    def __init__(self):
        Magazine.__init__(self)

        self._current = self.capacity

    def reload(self, i):
        return next(filter(lambda o: o.current() > 0, i), None), False

    def current(self):
        return self._current

    def eject(self):
        if self._current > 0:
            self._current -= 1
            return self.cartridge

    @property
    def mass(self):
        return self.basemass + self._current * self.cartridge.totmass

    @property
    def name(self):
        return f"{self.basename} ({self._current})"

class TubularMagazine(Magazine):
    continuous = True
    cartridge  = NotImplemented

    def __init__(self):
        Magazine.__init__(self)

        self.container = deque()

    def push(self, o):
        self.container.appendleft(o)

    def reload(self, i):
        if self.capacity <= self.current():
            return None, False

        it = filter(lambda o: o.current() > 0, i)

        if o := next(it, None):
            self.push(o.pop())
            return None, True

        return None, False

    def current(self):
        return len(self.container)

    def eject(self):
        if bool(self.container):
            return self.container.popleft()

    @property
    def mass(self):
        return sum(map(lambda o: o.totmass, self.container))

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
        self.player = player

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
