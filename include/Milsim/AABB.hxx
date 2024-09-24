#pragma once

#include <Milsim/Vector.hxx>

#include <algorithm>
#include <numbers>
#include <utility>

template<typename Real> struct Ray {
    Vector3<Real> origin, direction;

    constexpr inline Ray(const Vector3<Real> & r, const Vector3<Real> & d) : origin(r), direction(d) {}

    constexpr inline Ray<Real> translate(const Vector3<Real> & v) const
    { return Ray<Real>(origin + v, direction); }

    constexpr inline Ray<Real> rot(const Vector3<Real> & k, const Real θ) const
    { return Ray<Real>(origin.rot(k, θ), direction.rot(k, θ)); }

    constexpr inline Ray<Real> pointAt(const Vector3<Real> & k1, const Vector3<Real> & k2) const
    { return Ray<Real>(origin.pointAt(k1, k2), direction.pointAt(k1, k2)); }
};

template<typename Real> struct Arc {
    int index; Real t1, t2;

    constexpr inline Arc() : index(-1), t1(std::numeric_limits<Real>::infinity()), t2(std::numeric_limits<Real>::infinity()) {}

    constexpr inline Arc(int i, Real t1, Real t2) : index(i), t1(t1), t2(t2) {}

    constexpr inline Vector3<Real> begin(const Ray<Real> & r) const
    { return r.origin + r.direction * t1; }

    constexpr inline Vector3<Real> end(const Ray<Real> & r) const
    { return r.origin + r.direction * t2; }

    constexpr inline auto operator<=>(const Arc<Real> & w) const { return t1 <=> w.t1; };
};

template<typename Real> struct AABB {
    Vector3<Real> min, max;

    constexpr inline AABB(const Vector3<Real> & A, const Vector3<Real> & B) :
    min(std::min(A.x, B.x), std::min(A.y, B.y), std::min(A.z, B.z)),
    max(std::max(A.x, B.x), std::max(A.y, B.y), std::max(A.z, B.z)) {}

    constexpr inline Arc<Real> intersect(const int index, const Ray<Real> & r) const {
        using namespace std;

        // https://tavianator.com/2011/ray_box.html

        Real irx = 1 / r.direction.x, iry = 1 / r.direction.y, irz = 1 / r.direction.z;

        Real tx1 = (min.x - r.origin.x) * irx, tx2 = (max.x - r.origin.x) * irx;
        Real ty1 = (min.y - r.origin.y) * iry, ty2 = (max.y - r.origin.y) * iry;
        Real tz1 = (min.z - r.origin.z) * irz, tz2 = (max.z - r.origin.z) * irz;

        Real tmin = std::min(tx1, tx2), tmax = std::max(tx1, tx2);

        tmin = std::max(tmin, std::min(std::min(ty1, ty2), tmax));
        tmax = std::min(tmax, std::max(std::max(ty1, ty2), tmin));

        tmin = std::max(tmin, std::min(std::min(tz1, tz2), tmax));
        tmax = std::min(tmax, std::max(std::max(tz1, tz2), tmin));

        Real length = r.direction.abs();

        if (tmin < tmax && 0 <= tmin && tmin <= 1)
            return {index, tmin * length, tmax * length};

        return {};
    }
};

template<typename Real> struct Hitbox {
    int index; Vector3<Real> pivot, size; Real scale; AABB<Real> aabb;

    constexpr inline Hitbox(const int i, const Vector3<Real> & pivot, const Vector3<Real> & size, const Real scale) :
    index(i), pivot(pivot), size(size), scale(scale), aabb(pivot * scale, (pivot + size) * scale) {}

    constexpr inline auto intersect(const Ray<Real> & r) const { return aabb.intersect(index, r); }
};