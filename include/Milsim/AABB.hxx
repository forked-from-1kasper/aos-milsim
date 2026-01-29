#pragma once

/*
    Copyright © 2012–2014 Tavian Barnes <tavianator@tavianator.com>
    Copyright © 2024–2026 rzrn

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <https://www.gnu.org/licenses/>.
*/

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

    constexpr inline Real l() const { return max.x; } // left
    constexpr inline Real r() const { return min.x; } // right
    constexpr inline Real f() const { return max.y; } // forward
    constexpr inline Real b() const { return min.y; } // backward
    constexpr inline Real u() const { return min.z; } // up
    constexpr inline Real d() const { return max.z; } // down

    constexpr inline Vector3<Real> rfu() const { return {r(), f(), u()}; }
    constexpr inline Vector3<Real> lfu() const { return {l(), f(), u()}; }
    constexpr inline Vector3<Real> rbu() const { return {r(), b(), u()}; }
    constexpr inline Vector3<Real> lbu() const { return {l(), b(), u()}; }
    constexpr inline Vector3<Real> rfd() const { return {r(), f(), d()}; }
    constexpr inline Vector3<Real> lfd() const { return {l(), f(), d()}; }
    constexpr inline Vector3<Real> rbd() const { return {r(), b(), d()}; }
    constexpr inline Vector3<Real> lbd() const { return {l(), b(), d()}; }

    constexpr inline Quadrilateral<Real> front()  const { return {rfd(), rfu(), lfu(), lfd()}; }
    constexpr inline Quadrilateral<Real> back()   const { return {lbd(), lbu(), rbu(), rbd()}; }
    constexpr inline Quadrilateral<Real> top()    const { return {rfu(), rbu(), lbu(), lfu()}; }
    constexpr inline Quadrilateral<Real> bottom() const { return {rbd(), rfd(), lfd(), lbd()}; }
    constexpr inline Quadrilateral<Real> left()   const { return {lfd(), lfu(), lbu(), lbd()}; }
    constexpr inline Quadrilateral<Real> right()  const { return {rbd(), rbu(), rfu(), rfd()}; }

    constexpr inline bool inside(const Vector3<Real> & v) const
    { return min.x <= v.x && v.x <= max.y
          && min.y <= v.y && v.y <= max.y
          && min.z <= v.z && v.z <= max.z; }

    inline Real exposed(const Vector3<Real> & r0) const
    { return inside(r0)
           ? 4 * std::numbers::pi_v<Real>
           : front().exposed(r0)
           + back().exposed(r0)
           + top().exposed(r0)
           + bottom().exposed(r0)
           + left().exposed(r0)
           + right().exposed(r0);}

    constexpr inline Arc<Real> intersect(const int index, const Ray<Real> & r) const {
        using namespace std;

        /* [1] https://tavianator.com/2011/ray_box.html
           [2] https://tavianator.com/2015/03/fast-branchless-raybounding-box-intersections-part-2-nans/
           [3] https://tavianator.com/cgit/dimension.git/tree/libdimension/bvh/bvh.c */

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