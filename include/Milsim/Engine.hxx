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

extern "C" MapData * mapDataRef(PyObject *);

inline void retain(PyObject * & member, PyObject * const obj) {
    if (member != Py_None)
        Py_DECREF(member);

    if (obj != Py_None)
        Py_INCREF(obj);

    member = obj;
}

inline std::unordered_map<int, int> * getColorsOf(MapData * data)
{ return &data->colors; }

struct Material {
    double durability;
    double absorption;
    double density;
    double strength;
    double ricochet;
    double deflecting;
    bool crumbly;

    Material() {}
};

struct Object {
private:
    static uint64_t gidx; uint64_t _index;

public:
    PyObject * object; double mass, ballistic, area; uint32_t model;

    int thrower; double timestamp, v0;

    Vector3d position, velocity;

    Object(const int i, const Vector3d & r, const Vector3d & v, const double t, PyObject * o) :
        object(o), thrower(i), timestamp(t), position(r), velocity(v) {
        Py_INCREF(object); v0 = v.abs(); _index = gidx++;

        mass      = PyGetAttr<double>(object, "effmass");
        ballistic = PyGetAttr<double>(object, "ballistic");
        area      = PyGetAttr<double>(object, "area");
        model     = PyGetAttr<uint32_t>(object, "model");
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

    Player() {}
    ~Player() {}

    inline bool valid() const { return p != NULL; }

    inline void set_crouch(bool b)          { c = b; }
    inline void set_position(Vector * v)    { p = v; }
    inline void set_orientation(Vector * v) { f = v; }

    inline bool     crouch()      const { return c; }
    inline Vector3d position()    const { return Vector3d(p); }
    inline Vector3d orientation() const { return Vector3d(f); }
};

enum class Terminal { flying, ricochet, penetration };

using ObjectQueue    = std::list<Object>;
using ObjectIterator = ObjectQueue::iterator;

struct Voxel {
    size_t id; double durability;

    Voxel() : id(0), durability(1.0) {}
    Voxel(const size_t id, const double value) : id(id), durability(value) {}
};

struct Engine {
private:
    std::vector<Material> materials;
    std::map<int, Voxel> voxels;
    ObjectQueue objects;

    MapData * map; PyObject * onTrace, * onBlockHit, * onPlayerHit, * onDestroy;

    double _lag, _peak;

    // Independent variables.
    double _temperature, _pressure, _humidity; Vector3d _wind;
    // Derived variables.
    double _density, _mach, _ppo2;

private:
    inline Material & material(const Voxel & voxel)
    { return materials[voxel.id]; }

    inline bool crumbly(const Voxel & voxel)
    { return material(voxel).crumbly; }

    inline bool indestructible(int x, int y, int z)
    { return z >= 62 || !get_solid(x, y, z, map); }

    inline bool unstable(int x₀, int y₀, int z₀) {
        for (int z = z₀ + 1; z < 62; z++) {
            if (!get_solid(x₀, y₀, z, map))
                return true;

            if (!crumbly(get(x₀, y₀, z)))
                return false;
        }

        return false;
    }

    inline bool weaken(Voxel & voxel, double amount)
    { voxel.durability -= amount; return voxel.durability <= 0; }

public:
    std::vector<Player> players;

    Voxel water; size_t defaultMaterial, buildMaterial;

    Engine() : onTrace(Py_None), onBlockHit(Py_None), onPlayerHit(Py_None), onDestroy(Py_None)
    { srand(time(NULL)); players.reserve(32); _lag = _peak = 0.0; }

    ~Engine() { Py_XDECREF(onPlayerHit); Py_XDECREF(onBlockHit); Py_XDECREF(onTrace); Py_XDECREF(onDestroy); }

    Voxel & get(int x, int y, int z) {
        if (z == 63) return water;

        auto pos = get_pos(x, y, z);
        auto iter = voxels.find(pos);

        if (iter == voxels.end()) {
            std::tie(iter, std::ignore) = voxels.insert_or_assign(
                pos, Voxel(defaultMaterial, 1.0)
            );
        }

        return iter->second;
    }

    void set(const int index, const uint32_t i, const double value) {
        int x, y, z; get_xyz(index, &x, &y, &z); // ignore z = 63
        if (z < 63) voxels.insert_or_assign(index, Voxel(i, value));
    }

    template<typename... Args> inline uint64_t add(Args &&... args) {
        auto & obj = objects.emplace_back(args...);
        trace(obj.index(), obj.position, 1.0, true);
        return obj.index();
    }

