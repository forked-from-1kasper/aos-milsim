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

#include <ctypes.h>

extern "C" MapData * mapDataRef(PyObject *);
extern "C" Vector * vectorRef(PyObject *);

template<typename T> Vector3<T> cone(const Vector3<T> & v, const T σ);

struct Object {
private:
    static uint64_t gidx; uint64_t _index;

public:
    PyObject * object; double mass, ballistic, area; uint32_t model;

    int thrower; double timestamp, v0;

    Vector3d position, velocity;

    inline Object(const int i, const Vector3d & r, const Vector3d & v, const double t, PyObject * o) :
    object(o), thrower(i), timestamp(t), position(r), velocity(v) {
        Py_INCREF(o); v0 = v.abs(); _index = gidx++;

        mass      = PyGetAttr<double>(o, "effmass");
        ballistic = PyGetAttr<double>(o, "ballistic");
        area      = PyGetAttr<double>(o, "area");

        model = PyGetAttr<uint32_t>(o, "model");
    }

    inline ~Object() { Py_DECREF(object); }

    inline static void flush() { gidx = 0; }

    inline static uint64_t total() { return gidx; }

    inline uint64_t index() const { return _index; }

    inline double energy() { return 0.5 * mass * velocity.norm(); }
};

struct Player {
    bool c; Vector * p; Vector * f;

    inline Player() : p(nullptr), f(nullptr) {}

    inline bool valid() const { return p != nullptr; }

    inline void set_crouch(bool b)          { c = b; }
    inline void set_position(Vector * v)    { p = v; }
    inline void set_orientation(Vector * v) { f = v; }

    inline bool     crouch()      const { return c; }
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

    inline PyOwnedRef & waterMaterial() { return water.object; }

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
private:
    PyOwnedRef protocol;

    std::vector<Player> players;

    ObjectQueue objects;

    MapData * map; VoxelData vxlData; PyOwnedRef buildMaterial;

    PyOwnedRef onTrace, onBlockHit, onPlayerHit, onDestroy;

    double _lag, _peak;

    // Independent variables.
    double _temperature, _pressure, _humidity; Vector3d _wind;
    // Derived variables.
    double _density, _mach, _ppo2;

private:
    inline bool indestructible(int x, int y, int z)
    { return 62 <= z || !get_solid(x, y, z, map); }

    inline bool unstable(int x₀, int y₀, int z₀) {
        for (int z = z₀ + 1; z < 62; z++) {
            if (!get_solid(x₀, y₀, z, map))
                return true;

            if (!vxlData.get(x₀, y₀, z).material()->crumbly)
                return false;
        }

        return false;
    }

public:
    inline Engine() : _lag(0.0), _peak(0.0) { srand(time(NULL)); players.reserve(32); }

    inline double   temperature() const { return _temperature; } // ℃
    inline double   pressure()    const { return _pressure; }    // Pa
    inline double   humidity()    const { return _humidity; }    // %
    inline double   density()     const { return _density; }     // kg/m³
    inline double   mach()        const { return _mach; }        // m/s
    inline double   ppo2()        const { return _ppo2; }        // Pa
    inline Vector3d wind()        const { return _wind; }        // m/s

    inline double lag()  const { return _lag; }
    inline double peak() const { return _peak; }

    inline size_t alive() const { return objects.size(); }
    inline size_t total() const { return Object::total(); }

    inline size_t usage() const { return vxlData.usage(); }

    inline void setMaterial(int x, int y, int z, PyObject * o) {
        if (o == nullptr || !PyObject_TypeCheck(o, &MaterialType))
            return;

        vxlData.set(x, y, z, o);
    }

    inline PyObject * getMaterial(int x, int y, int z)
    { return vxlData.get(x, y, z).object.incref(); }

    inline double getDurability(int x, int y, int z)
    { return vxlData.get(x, y, z).durability; }

    inline void applyPalette(PyObject * dict) {
        for (auto & [k, v] : map->colors) {
            PyOwnedRef i(PyEncode<unsigned int>(v & 0xFFFFFF));
            vxlData.set(k, PyDict_GetItem(dict, i));
        }
    }

    template<typename... Args> inline void add(Args &&... args) {
        auto & o = objects.emplace_back(args...);
        trace(o.index(), o.position, 1.0, true);
    }

    inline void onSpawn(size_t i) {
        PyOwnedRef ds(protocol, "players");
        if (ds == nullptr) return;

        players.resize(dictLargestKey<int>(ds) + 1);

        auto o = PyDict_GetItem(ds, PyOwnedRef(PyEncode<size_t>(i)));
        if (o == nullptr) return;

        PyOwnedRef wo(o, "world_object");
        if (wo == nullptr) return;

        PyOwnedRef p(wo, "position"), f(wo, "orientation"), c(wo, "crouch");

        auto & player = players[i];
        player.set_crouch(c == Py_True);
        if (p != nullptr) player.set_position(vectorRef(p));
        if (f != nullptr) player.set_orientation(vectorRef(f));
    }

    inline void onDespawn(size_t i) {
        auto & player = players[i];
        player.set_crouch(false);
        player.set_position(nullptr);
        player.set_orientation(nullptr);

        PyOwnedRef ds(protocol, "players");
        if (ds == nullptr) return;

        players.resize(dictLargestKey<int>(ds) + 1);
    }

    inline void setAnimation(size_t i, bool crouch) {
        players[i].set_crouch(crouch);
    }

    void setWeather(double t, double p, double φ, const Vector3d & w);
    void clear();

    inline void dig(int player_id, int x, int y, int z, double value) {
        if (indestructible(x, y, z)) return;

        auto & voxel = vxlData.get(x, y, z); auto M = voxel.material();

        if (voxel.isub(value / M->durability))
            onDestroy(player_id, x, y, z);
    }

    inline void smash(int player_id, int x, int y, int z, double ΔE) {
        if (indestructible(x, y, z)) return;

        auto & voxel = vxlData.get(x, y, z); auto M = voxel.material();

        if (M->crumbly && randbool<double>(0.5) && unstable(x, y, z)) {
            onDestroy(player_id, x, y, z);
            return;
        }

        if (voxel.isub(ΔE * (M->durability / M->absorption)))
            onDestroy(player_id, x, y, z);
    }

    inline void build(int x, int y, int z) { vxlData.set(x, y, z, buildMaterial); }
    inline void destroy(int x, int y, int z) { vxlData.erase(x, y, z); }

    inline void setDefaultMaterial(PyObject * o) { vxlData.defaultMaterial.retain(o); }
    inline void setWaterMaterial(PyObject * o) { vxlData.waterMaterial().retain(o); }
    inline void setBuildMaterial(PyObject * o) { buildMaterial.retain(o); }

    inline void invokeOnPlayerHit(PyObject * o) { onPlayerHit.retain(PyCallable_Check(o) ? o : nullptr); }
    inline void invokeOnBlockHit(PyObject * o) { onBlockHit.retain(PyCallable_Check(o) ? o : nullptr); }
    inline void invokeOnTrace(PyObject * o) { onTrace.retain(PyCallable_Check(o) ? o : nullptr); }
    inline void invokeOnDestroy(PyObject * o) { onDestroy.retain(PyCallable_Check(o) ? o : nullptr); }
    inline void setProtocolObject(PyObject * o) { protocol.retain(o); }

    void step(const double t1, const double t2);

    inline void flush() { objects.clear(); }

private:
    inline void trace(const uint64_t index, const Vector3d & r, const double value, bool origin)
    { onTrace(index, r.x, r.y, r.z, value, origin); }

    void next(double t1, const double t2, ObjectIterator &);
};
