from libcpp cimport bool as bool_t

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
