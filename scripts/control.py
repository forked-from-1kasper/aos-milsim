from math import floor, fmod, acos, degrees
from itertools import product, islice

from piqueserver.commands import command, get_player, player_only
from pyspades.common import Vertex3
from pyspades.constants import *

from milsim.items import (
    BandageItem, TourniquetItem, SplintItem,
    RangefinderItem, ProtractorItem, CompassItem
)
from milsim.underbarrel import GrenadeLauncher, GrenadeItem
from milsim.engine import toMeters
from milsim.constants import Limb
from milsim.common import *

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
    def debug(protocol, value):
        o = protocol.engine

        if value == 'on':
            o.on_trace = protocol.onTrace
            return "Debug is turned on."
        elif value == 'off':
            o.on_trace = None
            return "Debug is turned off."
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
def engine(conn, subcmd, *w):
    protocol = conn.protocol

    if attr := getattr(Engine, subcmd, None):
        try:
            return attr(protocol, *w)
        except Exception as e:
            return str(e)
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
        return f"Material: {M.name}, durability: {d:.2f}, crumbly: {yn(M.crumbly)}."
    else:
        return "Block is too far."

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

@command()
@alive_only
def fracture(conn, target = None):
    """
    Break the specified limb (useful for debug)
    /fracture
    """
    if limb := limbs.get(target):
        conn.hit(5, kill_type = MELEE_KILL, fractured = True, limb = limb)
    else:
        return "Usage: /fracture (torso|head|arml|armr|legl|legr)"

@command()
@alive_only
def vein(conn, target = None):
    """
    Cut a vein in the specified limb (useful for debug)
    /vein
    """
    if limb := limbs.get(target):
        conn.body[limb].venous = True
    else:
        return "Usage: /vein (torso|head|arml|armr|legl|legr)"

@command()
@alive_only
def artery(conn, target = None):
    """
    Cut an artery in the specified limb (useful for debug)
    /artery
    """
    if limb := limbs.get(target):
        conn.body[limb].arterial = True
    else:
        return "Usage: /artery (torso|head|arml|armr|legl|legr)"

@command('bandage', 'b')
@alive_only
def bandage(conn):
    """
    Put the bandage (used to stop venous bleeding)
    /b or /bandage
    """
    return apply_item(BandageItem, conn, errmsg = "You do not have a bandage")

@command('tourniquet', 't')
@alive_only
def tourniquet(conn):
    """
    Put the tourniquet (used to stop arterial bleeding)
    /t or /tourniquet
    """
    return apply_item(TourniquetItem, conn, errmsg = "You do not have a tourniquet")

@command('splint', 's')
@alive_only
def splint(conn):
    """
    Splint a broken limb
    /s or /splint
    """
    return apply_item(SplintItem, conn, errmsg = "You do not have a splint")

@command('rangefinder', 'rf')
@alive_only
def rangefinder(conn):
    """
    Measure the distance between the player and a given point
    /rangefinder
    """
    return apply_item(RangefinderItem, conn, errmsg = "You do not have a rangefinder")

@command()
@alive_only
def protractor(conn):
    """
    Measure the angle between the player and two specified points
    /protractor
    """
    return apply_item(ProtractorItem, conn, errmsg = "You do not have a protractor")

@command()
@alive_only
def compass(conn):
    """
    Print the current azimuth
    /compass
    """
    return apply_item(CompassItem, conn, errmsg = "You do not have a compass")

@command('grenade', 'gr')
def grenade(conn):
    """
    Load a grenade into a grenade launcher
    /gr or /grenade
    """
    return apply_item(GrenadeItem, conn, errmsg = "You do not have a grenade")

@command('launcher', 'gl')
def grenade(conn):
    """
    Equip a grenade launcher
    /gl or /launcher
    """
    return apply_item(GrenadeLauncher, conn, errmsg = "You do not have a grenade launcher")

