from libcpp cimport bool as bool_t
from cpython.ref cimport PyTypeObject

from pyspades.common cimport Vector, Vertex3
from pyspades.vxl cimport VXLData, MapData
from pyspades.common import Vertex3

cdef public class Material[object Material, type MaterialType]:
    cdef public str name
    "Material name"

    cdef public double durability
    "Average number of seconds to break material with a shovel"

    cdef public double absorption
    "Amount of energy that material can absorb before breaking (J)"

    cdef public double density
    "Density of material (kg/m³)"

    cdef public double strength
    "Material cavity strength (Pa)"

    cdef public double ricochet
    "Conditional probability of ricochet"

    cdef public double deflecting
    "Minimum angle required for a ricochet to occur (radians)"

    cdef public bool_t crumbly
    "Whether material can crumble"

    def __init__(self, **kw):
        for k, v in kw.items():
            setattr(self, k, v)

cdef public MapData * mapDataRef(object o):
    assert isinstance(o, VXLData)

    return (<VXLData> o).map

cdef public Vector * vectorRef(object o):
    assert isinstance(o, Vertex3)

    cdef Vertex3 v = o

    assert v.is_ref
    return v.value

cdef extern from "Milsim/PyEngine.hxx":
    cdef T c_ofMeters "ofMeters"[T](const T)
    cdef T c_toMeters "toMeters"[T](const T)

    cdef cppclass Vector3[T]:
        T x, y, z

        Vector3()
        Vector3(T, T, T)

    cdef Vector3[T] c_cone "cone"[T](const Vector3[T] &, const T)

    void PyEngineReady()
    PyTypeObject PyEngineType

PyEngineReady()

Engine = <type> &PyEngineType

def ofMeters(float x): return c_ofMeters[double](x)
def toMeters(float y): return c_toMeters[double](y)

def cone(v, float deviation):
    cdef Vector3[double] u = c_cone[double](Vector3[double](v.x, v.y, v.z), deviation)

    return Vertex3(u.x, u.y, u.z)
