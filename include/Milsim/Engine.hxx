#pragma once

#include <Milsim/Vector.hxx>
#include <Milsim/AABB.hxx>

#include <Milsim/Fundamentals.hxx>

#include <unordered_map>
#include <utility>
#include <cstdint>
#include <vector>
#include <chrono>
#include <list>
#include <map>

#include <Python.hxx>

#include <common_c.h>
#include <vxl_c.h>

#include <engine.h>

struct Object {
private:
    static uint64_t gidx;

    PyObject * _object; uint64_t _index; uint32_t _model;
    int _thrower; double _timestamp, _v0;

public:
    double mass, ballistic, area;
    Vector3d position, velocity;

    inline static void     flush() { gidx = 0;    }
    inline static uint64_t total() { return gidx; }

    inline Object(const int i, const Vector3d & r, const Vector3d & v, const double t, PyObject * o) :
        _object(o),
        _model(PyGetAttr<uint32_t>(o, "model")),
        _thrower(i), _timestamp(t), _v0(v.abs()),
        mass(PyGetAttr<double>(o, "effmass")),
        ballistic(PyGetAttr<double>(o, "ballistic")),
        area(PyGetAttr<double>(o, "area")),
        position(r), velocity(v)
    { Py_INCREF(o); _index = gidx++; }

    inline ~Object() { Py_DECREF(_object); }

    inline double energy() const { return 0.5 * mass * velocity.norm(); }

    inline PyObject * object()    const { return _object;    }
    inline uint64_t   index()     const { return _index;     }
    inline uint32_t   model()     const { return _model;     }
    inline int        thrower()   const { return _thrower;   }
    inline double     timestamp() const { return _timestamp; }
    inline double     v0()        const { return _v0;        }
};

struct Player {
    bool c; Vector * p; Vector * f;

    inline Player() : p(nullptr), f(nullptr) {}

    inline bool valid() const { return p != nullptr; }

    inline void set_crouch(bool b)          { c = b; }
    inline void set_position(Vector * v)    { p = v; }
    inline void set_orientation(Vector * v) { f = v; }

    inline bool     crouch()      const { return c;           }
    inline Vector3d position()    const { return Vector3d(p); }
    inline Vector3d orientation() const { return Vector3d(f); }

    inline auto intersect(const Ray<double> & r) const {
        using namespace std;

        auto origin = position().translate(0, 0, crouch() ? -1.05 : -1.1);

        auto ray = r.translate(-origin).pointAt(
            orientation().xOy().normal(), Vector3d(0, 1, 0)
        );

        auto & head  = Box::head<double>;
        auto & torso = crouch() ? Box::torsoc<double>     : Box::torso<double>;
        auto & legl  = crouch() ? Box::legc_left<double>  : Box::leg_left<double>;
        auto & legr  = crouch() ? Box::legc_right<double> : Box::leg_right<double>;
        auto & armr  = crouch() ? Box::armc_right<double> : Box::arm_right<double>;
        auto & arml  = crouch() ? Box::armc_left<double>  : Box::arm_left<double>;

        return min(
            [](auto & w1, auto & w2) { return w1 < w2; },
            head.intersect(ray), torso.intersect(ray),
            legl.intersect(ray), legr.intersect(ray),
            armr.intersect(ray), arml.intersect(ray.rot(Vector3<double>(0, 0, 1), -std::numbers::pi_v<double> / 4))
        );
    }
};

enum class Terminal { flying, ricochet, penetration };

using ObjectQueue    = std::list<Object>;
using ObjectIterator = ObjectQueue::iterator;

struct Voxel {
    PyOwnedRef object; double durability;

    inline Voxel() : object(), durability(0) {}
    inline Voxel(PyObject * o, const double f) : object(o), durability(f) { Py_INCREF(o); }

    inline Material * material() const { return reinterpret_cast<Material *>(static_cast<PyObject *>(object)); }

    inline bool isub(double delta) { durability -= delta; return durability <= 0; }
};

class VoxelData {
private:
    Voxel water; std::unordered_map<int, Voxel> data;
public:
    PyOwnedRef defaultMaterial;

    inline VoxelData() { water.durability = std::numeric_limits<double>::infinity(); }

    inline auto & waterMaterial() { return water.object; }

    Voxel & set(int i, PyObject * o);
    Voxel & get(int x, int y, int z);

    inline Voxel & set(int x, int y, int z, PyObject * o)
    { return set(get_pos(x, y, z), o); }

    inline void erase(int x, int y, int z) { data.erase(get_pos(x, y, z)); }

    inline void clear() { data.clear(); defaultMaterial.retain(nullptr); waterMaterial().retain(nullptr); }

    // This is only the lower bound.
    inline size_t usage() const {
        constexpr size_t entrySize = sizeof(int) + sizeof(Voxel);
        return sizeof(decltype(data)) + entrySize * data.size();
    }
};

template<typename T> inline T dictLargestKey(PyObject * dict) {
    T retval = -1;

    Py_ssize_t i = 0; PyObject * k, * v;

    while (PyDict_Next(dict, &i, &k, &v))
        retval = std::max<T>(retval, PyDecode<T>(k));

    return retval;
}

struct Engine {
public:
    PyOwnedRef protocol;

private:
    MapData * _map;

    double _lag, _peak;

public:
    VoxelData vxlData;
    ObjectQueue objects;
    std::vector<Player> players;

    PyOwnedRef onTrace, onBlockHit, onPlayerHit, onDestroy;

    // Independent variables.
    double   temperature; // ℃
    double   pressure;    // Pa
    double   humidity;    // %
    Vector3d wind;        // m/s

private:
    // Derived variables.
    double _density; // kg/m³
    double _mach;    // m/s
    double _ppo2;    // Pa

    void next(double t1, const double t2, ObjectIterator &);

public:
    inline Engine(PyObject * o) : protocol(o), _lag(0.0), _peak(0.0)
    { srand(time(NULL)); players.reserve(32); }

    inline bool indestructible(int x, int y, int z)
    { return 62 <= z || !get_solid(x, y, z, _map); }

    inline bool unstable(int x₀, int y₀, int z₀) {
        for (int z = z₀ + 1; z < 62; z++) {
            if (!get_solid(x₀, y₀, z, _map))
                return true;

            if (!vxlData.get(x₀, y₀, z).material()->crumbly)
                return false;
        }

        return false;
    }

    inline MapData * map() const { return _map;      }

    inline double density() const { return _density; }
    inline double mach()    const { return _mach;    }
    inline double ppo2()    const { return _ppo2;    }

    inline double lag()  const { return _lag;  }
    inline double peak() const { return _peak; }

    inline size_t alive() const { return objects.size(); }
    inline size_t total() const { return Object::total(); }

    inline size_t usage() const { return vxlData.usage(); }

    void update();
    void clear();

    inline void trace(const uint64_t index, const Vector3d & r, const double value, bool origin)
    { onTrace(index, r.x, r.y, r.z, value, origin); }

    void step(const double t1, const double t2);
};
