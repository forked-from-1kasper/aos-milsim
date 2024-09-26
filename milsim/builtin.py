from math import radians

from milsim.engine import Material

Dirt     = Material(name = "dirt",     ricochet = 0.3,  deflecting = radians(75), durability = 1.0,  strength = 2500,   density = 1200, absorption = 1e+15,  crumbly = True)
Sand     = Material(name = "sand",     ricochet = 0.4,  deflecting = radians(83), durability = 1.0,  strength = 1500,   density = 1600, absorption = 1e+15,  crumbly = True)
Wood     = Material(name = "wood",     ricochet = 0.75, deflecting = radians(80), durability = 3.0,  strength = 2.1e+6, density = 800,  absorption = 50e+3,  crumbly = False)
Concrete = Material(name = "concrete", ricochet = 0.4,  deflecting = radians(75), durability = 5.0,  strength = 5e+6,   density = 2400, absorption = 100e+3, crumbly = False)
Asphalt  = Material(name = "asphalt",  ricochet = 0.6,  deflecting = radians(78), durability = 6.0,  strength = 1.2e+6, density = 2400, absorption = 80e+3,  crumbly = False)
Stone    = Material(name = "stone",    ricochet = 0.5,  deflecting = radians(90), durability = 30.0, strength = 20e+6,  density = 2500, absorption = 5e+5,   crumbly = False)
Brick    = Material(name = "brick",    ricochet = 0.3,  deflecting = radians(76), durability = 7.0,  strength = 2e+6,   density = 1800, absorption = 80e+3,  crumbly = False)
Steel    = Material(name = "steel",    ricochet = 0.80, deflecting = radians(77), durability = 10.0, strength = 500e+6, density = 7850, absorption = 150e+3, crumbly = False)
Glass    = Material(name = "glass",    ricochet = 0.0,  deflecting = radians(0),  durability = 0.15, strength = 7e+6,   density = 2500, absorption = 500,    crumbly = False)
Plastic  = Material(name = "plastic",  ricochet = 0.1,  deflecting = radians(85), durability = 0.5,  strength = 1e+5,   density = 300,  absorption = 50e+3,  crumbly = True)
Grass    = Material(name = "grass",    ricochet = 0.0,  deflecting = radians(0),  durability = 1.5,  strength = 100,    density = 50,   absorption = 1e+4,   crumbly = True)
Water    = Material(name = "water",    ricochet = 0.7,  deflecting = radians(78), durability = 1e+6, strength = 1,      density = 1000, absorption = 1e+15,  crumbly = False)
