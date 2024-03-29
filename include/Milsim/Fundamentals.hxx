#pragma once

#include <Milsim/Vector.hxx>
#include <Milsim/AABB.hxx>

template<typename T> inline T sign(T x)
{ return std::copysign(1, x); }

template<typename T, typename... Ts> inline auto max(T t, Ts... ts)
{ return std::max({ts...}, t); };

template<typename T> T random()
{ return static_cast<T>(rand()) / static_cast<T>(RAND_MAX); }

template<typename T> inline bool randbool(T probability)
{ return random<T>() < probability; }

template<typename T> T uniform(T m, T M)
{ return m + random<T>() * (M - m); }

enum class Limb : uint8_t {
    head  = 0,
    torso = 1,
    arml  = 2,
    armr  = 3,
    legl  = 4,
    legr  = 5
};

enum class HitEffect : uint8_t {
    block    = 0,
    headshot = 1,
    player   = 2,
};

constexpr inline HitEffect effectOfLimb(const Limb hit) {
    return hit == Limb::head ? HitEffect::headshot
                             : HitEffect::player;
}

namespace Fundamentals {
    template<typename T> constexpr T playerHeightInMeters = 1.8;
    template<typename T> constexpr T playerHeightInBlocks = 2.5;

    template<typename T> constexpr T m2b = playerHeightInBlocks<T> / playerHeightInMeters<T>;
    template<typename T> constexpr T b2m = 1 / m2b<T>;

    template<typename T> const Vector3<T> g(0, 0, 9.81);
    template<typename T> const T densityOfAir = 1.225;
}

template<typename T> constexpr inline T ofMeters(const T v) { return Fundamentals::m2b<T> * v; }
template<typename T> constexpr inline T toMeters(const T v) { return Fundamentals::b2m<T> * v; }

namespace Box {
    template<typename T> constexpr auto head = Hitbox<T>(
        Vector3<T>(-2.5, -2.5, -3.0), Vector3<T>(6, 6, 6), 0.1
    );

    template<typename T> constexpr auto torso = Hitbox<T>(
        Vector3<T>(-3.5, -1.5, 3.0), Vector3<T>(8, 4, 9), 0.1
    );

    template<typename T> constexpr auto torsoc = Hitbox<T>(
        Vector3<T>(-3.5, -6.5, 2.0), Vector3<T>(8, 8, 7), 0.1
    );

    template<typename T> constexpr auto arm_right = Hitbox<T>(
        Vector3<T>(-5.5, 0.5, 4.0), Vector3<T>(2, 9, 6), 0.1
    );

    template<typename T> constexpr auto armc_right = Hitbox<T>(
        Vector3<T>(-5.5, 0.5, 3.0), Vector3<T>(2, 9, 6), 0.1
    );

    template<typename T> constexpr auto arm_left = Hitbox<T>(
        Vector3<T>(3.5, -4.25, 4.0), Vector3<T>(3, 14, 2), 0.1
    );

    template<typename T> constexpr auto armc_left = Hitbox<T>(
        Vector3<T>(3.5, -4.25, 3.0), Vector3<T>(3, 14, 2), 0.1
    );

    template<typename T> constexpr auto leg_left = Hitbox<T>(
        Vector3<T>(1.5, -1.5, 11.5), Vector3<T>(3, 5, 12), 0.1
    );

    template<typename T> constexpr auto legc_left = Hitbox<T>(
        Vector3<T>(1.5, -6.75, 6.0), Vector3<T>(3, 7, 8), 0.1
    );

    template<typename T> constexpr auto leg_right = Hitbox<T>(
        Vector3<T>(-3.5, -1.5, 11.5), Vector3<T>(3, 5, 12), 0.1
    );

    template<typename T> constexpr auto legc_right = Hitbox<T>(
        Vector3<T>(-3.5, -6.75, 6.0), Vector3<T>(3, 7, 8), 0.1
    );
}