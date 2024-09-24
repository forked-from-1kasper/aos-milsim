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

struct Object {
private:
    static uint64_t gidx; uint64_t _index;

public:
    PyObject * object; double mass, ballistic, area; uint32_t model;

    int thrower; double timestamp, v0;

    Vector3d position, velocity;

    Object(const int i, const Vector3d & r, const Vector3d & v, const double t, PyObject * o) :
    object(o), thrower(i), timestamp(t), position(r), velocity(v) {
        Py_INCREF(o); v0 = v.abs(); _index = gidx++;

        mass      = PyGetAttr<double>(o, "effmass");
        ballistic = PyGetAttr<double>(o, "ballistic");
        area      = PyGetAttr<double>(o, "area");

        model = PyGetAttr<uint32_t>(o, "model");
    }

    ~Object() { Py_DECREF(object); }

    inline static void flush() { gidx = 0; }

    inline static uint64_t total() { return gidx; }

    constexpr inline uint64_t index() const { return _index; }

    inline double energy() { return 0.5 * mass * velocity.norm(); }
};

uint64_t Object::gidx = 0;

struct Player {
    bool c; Vector * p; Vector * f;

    Player() : p(nullptr), f(nullptr) {}
    ~Player() {}

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

    Voxel() : object(), durability(0) {}
    Voxel(PyObject * o, const double f) : object(o), durability(f) { Py_INCREF(o); }

    Material * material() const { return reinterpret_cast<Material *>(static_cast<PyObject *>(object)); }
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

    std::unordered_map<int, Voxel> voxels;
    ObjectQueue objects;

    PyOwnedRef onTrace, onBlockHit, onPlayerHit, onDestroy;

    PyOwnedRef defaultMaterial, buildMaterial, waterMaterial;

    MapData * map;

    double _lag, _peak;

    // Independent variables.
    double _temperature, _pressure, _humidity; Vector3d _wind;
    // Derived variables.
    double _density, _mach, _ppo2;

private:
    inline bool indestructible(int x, int y, int z)
    { return z >= 62 || !get_solid(x, y, z, map); }

    inline bool unstable(int x₀, int y₀, int z₀) {
        for (int z = z₀ + 1; z < 62; z++) {
            if (!get_solid(x₀, y₀, z, map))
                return true;

            if (!get(x₀, y₀, z).material()->crumbly)
                return false;
        }

        return false;
    }

    inline bool weaken(Voxel & voxel, double amount)
    { voxel.durability -= amount; return voxel.durability <= 0; }

public:
    std::vector<Player> players;

    Engine() : _lag(0.0), _peak(0.0) { srand(time(NULL)); players.reserve(32); }

    Voxel & get(int x, int y, int z) {
        auto pos = get_pos(x, y, z);
        auto iter = voxels.find(pos);

        if (iter == voxels.end()) {
            std::tie(iter, std::ignore) = voxels.insert_or_assign(
                pos, Voxel(z == 63 ? waterMaterial : defaultMaterial, 1.0)
            );
        }

        return iter->second;
    }

    inline PyObject * getMaterial(int x, int y, int z)
    { return get(x, y, z).object.incref(); }

    inline double getDurability(int x, int y, int z)
    { return get(x, y, z).durability; }

    void set(const int index, PyObject * o, const double value) {
        if (o == nullptr || !PyObject_TypeCheck(o, &MaterialType)) return;

        int x, y, z; get_xyz(index, &x, &y, &z); // ignore z = 63
        if (z < 63) voxels.insert_or_assign(index, Voxel(o, value));
    }

    void applyPalette(PyObject * dict) {
        for (auto & [k, v] : map->colors) {
            auto M = PyDict_GetItem(dict, PyOwnedRef(PyEncode<unsigned int>(v & 0xFFFFFF)));
            if (M == nullptr) M = defaultMaterial;

            set(k, M, 1.0);
        }
    }

    template<typename... Args> inline void add(Args &&... args) {
        auto & o = objects.emplace_back(args...);
        trace(o.index(), o.position, 1.0, true);
    }