    inline size_t alloc(PyObject * o) {
        size_t retval = materials.size();
        Material & M = materials.emplace_back();

        M.ricochet   = PyGetAttr<double>(o, "ricochet");
        M.density    = PyGetAttr<double>(o, "density");
        M.strength   = PyGetAttr<double>(o, "strength");
        M.deflecting = PyGetAttr<double>(o, "deflecting") * std::numbers::pi_v<double> / 180.0;
        M.durability = PyGetAttr<double>(o, "durability");
        M.absorption = PyGetAttr<double>(o, "absorption");
        M.crumbly    = PyGetAttr<bool>(o, "crumbly");

        return retval;
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

    void wipe(PyObject * o) {
        set(0, 101325, 0.3, Vector3d(0, 0, 0));

        _peak = 0.0;

        objects.clear();
        Object::flush();

        voxels.clear();
        materials.clear();

        map = mapDataRef(o);
    }

    inline void dig(int player_id, int x, int y, int z, double value) {
        if (indestructible(x, y, z)) return;

        auto & voxel = get(x, y, z); auto & M = material(voxel);
        if (weaken(voxel, value / M.durability) && onDestroy != Py_None)
            PyApply(onDestroy, player_id, x, y, z);
    }

    inline void smash(int player_id, int x, int y, int z, double ΔE) {
        if (indestructible(x, y, z)) return;

        auto & voxel = get(x, y, z); auto & M = material(voxel);

        if (M.crumbly) {
            if (randbool<double>(0.5) && unstable(x, y, z)) {
                if (onDestroy != Py_None)
                    PyApply(onDestroy, player_id, x, y, z);

                return;
            }
        }

        if (weaken(voxel, ΔE * (M.durability / M.absorption)) && onDestroy != Py_None)
            PyApply(onDestroy, player_id, x, y, z);
    }

    inline void build(int x, int y, int z)
    { voxels.insert_or_assign(get_pos(x, y, z), Voxel(buildMaterial, 1.0)); }

    inline void destroy(int x, int y, int z)
    { voxels.erase(get_pos(x, y, z)); }

    inline void invokeOnPlayerHit(PyObject * obj) { retain(onPlayerHit, obj); }
    inline void invokeOnBlockHit(PyObject * obj)  { retain(onBlockHit, obj); }
    inline void invokeOnTrace(PyObject * obj)     { retain(onTrace, obj); }
    inline void invokeOnDestroy(PyObject * obj)   { retain(onDestroy, obj); }

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
    { if (onTrace != Py_None) PyApply(onTrace, index, r.x, r.y, r.z, value, origin ? Py_True : Py_False); }

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
                voxel = &get(X, Y, Z); M = &material(*voxel);

                auto θ = acos(-(v, n) / v.abs());

                state = M->deflecting <= θ && random<double>() < M->ricochet ? Terminal::ricochet
                                                                             : Terminal::penetration;

                if (state != Terminal::flying) {
                    constexpr double hitEffectThresholdEnergy = 5.0;

                    trace(o.index(), r, v.abs() / o.v0, false);

                    if (onBlockHit != Py_None && hitEffectThresholdEnergy <= o.energy()) {
                        auto retval = PyApply(onBlockHit,
                            o.object, r.x, r.y, r.z, v.x, v.y, v.z, X, Y, Z,
                            o.thrower, o.energy(), o.area
                        );

                        stuck = retval == Py_True;
                    }
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

                if (voxel->durability <= 0.0 && onDestroy != Py_None)
                    PyApply(onDestroy, o.thrower, X, Y, Z);
            }

            int target = -1; int limb;
            auto dist = std::numeric_limits<double>::infinity();

            for (size_t i = 0; i < players.size(); i++) {
                Player & player = players[i];
                if (!player.valid()) continue;

                auto origin = player.position().translate(0, 0, player.crouch() ? -1.05 : -1.1);

                auto ray = Ray<double>(r, dr).translate(-origin).pointAt(
                    player.orientation().xOy().normal(), Vector3d(0, 1, 0)
                );

                auto & torso = player.crouch() ? Box::torsoc<double> : Box::torso<double>;
                auto d = torso.intersect(ray);

                if (d < dist) {
                    dist   = d;
                    target = i;
                    limb   = LIMB_TORSO;
                }

                auto & head = Box::head<double>;
                d = head.intersect(ray);

                if (d < dist) {
                    dist   = d;
                    target = i;
                    limb   = LIMB_HEAD;
                }

                auto & legl = player.crouch() ? Box::legc_left<double> : Box::leg_left<double>;
                d = legl.intersect(ray);

                if (d < dist) {
                    dist   = d;
                    target = i;
                    limb   = LIMB_LEGL;
                }

                auto & legr = player.crouch() ? Box::legc_right<double> : Box::leg_right<double>;
                d = legr.intersect(ray);

                if (d < dist) {
                    dist   = d;
                    target = i;
                    limb   = LIMB_LEGR;
                }

                auto & armr = player.crouch() ? Box::armc_right<double> : Box::arm_right<double>;
                d = armr.intersect(ray);

                if (d < dist) {
                    dist   = d;
                    target = i;
                    limb   = LIMB_ARMR;
                }

                auto & arml = player.crouch() ? Box::armc_left<double> : Box::arm_left<double>;
                d = arml.intersect(ray.rot(Vector3<double>(0, 0, 1), -std::numbers::pi_v<double> / 4));

                if (d < dist) {
                    dist   = d;
                    target = i;
                    limb   = LIMB_ARML;
                }
            }

            if (0 <= target && onPlayerHit != Py_None) {
                auto w = r + dr * dist;

                auto retval = PyApply(onPlayerHit,
                    o.object, w.x, w.y, w.z, v.x, v.y, v.z, X, Y, Z,
                    o.thrower, o.energy(), o.area, target, limb
                );

                stuck = retval == Py_True;

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
