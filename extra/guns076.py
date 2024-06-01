# https://raw.githubusercontent.com/iamgreaser/pysnip/master/feature_server/scripts/malsa076.py

from math import ceil

from pyspades.collision import distance_3d_vector
from pyspades import contained as loaders
from pyspades.weapon import BaseWeapon
from pyspades.constants import *

class Weapon076(BaseWeapon):
    def get_damage(self, value, v1, v2):
        d = distance_3d_vector(v1, v2)

        falloff = 1 - (d ** 1.5) * 0.0004
        return ceil(self.damage[value] * falloff)

class Rifle(Weapon076):
    id          = RIFLE_WEAPON
    name        = 'Rifle'
    delay       = 0.5
    ammo        = 8
    stock       = 48
    reload_time = 2.5
    slow_reload = False

    damage = {
        TORSO: 60,
        HEAD:  250,
        ARMS:  50,
        LEGS:  50
    }

class SMG(Weapon076):
    id          = SMG_WEAPON
    name        = 'SMG'
    delay       = 0.11
    ammo        = 30
    stock       = 150
    reload_time = 2.5
    slow_reload = False

    damage = {
        TORSO: 40,
        HEAD:  60,
        ARMS:  20,
        LEGS:  20
    }


class Shotgun(Weapon076):
    id          = SHOTGUN_WEAPON
    name        = 'Shotgun'
    delay       = 1.0
    ammo        = 8
    stock       = 48
    reload_time = 0.5
    slow_reload = True

    damage = {
        TORSO: 40,
        HEAD:  60,
        ARMS:  20,
        LEGS:  20
    }


weapons = {
    RIFLE_WEAPON:   Rifle,
    SMG_WEAPON:     SMG,
    SHOTGUN_WEAPON: Shotgun,
}

def apply_script(protocol, connection, config):
    class GunsConnection(connection):
        def set_weapon(self, weapon, local = False, no_kill = False):
            self.weapon = weapon

            if self.weapon_object is not None:
                self.weapon_object.reset()

            self.weapon_object = weapons[weapon](self._on_reload)

            if not local:
                change_weapon = loaders.ChangeWeapon()
                self.protocol.broadcast_contained(change_weapon, save = True)

                if not no_kill: self.kill(kill_type = CLASS_CHANGE_KILL)

        def on_spawn(self, pos):
            self._on_reload()
            return connection.on_spawn(self, pos)

    return protocol, GunsConnection