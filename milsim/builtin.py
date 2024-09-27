from math import radians

from pyspades.common import Vertex3

from milsim.engine import Material

from milsim.common import grain, gram, isosceles, yard, inch, mm, MOA
from milsim.blast import sendGrenadePacket, explode
from milsim.types import G1, G7, Shotshell

class G7HEI(G7):
    def explode(self, protocol, player_id, r):
        if player := protocol.players.get(player_id):
            sendGrenadePacket(protocol, player_id, r, Vertex3(1, 0, 0), -1)
            explode(4, 20, player, r)

            return True

    def on_block_hit(self, protocol, r, v, X, Y, Z, thrower, E, A):
        return self.explode(protocol, thrower, r)

    def on_player_hit(self, protocol, r, v, X, Y, Z, thrower, E, A, target, limb_index):
        return self.explode(protocol, thrower, r)

Dirt     = Material(name = "dirt",     ricochet = 0.30, deflecting = radians(75), durability = 1.0,  strength = 2500,   density = 1200, absorption = 1e+15,  crumbly = True)
Sand     = Material(name = "sand",     ricochet = 0.40, deflecting = radians(83), durability = 1.0,  strength = 1500,   density = 1600, absorption = 1e+15,  crumbly = True)
Wood     = Material(name = "wood",     ricochet = 0.75, deflecting = radians(80), durability = 3.0,  strength = 2.1e+6, density = 800,  absorption = 50e+3,  crumbly = False)
Concrete = Material(name = "concrete", ricochet = 0.40, deflecting = radians(75), durability = 5.0,  strength = 5e+6,   density = 2400, absorption = 100e+3, crumbly = False)
Asphalt  = Material(name = "asphalt",  ricochet = 0.60, deflecting = radians(78), durability = 6.0,  strength = 1.2e+6, density = 2400, absorption = 80e+3,  crumbly = False)
Stone    = Material(name = "stone",    ricochet = 0.50, deflecting = radians(90), durability = 30.0, strength = 20e+6,  density = 2500, absorption = 5e+5,   crumbly = False)
Brick    = Material(name = "brick",    ricochet = 0.30, deflecting = radians(76), durability = 7.0,  strength = 2e+6,   density = 1800, absorption = 80e+3,  crumbly = False)
Steel    = Material(name = "steel",    ricochet = 0.80, deflecting = radians(77), durability = 10.0, strength = 500e+6, density = 7850, absorption = 150e+3, crumbly = False)
Glass    = Material(name = "glass",    ricochet = 0.00, deflecting = radians(0),  durability = 0.15, strength = 7e+6,   density = 2500, absorption = 500,    crumbly = False)
Plastic  = Material(name = "plastic",  ricochet = 0.10, deflecting = radians(85), durability = 0.5,  strength = 1e+5,   density = 300,  absorption = 50e+3,  crumbly = True)
Grass    = Material(name = "grass",    ricochet = 0.00, deflecting = radians(0),  durability = 1.5,  strength = 100,    density = 50,   absorption = 1e+4,   crumbly = True)
Water    = Material(name = "water",    ricochet = 0.70, deflecting = radians(78), durability = 1e+6, strength = 1,      density = 1000, absorption = 1e+15,  crumbly = False)

Buckshot0000 = Shotshell(name = "0000 Buckshot", muzzle = 457.00, effmass = grain(82.000),  totmass = gram(150.00), grouping = isosceles(yard(25), inch(40)), deviation = 0.10, diameter = mm(9.65), pellets = 15)
Buckshot00   = Shotshell(name = "00 Buckshot",   muzzle = 396.24, effmass = grain(350.000), totmass = gram(170.00), grouping = isosceles(yard(25), inch(40)), deviation = 0.10, diameter = mm(8.38), pellets = 5)
Bullet       = Shotshell(name = "Bullet",        muzzle = 540.00, effmass = grain(109.375), totmass = gram(20.00),  grouping = 0,                             deviation = 0.10, diameter = mm(10.4), pellets = 1)

R145x114mm = G1(name = "R145x114mm", muzzle = 1000, effmass = gram(67.00), totmass = gram(191.00), grouping = MOA(0.7), deviation = 0.03, BC = 0.800, caliber = mm(14.50))
R127x108mm = G1(name = "R127x108mm", muzzle = 900,  effmass = gram(50.00), totmass = gram(130.00), grouping = MOA(0.7), deviation = 0.03, BC = 0.732, caliber = mm(12.70))
R762x54mm  = G7(name = "R762x54mm",  muzzle = 850,  effmass = gram(10.00), totmass = gram(22.00),  grouping = MOA(0.7), deviation = 0.03, BC = 0.187, caliber = mm(07.62))
Parabellum = G1(name = "Parabellum", muzzle = 600,  effmass = gram(8.03),  totmass = gram(12.00),  grouping = MOA(2.5), deviation = 0.05, BC = 0.212, caliber = mm(09.00))

HEI762x54mm = G7HEI(name = "HEI762x54mm", muzzle = 820, effmass = gram(160.00), totmass = gram(250.00), grouping = MOA(2.0), deviation = 0.07, BC = 0.190, caliber = mm(07.62))
