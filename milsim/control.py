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

from math import floor, fmod, acos, degrees
from itertools import product, islice

import inspect

from horseradish.commands import command, get_player, player_only
from pyspades.constants import MELEE_KILL
from pyspades.common import Vertex3

from milsimlib.items import (
    BandageItem, TourniquetItem, SplintItem,
    RangefinderItem, ProtractorItem, CompassItem,
    HandheldRadioItem, is_reachable
)

from milsimlib.common import (
    apply_item, format_item, format_taken_items, has_item, take_item, take_items,
    alive_only, azimuth, needle, floor3, xOy
)

from milsimlib.underbarrel import GrenadeLauncher, GrenadeItem
from milsimlib.engine import toMeters
from milsimlib.types import Item, ite
from milsimlib.constants import Limb
from milsimlib import ismilsim

yn = lambda b: "yes" if b else "no"

def ppBodyPart(P):
    label = P.abbrev.upper() if P.fractured and not P.splint else P.abbrev
    suffix = ite(P.venous, "*", "") + ite(P.arterial, "**", "")
    return f"{label}{suffix}: {P.hp:.2f}"

@command('position', 'pos')
@alive_only
def position(conn):
    """
    Print the current position on the map
    /position
    """
    return str(conn.world_object.position)

@command()
@alive_only
def health(conn):
    """
    Report health status
    /health
    """
    return " ".join(map(ppBodyPart, conn.body.values()))

def formatMicroseconds(T):
    if T <= 1e+3:
        return "{:.2f} us".format(T)
    elif T <= 1e+6:
        return "{:.2f} ms".format(T / 1e+3)
    else:
        return "{:.2f} s".format(T / 1e+6)

def formatBytes(x):
    if x <= 1024:
        return "{} B".format(x)
    elif x <= 1024 * 1024:
        return "{:.2f} KiB".format(x / 1024)
    else:
        return "{:.2f} MiB".format(x / 1024 / 1024)

class Engine:
    @staticmethod
    def debug(protocol, value = None):
        o = protocol.engine

        if value == 'on':
            o.on_trace = protocol.onTrace
            return "Debug is turned on"
        elif value == 'off':
            o.on_trace = None
            return "Debug is turned off"
        else:
            return "Usage: /engine debug (on|off)"

    @staticmethod
    def stats(protocol):
        o = protocol.engine

        return "Total: {total}, alive: {alive}, lag: {lag}, peak: {peak}, usage: {usage}".format(
            total = o.total,
            alive = o.alive,
            lag   = formatMicroseconds(o.lag),
            peak  = formatMicroseconds(o.peak),
            usage = formatBytes(o.usage)
        )

    @staticmethod
    def flush(protocol):
        alive = protocol.engine.alive()
        protocol.engine.flush()

        return "Removed {} object(s)".format(alive)

@command('engine', admin_only = True)
def engine(connection, subcmd, *w, **kw):
    protocol = connection.protocol

    if method := getattr(Engine, subcmd, None):
        sig = inspect.signature(method)

        try:
            b = sig.bind(protocol, *w, **kw)
        except TypeError:
            return "Wrong number of arguments"

        return method(*b.args, **b.kwargs)
    else:
        return "Unknown command: {}".format(subcmd)

@command()
@alive_only
def lookat(connection):
    """
    Report a given block durability
    /lookat
    """
    if loc := connection.world_object.cast_ray(7.0):
        protocol = connection.protocol

        M, d = protocol.engine[loc]
        return f"Material: {M.name}, durability: {d:.2f}, crumbly: {yn(M.crumbly)}"
    else:
        return "Block is too far"

@command()
def weather(connection):
    """
    Report current weather conditions
    /weather
    """

    protocol = connection.protocol

    o = protocol.engine
    W = protocol.environment.weather

    w = Vertex3(*o.wind)
    θ = azimuth(protocol.environment, xOy(w))

    return "{t:.0f} degrees, {p:.1f} hPa, humidity {φ:.0f} %, wind {v:.1f} m/s ({d}), cloud cover {k:.0f} %".format(
        t = o.temperature,       # Celsius
        p = o.pressure / 100,    # hPa
        φ = o.humidity * 100,    # %
        v = w.length(),          # m/s
        d = needle(θ),           # N/E/S/W
        k = W.cloudiness() * 100 # %
    )

limbs = {
    "torso": Limb.torso,
    "head":  Limb.head,
    "arml":  Limb.arml,
    "armr":  Limb.armr,
    "legl":  Limb.legl,
    "legr":  Limb.legr
}

@command('fracture')
@alive_only
def c_fracture(player, target = None):
    """
    Break the specified limb (useful for debug)
    /fracture
    """
    if limb := limbs.get(target):
        player.hit(5, kill_type = MELEE_KILL, fractured = True, limb = limb)
    else:
        return "Usage: /fracture (torso|head|arml|armr|legl|legr)"

@command('vein')
@alive_only
def c_vein(player, target = None):
    """
    Cut a vein in the specified limb (useful for debug)
    /vein
    """
    if limb := limbs.get(target):
        player.body[limb].venous = True
    else:
        return "Usage: /vein (torso|head|arml|armr|legl|legr)"

