from typing import Callable
from math import atan

from pyspades.constants import RIFLE_WEAPON, SMG_WEAPON, SHOTGUN_WEAPON

from milsim.types import *

Dirt     = Material(ricochet = 0.3,  deflecting = 75, durability = 1.0,  strength = 2500,   density = 1200, absorption = 1e+15)
Sand     = Material(ricochet = 0.4,  deflecting = 83, durability = 1.0,  strength = 1500,   density = 1600, absorption = 1e+15)
Wood     = Material(ricochet = 0.75, deflecting = 80, durability = 3.0,  strength = 2.1e+6, density = 800,  absorption = 50e+3)
Concrete = Material(ricochet = 0.4,  deflecting = 75, durability = 5.0,  strength = 5e+6,   density = 2400, absorption = 100e+3)
Asphalt  = Material(ricochet = 0.6,  deflecting = 78, durability = 6.0,  strength = 1.2e+6, density = 2400, absorption = 80e+3)
Steel    = Material(ricochet = 0.80, deflecting = 77, durability = 10.0, strength = 500e+6, density = 7850, absorption = 150e+3)
Glass    = Material(ricochet = 0.0,  deflecting = 0,  durability = 0.3,  strength = 7e+6,   density = 2500, absorption = 500)
Plastic  = Material(ricochet = 0.1,  deflecting = 85, durability = 0.5,  strength = 1e+5,   density = 300,  absorption = 50e+3)
Grass    = Material(ricochet = 0.0,  deflecting = 0,  durability = 1.5,  strength = 100,    density = 50,   absorption = 1e+15)

mm   = lambda s: s / 1000
gram = lambda m: m / 1000
yard = lambda s: s * 0.9144
inch = lambda s: s * 0.0254
Cone = lambda H, d: atan(0.5 * d / H)

R127x108mm = Round(900, gram(50.00), 150.0000, mm(12.70),  1)
R762x54mm  = Round(850, gram(10.00), 146.9415, mm(07.62),  1)
Parabellum = Round(600, gram(08.03), 104.7573, mm(09.00),  1)
Shot       = Round(457, gram(38.00),   5.0817, mm(18.40), 15)

Rifle = Gun(
    name               = "Rifle",
    ammo               = Magazines(5, 10),
    round              = R762x54mm,
    delay              = 0.50,
    reload_time        = 2.5,
    spread             = 0,
    velocity_deviation = 0.05
)

SMG = Gun(
    name               = "SMG",
    ammo               = Magazines(4, 30),
    round              = Parabellum,
    delay              = 0.11,
    reload_time        = 2.5,
    spread             = 0,
    velocity_deviation = 0.05
)

Shotgun = Gun(
    name               = "Shotgun",
    ammo               = Heap(6, 48),
    round              = Shot,
    delay              = 1.00,
    reload_time        = 0.5,
    spread             = Cone(yard(25), inch(40)),
    velocity_deviation = 0.10
)

guns = {RIFLE_WEAPON: Rifle, SMG_WEAPON: SMG, SHOTGUN_WEAPON: Shotgun}
