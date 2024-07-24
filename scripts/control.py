from piqueserver.commands import command, player_only
from pyspades.constants import *

from milsim.common import *

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

    if conn.weapon_object is not None:
        return conn.weapon_object.ammo.info()

@command('bandage', 'b')
@player_only
def bandage(conn):
    """
    Put the bandage (used to stop venous bleeding)
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

@command('engine', admin_only=True)
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
    if conn.ingame():
        if limb := limbs.get(target):
            conn.hit(5, kill_type = MELEE_KILL, fractured = True, limb = limb)
        else:
            return "Usage: /fracture (torso|head|arml|armr|legl|legr)"

@command()
@player_only
def vein(conn, target = None):
    if conn.ingame():
        if limb := limbs.get(target):
            conn.body[limb].venous = True
        else:
            return "Usage: /vein (torso|head|arml|armr|legl|legr)"

@command()
@player_only
def artery(conn, target = None):
    if conn.ingame():
        if limb := limbs.get(target):
            conn.body[limb].arterial = True
        else:
            return "Usage: /artery (torso|head|arml|armr|legl|legr)"

def apply_script(protocol, connection, config):
    return protocol, connection