@command('takegrenade', 'tg')
def takegrenade(conn, n = 1):
    """
    Try to take a given number of grenades and a grenade launcher
    /tg [n] or /takegrenade
    """
    n = int(n)

    if n <= 0: return "Invalid number of grenades"

    iu = conn.weapon_object.item_underbarrel

    if not isinstance(iu, GrenadeLauncher) and not has_item(conn, GrenadeLauncher):
       take_item(conn, GrenadeLauncher)

    take_items(conn, GrenadeItem, n, 5)

@command()
@alive_only
def packload(conn):
    return "{:.3f} kg".format(conn.gear_mass())

def format_item(o):
    if o.persistent:
        return "[{}] {}".format(o.id, o.name)
    else:
        return "{{{}}} {}".format(o.id, o.name)

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
def c_next(conn, argval = None):
    """
    Scroll to the next or specified page
    /n [page number | search query] or /next
    """
    conn.page = scroll(conn, argval, +1)
    return format_page(conn.page, available(conn))

@command('prev', 'p')
@alive_only
def c_prev(conn, argval = None):
    """
    Scroll to the previous or specified page
    /p [page number | search qeury] or /prev
    """
    conn.page = scroll(conn, argval, -1)
    return format_page(conn.page, available(conn))

@command('backpack', 'bp')
@alive_only
def c_backpack(conn, argval = None):
    """
    Print specified page in the player's inventory
    /bp [page number | search query] or /backpack
    """
    if argval is None:
        page = 1
    elif argval.isdigit():
        page = int(argval)
    else:
        page = query(argval, conn.inventory)

    return format_page(page, conn.inventory)

@command()
@alive_only
def take(conn, ID):
    """
    Take an item with the given ID to the inventory
    /take (ID)
    """
    for i in conn.get_available_inventory():
        if o := i[ID]:
            i.remove(o)
            conn.inventory.push(o)
            conn.sendWeaponReloadPacket()

            return

@command()
@alive_only
def drop(conn, ID):
    """
    Drop an item with the given ID from the inventory
    /drop (ID)
    """
    conn.drop(ID)

@command('use', 'u')
@alive_only
def use(conn, ID):
    """
    Use an item from the inventory with the given ID
    /u (ID) or /use
    """
    if o := conn.inventory[ID]:
        return o.apply(conn)

@command('prioritize', 'pr')
def prioritize(conn, ID):
    """
    Give the highest priority to an item with the given ID
    /pr (ID) or /priority
    """
    if o := conn.inventory[ID]:
        conn.inventory.remove(o)
        conn.inventory.push(o)

@command(admin_only = True)
def give(connection, nickname, *w):
    """
    Give an item to the specific player
    /give <player> <item>
    """
    protocol = connection.protocol
    player = get_player(protocol, nickname)

    if not player.alive():
        return

    try:
        o = connection.eval(' '.join(w))
    except Exception as exc:
        return protocol.format_exception(exc)

    if not isinstance(o, Item):
        return

    player.inventory.push(o)
    return "Given {} to {}".format(format_item(o), player.name)

def apply_script(protocol, connection, config):
    class ControlConnection(connection):
        def __init__(self, *w, **kw):
            self.previous_grid_position = None
            self.page = 0

            connection.__init__(self, *w, **kw)

        def on_position_update(self):
            r = self.world_object.position
            grid_position = (floor(r.x), floor(r.y), floor(r.z))

            if grid_position != self.previous_grid_position:
                self.page = 0

            self.previous_grid_position = grid_position

            connection.on_position_update(self)

        def on_reload_complete(self):
            if reply := self.weapon_object.format_ammo():
                self.send_chat(reply)

            connection.on_reload_complete(self)

        def on_flag_taken(self):
            flag = self.team.other.flag
            x, y, z = floor(flag.x), floor(flag.y), floor(flag.z)

            for Δx, Δy in product(range(-1, 2), range(-1, 2)):
                if e := self.protocol.get_tile_entity(x + Δx, y + Δy, z):
                    e.on_pressure()

            connection.on_flag_taken(self)

    return protocol, ControlConnection