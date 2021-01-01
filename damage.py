from pyspades.constants import (
    TORSO, HEAD, ARMS, LEGS, MELEE,
    RIFLE_WEAPON, SMG_WEAPON, SHOTGUN_WEAPON,
    WEAPON_KILL, HEADSHOT_KILL, MELEE_KILL, GRENADE_KILL,
    FALL_KILL, TEAM_CHANGE_KILL, CLASS_CHANGE_KILL
)
from pyspades.packet import register_packet_handler
from pyspades.collision import distance_3d_vector
from pyspades.common import Vertex3
from pyspades import contained as loaders
from piqueserver.commands import command
from math import pi, exp, sqrt, e, floor
from dataclasses import dataclass
from random import choice, random
from time import time

ρ      = 1.225 # Air density
factor = 0.5191
g      = 9.81

parts = [TORSO, HEAD, ARMS, LEGS]
names = {TORSO: "torso", HEAD: "head", ARMS: "arms", LEGS: "legs", MELEE: "melee"}

shoot_warning = {
    TORSO: "You got shot in the torso.",
    HEAD:  "You’ve been shot in the head.",
    ARMS:  "You got hit in the arm.",
    LEGS:  "You got shot in the leg."
}
bleeding_warning = "You’re bleeding."

#distr = lambda x: (exp(x) - 1) / (e - 1)
#distr = lambda x: log(x + 1) / log(2)
distr = sqrt

limit = lambda m, M, f: lambda x: max(m, min(M, f(x)))
scale = lambda x, y, f: lambda z: y * f(z / x)

guaranteed_death_energy = {TORSO: 2500, HEAD: 400, ARMS: 3700, LEGS: 4200}
guaranteed_bleeding_energy = {TORSO: 250, HEAD: 100, ARMS: 200, LEGS: 300}

damage = lambda part: limit(0, 100, scale(guaranteed_death_energy[part], 100, distr))
bleeding_prob = lambda part: limit(0, 1, scale(guaranteed_bleeding_energy[part], 1, distr))

randbool = lambda prob: random() <= prob

@dataclass
class Bullet:
    velocity:  float
    mass:      float
    ballistic: float
    caliber:   float

    def __post_init__(self):
        self.drag = (factor * self.mass) / (self.ballistic * (self.caliber ** 2))
        self.A = (pi * (self.caliber ** 2)) / 4
        self.k = (ρ * self.drag * self.A) / (2 * self.mass)

bullets = {
    RIFLE_WEAPON:   Bullet(850, 10.00/1000, 146.9415,  7.62/1000),
    SMG_WEAPON:     Bullet(400,  8.03/1000, 104.7573,  9.00/1000),
    SHOTGUN_WEAPON: Bullet(457, 38.00/1000,   5.0817, 18.40/1000)
}

def energy(bullet, pos1, pos2):
    dist = distance_3d_vector(pos1, pos2)
    Δh = pos1.z - pos2.z
    ΔW = -bullet.mass * g * Δh

    t = (exp(bullet.k * dist) - 1)/(bullet.k * bullet.velocity)
    v = bullet.velocity / (1 + bullet.k * t * bullet.velocity)

    T = (bullet.mass / 2) * (v ** 2)
    return T + ΔW

@dataclass
class Part:
    hp       : int  = 100
    bleeding : bool = False
    fracture : bool = False

    def hit(self, value):
        self.hp = max(0, self.hp - value)

healthy = lambda: {TORSO: Part(), HEAD: Part(), ARMS: Part(), LEGS: Part()}
bleeding_curve = lambda Δt: Δt

@command('health')
def health(conn, *args):
    try:
        return " ".join(map(lambda part: f"{names[part]}: {conn.body[part].hp}", parts))
    except AttributeError:
        return "Body not initialized."

@command('position')
def position(conn, *args):
    return str(conn.world_object.position)

@command('bandage', 'b')
def bandage(conn, *args):
    if not conn.hp: return
    if conn.bandage == 0: return "You do not have a bandage."

    for part in conn.body:
        if part.bleeding:
            part.bleeding = False
            conn.bandage -= 1
            return f"You have bandaged your {names[part]}"

    return "You are not bleeding."

def apply_script(protocol, connection, config):
    class DamageProtocol(protocol):
        def on_world_update(self):
            τ = time()
            for _, player in self.players.items():
                if player.last_hp_update is not None and player.hp is not None and player.hp > 0:
                    for _, part in player.body.items():
                        if part.bleeding:
                            part.hit(bleeding_curve(τ - player.last_hp_update))
                    player.set_hp(player.display(), kill_type=MELEE_KILL)
                player.last_hp_update = τ

            protocol.on_world_update(self)

    class DamageConnection(connection):
        def on_connect(self):
            self.reset_health()
            return connection.on_connect(self)

        def on_spawn(self, pos):
            self.reset_health()
            return connection.on_spawn(self, pos)

        def reset_health(self):
            self.last_hp_update = None
            self.body = healthy()

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

            # Shoot position
            pos1 = self.world_object.position
            # Hit position
            pos2 = player.world_object.position

            if not melee:
                E = energy(bullets[self.weapon], pos1, pos2)
                if E <= 0: return

                val = contained.value
                kill_type = (HEADSHOT_KILL if contained.value == HEAD else WEAPON_KILL)
                player.damage(
                    val, damage(val)(E), hit_by=self,
                    bleeding=randbool(bleeding_prob(val)(E)),
                    kill_type=kill_type
                )
            else:
                player.damage(
                    choice(parts), floor(50 + 50 * random()),
                    bleeding=True, hit_by=self, kill_type=MELEE_KILL
                )

        def display(self):
            total = 1
            for part in parts:
                total *= self.body[part].hp / 100
            return floor(100 * total)

        def bleeding(self):
            for _, part in self.body.items():
                if part.bleeding: return True
            return False

        def damage(self, part, value, hit_by=None, kill_type=WEAPON_KILL,
                   bleeding=False, fracture=False):
            if hit_by is not None and self.team is hit_by.team:
                if kill_type == MELEE_KILL: return
                elif not self.protocol.friendly_fire: return

            self.body[part].hit(value)

            if self.hp is not None and self.hp > 0:
                if kill_type == WEAPON_KILL or kill_type == HEADSHOT_KILL:
                    self.send_chat(shoot_warning[part])
                if bleeding and not self.bleeding():
                    self.send_chat(bleeding_warning)

                self.set_hp(self.display(), hit_by=hit_by, kill_type=kill_type)

            self.body[part].bleeding = bleeding
            self.body[part].fracture = fracture

    return DamageProtocol, DamageConnection