from enum import Enum

Pound = 0.45359237
Yard  = 0.9144
Inch  = 0.0254

class Limb(Enum):
    head  = 0
    torso = 1
    arml  = 2
    armr  = 3
    legl  = 4
    legr  = 5

class HitEffect:
    block    = 0
    headshot = 1
    player   = 2
