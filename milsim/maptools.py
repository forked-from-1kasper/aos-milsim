from random import uniform, choice, shuffle
from itertools import product
from math import floor

from pyspades.constants import BLUE_FLAG, GREEN_FLAG, BLUE_BASE, GREEN_BASE

from milsim.common import *

def failure(conn):
    return NotImplementedError

def Location(x, y, z):
    def Implementation(conn):
        return (x, y, z)

    return Implementation

def uniform2(M, xmin, xmax, ymin, ymax):
    x = floor(uniform(xmin, xmax))
    y = floor(uniform(ymin, ymax))
    z = M.get_z(x, y)
    return x, y, z

def Rectangle(x1 = 0, y1 = 0, x2 = 512, y2 = 512):
    xmin, xmax = min(x1, x2), max(x1, x2)
    ymin, ymax = min(y1, y2), max(y1, y2)

    def Implementation(conn):
        return uniform2(conn.protocol.map, xmin, xmax, ymin, ymax)

    return Implementation

def is_location_free(M, w):
    x, y, z = w
    return M.get_solid(x, y, z - 3) == 0 and \
           M.get_solid(x, y, z - 2) == 0 and \
           M.get_solid(x, y, z - 1) == 0 and \
           M.get_solid(x, y, z - 0) == 1

def Bitmap(x1 = 0, y1 = 0, x2 = 512, y2 = 512, zs = []):
    xmin, xmax = min(x1, x2), max(x1, x2)
    ymin, ymax = min(y1, y2), max(y1, y2)

    L0 = list(product(range(xmin, xmax + 1), range(ymin, ymax + 1), zs))

    def Implementation(conn):
        # Not the most performant solution but *seems* to be robust enough.
        L = list(filter(lambda w: is_location_free(conn.protocol.map, w), L0))
        return choice(L) if len(L) > 0 else uniform2(conn.protocol.map, xmin, xmax, ymin, ymax)

    return Implementation

def Team(blue = failure, green = failure):
    def Implementation(conn):
        if conn.team is conn.protocol.green_team:
            return green(conn)
        elif conn.team is conn.protocol.blue_team:
            return blue(conn)
        else:
            return conn.get_spawn_location()

    return Implementation

def Random(*fns):
    def Implementation(*w, **kw):
        fn = choice(fns)
        return fn(*w, **kw)

    return Implementation

default = (0, 0, 0)

def Entity(blue_flag = default, green_flag = default, blue_base = default, green_base = default):
    take = lambda o: choice(o) if isinstance(o, list) else o

    def Implementation(team, eid):
        x, y, z = take(blue_flag)  if eid == BLUE_FLAG  else \
                  take(green_flag) if eid == GREEN_FLAG else \
                  take(blue_base)  if eid == BLUE_BASE  else \
                  take(green_base) if eid == GREEN_BASE else \
                  default

        return x, y, team.protocol.map.get_z(x, y, z)

    return Implementation