@command('artery')
@alive_only
def c_artery(player, target = None):
    """
    Cut an artery in the specified limb (useful for debug)
    /artery
    """
    if limb := limbs.get(target):
        player.body[limb].arterial = True
    else:
        return "Usage: /artery (torso|head|arml|armr|legl|legr)"

@command('bandage', 'b')
@alive_only
def c_bandage(player, nickname = None):
    """
    Put the bandage (used to stop venous bleeding)
    /b or /bandage [player]
    """
    return apply_item(BandageItem, player, nickname, errmsg = "You do not have a bandage")

@command('tourniquet', 't')
@alive_only
def c_tourniquet(player, nickname = None):
    """
    Put the tourniquet (used to stop arterial bleeding)
    /t or /tourniquet [player]
    """
    return apply_item(TourniquetItem, player, nickname, errmsg = "You do not have a tourniquet")

@command('splint', 's')
@alive_only
def c_splint(player, nickname = None):
    """
    Splint a broken limb
    /s or /splint [player]
    """
    return apply_item(SplintItem, player, nickname, errmsg = "You do not have a splint")

@command('rangefinder', 'rf')
@alive_only
def c_rangefinder(player):
    """
    Measure the distance between the player and a given point
    /rangefinder
    """
    return apply_item(RangefinderItem, player, errmsg = "You do not have a rangefinder")

@command('protractor')
@alive_only
def c_protractor(player):
    """
    Measure the angle between the player and two specified points
    /protractor
    """
    return apply_item(ProtractorItem, player, errmsg = "You do not have a protractor")

@command('compass')
@alive_only
def c_compass(player):
    """
    Print the current azimuth
    /compass
    """
    return apply_item(CompassItem, player, errmsg = "You do not have a compass")

@command('grenade', 'gr')
@alive_only
def c_grenade(player):
    """
    Load a grenade into a grenade launcher
    /gr or /grenade
    """
    return apply_item(GrenadeItem, player, errmsg = "You do not have a grenade")

@command('launcher', 'gl')
@alive_only
def c_launcher(player):
    """
    Equip a grenade launcher
    /gl or /launcher
    """
    return apply_item(GrenadeLauncher, player, errmsg = "You do not have a grenade launcher")

def take_grenade_launcher(player, n):
    iu = player.weapon_object.item_underbarrel

    if not isinstance(iu, GrenadeLauncher) and not has_item(player, GrenadeLauncher):
       yield from take_item(player, GrenadeLauncher)

    yield from take_items(player, GrenadeItem, n, 3)

@command('takegrenade', 'tg')
@alive_only
def c_takegrenade(player, argval = 1):
    """
    Try to take a given number of grenades and a grenade launcher
    /tg [n] or /takegrenade
    """

    n = int(argval)

    if n <= 0: return "Invalid number of grenades"
    return format_taken_items(take_grenade_launcher(player, n))

@command('takeradio', 'tra')
@alive_only
def c_takeradio(player):
    """
    Try to take and equip a handheld radio
    /tra or /takeradio
    """

    if wt := player.handheld_radio_item:
        return "You already have an equipped radio"

    for o in take_item(player, HandheldRadioItem):
        return o.apply(player)

    return "No radio found"

@command('underbarrel', 'ub')
@alive_only
def underbarrel(player):
    """
    Print equipped underbarrel item
    /ub or /underbarrel
    """

    return "Underbarrel: {}".format(format_item(player.weapon_object.item_underbarrel))

@command('packload', 'gearmass', 'plo', 'gma')
@alive_only
def packload(player):
    """
    Print player's gear weight
    /packload or /gearmass
    """

    return "{:.3f} kg".format(player.gear_mass())

items_per_page = 3

def format_page(pagenum, i):
    it = islice(i, items_per_page * (pagenum - 1), items_per_page * pagenum)
    return "{}) {}".format(pagenum, ", ".join(map(format_item, it)))

def query(target, i):
    for k, o in enumerate(i):
        if target.lower() in o.name.lower():
            return k // items_per_page + 1

def available(player):
    for i in player.get_available_inventory():
        yield from i

def scroll(player, argval = None, direction = 0):
    if argval is None:
        return max(1, player.page + direction)
    elif argval.isdigit():
        return max(1, int(argval))
    else:
        return query(argval, available(player)) or max(1, player.page)

@command('next', 'n')
@alive_only
def c_next(player, argval = None):
    """
    Scroll to the next or specified page
    /n [page number | search query] or /next
    """

    player.page = scroll(player, argval, +1)
    return format_page(player.page, available(player))

@command('prev', 'p')
@alive_only
def c_prev(player, argval = None):
    """
    Scroll to the previous or specified page
    /p [page number | search query] or /prev
    """

    player.page = scroll(player, argval, -1)
    return format_page(player.page, available(player))

@command('backpack', 'bp')
@alive_only
def c_backpack(player, argval = None):
    """
    Print specified page in the player's inventory
    /bp [page number | search query] or /backpack
    """

    if argval is None:
        page = 1
    elif argval.isdigit():
        page = int(argval)
    else:
        page = query(argval, player.inventory)

    return format_page(page, player.inventory)

