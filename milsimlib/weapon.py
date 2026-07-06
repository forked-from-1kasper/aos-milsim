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

from math import hypot, inf
from time import monotonic
from random import gauss

from pyspades.constants import SPADE_TOOL, WEAPON_TOOL
from pyspades.common import Vertex3

from milsimlib.types import Tool, Item, CartridgeBox, BoxMagazine, TubularMagazine, Shotshell
from milsimlib.builtin import R762x54mm, HEI762x54mm, Parabellum, Buckshot0000
from milsimlib.engine import cone, absoluteZero, stefanBoltzmann

from milsimlib.common import NotImplementedField, toMeters3, format_item, icons

class UnderbarrelItem(Item):
    def on_press(self, player):
        pass

    def on_hold(self, player, t, dt):
        pass

    def on_release(self, player):
        pass

    def apply(self, player):
        player.inventory.remove(self)

        if o := player.weapon_object.item_underbarrel:
            player.inventory.push(o)

        player.weapon_object.item_underbarrel = self

        return "Equipped {}".format(format_item(self))

class ABCWeapon(Tool):
    name                      = NotImplementedField
    basemass                  = NotImplementedField
    delay                     = NotImplementedField
    reload_time               = NotImplementedField
    barrel_mass               = NotImplementedField # kg
    barrel_specific_heat      = NotImplementedField # J / (kg · K)
    barrel_surface_area       = NotImplementedField # m²
    barrel_emissivity         = NotImplementedField # 1
    handguard_mass            = NotImplementedField # kg
    handguard_specific_heat   = NotImplementedField # J / (kg · K)
    handguard_surface_area    = NotImplementedField # m²
    handguard_emissivity      = NotImplementedField # 1
    heat_transfer_coefficient = NotImplementedField # W / K
    barrel_heat_ratio         = NotImplementedField # 1

    def __init__(self, player):
        self.weapon_reload_timer = -inf
        self.player              = player
        self.item_underbarrel    = None

        self.reset()

    def reserve(self):
        raise NotImplementedError

    def restock(self):
        raise NotImplementedError

    def refill(self):
        raise NotImplementedError

    def enabled(self):
        return 0 < self.magazine.current() or 0 < self.reserved()

    @property
    def mass(self):
        return self.basemass + self.magazine.mass + getattr(self.item_underbarrel, 'mass', 0)

    def is_empty(self, tolerance = 0):
        return self.magazine.current() <= 0

    def reserved(self):
        return sum(map(lambda o: o.current(), self.reserve()))

    def can_reload(self):
        return 0 < self.reserved() and self.magazine.current() < self.magazine.capacity

    def reload(self):
        if self.reloading:
            return

        if self.can_reload():
            self.weapon_reload_timer = monotonic()
            self.reloading = True

    def get_player_velocity(self):
        if o := self.player.world_object:
            return toMeters3(o.velocity * 32)

    def update(self, t, dt):
        if self.reloading and t - self.weapon_reload_timer >= self.reload_time:
            self.weapon_reload_timer = t

            succ, self.reloading = self.magazine.reload(self.reserve())

            if succ is not None:
                i = self.player.inventory
                i.remove(succ)
                i.append(self.magazine)

                self.magazine = succ

            self.player.on_reload_complete()
            self.player.sendWeaponReloadPacket()

        engine = self.player.protocol.engine

        # We treat our weapon as a two-node lumped-element model: the barrel and the handguard,
        # with some fixed coefficient of heat transfer between them.

        T0 = engine.temperature - absoluteZero
        T1 = self.barrel_temperature - absoluteZero
        T2 = self.handguard_temperature - absoluteZero

        m1, m2 = self.barrel_mass, self.handguard_mass
        c1, c2 = self.barrel_specific_heat, self.handguard_specific_heat
        A1, A2 = self.barrel_surface_area, self.handguard_surface_area
        ε1, ε2 = self.barrel_emissivity, self.handguard_emissivity

        u = self.get_player_velocity()
        v = Vertex3(*engine.wind)

        # Rate of heat transfer between the barrel and the handguard, W
        vQt = self.heat_transfer_coefficient * (T1 - T2)

        # This is just some arbitrary approximation, as the actual law is much more complex.
        # See also: https://github.com/acemod/ACE3/blob/master/addons/overheating/functions/fnc_calculateCooling.sqf
        a, b, n = 10.0, 8.0, 0.7
        h = a + b * (v - u).length() ** n # Convective heat transfer coefficient, W / (m² · K)

        # Rate of convective heat transfer, W
        # See: https://en.wikipedia.org/wiki/Newton%27s_law_of_cooling
        vQc1 = h * A1 * (T1 - T0)
        vQc2 = h * A2 * (T2 - T0)

        σ = stefanBoltzmann

        # Rate of radiative heat transfer, W
        # [1] https://en.wikipedia.org/wiki/Stefan%E2%80%93Boltzmann_law
        # [2] https://en.wikipedia.org/wiki/Kirchhoff%27s_law_of_thermal_radiation
        # [3] https://physics.stackexchange.com/a/625662
        vQr1 = ε1 * σ * A1 * (T1 ** 4 - T0 ** 4)
        vQr2 = ε2 * σ * A2 * (T2 ** 4 - T0 ** 4)

        dQ1 = (-vQt - vQc1 - vQr1) * dt
        dQ2 = (+vQt - vQc2 - vQr2) * dt

        # See: https://en.wikipedia.org/wiki/Specific_heat_capacity
        self.barrel_temperature += dQ1 / (m1 * c1)
        self.handguard_temperature += dQ2 / (m2 * c2)

        if self.player.tool == WEAPON_TOOL:
            if self.handguard_temperature >= 60:
                self.player.body.pushl_message("Your weapon is too hot to hold")
                self.player.set_tool(SPADE_TOOL)

            if self.barrel_temperature >= 600:
                self.player.body.pushl_message("The barrel is too hot to shoot")
                self.player.set_tool(SPADE_TOOL)

    def on_sneak_press(self):
        if self.player.world_object.secondary_fire:
            if o := self.item_underbarrel:
                o.on_press(self.player)

    def on_rmb_press(self):
        if self.player.world_object.sneak:
            if o := self.item_underbarrel:
                o.on_press(self.player)

    def on_sneak_hold(self, t, dt):
        if self.player.world_object.secondary_fire:
            if o := self.item_underbarrel:
                o.on_hold(self.player, t, dt)

    def on_sneak_release(self):
        if o := self.item_underbarrel:
            o.on_release(self.player)

    def on_rmb_release(self):
        if o := self.item_underbarrel:
            o.on_release(self.player)

    def on_lmb_press(self):
        if self.magazine.continuous:
            self.reloading = False

            self.player.on_reload_complete()
            self.player.sendWeaponReloadPacket()

    def on_lmb_hold(self, t, dt):
        P = self.is_empty()
        Q = self.reloading
        R = t - self.last_shot < self.delay

        if P or Q or R:
            return

        if cartridge := self.magazine.eject():
            self.last_shot = t

            o = self.player.world_object
            n = o.orientation.normal()
            r = self.player.eye() + n * 1.2
            u = self.get_player_velocity()

            engine = self.player.protocol.engine

            spread = cartridge.grouping * (self.player.get_spread_modifier() + 1)

            for i in range(cartridge.pellets):
                v = n * gauss(mu = cartridge.muzzle, sigma = cartridge.muzzle * cartridge.deviation)
                K = engine.add(self.player.player_id, r, u + cone(v, spread), t, cartridge)

                m = self.barrel_mass
                c = self.barrel_specific_heat
                Q = self.barrel_heat_ratio * K

                # Here we assume that heat is transferred instantaneously
                self.barrel_temperature += Q / (m * c)

            self.player.sendWeaponReloadPacket()

    def reset(self):
        if o := self.item_underbarrel:
            if o.persistent:
                self.player.get_drop_inventory().push(o)

        self.last_shot = -inf
        self.reloading = False
        self.restock()
        self.clear()

        engine = self.player.protocol.engine

        t0 = engine.temperature

        self.barrel_temperature    = t0
        self.handguard_temperature = t0

    def clear(self):
        self.item_underbarrel = None

    def format_ammo(self):
        return None

