from math import pi, exp, sqrt, e, floor, ceil, inf
from itertools import product, chain

from random import choice, random
from dataclasses import dataclass
from typing import Callable

from twisted.internet.error import AlreadyCalled, AlreadyCancelled
from twisted.internet import reactor

from pyspades.constants import (
    TORSO, HEAD, ARMS, LEGS, MELEE, WEAPON_TOOL, SPADE_TOOL,
    RIFLE_WEAPON, SMG_WEAPON, SHOTGUN_WEAPON, CLIP_TOLERANCE,
    WEAPON_KILL, HEADSHOT_KILL, MELEE_KILL, GRENADE_KILL,
    FALL_KILL, TEAM_CHANGE_KILL, CLASS_CHANGE_KILL,
    GRENADE_DESTROY, DESTROY_BLOCK
)
from pyspades.collision import distance_3d_vector, vector_collision
from pyspades.packet import register_packet_handler
from pyspades.protocol import BaseConnection
from pyspades import contained as loaders
from pyspades.common import Vertex3

from piqueserver.commands import command
import scripts.blast as blast

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

shoot_warning = {
    TORSO: "You got shot in the torso.",
    HEAD:  "You've been shot in the head.",
    ARMS:  "You got hit in the arm.",
    LEGS:  "You got shot in the leg."
}
fracture_warning = {
    TORSO: "You broke your spine.",
    HEAD:  "You broke your neck.",
    ARMS:  "You broke your arm.",
    LEGS:  "You broke your leg."
}
bleeding_warning = "You're bleeding."

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
    velocity:  float
    mass:      float
    ballistic: float
    caliber:   float

    def __post_init__(self):
        self.drag = (factor * self.mass) / (self.ballistic * (self.caliber ** 2))
        self.A = (pi * (self.caliber ** 2)) / 4
        self.k = (ρ * self.drag * self.A) / (2 * self.mass)

    def energy(self, pos1, pos2):
        dist = distance_3d_vector(pos1, pos2)
        Δh = pos1.z - pos2.z
        ΔW = -self.mass * g * Δh

        t = (exp(self.k * dist) - 1)/(self.k * self.velocity)
        v = self.velocity / (1 + self.k * t * self.velocity)

        T = (self.mass / 2) * (v ** 2)
        return T + ΔW

    def damage(self, part, pos1, pos2):
        E = self.energy(pos1, pos2)
        if E <= 0: return 0, False, False
        else:
            bleeding = randbool(weighted_prob(guaranteed_bleeding_energy, part)(E))
            fracture = randbool(weighted_prob(guaranteed_fracture_energy, part)(E))
            return energy_to_damage(part)(E), bleeding, fracture

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

    def noammo(self):
        return all(map(lambda c: c <= 0, self.container))

    def next(self):
        self.loaded += 1
        self.loaded %= self.magazines

    def reload(self):
        if self.noammo():
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
    name        : str                # Name
    ammo        : Callable[[], Ammo] # Ammunition container constructor
    round       : Round              # Ammunition type used by weapon
    delay       : float              # Time between shots
    reload_time : float              # Time between reloading and being able to shoot again

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
        timestamp = reactor.seconds()

        P = self.ammo.current() > 0
        Q = self.reloading and not self.ammo.continuous
        R = timestamp - self.last_shot >= self.gun.delay
        S = self.conn.world_object.sprint or timestamp - self.conn.last_sprint < 0.5

        if P and not Q and R and not S:
            self.last_shot = timestamp
            self.ammo.shoot(1)

        self.defer = reactor.callLater(self.gun.delay, self.fire)

    def reload(self):
        if self.reloading:
            return

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

    def get_damage(self, value, pos1, pos2):
        return self.gun.round.damage(value, pos1, pos2)

