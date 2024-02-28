from math import pi, exp, sqrt, e, floor, ceil, inf, sin, cos, atan2, asin, prod
from itertools import product, chain

from random import choice, random, gauss, uniform, randint
from dataclasses import dataclass
from typing import Callable

from twisted.internet.error import AlreadyCalled, AlreadyCancelled
from twisted.internet import reactor

from pyspades.collision import distance_3d_vector, vector_collision
from pyspades.packet import register_packet_handler
from pyspades.protocol import BaseConnection
from pyspades import contained as loaders
from pyspades.world import Character
from pyspades.common import Vertex3
from pyspades.constants import *

from piqueserver.commands import command
import milsim.blast as blast

from milsim.simulator import Simulator, cone
from milsim.common import *

ρ      = 1.225 # Air density
factor = 0.5191
g      = 9.81

parts = [TORSO, HEAD, ARMS, LEGS]
names = {TORSO: "torso", HEAD: "head", ARMS: "arms", LEGS: "legs", MELEE: "melee"}

bounded_damage = lambda min: floor(min + (100 - min) * random())

SHOVEL_GUARANTEED_DAMAGE = 50
BLOCK_DESTROY_ENERGY = 2500

WARNING_ON_KILL = [
    "Type /b or /bandage to stop bleeding.",
    "Type /s or /splint to put a splint."
]
NO_WARNING = [TEAM_CHANGE_KILL, CLASS_CHANGE_KILL]

GRENADE_LETHAL_RADIUS = 4
GRENADE_SAFETY_RADIUS = 30

legs_fracture_warning = "You broke your leg."
arms_fracture_warning = "You broke your arm."
bleeding_warning      = "You're bleeding."

#distr = lambda x: (exp(x) - 1) / (e - 1)
#distr = lambda x: log(x + 1) / log(2)
distr = sqrt

clamp = lambda m, M, f: lambda x: max(m, min(M, f(x)))
scale = lambda x, y, f: lambda z: y * f(z / x)

guaranteed_death_energy    = {TORSO: 2500, HEAD: 400, ARMS: 3700, LEGS: 4200}
guaranteed_bleeding_energy = {TORSO:  250, HEAD: 100, ARMS:  200, LEGS:  300}
guaranteed_fracture_energy = {TORSO: 2700, HEAD: 500, ARMS: 4000, LEGS: 4500}

energy_to_damage = lambda part: clamp(0, 100, scale(guaranteed_death_energy[part], 100, distr))
weighted_prob = lambda tbl, part: clamp(0, 1, scale(tbl[part], 1, distr))

randbool = lambda prob: random() <= prob

@dataclass
class Round:
    speed     : float
    mass      : float
    ballistic : float
    caliber   : float
    pellets   : int

    def __post_init__(self):
        self.grenade = False
        self.drag    = (factor * self.mass) / (self.ballistic * (self.caliber ** 2))
        self.area    = (pi / 4) * (self.caliber ** 2)
        self.k       = (ρ * self.drag * self.area) / (2 * self.mass)

class Ammo:
    def total(self):
        return 0

    def current(self):
        return 0

    def reserved(self):
        return self.total() - self.current()

@dataclass
class Magazines(Ammo):
    magazines : int # Number of magazines
    capacity  : int # Number of rounds that fit in the weapon at once

    def __post_init__(self):
        self.continuous = False
        self.loaded     = 0
        self.restock()

    def empty(self):
        return all(map(lambda c: c <= 0, self.container))

    def next(self):
        self.loaded += 1
        self.loaded %= self.magazines

    def reload(self):
        if self.empty():
            return False

        self.next()
        while self.container[self.loaded] <= 0:
            self.next()

        return False

    def full(self):
        return self.total() >= self.capacity * self.magazines

    def current(self):
        return self.container[self.loaded]

    def total(self):
        return sum(self.container)

    def shoot(self, amount):
        avail = self.container[self.loaded]
        self.container[self.loaded] = max(avail - amount, 0)

    def restock(self):
        self.container = [self.capacity] * self.magazines

    def info(self):
        buff = ", ".join(map(str, self.container))
        return f"{self.magazines} magazines: {buff}"

