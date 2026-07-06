#pragma once

/*
    Copyright © 2024–2026 rzrn

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU Affero General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU Affero General Public License for more details.

    You should have received a copy of the GNU Affero General Public License
    along with this program.  If not, see <https://www.gnu.org/licenses/>.
*/

#include <Milsim/Vector.hxx>
#include <Milsim/AABB.hxx>

// https://www.jbmballistics.com/ballistics/downloads/downloads.shtml

template<typename T> constexpr T dragModelG1[] = {
    0.26290, 0.25580, 0.24870, 0.24130, 0.23440, 0.22780, 0.22140, 0.21550, 0.21040, 0.20610,
    0.20320, 0.20200, 0.20340, 0.20995, 0.21650, 0.23130, 0.25460, 0.29010, 0.34150, 0.40840,
    0.48050, 0.54270, 0.58830, 0.61910, 0.63930, 0.65180, 0.65890, 0.66210, 0.66250, 0.66070,
    0.65730, 0.65280, 0.64740, 0.64130, 0.63470, 0.62800, 0.62100, 0.61410, 0.60720, 0.60030,
    0.59340, 0.58670, 0.58040, 0.57430, 0.56850, 0.56300, 0.55770, 0.55270, 0.54810, 0.54380,
    0.53970, 0.53610, 0.53250, 0.52945, 0.52640, 0.52375, 0.52110, 0.51895, 0.51680, 0.51505,
    0.51330, 0.51190, 0.51050, 0.50945, 0.50840, 0.50755, 0.50670, 0.50605, 0.50540, 0.50470,
    0.50400, 0.50350, 0.50300, 0.50260, 0.50220, 0.50190, 0.50160, 0.50130, 0.50100, 0.50080,
    0.50060, 0.50040, 0.50020, 0.50000, 0.49980, 0.49973, 0.49965, 0.49957, 0.49950, 0.49943,
    0.49935, 0.49927, 0.49920, 0.49915, 0.49910, 0.49905, 0.49900, 0.49895, 0.49890, 0.49885,
    0.49880
};

template<typename T> constexpr T dragModelG7[] = {
    0.11980, 0.11970, 0.11960, 0.11940, 0.11930, 0.11940, 0.11940, 0.11940, 0.11930, 0.11930,
    0.11940, 0.11930, 0.11940, 0.11970, 0.12020, 0.12150, 0.12420, 0.13060, 0.14640, 0.20540,
    0.38030, 0.40430, 0.40140, 0.39550, 0.38840, 0.38100, 0.37320, 0.36570, 0.35800, 0.35100,
    0.34400, 0.33760, 0.33150, 0.32600, 0.32090, 0.31600, 0.31170, 0.30780, 0.30420, 0.30100,
    0.29800, 0.29510, 0.29220, 0.28920, 0.28640, 0.28350, 0.28070, 0.27790, 0.27520, 0.27250,
    0.26970, 0.26700, 0.26430, 0.26150, 0.25880, 0.25610, 0.25330, 0.25060, 0.24790, 0.24510,
    0.24240, 0.23960, 0.23680, 0.23405, 0.23130, 0.22855, 0.22580, 0.22315, 0.22050, 0.21795,
    0.21540, 0.21300, 0.21060, 0.20830, 0.20600, 0.20385, 0.20170, 0.19960, 0.19750, 0.19550,
    0.19350, 0.19165, 0.18980, 0.18795, 0.18610, 0.18440, 0.18270, 0.18100, 0.17930, 0.17772,
    0.17615, 0.17457, 0.17300, 0.17155, 0.17010, 0.16865, 0.16720, 0.16585, 0.16450, 0.16315,
    0.16180
};

template<typename T> constexpr T ballModel[] = {
    0.46620, 0.46890, 0.47170, 0.47450, 0.47720, 0.48000, 0.48270, 0.48520, 0.48820, 0.49200,
    0.49700, 0.50800, 0.52600, 0.55900, 0.59200, 0.62580, 0.66100, 0.69850, 0.73700, 0.77570,
    0.81400, 0.85120, 0.88700, 0.92100, 0.95100, 0.97400, 0.99100, 0.99900, 1.00300, 1.00600,
    1.00800, 1.00900, 1.00900, 1.00900, 1.00900, 1.00800, 1.00700, 1.00600, 1.00400, 1.00250,
    1.00100, 0.99900, 0.99700, 0.99560, 0.99400, 0.99160, 0.98900, 0.98690, 0.98500, 0.98300,
    0.98100, 0.97900, 0.97700, 0.97500, 0.97300, 0.97100, 0.96900, 0.96700, 0.96500, 0.96300,
    0.96100, 0.95890, 0.95700, 0.95550, 0.95400, 0.95200, 0.95000, 0.94850, 0.94700, 0.94500,
    0.94300, 0.94140, 0.94000, 0.93850, 0.93700, 0.93550, 0.93400, 0.93250, 0.93100, 0.92950,
    0.92800
};

