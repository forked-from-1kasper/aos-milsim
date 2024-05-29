from random import choice, gauss, uniform
from math import floor, inf, prod

from twisted.internet import reactor

from pyspades.packet import register_packet_handler
from pyspades.color import interpolate_rgb
from pyspades import contained as loaders
from pyspades.common import Vertex3
from pyspades.constants import *

import milsim.blast as blast

from milsim.simulator import Simulator, cone, toMeters
from milsim.weapon import weapons
from milsim.common import *

WARNING_ON_KILL = "/b for bandage, /t for tourniquet, /s for splint"

GRENADE_LETHAL_RADIUS = 4
GRENADE_SAFETY_RADIUS = 30

SHOVEL_GUARANTEED_DAMAGE = 50

fracture_warning = {
    Limb.torso: "You broke your spine.",
    Limb.head:  "You broke your neck.",
    Limb.arml:  "You broke your left arm.",
    Limb.armr:  "You broke your right arm.",
    Limb.legl:  "You broke your left leg.",
    Limb.legr:  "You broke your right leg."
}

bleeding_warning = "You're bleeding."

def dig(player, mu, dt, x, y, z):
    if not player.world_object or player.world_object.dead: return

    sigma = 0.01 if player.world_object.crouch else 0.05
    value = max(0, gauss(mu = mu, sigma = sigma) * dt)

    protocol = player.protocol

    if protocol.simulator.dig(x, y, z, value):
        protocol.onDestroy(player.player_id, x, y, z)

def toMeters3(v): return Vertex3(toMeters(v.x), toMeters(v.y), toMeters(v.z))