    inline void on_spawn(size_t i) {
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

    inline void on_despawn(size_t i) {
        auto & player = players[i];
        player.set_crouch(false);
        player.set_position(nullptr);
        player.set_orientation(nullptr);

        PyOwnedRef ds(protocol, "players");
        if (ds == nullptr) return;

        players.resize(dictLargestKey<int>(ds) + 1);
    }

    inline void set_animation(size_t i, bool crouch) {
        players[i].set_crouch(crouch);
    }

    void set(const double t, const double p, const double φ, const Vector3d & w) {
        using namespace Fundamentals;

        _temperature = t;
        _pressure    = p;
        _humidity    = φ;
        _wind        = w;

        // 1) Here we assume Dalton’s law.

        // https://en.wikipedia.org/wiki/Density_of_air#Humid_air
        auto p₁ = φ * vaporPressureOfWater<double>(t), p₂ = p - p₁;

        auto ε = gasConstant<double> * (t - absoluteZero<double>);

        _density = (p₁ * molarMassWaterVapor<double> + p₂ * molarMassDryAir<double>) / ε;
        _ppo2    = 0.20946 * p₂;

        // 2) Here we assume Amagat’s law.

        // https://en.wikipedia.org/wiki/Heat_capacity_ratio#Relation_with_degrees_of_freedom
        constexpr double γ₁ = 1.333333, γ₂ = 1.4;

        // https://physicspages.com/pdf/Thermal%20physics/Bulk%20modulus%20and%20the%20speed%20of%20sound.pdf
        // pV^γ = A, p = AV^−γ, K = −VdP/V = −Vd(AV^−γ)/V = −VA(−γ)V^(−γ + 1) = γAV^−γ = γp
        auto K₁ = γ₁ * p, K₂ = γ₂ * p;

        // https://en.wikipedia.org/wiki/Partial_pressure#Partial_volume_(Amagat's_law_of_additive_volume)
        auto x₁ = p₁ / p, x₂ = p₂ / p;

        /*
            https://eng.libretexts.org/Bookshelves/Civil_Engineering/Book%3A_Fluid_Mechanics_(Bar-Meir)/00%3A_Introduction/1.6%3A_Fluid_Properties/1.6.2%3A_Bulk_Modulus/1.6.2.1%3A_Bulk_Modulus_of_Mixtures

            Kᵢ = −VᵢdP/dVᵢ,
            dV = dV₁ + dV₂
               = −V₁dP/K₁ − V₂dP/K₂
               = −x₁VdP/K₁ − x₂VdP/K₂
               = −VdP(x₁/K₁ + x₂/K₂),
            K = −VdP/dV = 1/(x₁/K₁ + x₂/K₂)
        */
        auto K = 1.0 / (x₁ / K₁ + x₂ / K₂);

        // https://en.wikipedia.org/wiki/Speed_of_sound#Equations
        _mach = std::sqrt(K / _density);

        // See also: http://resource.npl.co.uk/acoustics/techguides/speedair/
    }

    inline double   temperature() const { return _temperature; } // ℃
    inline double   pressure()    const { return _pressure; }    // Pa
    inline double   humidity()    const { return _humidity; }    // %
    inline double   density()     const { return _density; }     // kg/m³
    inline double   mach()        const { return _mach; }        // m/s
    inline double   ppo2()        const { return _ppo2; }        // Pa
    inline Vector3d wind()        const { return _wind; }        // m/s

    void clear() {
        set(0, 101325, 0.3, Vector3d(0, 0, 0));

        _peak = 0.0;

        objects.clear();
        Object::flush();

        voxels.clear();

        defaultMaterial.retain(nullptr);
        buildMaterial.retain(nullptr);
        waterMaterial.retain(nullptr);

        PyOwnedRef M(protocol, "map");
        if (M != nullptr) map = mapDataRef(M);
    }

    inline void dig(int player_id, int x, int y, int z, double value) {
        if (indestructible(x, y, z)) return;

        auto & voxel = get(x, y, z); auto M = voxel.material();
        if (weaken(voxel, value / M->durability))
            onDestroy(player_id, x, y, z);
    }

    inline void smash(int player_id, int x, int y, int z, double ΔE) {
        if (indestructible(x, y, z)) return;

        auto & voxel = get(x, y, z); auto M = voxel.material();

        if (M->crumbly) {
            if (randbool<double>(0.5) && unstable(x, y, z)) {
                onDestroy(player_id, x, y, z);

                return;
            }
        }

        if (weaken(voxel, ΔE * (M->durability / M->absorption)))
            onDestroy(player_id, x, y, z);
    }

    inline void build(int x, int y, int z)
    { voxels.insert_or_assign(get_pos(x, y, z), Voxel(buildMaterial, 1.0)); }

    inline void destroy(int x, int y, int z)
    { voxels.erase(get_pos(x, y, z)); }

    inline void invokeOnPlayerHit(PyObject * o) { onPlayerHit.retain(PyCallable_Check(o) ? o : nullptr); }
    inline void invokeOnBlockHit(PyObject * o) { onBlockHit.retain(PyCallable_Check(o) ? o : nullptr); }
    inline void invokeOnTrace(PyObject * o) { onTrace.retain(PyCallable_Check(o) ? o : nullptr); }
    inline void invokeOnDestroy(PyObject * o) { onDestroy.retain(PyCallable_Check(o) ? o : nullptr); }
    inline void setProtocolObject(PyObject * o) { protocol.retain(o); }

    inline void setDefaultMaterial(PyObject * o) { defaultMaterial.retain(o); }
    inline void setBuildMaterial(PyObject * o) { buildMaterial.retain(o); }
    inline void setWaterMaterial(PyObject * o) { waterMaterial.retain(o); }

    void step(const double t1, const double t2) {
        using namespace std::chrono;

        const auto T1 = steady_clock::now();

        for (auto it = objects.begin(); it != objects.end(); next(t1, t2, it));

        const auto T2 = steady_clock::now();

        auto diff = duration_cast<microseconds>(T2 - T1).count();
        _lag  = (_lag + diff) / 2;
        _peak = std::max(_peak, double(diff));
    }

    inline void flush() { objects.clear(); }

    inline double lag()  const { return _lag; }
    inline double peak() const { return _peak; }

    inline size_t alive() const { return objects.size(); }
    inline size_t total() const { return Object::total(); }

    // This is only the lower bound.
    inline size_t usage() const {
        constexpr size_t entrySize = sizeof(int) + sizeof(Voxel);
        return sizeof(decltype(voxels)) + entrySize * voxels.size();
    }

private:
    inline void trace(const uint64_t index, const Vector3d & r, const double value, bool origin)
    { onTrace(index, r.x, r.y, r.z, value, origin); }

    void next(double t1, const double t2, ObjectIterator & it) {
        using namespace Fundamentals;

        Object & o = *it;

        Voxel * voxel = nullptr; Material * M = nullptr;
        Vector3d r(o.position), v(o.velocity), n;

        uint64_t N = 1;

        bool stuck = false;

        while (t1 < t2 && N < 10000 && !stuck) {
            N++;

            int64_t X = std::floor(r.x), Y = std::floor(r.y), Z = std::ceil(r.z);

            if (n.x != 0 && v.x < 0) X--;
            if (n.y != 0 && v.y < 0) Y--;
            if (n.z != 0 && v.z > 0) Z++;

            Terminal state = Terminal::flying;

            if (is_valid_position(X, Y, Z) && get_solid(X, Y, Z, map)) {
                voxel = &get(X, Y, Z); M = voxel->material();

                auto θ = acos(-(v, n) / v.abs());

                state = M->deflecting <= θ && random<double>() < M->ricochet ? Terminal::ricochet
                                                                             : Terminal::penetration;

                if (state != Terminal::flying) {
                    constexpr double hitEffectThresholdEnergy = 5.0;

                    trace(o.index(), r, v.abs() / o.v0, false);

                    if (hitEffectThresholdEnergy <= o.energy())
                        stuck = Py_True == onBlockHit(
                            o.object, r.x, r.y, r.z, v.x, v.y, v.z, X, Y, Z,
                            o.thrower, o.energy(), o.area
                        );
                }

                if (state == Terminal::ricochet) v -= n * (2 * (v, n));

                if (state == Terminal::penetration) v = cone(v, 0.05);
            }

            // `dr` depends only on direction, not the absolute value of `v`
            // That’s why all direction changes need to be made before this point.
            double x = v.x > 0 ? std::floor(r.x) + 1 : std::ceil(r.x) - 1;
            double y = v.y > 0 ? std::floor(r.y) + 1 : std::ceil(r.y) - 1;
            double z = v.z > 0 ? std::floor(r.z) + 1 : std::ceil(r.z) - 1;

            double dx = x - r.x, dy = y - r.y, dz = z - r.z;

            if (std::abs(dx) < 1e-20) dx = sign(v.x);
            if (std::abs(dy) < 1e-20) dy = sign(v.y);
            if (std::abs(dz) < 1e-20) dz = sign(v.z);

            double idt; std::tie(idt, n) = max(
                [](auto & w1, auto & w2){ return w1.first < w2.first; },
                std::pair(m2b<double> * v.x / dx, Vector3d(-sign(v.x), 0, 0)),
                std::pair(m2b<double> * v.y / dy, Vector3d(0, -sign(v.y), 0)),
                std::pair(m2b<double> * v.z / dz, Vector3d(0, 0, -sign(v.z)))
            );

            double dt = std::min(idt < 1e-9 ? INFINITY : 1 / idt, t2 - t1);
            auto dr = v * (m2b<double> * dt);

            if (state == Terminal::ricochet) v *= 0.6;

            if (state == Terminal::penetration) {
                // http://panoptesv.com/RPGs/Equipment/Weapons/Projectile_physics.php
                auto depth = dr.abs() * b2m<double>;
                auto E₀    = 0.5 * o.mass * v.norm();
                auto drag  = 1;
                auto xc    = o.mass / (drag * M->density * o.area);
                auto xmax  = xc * log(1 + (E₀ * drag * M->density) / (M->strength * o.mass));

                double ΔE = 0; // energy that will be absorbed by block

                if (xmax > depth) {
                    auto ε = exp(-drag * o.area * M->density * depth / o.mass);
                    auto E = E₀ * ε - M->strength * o.mass * (1 - ε) / (drag * M->density);
                    ΔE = E₀ - E;

                    v *= std::sqrt(E / E₀);
                } else {
                    ΔE = E₀; stuck = true;
                    v.x = v.y = v.z = 0.0;
                }

                // ignore Z ∈ {62, 63} (i.e. water and bottom indestructible layer)
                if (Z < 62) voxel->durability -= ΔE * (M->durability / M->absorption);

                if (voxel->durability <= 0.0) onDestroy(o.thrower, X, Y, Z);
            }

            Ray<double> ray(r, dr); Arc<double> arc{}; int target = -1;

            for (size_t i = 0; i < players.size(); i++) {
                auto & player = players[i];
                if (!player.valid()) continue;

                auto retval = player.intersect(ray);
                if (retval < arc) { arc = retval; target = i; }
            }

            if (0 <= target) {
                auto w = arc.begin(ray);

                stuck = Py_True == onPlayerHit(
                    o.object, w.x, w.y, w.z, v.x, v.y, v.z, X, Y, Z,
                    o.thrower, o.energy(), o.area, target, arc.index
                );

                trace(o.index(), w, v.abs() / o.v0, false);
            }

            auto m  = o.mass;
            auto u  = _wind - v;
            auto CD = drag(o.model, o.ballistic, u.abs() / _mach);
            auto F  = g<double> * m + u * (0.5 * _density * u.abs() * CD * o.area);

            auto dv = F * (dt / m);

            t1 += dt; r += dr; v += dv;
        }

        o.position.set(r); o.velocity.set(v);

        if (!stuck) trace(o.index(), r, v.abs() / o.v0, false);

        //if (t2 - o.timestamp > 10) printf("%ld: time out\n", o.index());
        //if (o.velocity.abs() <= 1e-3) printf("%ld: speed too low (%f m/s)\n", o.index(), o.velocity.abs());
        //if (!is_valid_position(o.position.x, o.position.y, o.position.z)) printf("%ld: out of map (%f, %f, %f)\n", o.index, o.position.x, o.position.y, o.position.z);

        auto P = t2 - o.timestamp <= 10;
        auto Q = o.velocity.abs() > 1e-2;
        auto R = is_valid_position(o.position.x, o.position.y, o.position.z);

        if (P && Q && R && !stuck) ++it; else it = objects.erase(it);
    }
};
