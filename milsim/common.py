from math import atan, atan2, tau, floor
from itertools import product
import functools

from pyspades.common import Vertex3

from piqueserver.commands import CommandError

from milsim.constants import Pound, Yard, Inch
from milsim.engine import toMeters
from milsim.types import *

def alive_only(func):
    @functools.wraps(func)
    def _decorated(connection, *w, **kw):
        if connection not in connection.protocol.players.values():
            raise CommandError("only players can use this command")

        if connection.alive():
            return func(connection, *w, **kw)

    return _decorated

def apply_item(klass, player, errmsg = None):
    it = filter(lambda o: isinstance(o, klass), player.inventory)

    if o := next(it, None):
        return o.apply(player)
    else:
        return errmsg

def has_item(player, klass):
    return any(map(lambda o: isinstance(o, klass), player.inventory))

def take_item(player, klass):
    for i, o in player.get_available_items():
        if isinstance(o, klass):
            i.remove(o)
            player.inventory.push(o)

            return

def take_items(player, klass, n, nmax):
    navail = sum(map(lambda o: isinstance(o, klass), player.inventory))

    if nmax <= n + navail: return
    for k in range(n): take_item(player, klass)

toMeters3 = lambda v: Vertex3(toMeters(v.x), toMeters(v.y), toMeters(v.z))

mm    = lambda s: s / 1000
gram  = lambda m: m / 1000
yard  = lambda s: s * Yard
inch  = lambda s: s * Inch
pound = lambda m: m * Pound
grain = lambda m: m * Pound / 7000
TNT   = lambda m: m * 4.6e+6
MOA   = lambda x: x * tau / 360 / 60

isosceles = lambda H, d: atan(0.5 * d / H)

grenade_zone = lambda x, y, z: product(range(x - 1, x + 2), range(y - 1, y + 2), range(z - 1, z + 2))

clamp = lambda m, M, x: max(m, min(M, x))

dot = lambda u, v: u.x * v.x + u.y * v.y + u.z * v.z
xOy = lambda v: Vertex3(v.x, v.y, 0)
xOz = lambda v: Vertex3(v.x, 0, v.z)
yOz = lambda v: Vertex3(0, v.y, v.z)

def clockwise(v1, v2):
    return atan2(v1.x * v2.y - v1.y * v2.x, v1.x * v2.x + v1.y * v2.y)

def azimuth(E, v):
    φ = clockwise(E.north, v)
    return φ if φ > 0 else φ + tau

def needle(φ):
    label = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
    N     = len(label)
    Δφ    = tau / N
    t     = (φ + Δφ / 2) / Δφ
    return label[floor(t) % N]

def icons(x, xs):
    yield x
    yield from xs

ilen   = lambda it: sum(1 for o in it)
iempty = lambda it: next(it, None) is None
