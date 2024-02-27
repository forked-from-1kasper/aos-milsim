#pragma once

#include <random>
#include <cmath>

template<typename T> struct Vector3 {
    T x, y, z;

    constexpr Vector3() : x(0), y(0), z(0) {}
    constexpr Vector3(const T x, const T y) : x(x), y(y), z(0) {}
    constexpr Vector3(const T x, const T y, const T z) : x(x), y(y), z(z) {}
    constexpr Vector3(const Vector3<T> & v) : x(v.x), y(v.y), z(v.z) {}

    constexpr inline T norm() const { return x * x + y * y + z * z; }
    constexpr inline T abs()  const { return std::hypot(x, y, z); }

    constexpr inline Vector3<T> xzy() const { return Vector3<T>(x, z, y); }
    constexpr inline Vector3<T> xOy() const { return Vector3<T>(x, y, 0); }
    constexpr inline Vector3<T> xOz() const { return Vector3<T>(x, 0, z); }
    constexpr inline Vector3<T> yOz() const { return Vector3<T>(0, y, z); }

    constexpr Vector3<T> normal() const
    { T k = abs(); return k <= 1e-30 ? Vector3<T>() : scale(1 / k); }

    constexpr void normalize() { T k = abs(); if (k > 1e-30) *this /= k; }

    template<typename U> constexpr operator Vector3<U>() const
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

    constexpr Vector3<T> cross(const Vector3<T> & N) const
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
};

template<typename T> Vector3<T> cone(const Vector3<T> & v, const T σ) {
    static std::random_device rd;
    static std::mt19937 randgen(rd());

    std::normal_distribution gauss(0.0, σ);
    std::uniform_real_distribution uniform(-std::numbers::pi_v<T>, std::numbers::pi_v<T>);

    auto n = v.normal(); auto left = Vector3<T>(n.y, -n.x, 0).normal();
    auto α = gauss(randgen), β = uniform(randgen);

    return v.rot(left, α).rot(n, β);
}