template<typename Real> inline Real lininpol(const Real * values, size_t size, Real step, Real x) {
    auto y = x / step;

    auto L = std::max<size_t>(0, std::floor(y));
    auto R = std::min<size_t>(size - 1, std::ceil(y));

    auto t = std::fmod(y, 1.0);
    return values[L] * (1 - t) + values[R] * t;
}

template<typename Real> inline Real drag(uint32_t model, const Real ballistic, const Real mach) {
    switch (model) {
        case 0:  return ballistic;
        case 1:  return ballistic * lininpol<Real>(dragModelG1<Real>, sizeof(dragModelG1<Real>), 0.05, mach);
        case 2:  return ballistic * lininpol<Real>(dragModelG7<Real>, sizeof(dragModelG7<Real>), 0.05, mach);
        case 3:  return lininpol<Real>(ballModel<Real>, sizeof(ballModel<Real>), 0.05, mach);
        default: return 0;
    }
}

template<typename T> inline T sign(T x)
{ return std::copysign(1, x); }

template<typename T, typename... Ts> inline auto min(T t, Ts... ts) { return std::min({ts...}, t); };
template<typename T, typename... Ts> inline auto max(T t, Ts... ts) { return std::max({ts...}, t); };

template<typename T> inline T random()
{ return static_cast<T>(rand()) / static_cast<T>(RAND_MAX); }

template<typename T> inline bool randbool(T probability)
{ return random<T>() < probability; }

template<typename T> inline T uniform(T m, T M)
{ return m + random<T>() * (M - m); }

enum {
    LIMB_HEAD  = 0,
    LIMB_TORSO = 1,
    LIMB_ARML  = 2,
    LIMB_ARMR  = 3,
    LIMB_LEGL  = 4,
    LIMB_LEGR  = 5
};

namespace Fundamentals {
    template<typename T> constexpr T playerHeightInMeters = 1.8;
    template<typename T> constexpr T playerHeightInBlocks = 2.5;

    template<typename T> constexpr T m2b = playerHeightInBlocks<T> / playerHeightInMeters<T>;
    template<typename T> constexpr T b2m = 1 / m2b<T>;

    template<typename T> constexpr Vector3<T> g(0, 0, 9.81); // m/s²

    template<typename T> constexpr T stefanBoltzmann     = 5.67e-08;  // W / (m² · K⁴)
    template<typename T> constexpr T molarMassDryAir     = 0.0289652; // kg/mol
    template<typename T> constexpr T molarMassWaterVapor = 0.018016;  // kg/mol
    template<typename T> constexpr T gasConstant         = 8.31446;   // J / (K · mol)
    template<typename T> constexpr T absoluteZero        = -273.15;   // Celsius
    template<typename T> constexpr T millisecond         = 0.001;     // s
    template<typename T> constexpr T bar                 = 100'000;   // Pa
}

template<typename Real> constexpr inline Real vaporPressureOfWater(const Real T) {
    // https://en.wikipedia.org/wiki/Tetens_equation
    auto k = T > 0 ? (17.27 * T) / (T + 237.3) : (21.875 * T) / (T + 265.5);
    return 610.78 * exp(k); // Pa
}

template<typename Real> inline Real overpressurePeakToAmbientRatio(const Real Z /* m / ∛kg */) {
    // Explosive Shocks in Air, G. F. Kinney, K. J. Graham, 2nd edition,
    // Ch. 6 “Blast Waves”, Tables and Equations for Blast Waves, p. 94

    constexpr Real α₁ = 4.5, α₂ = 0.048, α₃ = 0.32, α₄ = 1.35, β = 808;

    const Real Z² = Z * Z;

    const Real A₁ = 1 + Z² / α₁ / α₁;
    const Real A₂ = 1 + Z² / α₂ / α₂;
    const Real A₃ = 1 + Z² / α₃ / α₃;
    const Real A₄ = 1 + Z² / α₄ / α₄;

    return β * A₁ / std::sqrt(A₂ * A₃ * A₄);
}

template<typename Real> inline Real /* s */ overpressureDuration(const Real Z) {
    // Explosive Shocks in Air, G. F. Kinney, K. J. Graham, 2nd edition,
    // Ch. 6 “Blast Waves”, Duration, p. 97

    constexpr Real α₁ = 0.54, α₂ = 0.02, α₃ = 0.74, α₄ = 6.9, β = 980;

    constexpr Real α₁² = α₁ * α₁, α₁⁴ = α₁² * α₁², α₁⁸ = α₁⁴ * α₁⁴, α₁¹⁰ = α₁⁸ * α₁²;
    constexpr Real α₂² = α₂ * α₂, α₂³ = α₂² * α₂;
    constexpr Real α₃² = α₃ * α₃, α₃³ = α₃² * α₃, α₃⁶ = α₃³ * α₃³;
    constexpr Real α₄² = α₄ * α₄;

    const Real Z² = Z * Z, Z³ = Z² * Z, Z⁴ = Z² * Z², Z⁶ = Z³ * Z³, Z¹⁰ = Z⁶ * Z⁴;

    const Real A₁ = 1 + Z¹⁰ / α₁¹⁰;
    const Real A₂ = 1 + Z³ / α₂³;
    const Real A₃ = 1 + Z⁶ / α₃⁶;
    const Real A₄ = std::sqrt(1 + Z² / α₄²);

    using namespace Fundamentals;

    return millisecond<Real> * β * A₁ / (A₂ * A₃ * A₄);
}

