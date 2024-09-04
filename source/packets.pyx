from libcpp cimport bool as bool_t

from pyspades.bytes cimport ByteWriter
from pyspades.loaders cimport Loader

EXTENSION_BASE          = 0x40
EXTENSION_TRACE_BULLETS = 0x10
EXTENSION_HIT_EFFECTS   = 0x11

milsim_extensions = [(EXTENSION_TRACE_BULLETS, 1), (EXTENSION_HIT_EFFECTS, 1)]

cdef class TracerPacket(Loader):
    id = EXTENSION_BASE + EXTENSION_TRACE_BULLETS

    cdef public:
        int index
        float x, y, z
        float value
        bool_t origin

    def __init__(self, index, position, value, origin = False):
        self.index  = index
        self.x      = position.x
        self.y      = position.y
        self.z      = position.z
        self.value  = value
        self.origin = origin

    cpdef write(self, ByteWriter writer):
        writer.writeByte(self.id, True)

        writer.writeByte(self.index, False)

        writer.writeFloat(self.x, False)
        writer.writeFloat(self.y, False)
        writer.writeFloat(self.z, False)

        writer.writeFloat(self.value, False)

        writer.writeByte(0xFF if self.origin else 0x00, False)

def hasTraceExtension(player):
    return EXTENSION_TRACE_BULLETS in player.proto_extensions

cdef class HitEffectPacket(Loader):
    id = EXTENSION_BASE + EXTENSION_HIT_EFFECTS

    cdef public:
        int target
        int xi, yi, zi
        float xf, yf, zf

    def __init__(self, xf, yf, zf, xi, yi, zi, target):
        self.xf     = xf
        self.yf     = yf
        self.zf     = zf
        self.xi     = xi
        self.yi     = yi
        self.zi     = zi
        self.target = target

    cpdef write(self, ByteWriter writer):
        writer.writeByte(self.id, True)

        writer.writeFloat(self.xf, False)
        writer.writeFloat(self.yf, False)
        writer.writeFloat(self.zf, False)

        writer.writeInt(self.xi, False, False)
        writer.writeInt(self.yi, False, False)
        writer.writeInt(self.zi, False, False)

        writer.writeByte(self.target, False)

def hasHitEffects(player):
    return EXTENSION_HIT_EFFECTS in player.proto_extensions
