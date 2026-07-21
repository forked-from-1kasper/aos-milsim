# Copyright © 2024, 2026 rzrn

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
        writer.writeUInt8LE(self.id)

        writer.writeUInt8LE(self.index)

        writer.writeFloat32LE(self.x)
        writer.writeFloat32LE(self.y)
        writer.writeFloat32LE(self.z)

        writer.writeFloat32LE(self.value)

        writer.writeUInt8LE(0xFF if self.origin else 0x00)

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
        writer.writeUInt8LE(self.id)

        writer.writeFloat32LE(self.xf)
        writer.writeFloat32LE(self.yf)
        writer.writeFloat32LE(self.zf)

        writer.writeInt32LE(self.xi)
        writer.writeInt32LE(self.yi)
        writer.writeInt32LE(self.zi)

        writer.writeUInt8LE(self.target)

def hasHitEffects(player):
    return EXTENSION_HIT_EFFECTS in player.proto_extensions