def apply_script(protocol, connection, config):
    milsim_extensions = [(EXTENSION_TRACE_BULLETS, 1), (EXTENSION_HIT_EFFECTS, 1)]

    class CombatProtocol(protocol):
        complete_coverage_fog = (200, 200, 200)

        def __init__(self, *w, **kw):
            protocol.__init__(self, *w, **kw)
            self.environment = None
            self.time        = reactor.seconds()
            self.simulator   = Simulator(self)

            self.available_proto_extensions.extend(milsim_extensions)

        def update_weather(self):
            self.simulator.update(self.environment)

            fog = interpolate_rgb(
                self.default_fog,
                self.complete_coverage_fog,
                self.environment.weather.cloudiness()
            )
            self.set_fog_color(fog)

        def on_map_change(self, M):
            retval = protocol.on_map_change(self, M)

            self.simulator.wipe()

            E = self.map_info.extensions.get('environment')

            if isinstance(E, Environment):
                self.environment = E
                E.apply(self.simulator)
                self.update_weather()
            else:
                raise TypeError

            return retval

        def on_world_update(self):
            t = reactor.seconds()

            dt = t - self.time

            for _, player in self.players.items():
                P = player.team is not None and not player.team.spectator
                Q = player.world_object is not None and not player.world_object.dead

                if P and Q and player.last_hp_update is not None:
                    dt = t - player.last_hp_update

                    for P in player.body.values():
                        if P.arterial: P.hit(P.arterial_rate * dt)
                        if P.venous: P.hit(P.venous_rate * dt)

                    moving = player.world_object.up or player.world_object.down or \
                             player.world_object.left or player.world_object.right

                    if moving:
                        for leg in player.body.legs:
                            if leg.fractured:
                                if player.world_object.sprint:
                                    leg.hit(leg.sprint_damage_rate * dt)
                                elif not leg.splint:
                                    leg.hit(leg.walk_damage_rate * dt)

                    for arm in player.body.arms:
                        if player.world_object.primary_fire and arm.fractured:
                            arm.hit(arm.action_damage_rate * dt)

                    player.weapon_object.update(t)

                    if not player.cannot_work():
                        if player.tool == SPADE_TOOL and player.item_shown(t):
                            if player.world_object.primary_fire:
                                player.dig1(dt)

                            if player.world_object.secondary_fire:
                                player.dig2(dt)

                        if player.tool == WEAPON_TOOL:
                            if player.world_object.primary_fire:
                                player.shoot(t)

                    hp = player.display()
                    if player.hp != hp:
                        player.set_hp(hp, kill_type=MELEE_KILL)

                    if not self.environment.size.inside(player.world_object.position):
                        player.kill()

                player.last_hp_update = t

            if self.environment is not None:
                if self.environment.weather.update(dt):
                    self.update_weather()

            self.simulator.step(self.time, t)

            self.time = t

            protocol.on_world_update(self)

        def onTrace(self, index, x, y, z, value, origin):
            self.broadcast_contained(
                TracerPacket(index, Vertex3(x, y, z), value, origin = origin),
                rule = hasTraceExtension
            )

        def onHitEffect(self, x, y, z, X, Y, Z, target):
            self.broadcast_contained(
                HitEffectPacket(Vertex3(x, y, z), X, Y, Z, target),
                rule = hasHitEffects
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

        def onHit(self, thrower, target, index, E, A, grenade):
            if target not in self.players:
                return

            player    = self.players[target]
            hit_by    = self.players.get(thrower, player)
            limb      = Limb(index)
            kill_type = GRENADE_KILL if grenade else HEADSHOT_KILL if limb == Limb.head else WEAPON_KILL

            damage, venous, arterial, fractured = 0, False, False, False

            if E <= 0:
                return
            else:
                e = (E / A) / (100 * 100) # energy per area, J/cm²

                P = player.body[limb]

                if randbool(logistic(P.bleeding(e))):
                    if randbool(P.arterial_density):
                        arterial = True
                    else:
                        venous = True

                fractured = randbool(logistic(P.fracture(E)))
                damage    = 100 * logistic(P.damage(E))

            if damage > 0:
                player.hit(
                    damage, limb = limb, hit_by = hit_by, kill_type = kill_type,
                    venous = venous, arterial = arterial, fractured = fractured,
                )

    class CombatConnection(connection):
        def __init__(self, *w, **kw):
            self.last_hp_update   = None
            self.weapon_last_shot = -inf

            self.body = Body()

            connection.__init__(self, *w, **kw)

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
            return any(map(lambda P: P.venous or P.arterial, self.body.values()))

        def fractured(self):
            return any(map(lambda P: P.fractured, self.body.values()))

        def cannot_work(self):
            return (self.body.arml.fractured and not self.body.arml.splint) or \
                   (self.body.armr.fractured and not self.body.armr.splint)

        def item_shown(self, t):
            P = not self.world_object.sprint
            Q = t - self.last_sprint >= 0.5
            R = t - self.last_tool_update >= 0.5
            return P and Q and R

        def dig1(self, dt):
            loc = self.world_object.cast_ray(4.0)
            if loc: dig(self, dt, 1.0, *loc)

        def dig2(self, dt):
            loc = self.world_object.cast_ray(4.0)
            if loc:
                x, y, z = loc
                dig(self, dt, 0.7, x, y, z - 1)
                dig(self, dt, 0.7, x, y, z)
                dig(self, dt, 0.7, x, y, z + 1)

        def shoot(self, t):
            w = self.weapon_object

            P = w.ammo.current() > 0
            Q = not w.reloading
            R = t - self.weapon_last_shot >= w.delay

            if P and Q and R and self.item_shown(t):
                self.weapon_last_shot = t
                w.ammo.shoot(1)

                self.update_hud()

                n = self.world_object.orientation.normal()
                r = self.eye() + n * 1.2

                for i in range(0, w.round.pellets):
                    v = n * gauss(mu = w.round.muzzle, sigma = w.round.muzzle * w.velocity_deviation)
                    v0 = toMeters3(self.world_object.velocity)

                    self.protocol.simulator.add(self, r, v0 + cone(v, w.round.spread), t, w.round)

        def set_tool(self, tool):
            self.tool           = tool
            contained           = loaders.SetTool()
            contained.player_id = self.player_id
            contained.value     = tool

            self.send_contained(contained)
            self.protocol.broadcast_contained(contained)

        def reset_health(self):
            self.last_hp_update = reactor.seconds()

            for P in self.body.values():
                P.reset()

            self.hp = 100

        def refill(self, local = False):
            for P in self.body.values():
                if P.fractured: P.splint = True

                P.arterial = False
                P.venous   = False

            self.grenades   = 3
            self.blocks     = 50
            self.bandage    = 3
            self.tourniquet = 2
            self.splint     = 1

            self.weapon_object.restock()

            if not local:
                self.send_contained(loaders.Restock())
                self.update_hud()

                if self.display() != 100: # loaders.Restock() reverts hp to 100
                    self.set_hp(self.display(), kill_type=MELEE_KILL)

        def update_hud(self):
            weapon_reload              = loaders.WeaponReload()
            weapon_reload.player_id    = self.player_id
            weapon_reload.clip_ammo    = self.weapon_object.ammo.current()
            weapon_reload.reserve_ammo = self.weapon_object.ammo.reserved()
            self.send_contained(weapon_reload)

        def hit(self, value, hit_by = None, kill_type = WEAPON_KILL, limb = Limb.torso,
                venous = False, arterial = False, fractured = False):
            if hit_by is not None:
                if self.team is hit_by.team:
                    if kill_type == MELEE_KILL: return
                    if not self.protocol.friendly_fire: return

            P = self.body[limb]

            P.hit(value)

            if self.hp is not None and self.hp > 0:
                hp = self.display()

                if hp > 0:
                    if fractured and not P.fractured:
                        self.send_chat_status(fracture_warning[limb])
                    elif (venous or arterial) and not self.bleeding():
                        self.send_chat_status(bleeding_warning)

                if fractured and not P.fractured:
                    P.on_fracture(self)

                self.set_hp(hp, hit_by=hit_by, kill_type=kill_type)
                P.venous    = P.venous or venous
                P.arterial  = P.arterial or arterial
                P.fractured = P.fractured or fractured

        def grenade_destroy(self, x, y, z):
            if x < 0 or x > 512 or y < 0 or y > 512 or z < 0 or z > 63:
                return False

            if self.on_block_destroy(x, y, z, GRENADE_DESTROY) == False:
                return False

            for X, Y, Z in grenade_zone(x, y, z):
                if self.protocol.simulator.smash(X, Y, Z, TNT(gram(60))):
                    self.protocol.onDestroy(self.player_id, X, Y, Z)

            return True

        def grenade_explode(self, r):
            blast.explode(GRENADE_LETHAL_RADIUS, GRENADE_SAFETY_RADIUS, self, r)
            self.grenade_destroy(floor(r.x), floor(r.y), floor(r.z))

        def grenade_exploded(self, grenade):
            if self.name is None or self.team.spectator:
                return

            self.grenade_explode(grenade.position)

        def set_weapon(self, weapon, local = False, no_kill = False):
            if weapon not in weapons: return

            self.weapon = weapon
            self.weapon_object = weapons[weapon](self._on_reload)

            if not local:
                contained           = loaders.ChangeWeapon()
                contained.player_id = self.player_id
                contained.weapon    = weapon

                self.protocol.broadcast_contained(contained, save=True)
                if not no_kill: self.kill(kill_type=CLASS_CHANGE_KILL)

        def _on_reload(self):
            if not self.weapon_object.ammo.continuous:
                self.send_chat(self.weapon_object.ammo.info())

            self.update_hud()

        def _on_fall(self, damage):
            if not self.hp: return

            retval = self.on_fall(damage)

            if retval is False: return

            if retval is not None:
                damage = retval

            if damage > 0:
                legl, legr = self.body.legl, self.body.legr

                legl.hit(damage)
                legr.hit(damage)

                if randbool(logistic(legl.fall(damage))):
                    legl.fractured = True
                    legr.fractured = True
                    self.send_chat_status("You broke your legs.")

                self.set_hp(self.display(), kill_type=FALL_KILL)

        def on_block_build(self, x, y, z):
            self.blocks = 50 # due to the limitations of protocol we simply assume that each player has unlimited blocks

            self.protocol.simulator.build(x, y, z)
            return connection.on_block_build(self, x, y, z)

        def on_line_build(self, points):
            for (x, y, z) in points:
                self.protocol.simulator.build(x, y, z)

            return connection.on_line_build(self, points)

        def on_block_removed(self, x, y, z):
            self.protocol.simulator.destroy(x, y, z)
            return connection.on_block_removed(self, x, y, z)

        def on_spawn(self, pos):
            self.last_sprint      = -inf
            self.last_tool_update = -inf

            self.reset_health()
            self.update_hud()

            return connection.on_spawn(self, pos)

        def on_kill(self, killer, kill_type, grenade):
            if kill_type != TEAM_CHANGE_KILL and kill_type != CLASS_CHANGE_KILL:
                self.send_chat(WARNING_ON_KILL)

            return connection.on_kill(self, killer, kill_type, grenade)

        def on_animation_update(self, jump, crouch, sneak, sprint):
            if self.world_object.sprint and not sprint:
                self.last_sprint = reactor.seconds()

            return connection.on_animation_update(self, jump, crouch, sneak, sprint)

        def on_orientation_update(self, x, y, z):
            retval = connection.on_orientation_update(self, x, y, z)

            if retval == False:
                return False

            torso = self.body.torso

            if torso.fractured and not torso.splint:
                torso.hit(torso.rotation_damage)

            return retval

        def on_tool_set_attempt(self, tool):
            if self.body.arml.fractured or self.body.armr.fractured:
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

            if self.tool == WEAPON_TOOL or self.tool == SPADE_TOOL:
                if mode == DESTROY_BLOCK:
                    return False

            if mode == SPADE_DESTROY:
                return False

            return connection.on_block_destroy(self, x, y, z, mode)

        def on_shoot_set(self, fire):
            return connection.on_shoot_set(self, fire)

        def on_flag_take(self):
            flag = self.team.other.flag

            if self.world_object.position.z >= flag.z:
                return False

            if not self.world_object.can_see(flag.x, flag.y, flag.z - 0.5):
                return False

            return connection.on_flag_take(self)

        def on_flag_capture(self):
            self.protocol.environment.on_flag_capture(self)
            return connection.on_flag_capture(self)

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
                self.weapon_object.set_shoot(self.world_object.primary_fire)

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

            if contained.value == MELEE and not self.cannot_work():
                player = self.protocol.players.get(contained.player_id)

                if player is not None:
                    damage = floor(uniform(SHOVEL_GUARANTEED_DAMAGE, 100))

                    player.hit(
                        damage, limb = choice(player.body.keys()),
                        venous = True, hit_by = self, kill_type = MELEE_KILL
                    )

    return CombatProtocol, CombatConnection