class DetachableMagazineItem:
    magazine_class         = NotImplementedField
    default_magazine       = NotImplementedField
    default_magazine_count = NotImplementedField

    def reserve(self):
        return filter(
            lambda o: isinstance(o, self.magazine_class),
            self.player.inventory
        )

    def restock(self):
        self.magazine = self.default_magazine()
        self.magazine.mark_renewable()

    def refill(self):
        i = self.player.inventory
        for k in range(self.default_magazine_count):
            i.append(self.default_magazine().mark_renewable())

    def format_ammo(self):
        it = icons(
            "{}*".format(self.magazine.current()),
            map(lambda o: "{}".format(o.current()), self.reserve())
        )

        return "Magazines: {}".format(", ".join(it))

class IntegralMagazineItem:
    cartridge_class   = NotImplementedField
    default_magazine  = NotImplementedField
    default_cartridge = NotImplementedField
    default_reserve   = NotImplementedField

    def reserve(self):
        return filter(
            lambda o: isinstance(o, CartridgeBox) and
                      isinstance(o.object, self.cartridge_class),
            self.player.inventory
        )

    def restock(self):
        self.magazine = self.default_magazine()
        self.magazine.mark_renewable()

        for k in range(self.magazine.capacity):
            self.magazine.push(self.default_cartridge)

    def refill(self):
        i = self.player.inventory
        i.append(CartridgeBox(self.default_cartridge, self.default_reserve).mark_renewable())

