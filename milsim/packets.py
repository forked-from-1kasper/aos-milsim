EXTENSION_BASE          = 0x40
EXTENSION_TRACE_BULLETS = 0x10
EXTENSION_HIT_EFFECTS   = 0x11

milsim_extensions = [(EXTENSION_TRACE_BULLETS, 1), (EXTENSION_HIT_EFFECTS, 1)]

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

class HitEffectPacket:
    id = EXTENSION_BASE + EXTENSION_HIT_EFFECTS

    def __init__(self, position, x, y, z, target):
        self.position = position
        self.x        = x
        self.y        = y
        self.z        = z
        self.target   = target

    def write(self, writer):
        writer.writeByte(self.id, True)

        writer.writeFloat(self.position.x, False)
        writer.writeFloat(self.position.y, False)
        writer.writeFloat(self.position.z, False)

        writer.writeInt(self.x, False, False)
        writer.writeInt(self.y, False, False)
        writer.writeInt(self.z, False, False)

        writer.writeByte(self.target, False)

def hasHitEffects(conn):
    return EXTENSION_HIT_EFFECTS in conn.proto_extensions
