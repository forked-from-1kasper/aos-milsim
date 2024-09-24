from libcpp.unordered_map cimport unordered_map as unordered_map_t
from libcpp cimport bool as bool_t
from libcpp.vector cimport vector

from cython.operator import dereference as deref
from cython.operator import postincrement
from cpython.ref cimport PyObject

from math import sin, cos

from pyspades.common cimport Vertex3, Vector
from pyspades.vxl cimport VXLData, MapData
from pyspades.common import Vertex3

cdef public MapData * mapDataRef(object o):
    assert isinstance(o, VXLData)

    return (<VXLData> o).map

cdef public Vector * vectorRef(object o):
    assert isinstance(o, Vertex3)

    cdef Vertex3 v = o

    assert v.is_ref
    return v.value

cdef extern from "vxl_c.h":
    int get_pos(int, int, int)

cdef extern from "Milsim/Engine.hxx":
    cdef T c_ofMeters "ofMeters"[T](const T)
    cdef T c_toMeters "toMeters"[T](const T)

    cdef cppclass Vector3[T]:
        T x, y, z

        Vector3()
        Vector3(T, T, T)

    cdef Vector3[T] c_cone "cone"[T](const Vector3[T] &, const T)

    cdef cppclass Engine:
        Engine()
        void add(int, Vector3[double] r, Vector3[double] v, double timestamp, object)
        void step(double, double)

        void clear()

        void invokeOnTrace(object)
        void invokeOnBlockHit(object)
        void invokeOnPlayerHit(object)
        void invokeOnDestroy(object)
        void setProtocolObject(object)

        void setDefaultMaterial(object)
        void setBuildMaterial(object)
        void setWaterMaterial(object)

        void set(const int, object, const double)

        object getMaterial(int, int, int)
        double getDurability(int, int, int)

        void applyPalette(object)

        void set(const double, const double, const double, const Vector3[double] &)

        double temperature()
        double pressure()
        double humidity()
        double density()
        double mach()
        double ppo2()
        Vector3[double] wind()

        void on_spawn(size_t)
        void on_despawn(size_t)
        void set_animation(size_t, bool_t)

        void dig(int, int, int, int, double)
        void smash(int, int, int, int, double)

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

cdef Vector3[double] polar(object v, float r, float t):
    x = v.x * cos(t) - v.y * sin(t)
    y = v.x * sin(t) + v.y * cos(t)
    return Vector3[double](r * x, r * y, 0)

cdef class Simulator:
    cdef Engine engine

    def __init__(self, protocol):
        self.engine.setProtocolObject(protocol)
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
        t = E.temperature()
        p = E.pressure()
        h = E.humidity()
        w = E.wind()
        self.engine.set(t, p, h, Vector3[double](w.x, w.y, w.z))

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

    def ppo2(self):
        return self.engine.ppo2()

    def wind(self):
        cdef Vector3[double] w = self.engine.wind()
        return Vertex3(w.x, w.y, w.z)

    def invokeOnTrace(self, o):
        self.engine.invokeOnTrace(o)

    def build(self, x, y, z):
        self.engine.build(x, y, z)

    def destroy(self, x, y, z):
        self.engine.destroy(x, y, z)

    def dig(self, player_id, x, y, z, value):
        self.engine.dig(player_id, x, y, z, value)

    def smash(self, player_id, x, y, z, value):
        self.engine.smash(player_id, x, y, z, value)

    def clear(self):
        self.engine.clear()

    def add(self, thrower, r, v, timestamp, params):
        self.engine.add(
            thrower.player_id,
            Vector3[double](r.x, r.y, r.z),
            Vector3[double](v.x, v.y, v.z),
            timestamp,
            params
        )

    def setDefaultMaterial(self, o):
        self.engine.setDefaultMaterial(o)

    def setBuildMaterial(self, o):
        self.engine.setBuildMaterial(o)

    def setWaterMaterial(self, o):
        self.engine.setWaterMaterial(o)

    def applyPalette(self, palette):
        self.engine.applyPalette(palette)

    def getMaterial(self, int x, int y, int z):
        return self.engine.getMaterial(x, y, z)

    def getDurability(self, int x, int y, int z):
        return self.engine.getDurability(x, y, z)

    def set(self, int x, int y, int z, o):
        self.engine.set(get_pos(x, y, z), o, 1.0)

    def on_spawn(self, size_t i):
        self.engine.on_spawn(i)

    def on_despawn(self, size_t i):
        self.engine.on_despawn(i)

    def set_animation(self, size_t i, bool_t value):
        self.engine.set_animation(i, value)

    def step(self, t1, t2):
        self.engine.step(t1, t2)
