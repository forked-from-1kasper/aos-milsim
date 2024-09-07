from libcpp.unordered_map cimport unordered_map as unordered_map_t
from libcpp cimport bool as bool_t
from libcpp.vector cimport vector

from libc.stdint cimport uint32_t

from cython.operator import dereference as deref
from cython.operator import postincrement
from cpython.ref cimport PyObject

from math import pi, sin, cos

from pyspades.common cimport Vertex3, Vector
from pyspades.vxl cimport VXLData, MapData
from pyspades.common import Vertex3

from milsim.types import Material as PyMaterial, Voxel as PyVoxel

cdef extern from "stdint.h":
    ctypedef unsigned long long uint64_t

cdef extern from "vxl_c.h":
    int get_pos(int, int, int)

cdef extern from "Milsim/Engine.hxx":
    """
    template struct Engine<double>;
    """

    cdef T c_ofMeters "ofMeters"[T](const T)
    cdef T c_toMeters "toMeters"[T](const T)

    unordered_map_t[int, int] * getColorsOf(MapData *)

    cdef cppclass Vector3[T]:
        T x, y, z

        Vector3()
        Vector3(T, T, T)

    cdef Vector3[T] c_cone "cone"[T](const Vector3[T] &, const T)

    cdef cppclass Player[T]:
        void set_crouch(bool_t)
        void set_position(Vector *)
        void set_orientation(Vector *)

    cdef cppclass Material[T]:
        T ricochet
        T density
        T strength
        T deflecting
        T durability
        T absorption
        bool_t crumbly

    cdef cppclass Voxel[T]:
        size_t id
        T durability

    cpdef cppclass DragModel:
        pass

    cdef cppclass Engine[T]:
        vector[Player[T]] players

        Engine()
        uint64_t add(object, int, Vector3[T] r, Vector3[T] v, T timestamp, T mass, T ballistic, uint32_t model, T area)
        void step(T, T)

        void wipe(MapData *)

        void invokeOnTrace(object)
        void invokeOnBlockHit(object)
        void invokeOnPlayerHit(object)
        void invokeOnDestroy(object)

        size_t defaultMaterial, buildMaterial
        Voxel[T] water

        Material[T] & alloc(size_t *)

        void set(const int, const uint32_t, const T)
        Voxel[T] & get(int, int, int)

        void set(const T, const T, const T, const Vector3[T] &)

        T temperature()
        T pressure()
        T humidity()
        T density()
        T mach()
        T po2()
        Vector3[T] wind()

        bool_t dig(int, int, int, T)
        bool_t smash(int, int, int, T)

        void build(int, int, int)
        void destroy(int, int, int)

        void flush()
        double lag()
        double peak()
        size_t alive()
        size_t total()
        size_t usage()

def ofMeters(float x): return c_ofMeters[double](x)
def toMeters(float y): return c_toMeters[double](y)

def cone(v, float deviation):
    cdef Vector3[double] u = c_cone[double](Vector3[double](v.x, v.y, v.z), deviation)

    return Vertex3(u.x, u.y, u.z)

cdef void unpackMaterial(object o, Material[double] * M):
    M.ricochet   = o.ricochet
    M.density    = o.density
    M.strength   = o.strength
    M.deflecting = (o.deflecting / 180) * pi
    M.durability = o.durability
    M.absorption = o.absorption
    M.crumbly    = o.crumbly

cdef Vector3[double] polar(object v, float r, float t):
    x = v.x * cos(t) - v.y * sin(t)
    y = v.x * sin(t) + v.y * cos(t)
    return Vector3[double](r * x, r * y, 0)

