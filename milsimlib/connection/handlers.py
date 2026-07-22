# Copyright © 2024–2026 rzrn

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.

# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

from math import log10, copysign, isfinite
from time import monotonic

from twisted.internet import reactor
from twisted.logger import Logger

from pyspades.constants import GRENADE_TOOL, TOOL_INTERVAL
from pyspades.collision import distance_3d_vector

from piqueserver.player import FeatureConnection

from milsimlib.engine import toMeters
from milsimlib.common import iempty

log = Logger()

def on_killed(self, killer, kill_type, grenade):
    pass

def on_reload_complete(self):
    pass

def on_flag_taken(self):
    pass

def on_chat(self, value, is_global_message):
    if is_global_message is False:
        if self.handheld_radio_item is None:
            self.send_chat("You don't have an equipped radio")

            return False

    return FeatureConnection.on_chat(self, value, is_global_message)

def on_chat_delivered(self, player, value, is_global_message):
    if self.deaf: return False

    if self.alive() and self.body.deaf: return False

    # We observe that attenuation α = α(f) is a monotonic function of a frequency `f`,
    # thus if a fixed frequency f = f₀ is getting attenuated below the background noise level,
    # so does any freqeuncy f > f₀. Cutting of everything above f = 1 kHz will drop many consonants,
    # therefore we take this frequency as a cutoff frequency.
    # [1] https://physics.stackexchange.com/questions/856827/looking-for-a-formula-to-realistically-model-sound-loudness-at-a-given-distance
    # [2] https://physics.stackexchange.com/questions/415409/how-far-can-a-shout-travel
    # [3] https://en.wikibooks.org/wiki/Engineering_Acoustics/Outdoor_Sound_Propagation

    if is_global_message:
        if self.dead(): # dead player can hear anyone anywhere
            return True # TODO: is this a good idea?

        if player.name is None or player.team.spectator: # spectators can be heard anywhere
            return True

        if player.dead(): # alive players can’t hear dead players
            return False

        d = toMeters(distance_3d_vector(self.world_object.position, player.world_object.position))

        d0 = 0.3 # Some arbitrary distance at which SPL₀ (initial sound pressure level) is measured (m).
        L0 = 80.0 if value.isupper() else 65.0 # SPL₀ (dB), where we interpret uppercase as shouting.

        if d < d0:
            L = L0
        else:
            α = self.protocol.attenuation_coefficient
            L = L0 - 20 * log10(d / d0) - α * d

        o = self.protocol.environment

        return L > o.ANL
    else:
        if wt := self.handheld_radio_item:
            channel = player.handheld_radio_item.radio_channel

            return wt.is_listening_to(channel)
        else:
            return False

def on_orientation_update(self, x, y, z):
    ε = 1e-9

    retval = FeatureConnection.on_orientation_update(self, x, y, z)

    if retval is False: return False

    if retval is not None: x, y, z = retval

    if -ε < x < ε: retval = copysign(ε, x), y, z

    torso = self.body.torso

    if torso.fractured and not torso.splint:
        torso.hit(torso.rotation_damage)

    return retval

def on_animation_update(self, jump, crouch, sneak, sprint):
    retval = FeatureConnection.on_animation_update(self, jump, crouch, sneak, sprint)
    if retval is not None: jump, crouch, sneak, sprint = retval

    if self.world_object.sprint and not sprint:
        self.last_sprint = monotonic()

    if self.world_object.sneak != sneak:
        if sneak:
            self.tool_object.on_sneak_press()
        else:
            self.tool_object.on_sneak_release()

    if not self.world_object.jump and jump:
        for leg in self.body.legs():
            if leg.fractured:
                leg.hit(leg.jump_damage)

    self.protocol.engine.set_animation(self.player_id, crouch)

    return retval

def on_tool_set_attempt(self, tool):
    if self.body.arml.fractured or self.body.armr.fractured:
        return False

    if tool == GRENADE_TOOL and iempty(self.handgrenades()):
        return False

    return FeatureConnection.on_tool_set_attempt(self, tool)

def on_flag_capture(self):
    if map_on_flag_capture := self.protocol.map_info.on_flag_capture:
        map_on_flag_capture(self)

    FeatureConnection.on_flag_capture(self)

def on_client_info(self):
    log.info("{address} connected with {client}",
        address  = self.address[0],
        client   = self.client_string
    )

    FeatureConnection.on_client_info(self)

def on_spawn(self, loc):
    FeatureConnection.on_spawn(self, loc)

    self.world_object.on_block_stepped = self.on_block_stepped

    self.last_spawn_time = monotonic()

    self.tool_object = self.weapon_object
    self.tool_object.on_tool_equipped(None)

    self.last_sprint      = 0
    self.last_tool_update = 0

    self.suppression_value        = 0.0
    self.suppression_warning_sent = False

    self.last_hp_update = monotonic()

    self.handheld_radio_item = None

    self.body.reset()

    self.hp       = 100
    self.blocks   = 50
    self.grenades = 3

    self.sendWeaponReloadPacket()

    self.protocol.engine.on_spawn(self.player_id)

    if isfinite(self.get_respawn_time()):
        pass
    else:
        self.kill() # if spawn is disabled

def on_disconnect(self):
    if o := self.weapon_object:
        o.reset()

    self.drop_inventory()

    FeatureConnection.on_disconnect(self)

def on_tool_rapid_hack(self, tool):
    t1, t2 = self.last_block, reactor.seconds()

    self.last_block = t2

    if self.rapid_hack_detect and t1 is not None and t2 - t1 < TOOL_INTERVAL[tool]:
        self.rapids.record_event(t2)

        if self.rapids.above_limit():
            self.on_hack_attempt('Rapid hack detected')
            return True

    return False

def on_refill(self):
    self.inventory.extend(io.mark_renewable() for io in self.default_loadout())

def on_block_stepped(self, x, y, z):
    M = self.protocol.map
    if M.get_solid(x, y, z):
        if e := self.protocol.get_tile_entity(x, y, z):
            e.on_pressure()
