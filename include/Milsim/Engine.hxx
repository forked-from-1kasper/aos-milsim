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

#include "Python.h"
#include "vxl_c.h"

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
    bool grenade; T mass, drag, area;

    int thrower; T timestamp, v0;

    Vector3<T> position, velocity;

    Object(
        const int i, const Vector3<T> & r, const Vector3<T> & v,
        const T timestamp, bool grenade, const T m, const T drag, const T A
    ) : thrower(i), timestamp(timestamp), position(r), velocity(v),
        grenade(grenade), mass(m), drag(drag), area(A)
    { v0 = v.abs(); _index = gidx; gidx++; }

    ~Object() {}

    inline static void flush() { gidx = 0; }

    inline static uint64_t total() { return gidx; }

    constexpr inline uint64_t index() const { return _index; }

    inline T energy() { return 0.5 * mass * velocity.norm(); }
};

template<typename T> uint64_t Object<T>::gidx = 0;

template<typename T> void __Pyx_call_destructor(T & x) { x.~T(); }

template<typename T> struct Player {
    int id; Vector3<T> position, orientation; bool crouch;

    Player() {}
    ~Player() {}

    constexpr inline void set(int i, T x, T y, T z, T ox, T oy, T oz, bool c)
    { id = i; crouch = c; position.set(x, y, z); orientation.set(ox, oy, oz); }
};

enum class Terminal { flying, ricochet, penetration };

template<typename T> using Iterator = std::list<Object<T>>::iterator;

template<typename T> struct Voxel {
    size_t id; T durability;

    Voxel(const size_t id, const T value) : id(id), durability(value) {}
};

