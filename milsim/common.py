from itertools import product
from math import atan

from milsim.types import *

mm   = lambda s: s / 1000
gram = lambda m: m / 1000
yard = lambda s: s * 0.9144
inch = lambda s: s * 0.0254
TNT  = lambda m: m * 4.6e+6

isosceles = lambda H, d: atan(0.5 * d / H)

Dirt     = Material(name = "dirt",     ricochet = 0.3,  deflecting = 75, durability = 1.0,  strength = 2500,   density = 1200, absorption = 1e+15,  crumbly = True)
Sand     = Material(name = "sand",     ricochet = 0.4,  deflecting = 83, durability = 1.0,  strength = 1500,   density = 1600, absorption = 1e+15,  crumbly = True)
Wood     = Material(name = "wood",     ricochet = 0.75, deflecting = 80, durability = 3.0,  strength = 2.1e+6, density = 800,  absorption = 50e+3,  crumbly = False)
Concrete = Material(name = "concrete", ricochet = 0.4,  deflecting = 75, durability = 5.0,  strength = 5e+6,   density = 2400, absorption = 100e+3, crumbly = False)
Asphalt  = Material(name = "asphalt",  ricochet = 0.6,  deflecting = 78, durability = 6.0,  strength = 1.2e+6, density = 2400, absorption = 80e+3,  crumbly = False)
Steel    = Material(name = "steel",    ricochet = 0.80, deflecting = 77, durability = 10.0, strength = 500e+6, density = 7850, absorption = 150e+3, crumbly = False)
Glass    = Material(name = "glass",    ricochet = 0.0,  deflecting = 0,  durability = 0.15, strength = 7e+6,   density = 2500, absorption = 500,    crumbly = False)
Plastic  = Material(name = "plastic",  ricochet = 0.1,  deflecting = 85, durability = 0.5,  strength = 1e+5,   density = 300,  absorption = 50e+3,  crumbly = True)
Grass    = Material(name = "grass",    ricochet = 0.0,  deflecting = 0,  durability = 1.5,  strength = 100,    density = 50,   absorption = 1e+4,   crumbly = True)
Water    = Material(name = "water",    ricochet = 0.7,  deflecting = 78, durability = 1e+6, strength = 1,      density = 1000, absorption = 1e+15,  crumbly = False)

R127x108mm = Round(900, gram(50.00), 150.0000, mm(12.70),  1)
R762x54mm  = Round(850, gram(10.00), 146.9415, mm(07.62),  1)
Parabellum = Round(600, gram(08.03), 104.7573, mm(09.00),  1)
Shot       = Round(457, gram(38.00),  15.0817, mm(18.40), 15)

grenade_zone = lambda x, y, z: product(range(x - 1, x + 2), range(y - 1, y + 2), range(z - 1, z + 2))
