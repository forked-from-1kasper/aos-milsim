from math import fmod, acos, degrees

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

@command()
@player_only
def health(conn):
    """
    Report health status
    /health
    """
    if conn.ingame():
        return " ".join(map(ppBodyPart, conn.body.values()))

@command()
@player_only
def weapon(conn):
    """
    Print remaining ammo status
    /weapon
    """
    if o := conn.weapon_object:
        return o.ammo.info()

@command('bandage', 'b')
@player_only
def bandage(conn):
    """
    Put the bandage (used to stop venous bleeding)
    /b or /bandage
    """
    if not conn.ingame(): return

    if not conn.body.bleeding():
        return "You are not bleeding."

    if conn.bandage <= 0:
        return "You do not have a bandage."

    for P in conn.body.values():
        if P.arterial or P.venous:
            P.venous = False
            conn.bandage -= 1
            return f"You have bandaged your {P.label}."

@command('tourniquet', 't')
@player_only
def tourniquet(conn):
    """
    Put the tourniquet (used to stop arterial bleeding)
    /t or /tourniquet
    """
    if not conn.ingame(): return

    if not conn.body.bleeding():
        return "You are not bleeding."

    if conn.tourniquet <= 0:
        return "You do not have a tourniquet."

    for P in conn.body.values():
        if P.arterial:
            P.arterial = False
            conn.tourniquet -= 1
            return f"You put a tourniquet on your {P.label}."

@command('splint', 's')
@player_only
def splint(conn):
    """
    Splint a broken limb
    /s or /splint
    """
    if not conn.ingame(): return

    if not conn.body.fractured():
        return "You have no fractures."

    if conn.splint <= 0:
        return "You do not have a split."

    for P in conn.body.values():
        if P.fractured:
            P.splint = True
            conn.splint -= 1
            return f"You put a splint on your {P.label}."

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
@player_only
def fracture(conn, target = None):
    """
    Breaks the specified limb (useful for debug).
    /fracture
    """
    if conn.ingame():
        if limb := limbs.get(target):
            conn.hit(5, kill_type = MELEE_KILL, fractured = True, limb = limb)
        else:
            return "Usage: /fracture (torso|head|arml|armr|legl|legr)"

@command()
@player_only
def vein(conn, target = None):
    """
    Cuts a vein in the specified limb (useful for debug).
    /vein
    """
    if conn.ingame():
        if limb := limbs.get(target):
            conn.body[limb].venous = True
        else:
            return "Usage: /vein (torso|head|arml|armr|legl|legr)"

@command()
@player_only
def artery(conn, target = None):
    """
    Cuts an artery in the specified limb (useful for debug).
    /artery
    """
    if conn.ingame():
        if limb := limbs.get(target):
            conn.body[limb].arterial = True
        else:
            return "Usage: /artery (torso|head|arml|armr|legl|legr)"

@command()
@player_only
def rangefinder(conn):
    """
    Measures the distance between the player and a given point
    /rangefinder
    """

    error = 2.0

    if conn.ingame():
        if loc := conn.world_object.cast_ray(1024):
            # this number is a little wrong, but anyway we’ll truncate the result
            d = conn.world_object.position.distance(Vertex3(*loc))
            m = toMeters(d)
            M = m - fmod(m, error)

            if m < error:
                return "< {:.0f} m".format(error)
            else:
                return "{:.0f} m".format(M)
        else:
            return "Too far."

@command()
@player_only
def protractor(conn):
    """
    Measures the angle between the player and two specified points
    /protractor
    """

    if conn.ingame():
        o = conn.world_object.orientation

        if o.length() < 1e-4:
            return

        if conn.protractor is None:
            conn.protractor = o.normal().copy()
            return "Use /protractor again while facing the second point."
        else:
            t = dot(o.normal(), conn.protractor)
            θ = degrees(acos(t))

            conn.protractor = None
            return "{:.2f} deg".format(θ)

@command()
@player_only
def compass(conn):
    """
    Prints the current azimuth
    /compass
    """

    if conn.ingame():
        o = xOy(conn.world_object.orientation)
        φ = azimuth(conn.protocol.environment, o)
        θ = degrees(φ)
        return "{:.0f} deg, {}".format(θ, needle(φ))

def apply_script(protocol, connection, config):
    class ControlConnection(connection):
        def __init__(self, *w, **kw):
            connection.__init__(self, *w, **kw)
            self.protractor = None

        def on_connect(self):
            self.pos1 = None
            self.pos2 = None

            connection.on_connect(self)

        def on_reload_complete(self):
            if not self.weapon_object.ammo.continuous:
                self.send_chat(self.weapon_object.ammo.info())

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