template<typename T> struct Engine {
private:
    std::vector<Material<T>> materials;
    std::map<int, Voxel<T>> voxels;
    std::list<Object<T>> objects;

    MapData * map; PyObject * onTrace, * onHitEffect, * onHit, * onDestroy;

    double _lag;

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
    size_t defaultMaterial, buildMaterial;

    Engine() : onTrace(Py_None), onHitEffect(Py_None), onHit(Py_None), onDestroy(Py_None)
    { srand(time(NULL)); players.reserve(32); _lag = 0.0; }

    ~Engine() { Py_XDECREF(onTrace); }

    Voxel<T> & get(int x, int y, int z) {
        auto pos = get_pos(x, y, z);
        auto iter = voxels.find(pos);

        if (iter == voxels.end()) {
            std::tie(iter, std::ignore) = voxels.insert_or_assign(
                pos, Voxel<T>(defaultMaterial, 1.0)
            );
        }

        return iter->second;
    }

    void set(const int index, const uint32_t i, const T value)
    { voxels.insert_or_assign(index, Voxel<T>(i, value)); }

    template<typename... Args> inline uint64_t add(Args &&... args) {
        auto & obj = objects.emplace_back(args...);
        trace(obj.index(), obj.position, 1.0, true);
        return obj.index();
    }

    inline Material<T> & alloc(size_t * id)
    { *id = materials.size(); return materials.emplace_back(); }

    void wipe(MapData * ptr) {
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

    inline void invokeOnHit(PyObject * obj)       { retain(onHit, obj); }
    inline void invokeOnHitEffect(PyObject * obj) { retain(onHitEffect, obj); }
    inline void invokeOnTrace(PyObject * obj)     { retain(onTrace, obj); }
    inline void invokeOnDestroy(PyObject * obj)   { retain(onDestroy, obj); }

    void step(const T t1, const T t2) {
        using namespace std::chrono;

        const auto T1 = steady_clock::now();

        for (auto it = objects.begin(); it != objects.end(); next(t1, t2, it));

        const auto T2 = steady_clock::now();

        auto diff = duration_cast<microseconds>(T2 - T1).count();
        _lag = (_lag + diff) / 2;
    }

    inline void flush() { objects.clear(); }

    inline double lag() const { return _lag; }

    inline size_t alive() const { return objects.size(); }
    inline size_t total() const { return Object<T>::total(); }

private:
    inline void trace(const uint64_t index, const Vector3<T> & r, const T value, bool origin) {
        if (onTrace != Py_None) {
            PyObject_CallFunction(onTrace, "iffffO",
                index, r.x, r.y, r.z, value, origin ? Py_True : Py_False
            );
        }
    }

    void next(T t1, const T t2, Iterator<T> & it) {
        using namespace Fundamentals;

        Object<T> & o = *it;

        Voxel<T> * voxel = nullptr; Material<T> * M = nullptr;
        T m = o.mass; Vector3<T> r(o.position), v(o.velocity), n;

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
                    trace(o.index(), r, v.abs() / o.v0, false);

                    if (onHitEffect != Py_None) {
                        PyObject_CallFunction(
                            onHitEffect, "fffiiii", r.x, r.y, r.z, X, Y, Z,
                            static_cast<uint8_t>(HitEffectTarget::ground)
                        );
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

                    v *= sqrt(E / E₀);
                } else {
                    ΔE = E₀; stuck = true;
                    v.x = v.y = v.z = 0.0;
                }

                voxel->durability -= ΔE * (M->durability / M->absorption);

                if (voxel->durability <= 0.0) {
                    if (onDestroy != Py_None)
                        PyObject_CallFunction(onDestroy, "iiii", o.thrower, X, Y, Z);
                }
            }

            int target = -1; HitType hit;
            T mindist = std::numeric_limits<T>::infinity();

            for (const auto & player : players) {
                auto origin = player.position.translate(0, 0, player.crouch ? -1.05 : -1.1);

                auto ray = Ray<T>(r, dr).translate(-origin).pointAt(
                    player.orientation.xOy().normal(), Vector3<T>(0, 1, 0)
                );

                auto & torso = player.crouch ? Box::torsoc<T> : Box::torso<T>;
                auto dist = torso.intersect(ray);

                if (dist < mindist) {
                    mindist = dist;
                    target  = player.id;
                    hit     = TORSO;
                }

                auto & head = Box::head<T>;
                dist = head.intersect(ray);

                if (dist < mindist) {
                    mindist = dist;
                    target  = player.id;
                    hit     = HEAD;
                }

                auto & legl = player.crouch ? Box::legc_left<T> : Box::leg_left<T>;
                dist = legl.intersect(ray);

                if (dist < mindist) {
                    mindist = dist;
                    target  = player.id;
                    hit     = LEGS;
                }

                auto & legr = player.crouch ? Box::legc_right<T> : Box::leg_right<T>;
                dist = legr.intersect(ray);

                if (dist < mindist) {
                    mindist = dist;
                    target  = player.id;
                    hit     = LEGS;
                }

                auto & armr = player.crouch ? Box::armc_right<T> : Box::arm_right<T>;
                dist = armr.intersect(ray.rot(Vector3<T>(0, 0, 1), -std::numbers::pi_v<T> / 4));

                if (dist < mindist) {
                    mindist = dist;
                    target  = player.id;
                    hit     = ARMS;
                }

                auto & arml = player.crouch ? Box::armc_left<T> : Box::arm_left<T>;
                dist = arml.intersect(ray);

                if (dist < mindist) {
                    mindist = dist;
                    target  = player.id;
                    hit     = ARMS;
                }
            }

            if (target >= 0) {
                if (onHit != Py_None) {
                    PyObject_CallFunction(onHit, "iiiddO",
                        o.thrower, target, hit, o.energy(), o.area,
                        o.grenade ? Py_True : Py_False
                    );
                }

                if (onHitEffect != Py_None) {
                    Vector3<T> w = r + dr * mindist;

                    PyObject_CallFunction(
                        onHitEffect, "fffiiii", w.x, w.y, w.z, X, Y, Z,
                        static_cast<uint8_t>(targetOfHitType(hit))
                    );
                }

                stuck = true;
            }

            auto wind = Vector3<T>(0, 0, 0), u = wind - v;

            auto F = g<T> * m + u * (0.5 * densityOfAir<T> * u.abs() * o.drag * o.area);
            auto dv = F * (dt / m);

            t1 += dt; r += dr; v += dv;
        }

        o.position.set(r); o.velocity.set(v);

        trace(o.index(), r, v.abs() / o.v0, false);

        //if (t2 - o.timestamp > 10) printf("%ld: time out\n", o.index());
        //if (o.velocity.abs() <= 1e-3) printf("%ld: speed too low (%f m/s)\n", o.index(), o.velocity.abs());
        //if (!is_valid_position(o.position.x, o.position.y, o.position.z)) printf("%ld: out of map (%f, %f, %f)\n", o.index, o.position.x, o.position.y, o.position.z);

        auto P = t2 - o.timestamp <= 10;
        auto Q = o.velocity.abs() > 1e-2;
        auto R = is_valid_position(o.position.x, o.position.y, o.position.z);

        if (P && Q && R && !stuck) ++it; else it = objects.erase(it);
    }
};