class RifleMagazine(BoxMagazine):
    pass

class R762Magazine(RifleMagazine):
    basemass  = 0.227
    basename  = "AA762R02"
    capacity  = 10
    cartridge = R762x54mm

class HEIMagazine(RifleMagazine):
    basemass  = 0.150
    basename  = "AA762HEI"
    capacity  = 5
    cartridge = HEI762x54mm

class Rifle(DetachableMagazineItem):
    name                      = "Rifle"
    basemass                  = 4.220
    delay                     = 0.50
    reload_time               = 2.5
    magazine_class            = RifleMagazine
    default_magazine          = R762Magazine
    default_magazine_count    = 3
    barrel_mass               = 1.800
    barrel_specific_heat      = 466.0
    barrel_surface_area       = 0.044
    barrel_emissivity         = 0.800
    handguard_mass            = 0.550
    handguard_specific_heat   = 1300.0
    handguard_surface_area    = 0.040
    handguard_emissivity      = 0.9
    heat_transfer_coefficient = 1.5
    barrel_heat_ratio         = 1.0

class SMGMagazine(BoxMagazine):
    pass

class ParabellumMagazine(SMGMagazine):
    basemass  = 0.160
    basename  = "MP5MAG30"
    capacity  = 30
    cartridge = Parabellum

class SMG(DetachableMagazineItem):
    name                      = "SMG"
    basemass                  = 3.600
    delay                     = 0.11
    reload_time               = 2.5
    magazine_class            = SMGMagazine
    default_magazine          = ParabellumMagazine
    default_magazine_count    = 2
    barrel_mass               = 0.350
    barrel_specific_heat      = 466.0
    barrel_surface_area       = 0.013
    barrel_emissivity         = 0.800
    handguard_mass            = 0.250
    handguard_specific_heat   = 1300.0
    handguard_surface_area    = 0.025
    handguard_emissivity      = 0.9
    heat_transfer_coefficient = 0.02
    barrel_heat_ratio         = 1.0

class ShotgunMagazine(TubularMagazine):
    capacity = 6

class Shotgun(IntegralMagazineItem):
    name                      = "Shotgun"
    basemass                  = 3.600
    delay                     = 1.00
    reload_time               = 0.5
    cartridge_class           = Shotshell
    default_magazine          = ShotgunMagazine
    default_cartridge         = Buckshot0000
    default_reserve           = 35
    barrel_mass               = 0.800
    barrel_specific_heat      = 466.0
    barrel_surface_area       = 0.050
    barrel_emissivity         = 0.8
    handguard_mass            = 0.350
    handguard_specific_heat   = 1300.0
    handguard_surface_area    = 0.030
    handguard_emissivity      = 0.9
    heat_transfer_coefficient = 0.3
    barrel_heat_ratio         = 1.0
