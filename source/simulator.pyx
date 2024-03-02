from libcpp.map cimport map as map_t
from libcpp cimport bool as bool_t
from libcpp.vector cimport vector
from libc.stdint cimport uint32_t
from cpython.ref cimport PyObject
from math import pi

from pyspades.vxl cimport VXLData, MapData
from pyspades.common import Vertex3

cdef extern from "stdint.h":
    ctypedef unsigned long long uint64_t

cdef extern from "world_c.cpp":
    MapData * global_map

    int c_can_see "can_see" (
        MapData *,
        float x0, float y0, float z0,
        float x1, float y1, float z1
    )

    int c_cast_ray "cast_ray" (
        MapData *, float x0, float y0, float z0,
        float x1, float y1, float z1, float length,
        long * x, long * y, long * z
    )

cdef extern from "Milsim/Engine.hxx":
    """
    template struct Engine<double>;
    """

    cdef cppclass Vector3[T]:
        T x, y, z

        Vector3()
        Vector3(T, T, T)

    cdef Vector3[T] c_cone "cone"[T](const Vector3[T] &, const T)

    cdef cppclass Player[T]:
        void set(int, T x, T y, T z, T ox, T oy, T oz, bool_t)

    cdef cppclass Material[T]:
        T      ricochet
        T      density
        T      strength
        T      deflecting
        T      durability
        T      absorption
        bool_t crumbly

    cdef cppclass Engine[T]:
        vector[Player[T]] players

        Engine()
        uint64_t add(int, Vector3[T] r, Vector3[T] v, T timestamp, bool_t grenade, T mass, T drag, T area)
        void step(T, T)

        void uploadMap(MapData *)

        void invokeOnTrace(object)
        void invokeOnHitEffect(object)
        void invokeOnHit(object)
        void invokeOnDestroy(object)

        Material[T] defaultMaterial, buildMaterial

        Material[T] & allocMaterial(uint32_t)
        void resetMaterials()

        bool_t dig(int, int, int, T)
        bool_t smash(int, int, int, T)

        void build(int, int, int)
        void destroy(int, int, int)

        void flush()
        double lag()
        size_t alive()
        size_t total()

def can_see(VXLData data, float x0, float y0, float z0, float x1, float y1, float z1):
    global global_map
    global_map = data.map

    cdef bint retval = c_can_see(data.map, x0, y0, z0, x1, y1, z1)
    return retval

def raycast(VXLData data, float x0, float y0, float z0, float x1, float y1, float z1, float length):
    global global_map
    global_map = data.map

    cdef long x = -1, y = -1, z = -1

    if c_cast_ray(data.map, x0, y0, z0, x1, y1, z1, length, &x, &y, &z):
        return (x, y, z)
    else:
        return None

def cone(v, float deviation):
    cdef Vector3[double] u = c_cone[double](Vector3[double](v.x, v.y, v.z), deviation)

    return Vertex3(u.x, u.y, u.z)

cdef void unpackMaterial(object o, Material[double] * M):
    if o is not None:
        M.ricochet   = o.ricochet
        M.density    = o.density
        M.strength   = o.strength
        M.deflecting = (o.deflecting / 180) * pi
        M.durability = o.durability
        M.absorption = o.absorption
        M.crumbly    = o.crumbly

cdef class Simulator:
    cdef Engine[double] engine
    cdef object protocol

    def __init__(self, protocol):
        self.protocol = protocol

        self.engine.invokeOnHitEffect(protocol.onHitEffect)

        self.engine.invokeOnHit(protocol.onHit)
        self.engine.invokeOnDestroy(protocol.onDestroy)

    def flush(self):
        self.engine.flush()

    def lag(self):
        return self.engine.lag()

    def alive(self):
        return self.engine.alive()

    def total(self):
        return self.engine.total()

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

    def uploadMap(self):
        cdef VXLData data = <VXLData> self.protocol.map
        self.engine.uploadMap(data.map)

    def add(self, thrower, r, v, timestamp, params):
        return self.engine.add(
            thrower.player_id,
            Vector3[double](r.x, r.y, r.z),
            Vector3[double](v.x, v.y, v.z),
            timestamp,
            params.grenade,
            params.mass,
            params.drag,
            params.area
        )

    def setDefaultMaterial(self, o):
        unpackMaterial(o, &self.engine.defaultMaterial)

    def setBuildMaterial(self, o):
        unpackMaterial(o, &self.engine.buildMaterial)

    def registerMaterial(self, color, o):
        unpackMaterial(o, &self.engine.allocMaterial(color))

    def resetMaterials(self):
        self.engine.resetMaterials()

    def step(self, t1, t2):
        self.engine.players.resize(len(self.protocol.players))

        for i, player in enumerate(self.protocol.players.values()):
            character = player.world_object

            if character and not character.dead:
                position    = character.position
                orientation = character.orientation

                self.engine.players[i].set(
                    player.player_id, position.x, position.y, position.z,
                    orientation.x, orientation.y, orientation.z, character.crouch
                )
            else:
                self.engine.players[i].set(player.player_id, 0, -64, 0, 0, 0, 0, 0)

        self.engine.step(t1, t2)