@dataclass
class Heap(Ammo):
    capacity : int # Number of rounds that fit in the weapon at once
    stock    : int # Total number of rounds

    def __post_init__(self):
        self.continuous = True
        self.loaded     = self.capacity
        self.restock()

    def reload(self):
        if self.loaded < self.capacity and self.remaining > 0:
            self.loaded    += 1
            self.remaining -= 1
            return True

        return False

    def full(self):
        return self.total() >= self.stock

    def current(self):
        return self.loaded

    def total(self):
        return self.remaining + self.loaded

    def shoot(self, amount):
        self.loaded = max(self.loaded - amount, 0)

    def restock(self):
        self.remaining = self.stock - self.loaded

    def info(self):
        noun = "rounds" if self.remaining != 1 else "round"
        return f"{self.remaining} {noun} in reserve"

@dataclass
class Gun:
    name               : str                # Name
    ammo               : Callable[[], Ammo] # Ammunition container constructor
    round              : Round              # Ammunition type used by weapon
    delay              : float              # Time between shots
    reload_time        : float              # Time between reloading and being able to shoot again
    spread             : float
    velocity_deviation : float

@dataclass
class Weapon:
    conn            : BaseConnection
    gun             : Gun
    reload_callback : Callable

    def __post_init__(self):
        self.reloading   = False
        self.reload_call = None

        self.shooting    = False
        self.defer       = None

        self.ammo        = None
        self.last_shot   = -inf

        self.reset()

    def restock(self):
        self.ammo.restock()

    def reset(self):
        self.cease()
        self.ready()

        self.shooting  = False
        self.ammo      = self.gun.ammo()
        self.last_shot = -inf

    def set_shoot(self, value : bool) -> None:
        if self.shooting != value:
            if value:
                if self.ammo.continuous:
                    self.ready()

                if self.defer is None:
                    self.fire()
            else:
                self.cease()

        self.shooting = value

    def ready(self):
        if self.reload_call is not None:
            try:
                self.reload_call.cancel()
            except (AlreadyCalled, AlreadyCancelled):
                pass

        self.reloading = False

    def cease(self):
        if self.defer is not None:
            try:
                self.defer.cancel()
            except (AlreadyCalled, AlreadyCancelled):
                pass

            self.defer = None

    def fire(self):
        if not self.conn.world_object:
            return

        if self.conn.cannot_work():
            return

        timestamp = reactor.seconds()

        P = self.ammo.current() > 0
        Q = self.reloading and not self.ammo.continuous
        R = timestamp - self.last_shot >= self.gun.delay
        S = self.conn.world_object.sprint or timestamp - self.conn.last_sprint < 0.5
        T = timestamp - self.conn.last_tool_update < 0.5

        if P and not Q and R and not S and not T:
            self.last_shot = timestamp
            self.ammo.shoot(1)

            n = self.conn.world_object.orientation.normal()
            r = self.conn.eye() + n * 1.2

            for i in range(0, self.gun.round.pellets):
                v = n * gauss(mu = self.gun.round.speed, sigma = self.gun.round.speed * self.gun.velocity_deviation)
                self.conn.protocol.sim.add(self.conn, r, cone(v, self.gun.spread), timestamp, self.gun.round)

        self.defer = reactor.callLater(self.gun.delay, self.fire)

    def reload(self):
        if self.reloading: return

        self.reloading   = True
        self.reload_call = reactor.callLater(self.gun.reload_time, self.on_reload)

    def on_reload(self):
        self.reloading = False

        if self.ammo.continuous:
            if self.ammo.full() or self.shooting:
                return

        again = self.ammo.reload()
        self.reload_callback()

        if again: self.reload()

    def is_empty(self, tolerance=CLIP_TOLERANCE) -> bool:
        return self.ammo.current() <= 0

