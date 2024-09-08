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

template<typename Real> Real vaporPressureOfWater(const Real T) {
    // https://en.wikipedia.org/wiki/Tetens_equation
    auto k = T > 0 ? (17.27 * T) / (T + 237.3) : (21.875 * T) / (T + 265.5);
    return 610.78 * exp(k); // Pa
}

inline void retain(PyObject * & member, PyObject * const obj) {
    if (member != Py_None)
        Py_DECREF(member);

    if (obj != Py_None)
        Py_INCREF(obj);

    member = obj;
}

inline std::unordered_map<int, int> * getColorsOf(MapData * data)
{ return &data->colors; }

template<typename T> struct Material {
    T durability;
    T absorption;
    T density;
    T strength;
    T ricochet;
    T deflecting;
    bool crumbly;

    Material() {}
};

template<typename T> struct Object {
private:
    static uint64_t gidx; uint64_t _index;

public:
    PyObject * object; T mass, ballistic, area; uint32_t model;

    int thrower; T timestamp, v0;

    Vector3<T> position, velocity;

    Object(
        PyObject * object,
        const int i, const Vector3<T> & r, const Vector3<T> & v,
        const T timestamp, const T m, const T ballistic,
        const uint32_t model, const T A
    ) : object(object), mass(m), ballistic(ballistic), area(A), model(model),
        thrower(i), timestamp(timestamp), position(r), velocity(v)
    { Py_INCREF(object); v0 = v.abs(); _index = gidx; gidx++; }

    ~Object() { Py_DECREF(object); }

    inline static void flush() { gidx = 0; }

    inline static uint64_t total() { return gidx; }

    constexpr inline uint64_t index() const { return _index; }

    inline T energy() { return 0.5 * mass * velocity.norm(); }
};

template<typename T> uint64_t Object<T>::gidx = 0;

template<typename T> struct Player {
    bool c; Vector * p; Vector * f;

    Player() {}
    ~Player() {}

    inline bool valid() const { return p != NULL; }

    inline void set_crouch(bool b)          { c = b; }
    inline void set_position(Vector * v)    { p = v; }
    inline void set_orientation(Vector * v) { f = v; }

    inline bool       crouch()      const { return c; }
    inline Vector3<T> position()    const { return Vector3<T>(p); }
    inline Vector3<T> orientation() const { return Vector3<T>(f); }
};

enum class Terminal { flying, ricochet, penetration };

template<typename T> using Iterator = std::list<Object<T>>::iterator;

template<typename T> struct Voxel {
    size_t id; T durability;

    Voxel() : id(0), durability(1.0) {}
    Voxel(const size_t id, const T value) : id(id), durability(value) {}
};