template<typename Real> inline Real /* Pa · s */ overpressureImpulse(const Real Z) {
    // Explosive Shocks in Air, G. F. Kinney, K. J. Graham, 2nd edition,
    // Ch. 6 “Blast Waves”, Blast Wave Impulse per Unit Area, p. 98

    constexpr Real β = 0.067, α₁ = 0.23, α₂ = 1.55;

    constexpr Real α₁² = α₁ * α₁, α₁⁴ = α₁² * α₁²;
    constexpr Real α₂² = α₂ * α₂, α₂³ = α₂² * α₂;

    const Real Z² = Z * Z, Z³ = Z² * Z, Z⁴ = Z² * Z²;

    const Real A₁ = std::sqrt(1 + Z⁴ / α₁⁴);
    const Real A₂ = std::cbrt(1 + Z³ / α₂³);
    const Real A₃ = β / Z²;

    using namespace Fundamentals;

    return (bar<Real> * millisecond<Real>) * A₁ * A₃ / A₂;
}

template<typename T> constexpr inline T ofMeters(const T v) { return Fundamentals::m2b<T> * v; }
template<typename T> constexpr inline T toMeters(const T v) { return Fundamentals::b2m<T> * v; }

template<typename T> constexpr inline auto ofMeters3(const Vector3<T> & v)
{ return Vector3<T>(ofMeters<T>(v.x), ofMeters<T>(v.y), ofMeters<T>(v.z)); }

template<typename T> constexpr inline auto toMeters3(const Vector3<T> & v)
{ return Vector3<T>(toMeters<T>(v.x), toMeters<T>(v.y), toMeters<T>(v.z)); }

template<typename T> Vector3<T> cone(const Vector3<T> & v, const T σ);

namespace Box {
    template<typename T> constexpr auto head = Hitbox<T>(
        LIMB_HEAD, Vector3<T>(-2.5, -2.5, -3.0), Vector3<T>(6, 6, 6), 0.1
    );

    template<typename T> constexpr auto torso = Hitbox<T>(
        LIMB_TORSO, Vector3<T>(-3.5, -1.5, 3.0), Vector3<T>(8, 4, 9), 0.1
    );

    template<typename T> constexpr auto torsoc = Hitbox<T>(
        LIMB_TORSO, Vector3<T>(-3.5, -6.5, 2.0), Vector3<T>(8, 8, 7), 0.1
    );

    template<typename T> constexpr auto arm_right = Hitbox<T>(
        LIMB_ARMR, Vector3<T>(-5.5, 0.5, 4.0), Vector3<T>(2, 9, 6), 0.1
    );

    template<typename T> constexpr auto armc_right = Hitbox<T>(
        LIMB_ARMR, Vector3<T>(-5.5, 0.5, 3.0), Vector3<T>(2, 9, 6), 0.1
    );

    template<typename T> constexpr auto arm_left = Hitbox<T>(
        LIMB_ARML, Vector3<T>(3.5, -4.25, 4.0), Vector3<T>(3, 14, 2), 0.1
    );

    template<typename T> constexpr auto armc_left = Hitbox<T>(
        LIMB_ARML, Vector3<T>(3.5, -4.25, 3.0), Vector3<T>(3, 14, 2), 0.1
    );

    template<typename T> constexpr auto leg_left = Hitbox<T>(
        LIMB_LEGL, Vector3<T>(1.5, -1.5, 11.5), Vector3<T>(3, 5, 12), 0.1
    );

    template<typename T> constexpr auto legc_left = Hitbox<T>(
        LIMB_LEGL, Vector3<T>(1.5, -6.75, 6.0), Vector3<T>(3, 7, 8), 0.1
    );

    template<typename T> constexpr auto leg_right = Hitbox<T>(
        LIMB_LEGR, Vector3<T>(-3.5, -1.5, 11.5), Vector3<T>(3, 5, 12), 0.1
    );

    template<typename T> constexpr auto legc_right = Hitbox<T>(
        LIMB_LEGR, Vector3<T>(-3.5, -6.75, 6.0), Vector3<T>(3, 7, 8), 0.1
    );

    template<typename T> constexpr auto player = AABB<T>(
        Vector3<T>(arm_right<T>.aabb.min.x, torso<T>.aabb.min.y, leg_left<T>.aabb.min.z),
        Vector3<T>(arm_left<T>.aabb.max.x, torso<T>.aabb.max.y, head<T>.aabb.max.z)
    );

    template<typename T> constexpr auto playerc = AABB<T>(
        Vector3<T>(armc_right<T>.aabb.min.x, torsoc<T>.aabb.min.y, legc_left<T>.aabb.min.z),
        Vector3<T>(armc_left<T>.aabb.max.x, torsoc<T>.aabb.max.y, head<T>.aabb.max.z)
    );
}
