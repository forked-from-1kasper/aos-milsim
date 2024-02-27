from dataclasses import dataclass

EXTENSION_BASE          = 0x40
EXTENSION_TRACE_BULLETS = 0x10

class TracerPacket:
    id = EXTENSION_BASE + EXTENSION_TRACE_BULLETS

    def __init__(self, index, position, value, origin = False):
        self.index    = index
        self.position = position
        self.value    = value
        self.origin   = origin

    def write(self, writer):
        writer.writeByte(self.id, True)
        writer.writeByte(self.index, False)
        writer.writeFloat(self.position.x, False)
        writer.writeFloat(self.position.y, False)
        writer.writeFloat(self.position.z, False)
        writer.writeFloat(self.value, False)
        writer.writeByte(0xFF if self.origin else 0x00, False)

def hasTraceExtension(conn):
    return EXTENSION_TRACE_BULLETS in conn.proto_extensions

default = 'default'
build   = 'build'

@dataclass
class Material:
    ricochet   : float
    density    : float
    strength   : float
    deflecting : float
    durability : float
    absorption : float

Dirt     = Material(ricochet = 0.3,  deflecting = 75, durability = 1.0,  strength = 2500,   density = 1200, absorption = 1e+15)
Sand     = Material(ricochet = 0.4,  deflecting = 83, durability = 1.0,  strength = 1500,   density = 1600, absorption = 1e+15)
Wood     = Material(ricochet = 0.75, deflecting = 80, durability = 3.0,  strength = 2.1e+6, density = 800,  absorption = 50e+3)
Concrete = Material(ricochet = 0.4,  deflecting = 75, durability = 5.0,  strength = 5e+6,   density = 2400, absorption = 100e+3)
Asphalt  = Material(ricochet = 0.6,  deflecting = 78, durability = 6.0,  strength = 1.2e+6, density = 2400, absorption = 80e+3)
Steel    = Material(ricochet = 0.80, deflecting = 77, durability = 10.0, strength = 500e+6, density = 7850, absorption = 150e+3)
Glass    = Material(ricochet = 0.0,  deflecting = 0,  durability = 0.3,  strength = 7e+6,   density = 2500, absorption = 500)
Plastic  = Material(ricochet = 0.1,  deflecting = 85, durability = 0.5,  strength = 1e+5,   density = 300,  absorption = 50e+3)
Grass    = Material(ricochet = 0.0,  deflecting = 0,  durability = 1.5,  strength = 100,    density = 50,   absorption = 1e+15)