guns = {
    RIFLE_WEAPON:   Gun("Rifle",   lambda: Magazines(5, 10), Round(850, 10.00/1000, 146.9415,  7.62/1000), 0.50, 2.5),
    SMG_WEAPON:     Gun("SMG",     lambda: Magazines(4, 30), Round(600,  8.03/1000, 104.7573,  9.00/1000), 0.11, 2.5),
    SHOTGUN_WEAPON: Gun("Shotgun", lambda: Heap(6, 48),      Round(457, 38.00/1000,   5.0817, 18.40/1000), 1.00, 0.5)
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

def apply_script(protocol, connection, config):
    class DamageProtocol(protocol):
        def on_world_update(self):
            τ = reactor.seconds()
            for _, player in self.players.items():
                if player.last_hp_update is not None and player.hp is not None and player.hp > 0:
                    for _, part in player.body.items():
                        if part.bleeding:
                            part.hit(bleeding_curve(τ - player.last_hp_update))

                    hp = player.display()
                    if player.hp != hp:
                        player.set_hp(hp, kill_type=MELEE_KILL)

                player.last_hp_update = τ

            protocol.on_world_update(self)

    class DamageConnection(connection):
        def on_connect(self):
            self.reset_health()
            self.last_sprint = -inf
            return connection.on_connect(self)

        def on_spawn(self, pos):
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

        def reset_tool(self):
            act = loaders.SetTool()
            act.player_id = self.player_id
            act.value = SPADE_TOOL
            self.send_contained(act)
            self.protocol.broadcast_contained(act)

        def on_tool_set_attempt(self, tool):
            if self.body[ARMS].fracture:
                self.reset_tool()
                return False
            else:
                return connection.on_tool_set_attempt(self, tool)

        def on_grenade(self, fuse):
            if self.cannot_work():
                self.send_chat("How did you do that??")
                return False

            return connection.on_grenade(self, fuse)

        def on_block_destroy(self, x, y, z, mode):
            if self.cannot_work(): return False

            if mode == DESTROY_BLOCK and self.tool == WEAPON_TOOL:
                energy = self.weapon_object.gun.round.energy(
                    self.world_object.position, Vertex3(x, y, z)
                )
                if energy <= BLOCK_DESTROY_ENERGY:
                    return False

            return connection.on_block_destroy(self, x, y, z, mode)

        def reset_health(self):
            self.last_hp_update = None
            self.body           = healthy()
            self.hp             = 100

            self.bandage = 2
            self.splint  = 1

        @register_packet_handler(loaders.HitPacket)
        def on_hit_recieved(self, contained):
            if not self.hp: return
            melee = (contained.value == MELEE)

            try:
                player = self.protocol.players[contained.player_id]
            except KeyError:
                return

            pos1 = self.world_object.position   # Shoot position
            pos2 = player.world_object.position # Hit position

            if not melee:
                damage, bleeding, fracture = self.weapon_object.get_damage(contained.value, pos1, pos2)
                if damage <= 0: return

                val = contained.value
                kill_type = (HEADSHOT_KILL if contained.value == HEAD else WEAPON_KILL)
                player.hit(
                    damage, part=val, hit_by=self, bleeding=bleeding,
                    fracture=fracture, kill_type=kill_type
                )
            else:
                player.hit(
                    bounded_damage(SHOVEL_GUARANTEED_DAMAGE), part=choice(parts),
                    bleeding=True, hit_by=self, kill_type=MELEE_KILL
                )

        def refill(self, local=False):
            self.grenades = 3
            self.blocks   = 50
            self.bandage  = 2
            self.splint   = 1

            self.weapon_object.restock()

            if not local:
                restock = loaders.Restock()
                self.send_contained(restock)

        def display(self):
            total = 1
            for part in parts:
                total *= self.body[part].hp / 100
            return floor(100 * total)

        def bleeding(self):
            for _, part in self.body.items():
                if part.bleeding: return True
            return False

        def fracture(self):
            for _, part in self.body.items():
                if part.fracture: return True
            return False

        def can_walk(self):
            legs = self.body[LEGS]
            return (not legs.fracture) or (legs.fracture and legs.splint)

        def cannot_work(self):
            arms = self.body[ARMS]
            return arms.fracture and (not arms.splint)

        def hit(self, value, hit_by=None, kill_type=WEAPON_KILL,
                bleeding=False, fracture=False, part=TORSO):
            if hit_by is not None:
                if self.team is hit_by.team:
                    if kill_type == MELEE_KILL: return
                    if not self.protocol.friendly_fire: return

                # So that if a player threw a greande, and then his arm
                # was broken, this grenade will still deal damage.
                if hit_by.cannot_work() and (kill_type == WEAPON_KILL or
                                             kill_type == HEADSHOT_KILL or
                                             kill_type == MELEE_KILL):
                    return

            self.body[part].hit(value)

            if self.hp is not None and self.hp > 0:
                if kill_type == WEAPON_KILL or kill_type == HEADSHOT_KILL:
                    self.send_chat(shoot_warning[part])
                if bleeding and not self.bleeding():
                    self.send_chat(bleeding_warning)
                if fracture and not self.fracture():
                    self.send_chat(fracture_warning[part])

                self.set_hp(self.display(), hit_by=hit_by, kill_type=kill_type)
                self.body[part].bleeding = bleeding
                self.body[part].fracture = fracture

                if part == ARMS and fracture: self.reset_tool()
                if part == LEGS and fracture: self.break_legs()

        def break_legs(self):
            pass

        def _on_fall(self, damage):
            if not self.hp: return
            returned = self.on_fall(damage)
            if returned is False: return
            elif returned is not None: damage = returned

            self.body[LEGS].hit(damage)
            if randbool(damage / 100):
                self.body[LEGS].fracture = True
                self.send_chat(fracture_warning[LEGS])

            self.break_legs()
            self.set_hp(self.display(), kill_type=FALL_KILL)

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
            self.weapon = weapon
            if self.weapon_object is not None:
                self.weapon_object.reset()
            self.weapon_object = Weapon(self, guns[weapon], self._on_reload)

            if not local:
                change_weapon = loaders.ChangeWeapon()
                self.protocol.broadcast_contained(change_weapon, save=True)
                if not no_kill: self.kill(kill_type=CLASS_CHANGE_KILL)

        def update_hud(self):
            weapon_reload              = loaders.WeaponReload()
            weapon_reload.player_id    = self.player_id
            weapon_reload.clip_ammo    = self.weapon_object.ammo.current()
            weapon_reload.reserve_ammo = self.weapon_object.ammo.reserved()
            self.send_contained(weapon_reload)

        def _on_reload(self):
            if not self.weapon_object.ammo.continuous:
                self.send_chat(self.weapon_object.ammo.info())

            self.update_hud()

        def on_shoot_set(self, fire):
            self.update_hud()
            return connection.on_shoot_set(self, fire)

    return DamageProtocol, DamageConnection