template<typename T> struct Engine {
private:
    std::vector<Material<T>> materials;
    std::map<int, Voxel<T>> voxels;
    std::list<Object<T>> objects;

    MapData * map; PyObject * onTrace, * onBlockHit, * onPlayerHit, * onDestroy;

    double _lag, _peak;

    // Independent variables.
    T _temperature, _pressure, _humidity; Vector3<T> _wind;
    // Derived variables.
    T _density, _mach, _ppo2;

private:
    inline Material<T> & material(const Voxel<T> & voxel)
    { return materials[voxel.id]; }

    inline bool crumbly(const Voxel<T> & voxel)
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

    inline bool weaken(Voxel<T> & voxel, T amount)
    { voxel.durability -= amount; return voxel.durability <= 0; }

public:
    std::vector<Player<T>> players;

    Voxel<T> water; size_t defaultMaterial, buildMaterial;

    Engine() : onTrace(Py_None), onBlockHit(Py_None), onPlayerHit(Py_None), onDestroy(Py_None)
    { srand(time(NULL)); players.reserve(32); _lag = _peak = 0.0; }

    ~Engine() { Py_XDECREF(onPlayerHit); Py_XDECREF(onBlockHit); Py_XDECREF(onTrace); Py_XDECREF(onDestroy); }

    Voxel<T> & get(int x, int y, int z) {
        if (z == 63) return water;

        auto pos = get_pos(x, y, z);
        auto iter = voxels.find(pos);

        if (iter == voxels.end()) {
            std::tie(iter, std::ignore) = voxels.insert_or_assign(
                pos, Voxel<T>(defaultMaterial, 1.0)
            );
        }

        return iter->second;
    }

    void set(const int index, const uint32_t i, const T value) {
        int x, y, z; get_xyz(index, &x, &y, &z); // ignore z = 63
        if (z < 63) voxels.insert_or_assign(index, Voxel<T>(i, value));
    }

    template<typename... Args> inline uint64_t add(Args &&... args) {
        auto & obj = objects.emplace_back(args...);
        trace(obj.index(), obj.position, 1.0, true);
        return obj.index();
    }

    inline Material<T> & alloc(size_t * id)
    { *id = materials.size(); return materials.emplace_back(); }

    void set(const T t, const T p, const T φ, const Vector3<T> & w) {
        using namespace Fundamentals;

        _temperature = t;
        _pressure    = p;
        _humidity    = φ;
        _wind        = w;

        // 1) Here we assume Dalton’s law.

        // https://en.wikipedia.org/wiki/Density_of_air#Humid_air
        auto p₁ = φ * vaporPressureOfWater<T>(t), p₂ = p - p₁;

        auto ε = gasConstant<T> * (t - absoluteZero<T>);

        _density = (p₁ * molarMassWaterVapor<T> + p₂ * molarMassDryAir<T>) / ε;
        _ppo2    = 0.20946 * p₂;

        // 2) Here we assume Amagat’s law.

        // https://en.wikipedia.org/wiki/Heat_capacity_ratio#Relation_with_degrees_of_freedom
        constexpr T γ₁ = 1.333333, γ₂ = 1.4;

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

    inline T          temperature() const { return _temperature; } // ℃
    inline T          pressure()    const { return _pressure; }    // Pa
    inline T          humidity()    const { return _humidity; }    // %
    inline T          density()     const { return _density; }     // kg/m³
    inline T          mach()        const { return _mach; }        // m/s
    inline T          ppo2()        const { return _ppo2; }        // Pa
    inline Vector3<T> wind()        const { return _wind; }        // m/s

    void wipe(MapData * ptr) {
        set(0, 101325, 0.3, Vector3<T>(0, 0, 0));

        _peak = 0.0;

        objects.clear();
        Object<T>::flush();

        voxels.clear();
        materials.clear();

        map = ptr;
    }

    inline bool dig(int x, int y, int z, T value) {
        if (indestructible(x, y, z)) return false;

        auto & voxel = get(x, y, z); auto & M = material(voxel);
        return weaken(voxel, value / M.durability);
    }

    inline bool smash(int x, int y, int z, T ΔE) {
        if (indestructible(x, y, z)) return false;

        auto & voxel = get(x, y, z); auto & M = material(voxel);

        if (M.crumbly) {
            if (randbool<T>(0.5) && unstable(x, y, z))
                return true;
        }

        return weaken(voxel, ΔE * (M.durability / M.absorption));
    }

    inline void build(int x, int y, int z)
    { voxels.insert_or_assign(get_pos(x, y, z), Voxel<T>(buildMaterial, 1.0)); }

    inline void destroy(int x, int y, int z)
    { voxels.erase(get_pos(x, y, z)); }

    inline void invokeOnPlayerHit(PyObject * obj) { retain(onPlayerHit, obj); }
    inline void invokeOnBlockHit(PyObject * obj)  { retain(onBlockHit, obj); }
    inline void invokeOnTrace(PyObject * obj)     { retain(onTrace, obj); }
    inline void invokeOnDestroy(PyObject * obj)   { retain(onDestroy, obj); }

    void step(const T t1, const T t2) {
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
    inline size_t total() const { return Object<T>::total(); }

    // This is only the lower bound.
    inline size_t usage() const {
        constexpr size_t entrySize = sizeof(int) + sizeof(Voxel<T>);
        return sizeof(decltype(voxels)) + entrySize * voxels.size();
    }

private:
    inline void trace(const uint64_t index, const Vector3<T> & r, const T value, bool origin) {
        if (onTrace != Py_None) PyObject_Call(
            onTrace, PyTuple(index, r.x, r.y, r.z, value, origin ? Py_True : Py_False), NULL
        );
    }

    void next(T t1, const T t2, Iterator<T> & it) {
        using namespace Fundamentals;

        Object<T> & o = *it;

        Voxel<T> * voxel = nullptr; Material<T> * M = nullptr;
        Vector3<T> r(o.position), v(o.velocity), n;

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

                state = M->deflecting <= θ && random<T>() < M->ricochet ? Terminal::ricochet
                                                                        : Terminal::penetration;

                if (state != Terminal::flying) {
                    constexpr T hitEffectThresholdEnergy = 5.0;

                    trace(o.index(), r, v.abs() / o.v0, false);

                    if (onBlockHit != Py_None && hitEffectThresholdEnergy <= o.energy()) {
                        auto retval = PyObject_Call(
                            onBlockHit, PyTuple(
                                o.object, r.x, r.y, r.z, v.x, v.y, v.z, X, Y, Z,
                                o.thrower, o.energy(), o.area
                            ), NULL
                        );

                        stuck = retval == Py_True;
                    }
                }

                if (state == Terminal::ricochet) v -= n * (2 * (v, n));

                if (state == Terminal::penetration) v = cone(v, 0.05);
            }

            // `dr` depends only on direction, not the absolute value of `v`
            // That’s why all direction changes need to be made before this point.
            T x = v.x > 0 ? std::floor(r.x) + 1 : std::ceil(r.x) - 1;
            T y = v.y > 0 ? std::floor(r.y) + 1 : std::ceil(r.y) - 1;
            T z = v.z > 0 ? std::floor(r.z) + 1 : std::ceil(r.z) - 1;

            T dx = x - r.x, dy = y - r.y, dz = z - r.z;

            if (std::abs(dx) < 1e-20) dx = sign(v.x);
            if (std::abs(dy) < 1e-20) dy = sign(v.y);
            if (std::abs(dz) < 1e-20) dz = sign(v.z);

            T idt; std::tie(idt, n) = max(
                [](auto & w1, auto & w2){ return w1.first < w2.first; },
                std::pair(m2b<T> * v.x / dx, Vector3<T>(-sign(v.x), 0, 0)),
                std::pair(m2b<T> * v.y / dy, Vector3<T>(0, -sign(v.y), 0)),
                std::pair(m2b<T> * v.z / dz, Vector3<T>(0, 0, -sign(v.z)))
            );

            T dt = std::min(idt < 1e-9 ? INFINITY : 1 / idt, t2 - t1);
            auto dr = v * (m2b<T> * dt);

            if (state == Terminal::ricochet) v *= 0.6;

            if (state == Terminal::penetration) {
                // http://panoptesv.com/RPGs/Equipment/Weapons/Projectile_physics.php
                auto depth = dr.abs() * b2m<T>;
                auto E₀    = 0.5 * o.mass * v.norm();
                auto drag  = 1;
                auto xc    = o.mass / (drag * M->density * o.area);
                auto xmax  = xc * log(1 + (E₀ * drag * M->density) / (M->strength * o.mass));

                T ΔE = 0; // energy that will be absorbed by block

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

                if (voxel->durability <= 0.0) {
                    if (onDestroy != Py_None)
                        PyObject_CallFunction(onDestroy, "iiii", o.thrower, X, Y, Z);
                }
            }

            int target = -1; int limb;
            T dist = std::numeric_limits<T>::infinity();

            for (size_t i = 0; i < players.size(); i++) {
                Player<T> & player = players[i];
                if (!player.valid()) continue;

                auto origin = player.position().translate(0, 0, player.crouch() ? -1.05 : -1.1);

                auto ray = Ray<T>(r, dr).translate(-origin).pointAt(
                    player.orientation().xOy().normal(), Vector3<T>(0, 1, 0)
                );

                auto & torso = player.crouch() ? Box::torsoc<T> : Box::torso<T>;
                auto d = torso.intersect(ray);

                if (d < dist) {
                    dist   = d;
                    target = i;
                    limb   = LIMB_TORSO;
                }

                auto & head = Box::head<T>;
                d = head.intersect(ray);

                if (d < dist) {
                    dist   = d;
                    target = i;
                    limb   = LIMB_HEAD;
                }

                auto & legl = player.crouch() ? Box::legc_left<T> : Box::leg_left<T>;
                d = legl.intersect(ray);

                if (d < dist) {
                    dist   = d;
                    target = i;
                    limb   = LIMB_LEGL;
                }

                auto & legr = player.crouch() ? Box::legc_right<T> : Box::leg_right<T>;
                d = legr.intersect(ray);

                if (d < dist) {
                    dist   = d;
                    target = i;
                    limb   = LIMB_LEGR;
                }

                auto & armr = player.crouch() ? Box::armc_right<T> : Box::arm_right<T>;
                d = armr.intersect(ray);

                if (d < dist) {
                    dist   = d;
                    target = i;
                    limb   = LIMB_ARMR;
                }

                auto & arml = player.crouch() ? Box::armc_left<T> : Box::arm_left<T>;
                d = arml.intersect(ray.rot(Vector3<T>(0, 0, 1), -std::numbers::pi_v<T> / 4));

                if (d < dist) {
                    dist   = d;
                    target = i;
                    limb   = LIMB_ARML;
                }
            }

            if (0 <= target && onPlayerHit != Py_None) {
                Vector3<T> w = r + dr * dist;

                auto retval = PyObject_Call(
                    onPlayerHit, PyTuple(
                        o.object, w.x, w.y, w.z, v.x, v.y, v.z, X, Y, Z,
                        o.thrower, o.energy(), o.area, target, limb
                    ), NULL
                );

                stuck = retval == Py_True;

                trace(o.index(), w, v.abs() / o.v0, false);
            }

            auto m  = o.mass;
            auto u  = _wind - v;
            auto CD = drag(o.model, o.ballistic, u.abs() / _mach);
            auto F  = g<T> * m + u * (0.5 * _density * u.abs() * CD * o.area);

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
