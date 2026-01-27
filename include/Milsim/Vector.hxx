#pragma once

#include <random>
#include <tuple>

#include <cmath>

#include <common_c.h> // for cast from “Vector”

template<typename T> struct Vector3 {
    T x, y, z;

    constexpr inline Vector3() : x(0), y(0), z(0) {}
    constexpr inline Vector3(const T x, const T y) : x(x), y(y), z(0) {}
    constexpr inline Vector3(const T x, const T y, const T z) : x(x), y(y), z(z) {}
    constexpr inline Vector3(const Vector3<T> & v) : x(v.x), y(v.y), z(v.z) {}
    constexpr inline Vector3(const Vector * v) : x(v->x), y(v->y), z(v->z) {}

    constexpr Vector3<T> & operator=(const Vector3<T> &) = default;
    constexpr Vector3<T> & operator=(Vector3<T> &&) = default;

    constexpr inline T norm() const { return x * x + y * y + z * z; }
    constexpr inline T abs()  const { return std::hypot(x, y, z); }

    constexpr inline Vector3<T> xzy() const { return Vector3<T>(x, z, y); }
    constexpr inline Vector3<T> xOy() const { return Vector3<T>(x, y, 0); }
    constexpr inline Vector3<T> xOz() const { return Vector3<T>(x, 0, z); }
    constexpr inline Vector3<T> yOz() const { return Vector3<T>(0, y, z); }

    constexpr static T ε = 1e-30;

    constexpr inline Vector3<T> normal() const
    { T k = abs(); return k <= ε ? Vector3<T>() : scale(1 / k); }

    constexpr inline void normalize() { T k = abs(); if (k > ε) *this /= k; }

    constexpr inline auto polar() const {
        T k = abs();

        return k <= ε ? std::tuple(T(0), Vector3<T>())
                      : std::tuple(k, scale(1 / k));
    }

    template<typename U> constexpr inline operator Vector3<U>() const
    { return Vector3<U>(x, y, z); }

    constexpr inline T dot(const Vector3<T> & N) const
    { return x * N.x + y * N.y + z * N.z; }

    constexpr inline Vector3<T> translate(const T dx, const T dy, const T dz) const
    { return Vector3<T>(x + dx, y + dy, z + dz); }

    constexpr inline T operator,(const Vector3<T> & N) const
    { return dot(N); }

    constexpr inline Vector3<T> operator+(const Vector3<T> & N) const
    { return Vector3<T>(x + N.x, y + N.y, z + N.z); }

    constexpr inline Vector3<T> operator-(const Vector3<T> & N) const
    { return Vector3<T>(x - N.x, y - N.y, z - N.z); }

    constexpr inline Vector3<T> operator*(const Vector3<T> & N) const
    { return Vector3<T>(x * N.x, y * N.y, z * N.z); }

    constexpr inline Vector3<T> scale(const T k) const
    { return Vector3<T>(x * k, y * k, z * k); }

    constexpr inline Vector3<T> operator*(const T k) const
    { return scale(k); }

    constexpr inline Vector3<T> operator/(const T k) const
    { return Vector3<T>(x / k, y / k, z / k); }

    constexpr inline Vector3<T> & operator+=(const Vector3<T> & N) &
    { x += N.x; y += N.y; z += N.z; return *this; }

    constexpr inline Vector3<T> & operator-=(const Vector3<T> & N) &
    { x -= N.x; y -= N.y; z -= N.z; return *this; }

    constexpr inline Vector3<T> & operator*=(const Vector3<T> & N) &
    { x *= N.x; y *= N.y; z *= N.z; return *this; }

    constexpr inline Vector3<T> & operator*=(const T k) &
    { x *= k; y *= k; z *= k; return *this; }

    constexpr inline Vector3<T> & operator/=(const T k) &
    { x /= k; y /= k; z /= k; return *this; }

    constexpr inline auto operator-() const { return Vector3<T>(-x, -y, -z); }
    constexpr inline auto operator+() const { return *this; }

    constexpr inline Vector3<T> cross(const Vector3<T> & N) const
    { return Vector3<T>(y * N.z - z * N.y, z * N.x - x * N.z, x * N.y - y * N.x); }

    constexpr inline void set(const T nx, const T ny, const T nz) { x = nx; y = ny; z = nz; }
    constexpr inline void set(const Vector3<T> & N) { x = N.x; y = N.y; z = N.z; }

    // https://en.wikipedia.org/wiki/Rodrigues%27_rotation_formula
    constexpr inline Vector3<T> rot(const Vector3<T> & k, const T θ) const
    { return scale(cos(θ)) - cross(k) * sin(θ) + k * (dot(k) * (1 - cos(θ))); }

    constexpr inline Vector3<T> pointAt(const Vector3<T> & k1, const Vector3<T> & k2) const {
        auto k3 = k1.cross(k2); auto k = k3.normal(); auto cosθ = (k1, k2);
        return scale(cosθ) - cross(k3) + k * (dot(k) * (1 - cosθ));
    }

    constexpr inline bool isZero() const { return x == T(0) && y == T(0) && z == T(0); }
};

using Vector3i = Vector3<int>;
using Vector3f = Vector3<float>;
using Vector3d = Vector3<double>;

template<typename T> inline T solid(const Vector3<T> & r1, const Vector3<T> & r2, const Vector3<T> & r3) {
    // The Solid Angle of a Plane Triangle, A. van Oosterom & J. Strackee, 1983

    auto R1 = r1.abs(), R2 = r2.abs(), R3 = r3.abs();
    auto R12 = (r1, r2), R13 = (r1, r3), R23 = (r2, r3);

    auto n = (r1, r2.cross(r3));
    auto d = R1 * R2 * R3 + R12 * R3 + R13 * R2 + R23 * R1;

    return 2 * atan2<T>(n, d);
}

template<typename T> struct Quadrilateral {
    Vector3<T> r1, r2, r3, r4;

    inline T solid(const Vector3<T> & r0) const {
        auto R1 = r1 - r0, R2 = r2 - r0, R3 = r3 - r0, R4 = r4 - r0;
        return solid<T>(R1, R2, R3) + solid<T>(R1, R3, R4);
    }

    inline T exposed(const Vector3<T> & r0) const
    { return std::max<T>(0, solid(r0)); }
};