@command('take')
@alive_only
def c_take(player, ID):
    """
    Take an item with the given ID to the inventory
    /take <ID>
    """

    for i in player.get_available_inventory():
        if o := i[ID]:
            i.remove(o)
            player.inventory.push(o)
            player.sync()

            return "Taken {}".format(format_item(o))

    return "There's no [{}] nearby".format(ID.upper())

@command('drop')
@alive_only
def c_drop(player, ID):
    """
    Drop an item with the given ID from the inventory
    /drop <ID>
    """

    if o := player.drop(ID):
        return "Thrown away {}".format(format_item(o))
    else:
        return "There's no [{}] in your backpack".format(ID.upper())

@command('use', 'u')
@alive_only
def c_use(player, ID, *w, **kw):
    """
    Use an item from the inventory with the given ID
    /u <ID> or /use
    """

    if o := player.inventory[ID]:
        sig = inspect.signature(o.apply)

        try:
            b = sig.bind(player, *w, **kw)
        except TypeError:
            return "Wrong number of arguments"

        return o.apply(*b.args, **b.kwargs)
    else:
        return "There's no [{}] in your backpack".format(ID.upper())

@command('prioritize', 'pr')
@alive_only
def c_prioritize(player, ID):
    """
    Give the highest priority to an item with the given ID
    /pr <ID> or /priority
    """

    i = player.inventory

    if o := i[ID]:
        i.remove(o)
        i.push(o)
    else:
        return "There's no [{}] in your backpack".format(ID.upper())

@command('handover', 'hdo')
@alive_only
def c_handover(player, nickname, ID):
    """
    Hand an item with the given ID over to the given player
    /hdo <nickname> <ID> or /handover
    """

    protocol = player.protocol
    target = get_player(protocol, nickname)

    if target is player:
        return "{} is you".format(target.name)

    if errmsg := is_reachable(player, target):
        return errmsg

    i1 = player.inventory
    i2 = target.inventory

    if o := i1[ID]:
        i1.remove(o)
        i2.push(o)

        player.sync()
        target.sync()

        target.send_chat(
            "{} has handed [{}] over to you".format(player.name, ID.upper())
        )
        return "You have handed [{}] over to {}".format(ID.upper(), target.name)
    else:
        return "There's no [{}] in your backpack".format(ID.upper())

from scripts.toolbox import c_globals, format_exception

@command(admin_only = True)
def give(connection, nickname, *w):
    """
    Give an item to the specific player
    /give <player> <item>
    """

    protocol = connection.protocol
    player = get_player(protocol, nickname)

    if player.alive():
        try:
            o = eval(' '.join(w), c_globals(connection))
        except Exception as exc:
            return format_exception(exc)

        if isinstance(o, Item):
            player.inventory.push(o)
            player.sync()

            return "Given {} to {}".format(format_item(o), player.name)
        else:
            return "milsimlib.types.Item instance expected, got {}: {}".format(
                type(o).__name__, o
            )

@command()
@alive_only
def sync(connection):
    """
    Restore block count
    /sync
    """

    connection.sync()

@command('togglespade', 'ts')
@player_only
def togglespade(connection):
    """
    Toggle spade friendly fire
    /togglespade /ts
    """

    connection.spade_friendly_fire = not connection.spade_friendly_fire
    return "Spade friendly fire is {} now".format("enabled" if connection.spade_friendly_fire else "disabled")

@command('heal', admin_only = True)
def c_heal(connection, nickname = None):
    """
    Heal you or a given player
    /heal [player]
    """

    protocol = connection.protocol
    player = get_player(protocol, nickname)

    if player.alive():
        player.body.reset()

        protocol.broadcast_chat(
            "{} has been healed by {}".format(player.name, connection.name)
        )

@command('refill', admin_only = True)
def c_refill(connection, nickname = None):
    """
    Refill you or a given player
    /refill [player]
    """

    protocol = connection.protocol
    player = get_player(protocol, nickname)

    if player.alive():
        player.refill()

        protocol.broadcast_chat(
            "{} has been refilled by {}".format(player.name, connection.name)
        )

def apply_script(protocol, connection, config):
    assert ismilsim(protocol, connection)

    class ControlConnection(connection):
        def __init__(self, *w, **kw):
            self.previous_grid_position = None
            self.page = 0

            connection.__init__(self, *w, **kw)

        def on_position_update(self):
            r = self.world_object.position
            grid_position = floor3(r)

            if grid_position != self.previous_grid_position:
                self.page = 0

            self.previous_grid_position = grid_position

            connection.on_position_update(self)

        def on_reload_complete(self):
            if reply := self.weapon_object.format_ammo():
                self.send_chat(reply)

            connection.on_reload_complete(self)

        def on_flag_taken(self):
            x, y, z = floor3(self.team.other.flag)

            for Δx, Δy in product(range(-1, 2), range(-1, 2)):
                if e := self.protocol.get_tile_entity(x + Δx, y + Δy, z):
                    e.on_pressure()

            connection.on_flag_taken(self)

    return protocol, ControlConnection