cdef class Simulator:
    cdef Engine[double] engine
    cdef object protocol

    cdef object defaultMaterial, buildMaterial, waterMaterial

    cdef dict materials

    def __init__(self, protocol):
        self.materials = {}
        self.protocol  = protocol

        self.engine.invokeOnPlayerHit(protocol.onPlayerHit)
        self.engine.invokeOnBlockHit(protocol.onBlockHit)
        self.engine.invokeOnDestroy(protocol.onDestroy)

    def flush(self):
        self.engine.flush()

    def lag(self):
        return self.engine.lag()

    def peak(self):
        return self.engine.peak()

    def alive(self):
        return self.engine.alive()

    def total(self):
        return self.engine.total()

    def usage(self):
        return self.engine.usage()

    def update(self, E):
        o = E.weather
        t = o.temperature()
        p = o.pressure()
        h = o.humidity()

        v, d = o.wind()
        self.engine.set(t, p, h, polar(E.north, v, d))

    def temperature(self):
        return self.engine.temperature()

    def pressure(self):
        return self.engine.pressure()

    def humidity(self):
        return self.engine.humidity()

    def density(self):
        return self.engine.density()

    def mach(self):
        return self.engine.mach()

    def po2(self):
        return self.engine.po2()

    def wind(self):
        cdef Vector3[double] w = self.engine.wind()
        return Vertex3(w.x, w.y, w.z)

    def invokeOnTrace(self, callback):
        self.engine.invokeOnTrace(callback)

    def build(self, x, y, z):
        self.engine.build(x, y, z)

    def destroy(self, x, y, z):
        self.engine.destroy(x, y, z)

    def dig(self, x, y, z, value):
        return self.engine.dig(x, y, z, value)

    def smash(self, x, y, z, value):
        return self.engine.smash(x, y, z, value)

    def wipe(self):
        self.materials.clear()

        cdef VXLData data = <VXLData> self.protocol.map
        self.engine.wipe(data.map)

    def add(self, thrower, r, v, timestamp, params):
        return self.engine.add(
            params,
            thrower.player_id,
            Vector3[double](r.x, r.y, r.z),
            Vector3[double](v.x, v.y, v.z),
            timestamp,
            params.effmass,
            params.ballistic,
            params.model,
            params.area
        )

    def register(self, o):
        cdef size_t index

        if isinstance(o, PyMaterial):
            unpackMaterial(o, &self.engine.alloc(&index))
            o.index = index

            self.materials[index] = o
        else:
            raise TypeError

    def setDefaultMaterial(self, o):
        self.engine.defaultMaterial = o.index
        self.defaultMaterial = o

    def setBuildMaterial(self, o):
        self.engine.buildMaterial = o.index
        self.buildMaterial = o

    def setWaterMaterial(self, o):
        self.engine.water.id = o.index
        self.waterMaterial = o

    def applyPalette(self, palette):
        cdef VXLData data = <VXLData> self.protocol.map

        it = getColorsOf(data.map).begin()

        while it != getColorsOf(data.map).end():
            index = deref(it).first
            color = deref(it).second & 0xFFFFFF

            m = palette.get(color, self.defaultMaterial)
            self.engine.set(index, m.index, 1.0)

            postincrement(it)

    def get(self, int x, int y, int z):
        cdef Voxel[double] * voxel = &self.engine.get(x, y, z)
        return PyVoxel(self.materials[voxel.id], voxel.durability)

    def set(self, int x, int y, int z, o):
        self.engine.set(get_pos(x, y, z), o.index, 1.0)

    cdef void resize(self):
        self.engine.players.resize(len(self.protocol.players))

    def set_animation(self, size_t i, bool_t value):
        self.engine.players[i].set_crouch(value)

    def on_spawn(self, size_t i):
        self.resize()
        wo = self.protocol.players[i].world_object

        p = <Vertex3> wo.position
        f = <Vertex3> wo.orientation

        assert p.is_ref and f.is_ref

        cdef Player[double] * player = &self.engine.players[i]

        player.set_crouch(wo.crouch)
        player.set_position(p.value)
        player.set_orientation(f.value)

    def on_despawn(self, size_t i):
        cdef Player[double] * player = &self.engine.players[i]

        player.set_crouch(0)
        player.set_position(NULL)
        player.set_orientation(NULL)

        self.resize()

    def step(self, t1, t2):
        self.engine.step(t1, t2)
