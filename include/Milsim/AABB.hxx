#pragma once

#include <Milsim/Vector.hxx>

#include <algorithm>
#include <numbers>

template<typename T> struct Ray {
    Vector3<T> origin, direction;

    constexpr Ray(const Vector3<T> & r, const Vector3<T> & d) : origin(r), direction(d) {}

    constexpr inline Ray<T> translate(const Vector3<T> & v) const
    { return Ray<T>(origin + v, direction); }

    constexpr inline Ray<T> rot(const Vector3<T> & k, const T θ) const
    { return Ray<T>(origin.rot(k, θ), direction.rot(k, θ)); }

    constexpr inline Ray<T> pointAt(const Vector3<T> & k1, const Vector3<T> & k2) const
    { return Ray<T>(origin.pointAt(k1, k2), direction.pointAt(k1, k2)); }
};

template<typename T> struct AABB {
    Vector3<T> min, max;

    constexpr AABB(const Vector3<T> & A, const Vector3<T> & B) :
    min(std::min(A.x, B.x), std::min(A.y, B.y), std::min(A.z, B.z)),
    max(std::max(A.x, B.x), std::max(A.y, B.y), std::max(A.z, B.z)) {}

    constexpr T intersect(const Ray<T> & r) const {
        // https://tavianator.com/2011/ray_box.html

        T irx = 1 / r.direction.x, iry = 1 / r.direction.y, irz = 1 / r.direction.z;

        T tx1 = (min.x - r.origin.x) * irx, tx2 = (max.x - r.origin.x) * irx;
        T ty1 = (min.y - r.origin.y) * iry, ty2 = (max.y - r.origin.y) * iry;
        T tz1 = (min.z - r.origin.z) * irz, tz2 = (max.z - r.origin.z) * irz;

        T tmin = std::min(tx1, tx2), tmax = std::max(tx1, tx2);

        tmin = std::max(tmin, std::min(std::min(ty1, ty2), tmax));
        tmax = std::min(tmax, std::max(std::max(ty1, ty2), tmin));

        tmin = std::max(tmin, std::min(std::min(tz1, tz2), tmax));
        tmax = std::min(tmax, std::max(std::max(tz1, tz2), tmin));

        return (tmax > tmin && 0 <= tmin && tmin <= 1) ? tmin * r.direction.abs() : std::numeric_limits<T>::infinity();
    }
};

template<typename T> struct Hitbox {
    Vector3<T> pivot, size; T scale; AABB<T> aabb;

    constexpr Hitbox(const Vector3<T> & pivot, const Vector3<T> & size, const T scale) :
    pivot(pivot), size(size), scale(scale), aabb(pivot * scale, (pivot + size) * scale) {}

    constexpr inline T intersect(const Ray<T> & r) const { return aabb.intersect(r); }
};