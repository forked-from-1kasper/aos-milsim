from piqueserver.commands import command
from pyspades.constants import *
from milsim.common import *

yn = lambda b: "yes" if b else "no"

def ppBodyPart(P):
    label = P.abbrev.upper() if P.fractured and not P.splint else P.abbrev
    suffix = ite(P.venous, "*", "") + ite(P.arterial, "**", "")
    return f"{label}{suffix}: {P.hp:.2f}"

@command()
def health(conn):
    try:
        if conn.world_object is not None and not conn.world_object.dead:
            return " ".join(map(ppBodyPart, conn.body.values()))
    except AttributeError:
        return "Body not initialized."

@command()
def weapon(conn):
    if conn.weapon_object is not None:
        return conn.weapon_object.ammo.info()

@command('bandage', 'b')
def bandage(conn):
    if not conn.hp: return

    if not conn.bleeding():
        return "You are not bleeding."

    if conn.bandage <= 0:
        return "You do not have a bandage."

    for P in conn.body.values():
        if P.arterial or P.venous:
            P.venous = False
            conn.bandage -= 1
            return f"You have bandaged your {P.label}."

@command('tourniquet', 't')
def tourniquet(conn):
    if not conn.hp: return

    if not conn.bleeding():
        return "You are not bleeding."

    if conn.tourniquet <= 0:
        return "You do not have a tourniquet."

    for P in conn.body.values():
        if P.arterial:
            P.arterial = False
            conn.tourniquet -= 1
            return f"You put a tourniquet on your {P.label}."

@command('splint', 's')
def splint(conn):
    if not conn.hp: return

    if not conn.fractured():
        return "You have no fractures."

    if conn.splint <= 0:
        return "You do not have a split."

    for P in conn.body.values():
        if P.fractured:
            P.splint = True
            conn.splint -= 1
            return f"You put a splint on your {P.label}."

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
        return "Total: %d, alive: %d, lag: %.2f us, peak: %.2f us" % (
            protocol.simulator.total(),
            protocol.simulator.alive(),
            protocol.simulator.lag(),
            protocol.simulator.peak(),
        )

    @staticmethod
    def flush(protocol, *w):
        alive = protocol.simulator.alive()
        protocol.simulator.flush()

        return "Removed %d object(s)" % alive

@command('engine', admin_only=True)
def engine(conn, subcmd, *w):
    protocol = conn.protocol

    if hasattr(Engine, subcmd):
        return getattr(Engine, subcmd)(protocol, *w)
    else:
        return "Unknown command: %s" % str(subcmd)

@command()
def lookat(conn):
    if not conn.world_object: return
    loc = conn.world_object.cast_ray(7.0)

    if loc is not None:
        block = conn.protocol.simulator.get(*loc)
        return f"Material: {block.material.name}, durability: {block.durability:.2f}, crumbly: {yn(block.material.crumbly)}."
    else:
        return "Block is too far."

@command()
def weather(conn):
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
def fracture(conn, target):
    if not conn.hp: return

    limb = limbs.get(target)

    if limb is not None:
        conn.hit(5, kill_type = MELEE_KILL, fractured = True, limb = limb)
    else:
        return "Usage: /fracture (torso|head|arml|armr|legl|legr)"

@command()
def vein(conn, target):
    if not conn.hp: return

    limb = limbs.get(target)

    if limb is not None:
        conn.body[limb].venous = True
    else:
        return "Usage: /vein (torso|head|arml|armr|legl|legr)"

@command()
def artery(conn, target):
    if not conn.hp: return

    limb = limbs.get(target)

    if limb is not None:
        conn.body[limb].arterial = True
    else:
        return "Usage: /artery (torso|head|arml|armr|legl|legr)"

def apply_script(protocol, connection, config):
    return protocol, connection