from random import uniform, choice, shuffle
from itertools import product
from math import floor


from pyspades.constants import BLUE_FLAG, GREEN_FLAG, BLUE_BASE, GREEN_BASE

from milsim.common import *

def Confined(func):
    neighbours = list(product(range(-3, 4), repeat = 2))

    def Implementation(conn):
        x, y, z = func(conn)

        if conn.is_location_free(x, y, z):
            return (x, y, z)

        shuffle(neighbours)
        for dx, dy in neighbours:
            if conn.is_location_free(x + dx, y + dy, z):
                return (x + dx, y + dy, z)

        return (x, y, z)

    return Implementation

def failure(conn):
    return NotImplementedError

def Location(x, y, z):
    def Implementation(conn):
        return (x, y, z)

    return Implementation

def Rectangle(x1 = 0, y1 = 0, x2 = 512, y2 = 512, zs = None):
    xmin, xmax = min(x1, x2), max(x1, x2)
    ymin, ymax = min(y1, y2), max(y1, y2)

    def Implementation(conn):
        x = floor(uniform(xmin, xmax))
        y = floor(uniform(ymin, ymax))
        z = conn.protocol.map.get_z(x, y) if zs is None else choice(zs)
        return (x, y, z)

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

def Random(*argv):
    def Implementation(conn):
        fun = choice(argv)
        return fun(conn)

    return Implementation

default = (0, 0, 0)

def Entity(blue_flag = default, green_flag = default, blue_base = default, green_base = default):
    def Implementation(team, eid):
        if eid == BLUE_FLAG:
            return blue_flag
        if eid == GREEN_FLAG:
            return green_flag
        if eid == BLUE_BASE:
            return blue_base
        if eid == GREEN_BASE:
            return green_base

    return Implementation