guns = {
    RIFLE_WEAPON:   Gun("Rifle",   lambda: Magazines(5, 10), Round(850, 10.00/1000, 146.9415,  7.62/1000,  1), 0.50, 2.5,               0, 0.05),
    SMG_WEAPON:     Gun("SMG",     lambda: Magazines(4, 30), Round(600,  8.03/1000, 104.7573,  9.00/1000,  1), 0.11, 2.5,               0, 0.05),
    SHOTGUN_WEAPON: Gun("Shotgun", lambda: Heap(6, 48),      Round(457, 38.00/1000,   5.0817, 18.40/1000, 15), 1.00, 0.5, (2 * pi) * 1e-2, 0.10)
}

@dataclass
class Part:
    hp       : int  = 100
    bleeding : bool = False
    fracture : bool = False
    splint   : bool = False

    def hit(self, value):
        if value <= 0: return
        self.hp = max(0, self.hp - value)

healthy = lambda: {TORSO: Part(), HEAD: Part(), ARMS: Part(), LEGS: Part()}
bleeding_curve = lambda Δt: Δt

@command()
def health(conn, *args):
    try:
        return " ".join(map(lambda part: f"{names[part]}: {conn.body[part].hp:.2f}", parts))
    except AttributeError:
        return "Body not initialized."

@command()
def weapon(conn, *args):
    if conn.weapon_object is not None:
        return conn.weapon_object.ammo.info()

@command('bandage', 'b')
def bandage(conn, *args):
    if not conn.hp: return

    if conn.bandage == 0:
        return "You do not have a bandage."

    for idx, part in conn.body.items():
        if part.bleeding:
            part.bleeding = False
            conn.bandage -= 1
            return f"You have bandaged your {names[idx]}."

    return "You are not bleeding."

@command('splint', 's')
def splint(conn, *args):
    if not conn.hp: return

    if conn.splint == 0:
        return "You do not have a split."

    for idx, part in conn.body.items():
        if part.fracture:
            part.splint  = True
            conn.splint -= 1
            return f"You put a splint on your {names[idx]}."

    return "You have no fractures."

class Engine:
    def debug(protocol, *argv):
        usage = "Usage: /engine debug (on|off)"

        try:
            (value,) = argv
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

    def stats(protocol, *argv):
        return "Total: %d, alive: %d, lag: %.2f us" % (
            protocol.sim.total(),
            protocol.sim.alive(),
            protocol.sim.lag(),
        )

    def flush(protocol, *argv):
        alive = protocol.sim.alive()
        protocol.sim.flush()

        return "Removed %d object(s)" % alive

@command('engine', admin_only=True)
def engine(conn, subcmd, *argv):
    protocol = conn.protocol

    if hasattr(Engine, subcmd):
        return getattr(Engine, subcmd)(protocol, *argv)
    else:
        return "Unknown command: %s" % str(subcmd)

@command()
def shoot(conn, what):
    if not conn.hp: return

    where = {"torso": TORSO, "head": HEAD, "arm": ARMS, "leg": LEGS}.get(what)

    if where is not None:
        conn.hit(20, kill_type=MELEE_KILL, fracture=True, part=where)
    else:
        return "Usage: /shoot (torso|head|arm|leg)"

