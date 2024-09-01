from math import floor, fmod, acos, degrees
from itertools import product, islice

from piqueserver.commands import command, player_only
from pyspades.common import Vertex3
from pyspades.constants import *

from milsim.simulator import toMeters
from milsim.constants import Limb
from milsim.common import *

WARNING_ON_KILL = "/b for bandage, /t for tourniquet, /s for splint"

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

@command()
@alive_only
def weapon(conn):
    """
    Print remaining ammo status
    /weapon
    """
    if o := conn.weapon_object:
        return o.magazine.info(conn.inventory)

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
    def debug(protocol, *w):
        usage = "Usage: /engine debug (on|off)"

        try:
            (value,) = w
        except ValueError:
            return usage

        if value == 'on':
            protocol.simulator.invokeOnTrace(protocol.onTrace)
            return "Debug is turned on."
        elif value == 'off':
            protocol.simulator.invokeOnTrace(None)
            return "Debug is turned off."
        else:
            return usage

    @staticmethod
    def stats(protocol, *w):
        return "Total: {total}, alive: {alive}, lag: {lag}, peak: {peak}, usage: {usage}".format(
            total = protocol.simulator.total(),
            alive = protocol.simulator.alive(),
            lag   = formatMicroseconds(protocol.simulator.lag()),
            peak  = formatMicroseconds(protocol.simulator.peak()),
            usage = formatBytes(protocol.simulator.usage())
        )

    @staticmethod
    def flush(protocol, *w):
        alive = protocol.simulator.alive()
        protocol.simulator.flush()

        return "Removed {} object(s)".format(alive)

@command('engine', admin_only = True)
def engine(conn, subcmd, *w):
    protocol = conn.protocol

    if hasattr(Engine, subcmd):
        return getattr(Engine, subcmd)(protocol, *w)
    else:
        return "Unknown command: {}".format(subcmd)

@command()
@player_only
def lookat(conn):
    """
    Report a given block durability
    /lookat
    """
    if loc := conn.world_object.cast_ray(7.0):
        block = conn.protocol.simulator.get(*loc)
        return f"Material: {block.material.name}, durability: {block.durability:.2f}, crumbly: {yn(block.material.crumbly)}."
    else:
        return "Block is too far."

@command()
def weather(conn):
    """
    Report current weather conditions
    /weather
    """

    o = conn.protocol.simulator
    W = conn.protocol.environment.weather

    wind = o.wind()
    θ = azimuth(conn.protocol.environment, xOy(wind))

    t = o.temperature()      # Celsius
    p = o.pressure() / 100   # hPa
    φ = o.humidity() * 100   # %
    v = wind.length()        # m/s
    d = needle(θ)            # N/E/S/W
    k = W.cloudiness() * 100 # %

    return f"{t:.0f} degrees, {p:.1f} hPa, humidity {φ:.0f} %, wind {v:.1f} m/s ({d}), cloud cover {k:.0f} %"

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
    Breaks the specified limb (useful for debug)
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
    Cuts a vein in the specified limb (useful for debug)
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
    Cuts an artery in the specified limb (useful for debug)
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
    Measures the distance between the player and a given point
    /rangefinder
    """
    return apply_item(RangefinderItem, conn, errmsg = "You do not have a rangefinder")

@command()
@alive_only
def protractor(conn):
    """
    Measures the angle between the player and two specified points
    /protractor
    """
    return apply_item(ProtractorItem, conn, errmsg = "You do not have a protractor")

@command()
@alive_only
def compass(conn):
    """
    Prints the current azimuth
    /compass
    """
    return apply_item(CompassItem, conn, errmsg = "You do not have a compass")

@command()
@alive_only
def packload(conn):
    L = conn.packload()
    return f"{L:.3f} kg"

def format_item(o):
    if o.persistent:
        return "[{}] {}".format(o.id, o.name)
    else:
        return "{{{}}} {}".format(o.id, o.name)

def format_items(pagenum, it):
    return "{}) {}".format(pagenum, ", ".join(map(format_item, it)))

def find(target, it):
    for i, o in enumerate(it):
        if target.lower() in o.name.lower():
            return i // 3 + 1

@command('backpack', 'bp')
@alive_only
def c_backpack(conn, argval = None):
    if argval is None:
        page = 1
    elif argval.isdigit():
        page = int(argval)
    else:
        page = find(argval, conn.inventory)

    it = islice(conn.inventory, 3 * (page - 1), 3 * page)
    return format_items(page, it)

def available(player):
    for i in player.get_available_inventory():
        yield from i

def succpage(player, argval, direction):
    if argval is None:
        return max(1, player.page + direction)
    elif argval.isdigit():
        return max(1, int(argval))
    else:
        return find(argval, available(player)) or max(1, player.page)

@command('next', 'n')
@alive_only
def c_next(conn, argval = None):
    conn.page = succpage(conn, argval, +1)

    it = islice(available(conn), 3 * (conn.page - 1), 3 * conn.page)
    return format_items(conn.page, it)

@command('prev', 'p')
@alive_only
def c_prev(conn, argval = None):
    conn.page = succpage(conn, argval, -1)

    it = islice(available(conn), 3 * (conn.page - 1), 3 * conn.page)
    return format_items(conn.page, it)

@command()
@alive_only
def take(conn, ID):
    for i in conn.get_available_inventory():
        if o := i[ID]:
            i.remove(o)
            conn.inventory.push(o)
            conn.sendWeaponReloadPacket()

            return

@command()
@alive_only
def drop(conn, ID):
    conn.drop(ID)

@command('use', 'u')
@alive_only
def use(conn, ID):
    if o := conn.inventory[ID]:
        return o.apply(conn)

def apply_script(protocol, connection, config):
    class ControlConnection(connection):
        def __init__(self, *w, **kw):
            self.page = 0
            connection.__init__(self, *w, **kw)

        def on_position_update(self):
            self.page = 0
            connection.on_position_update(self)

        def on_reload_complete(self):
            if not self.weapon_object.magazine.continuous:
                self.send_chat(self.weapon_object.magazine.info(self.inventory))

            connection.on_reload_complete(self)

        def on_flag_taken(self):
            flag = self.team.other.flag
            x, y, z = floor(flag.x), floor(flag.y), floor(flag.z)

            for Δx, Δy in product(range(-1, 2), range(-1, 2)):
                if e := self.protocol.get_tile_entity(x + Δx, y + Δy, z):
                    e.on_pressure()

            connection.on_flag_taken(self)

        def on_kill(self, killer, kill_type, grenade):
            if connection.on_kill(self, killer, kill_type, grenade) is False:
                return False

            if kill_type != TEAM_CHANGE_KILL and kill_type != CLASS_CHANGE_KILL:
                self.send_chat(WARNING_ON_KILL)

    return protocol, ControlConnection