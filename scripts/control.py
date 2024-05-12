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
            protocol.sim.invokeOnTrace(protocol.onTrace)
            return "Debug is turned on."
        elif value == 'off':
            protocol.sim.invokeOnTrace(None)
            return "Debug is turned off."
        else:
            return usage

    @staticmethod
    def stats(protocol, *w):
        return "Total: %d, alive: %d, lag: %.2f us, peak: %.2f us" % (
            protocol.sim.total(),
            protocol.sim.alive(),
            protocol.sim.lag(),
            protocol.sim.peak(),
        )

    @staticmethod
    def flush(protocol, *w):
        alive = protocol.sim.alive()
        protocol.sim.flush()

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
        block = conn.protocol.sim.get(*loc)
        return f"Material: {block.material.name}, durability: {block.durability:.2f}, crumbly: {yn(block.material.crumbly)}."
    else:
        return "Block is too far."

@command()
def shoot(conn, what):
    if not conn.hp: return

    where = {
        "torso": Limb.torso,
        "head":  Limb.head,
        "arml":  Limb.arml,
        "armr":  Limb.armr,
        "legl":  Limb.legl,
        "legr":  Limb.legr
    }.get(what)

    if where is not None:
        conn.hit(5, kill_type = MELEE_KILL, fractured = True, limb = where)
    else:
        return "Usage: /shoot (torso|head|arml|armr|legl|legr)"

def apply_script(protocol, connection, config):
    return protocol, connection