def apply_script(protocol, connection, config):
    class DamageProtocol(protocol):
        def __init__(self, *arg, **kw):
            protocol.__init__(self, *arg, **kw)
            self.time = reactor.seconds()
            self.sim  = Simulator(self)

        def on_map_change(self, M):
            self.sim.resetMaterials()
            materials = self.map_info.extensions.get('materials', {})

            for color, material in materials.items():
                if isinstance(color, int):
                    self.sim.registerMaterial(color, material)

            self.sim.setDefaultMaterial(materials.get(default))
            self.sim.setBuildMaterial(materials.get(build))

            self.sim.uploadMap()

            return protocol.on_map_change(self, M)

        def on_world_update(self):
            t = reactor.seconds()

            dt = t - self.time

            for _, player in self.players.items():
                if player.last_hp_update is not None and player.hp is not None and player.hp > 0:
                    for _, part in player.body.items():
                        if part.bleeding:
                            part.hit(bleeding_curve(t - player.last_hp_update))

                    if player.tool == SPADE_TOOL and player.world_object and not player.cannot_work():
                        if player.world_object.primary_fire:
                            loc = player.world_object.cast_ray(4.0)
                            if loc: player.dig(dt, 1.0, *loc)

                        if player.world_object.secondary_fire:
                            loc = player.world_object.cast_ray(4.0)
                            if loc:
                                x, y, z = loc
                                player.dig(dt, 0.7, x, y, z - 1)
                                player.dig(dt, 0.7, x, y, z)
                                player.dig(dt, 0.7, x, y, z + 1)

                    hp = player.display()
                    if player.hp != hp:
                        player.set_hp(hp, kill_type=MELEE_KILL)

                player.last_hp_update = t

            if self.sim: self.sim.step(self.time, t)

            self.time = t

            protocol.on_world_update(self)

        def onTrace(self, index, x, y, z, value, origin):
            self.broadcast_contained(
                TracerPacket(index, Vertex3(x, y, z), value, origin = origin),
                rule = hasTraceExtension
            )

        def onDestroy(self, pid, x, y, z):
            if pid not in self.players:
                return

            player = self.players[pid]

            count = self.map.destroy_point(x, y, z)

            if count:
                contained           = loaders.BlockAction()
                contained.x         = x
                contained.y         = y
                contained.z         = z
                contained.value     = DESTROY_BLOCK
                contained.player_id = pid

                self.broadcast_contained(contained, save=True)
                self.update_entities()

                player.on_block_removed(x, y, z)
                player.total_blocks_removed += count

        def onHit(self, thrower, target, part, E, grenade):
            if target not in self.players:
                return

            player    = self.players[target]
            hit_by    = self.players.get(thrower, player)
            kill_type = GRENADE_KILL if grenade else HEADSHOT_KILL if part == HEAD else WEAPON_KILL

            damage, bleeding, fracture = 0, False, False

            if E <= 0:
                return
            else:
                bleeding = randbool(weighted_prob(guaranteed_bleeding_energy, part)(E))
                fracture = randbool(weighted_prob(guaranteed_fracture_energy, part)(E))
                damage   = energy_to_damage(part)(E)

            if damage > 0:
                player.hit(
                    damage, part=part, hit_by=hit_by,
                    bleeding=bleeding, fracture=fracture,
                    kill_type=kill_type
                )

    class DamageConnection(connection):
        def height(self):
            if self.world_object:
                return 1.05 if self.world_object.crouch else 1.1

        def eye(self):
            if o := self.world_object:
                dt = reactor.seconds() - self.last_position_update

                return Vertex3(
                    o.position.x + o.velocity.x * dt,
                    o.position.y + o.velocity.y * dt,
                    o.position.z + o.velocity.z * dt - self.height(),
                )

        def display(self):
            avg = prod(map(lambda P: P.hp / 100, self.body.values()))
            return floor(100 * avg)

        def bleeding(self):
            return any(map(lambda P: P.bleeding, self.body.values()))

        def fracture(self):
            return any(map(lambda P: P.fracture, self.body.values()))

        def can_walk(self):
            legs = self.body[LEGS]
            return (not legs.fracture) or (legs.fracture and legs.splint)

        def cannot_work(self):
            arms = self.body[ARMS]
            return arms.fracture and (not arms.splint)

        def dig(self, mu, dt, x, y, z):
            if not self.world_object: return

            sigma = 0.01 if self.world_object.crouch else 0.05
            value = max(0, gauss(mu = mu, sigma = sigma) * dt)

            if self.protocol.sim.dig(x, y, z, value):
                self.protocol.onDestroy(self.player_id, x, y, z)

        def set_tool(self, tool):
            self.tool           = tool
            contained           = loaders.SetTool()
            contained.player_id = self.player_id
            contained.value     = tool

            self.send_contained(contained)
            self.protocol.broadcast_contained(contained)

        def break_legs(self):
            pass

        def reset_health(self):
            self.last_hp_update = None
            self.body           = healthy()
            self.hp             = 100

            self.bandage = 2
            self.splint  = 1

        def refill(self, local=False):
            for part in self.body.values():
                part.fracture = False
                part.bleeding = False

            self.grenades = 3
            self.blocks   = 50
            self.bandage  = 2
            self.splint   = 1

            self.weapon_object.restock()

            if not local:
                self.send_contained(loaders.Restock())

                self.update_hud()
                self.set_hp(self.display(), kill_type=MELEE_KILL)

        def update_hud(self):
            weapon_reload              = loaders.WeaponReload()
            weapon_reload.player_id    = self.player_id
            weapon_reload.clip_ammo    = self.weapon_object.ammo.current()
            weapon_reload.reserve_ammo = self.weapon_object.ammo.reserved()
            self.send_contained(weapon_reload)

        def hit(self, value, hit_by=None, kill_type=WEAPON_KILL,
                bleeding=False, fracture=False, part=TORSO):
            if hit_by is not None:
                if self.team is hit_by.team:
                    if kill_type == MELEE_KILL: return
                    if not self.protocol.friendly_fire: return

                # So that if a player threw a grenade, and then his arm
                # was broken, this grenade will still deal damage.
                if hit_by.cannot_work() and (kill_type == WEAPON_KILL or
                                             kill_type == HEADSHOT_KILL or
                                             kill_type == MELEE_KILL):
                    return

            self.body[part].hit(value)

            if self.hp is not None and self.hp > 0:
                if fracture and part == ARMS and not self.body[ARMS].fracture:
                    self.send_chat_status(arms_fracture_warning)
                elif bleeding and not self.bleeding():
                    self.send_chat_status(bleeding_warning)

                self.set_hp(self.display(), hit_by=hit_by, kill_type=kill_type)
                self.body[part].bleeding = bleeding
                self.body[part].fracture = fracture

                if part == ARMS and fracture: self.set_tool(SPADE_TOOL)
                if part == LEGS and fracture: self.break_legs()

        def grenade_zone(self, x, y, z):
            return product(range(x - 1, x + 2), range(y - 1, y + 2), range(z - 1, z + 2))

        def grenade_destroy(self, x, y, z):
            if x < 0 or x > 512 or y < 0 or y > 512 or z < 0 or z > 63:
                return False

            if self.on_block_destroy(x, y, z, GRENADE_DESTROY) == False:
                return False

            for x1, y1, z1 in self.grenade_zone(x, y, z):
                count = self.protocol.map.destroy_point(x1, y1, z1)
                if count:
                    self.total_blocks_removed += count
                    self.on_block_removed(x1, y1, z1)

            block_action           = loaders.BlockAction()
            block_action.x         = x
            block_action.y         = y
            block_action.z         = z
            block_action.value     = GRENADE_DESTROY
            block_action.player_id = self.player_id
            self.protocol.broadcast_contained(block_action, save=True)
            self.protocol.update_entities()

            return True

        def grenade_exploded(self, grenade):
            if self.name is None or self.team.spectator:
                return

            blast.explode(GRENADE_LETHAL_RADIUS, GRENADE_SAFETY_RADIUS, self, grenade.position)

            x, y, z = floor(grenade.position.x), floor(grenade.position.y), floor(grenade.position.z)
            self.grenade_destroy(x, y, z)

        def set_weapon(self, weapon, local=False, no_kill=False):
            if weapon not in guns:
                return

            self.weapon = weapon
            if self.weapon_object is not None:
                self.weapon_object.reset()

            self.weapon_object = Weapon(self, guns[weapon], self._on_reload)

            if not local:
                change_weapon = loaders.ChangeWeapon()
                self.protocol.broadcast_contained(change_weapon, save=True)
                if not no_kill: self.kill(kill_type=CLASS_CHANGE_KILL)

        def _on_reload(self):
            if not self.weapon_object.ammo.continuous:
                self.send_chat(self.weapon_object.ammo.info())

            self.update_hud()

        def _on_fall(self, damage):
            if not self.hp: return

            returned = self.on_fall(damage)

            if returned is False: return
            if returned is not None: damage = returned

            self.body[LEGS].hit(damage)
            if randbool(damage / 100):
                self.body[LEGS].fracture = True
                self.send_chat_status(legs_fracture_warning)

            self.break_legs()
            self.set_hp(self.display(), kill_type=FALL_KILL)

        def on_connect(self):
            self.reset_health()

            return connection.on_connect(self)

        def on_block_build(self, x, y, z):
            self.blocks = 50 # due to the limitations of protocol we simply assume that each player has unlimited blocks

            self.protocol.sim.build(x, y, z)
            return connection.on_block_build(self, x, y, z)

        def on_line_build(self, points):
            for (x, y, z) in points:
                self.protocol.sim.build(x, y, z)

            return connection.on_line_build(self, points)

        def on_block_removed(self, x, y, z):
            self.protocol.sim.destroy(x, y, z)
            return connection.on_block_removed(self, x, y, z)

        def on_spawn(self, pos):
            self.last_sprint      = -inf
            self.last_tool_update = -inf

            self.reset_health()

            return connection.on_spawn(self, pos)

        def on_kill(self, killer, kill_type, grenade):
            self.body = healthy()
            if kill_type not in NO_WARNING:
                self.send_lines(WARNING_ON_KILL, 'warning')
            return connection.on_kill(self, killer, kill_type, grenade)

        def on_animation_update(self, jump, crouch, sneak, sprint):
            if self.world_object.sprint and not sprint:
                self.last_sprint = reactor.seconds()

            return connection.on_animation_update(self, jump, crouch, sneak, sprint)

        def on_tool_set_attempt(self, tool):
            if self.body[ARMS].fracture:
                self.set_tool(SPADE_TOOL)
                return False
            else:
                return connection.on_tool_set_attempt(self, tool)

        def on_grenade(self, fuse):
            if self.cannot_work():
                self.send_chat_error("How did you do that??")
                return False

            return connection.on_grenade(self, fuse)

        def on_block_destroy(self, x, y, z, mode):
            if self.cannot_work():
                return False

            if mode == DESTROY_BLOCK and (self.tool == WEAPON_TOOL or self.tool == SPADE_TOOL):
                return False

            if mode == SPADE_DESTROY:
                return False

            return connection.on_block_destroy(self, x, y, z, mode)

        def on_shoot_set(self, fire):
            self.update_hud()
            return connection.on_shoot_set(self, fire)

        @register_packet_handler(loaders.SetTool)
        def on_tool_change_recieved(self, contained):
            if not self.hp: return

            if self.on_tool_set_attempt(contained.value) == False:
                return

            old_tool              = self.tool
            self.tool             = contained.value
            self.last_tool_update = reactor.seconds()

            if old_tool == WEAPON_TOOL:
                self.weapon_object.set_shoot(False)

            if self.tool == WEAPON_TOOL:
                self.on_shoot_set(self.world_object.primary_fire)
                self.weapon_object.set_shoot(
                    self.world_object.primary_fire)

            self.world_object.set_weapon(self.tool == WEAPON_TOOL)
            self.on_tool_changed(self.tool)

            if self.filter_visibility_data or self.filter_animation_data:
                return

            pingback           = loaders.SetTool()
            pingback.player_id = self.player_id
            pingback.value     = contained.value
            self.protocol.broadcast_contained(pingback, sender=self, save=True)

        @register_packet_handler(loaders.ExistingPlayer)
        @register_packet_handler(loaders.ShortPlayerData)
        def on_new_player_recieved(self, contained):
            if contained.team not in self.protocol.teams:
                return

            return connection.on_new_player_recieved(self, contained)

        @register_packet_handler(loaders.ChangeTeam)
        def on_team_change_recieved(self, contained):
            if contained.team not in self.protocol.teams:
                return

            return connection.on_team_change_recieved(self, contained)

        @register_packet_handler(loaders.HitPacket)
        def on_hit_recieved(self, contained):
            if not self.hp: return

            if contained.value == MELEE:
                player = self.protocol.players.get(contained.player_id)
                if player is not None:
                    player.hit(
                        bounded_damage(SHOVEL_GUARANTEED_DAMAGE), part=choice(parts),
                        bleeding=True, hit_by=self, kill_type=MELEE_KILL
                    )

    return DamageProtocol, DamageConnection
