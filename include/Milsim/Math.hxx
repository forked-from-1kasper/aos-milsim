#pragma once

/*
    Copyright © 2026 rzrn

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

#include <numeric>
#include <utility>
#include <limits>
#include <cmath>

template<typename Real> constexpr Real epsilon = 1e-9; // Just some arbitrary small number

template<typename Real> inline Real igammaApprox(const Real y) /* y > 1.0 */ {
    constexpr Real α = 1.701, β = 0.703; // Obtained by experimental fitting

    /* Γ⁻¹(x) grows like log(x) / W(log(x)) [1], and W(log(x)) grows like log(log(x)) [2],
       hence Γ⁻¹(x) ~ log(x) / log(log(x)), and we just fit this expression linearly.
       It is already not bad and gives an absolute error slightly greater than 1 for typical values.
       [1] https://en.wikipedia.org/wiki/Inverse_gamma_function#Approximation
       [2] https://en.wikipedia.org/wiki/Lambert_W_function#Asymptotic_expansions */
    auto logy = log(y); return α * logy / log(logy) + β;
}

template<typename Real> inline Real igamma(const Real y) {
    // https://en.wikipedia.org/wiki/Gamma_function#Minima_and_maxima
    constexpr Real xmin = 1.46163214496836234126;
    constexpr Real ymin = 0.88560319441088870027;

    if (y < ymin) return std::numeric_limits<Real>::quiet_NaN();

    Real x1, x2;

    if (y > 1.0) {
        const auto x0 = igammaApprox(y);

        x1 = std::max(x0 - 1, xmin);
        x2 = std::max(x0 + 1, xmin);
    } else {
        x1 = xmin;
        x2 = 2.0;
    }

    Real logy = log(y);

    // Since we are using log|Γ(x)|, this is fast enough.
    while (lgamma(x1) > logy) x1 = std::max(x1 - 1, xmin);
    while (lgamma(x2) < logy) x2 = x2 + 1;

    // The standard bistection method goes here.

    while (x2 - x1 > epsilon<Real>) {
        Real x = std::midpoint(x1, x2);

        if (lgamma(x) > logy)
            x2 = x;
        else
            x1 = x;
    }

    return std::midpoint(x1, x2);
}

template<typename Real, Real... cₖ> struct Laurent {
    static inline void eval(Real x, Real & y) {
        // y += c₁ / x + c₂ / x² + c₃ / x³ + ...
        Real xᵏ = 1.0; ((xᵏ /= x, y += cₖ * xᵏ), ...);
    }
};

template<typename Real> inline Real digamma(Real x) /* x > 0.0 */ {
    /* [1] https://math.stackexchange.com/a/1441768
       [2] https://en.wikipedia.org/wiki/Digamma_function#Computation_and_approximation */

    using DigammaLaurent =
    Laurent<Real, -0.083333333333, +0.008333333333, -0.003968253968, +0.004166666667,
                  -0.007575757576, +0.021092796093, -0.083333333333, +0.443259803922>;

    constexpr Real x₀ = 6.0; // Threshold value for which the series above is accurate enough

    Real y = 0.0; while (x < x₀) { y -= 1.0 / x; x += 1.0; }
    y += log<Real>(x) - 0.5 / x; DigammaLaurent::eval(x * x, y);

    return y;
}

template<typename Real> inline Real idigamma(const Real y) {
    /* [1] https://mathoverflow.net/questions/279575/the-inverse-of-the-digamma-function
       [2] https://arxiv.org/pdf/1705.06547 */

    Real x1 = 1.0 / log1p(exp(-y));
    Real x2 = exp(y) + 0.5;

    while (x2 - x1 > epsilon<Real>) {
        Real x = std::midpoint(x1, x2);

        if (digamma(x) > y)
            x2 = x;
        else
            x1 = x;
    }

    return std::midpoint(x1, x2);
}

template<typename Real> inline Real weibullGustFactor(const Real log1mp, const Real ik)
{ return pow(log1mp, ik) / tgamma(1 + ik); }

template<typename Real> constexpr Real EulerMascheroni = 0.577215664901532860606512090082;

template<typename Real> inline auto shapeScaleWeibull(const Real p, const Real x, const Real μ) {
    /* We have one fixed point (x, p) on the CDF and an expected value μ. Thus:
         x = λ(−log(1 − p))^(1/k),
         μ = λ Γ(1 + 1/k).
       We call the ‘x / μ’ ratio the ‘gust factor’. So we have:
         x / μ = (−log(1 − p))^(1/k) / Γ(1 + 1/k).
       By considering the function
         GF(t) = (−log(1 − p))^t / Γ(1 + t)
       we solve the equation above as GF(t) = x / μ using the bisection method.

       To do it, we consider its behavior. First,
         GF′(t) = [log(−log(1 − p)) (−log(1 − p))^t Γ(1 + t) − (−log(1 − p))^t Γ′(1 + t)] / Γ²(1 + t)
                = [log(−log(1 − p)) (−log(1 − p))^t − (−log(1 − p))^t ψ(1 + t)] / Γ(1 + t)
                = (−log(1 − p))^t [log(−log(1 − p)) − ψ(1 + t)] / Γ(1 + t).
       In particular,
         GF′(0) = (−log(1 − p))^0 [log(−log(1 − p)) − ψ(1)] / Γ(1)
                = [log(−log(1 − p)) + γ] / Γ(1).
       So if log(−log(1 − p)) > −γ or, equivalently, −log(1 − p) > e^−γ, then GF′(0) > 0.

       Second, GF′(t) = 0 iff log(−log(1 − p)) = ψ(1 + t), and we check that
         x / μ ≤ GF(t₀), where t₀ = ψ⁻¹(log(−log(1 − p))) − 1.
       Under the given conditions, GF increases monotonically on [0; t₀].
       Since GF′(t) < 0 for t > t₀, t = t₀ is a maximum for t > 0.

       Finally, λ = x / (−log(1 − p))^(1/k). */

    Real gf = x / μ, log1mp = -log1p(-p), loglog1mp = log(log1mp), ikmax = idigamma(loglog1mp) - 1;

    if (loglog1mp <= -EulerMascheroni<Real> || x < μ || gf > weibullGustFactor(log1mp, ikmax))
        return std::pair(
            std::numeric_limits<Real>::quiet_NaN(),
            std::numeric_limits<Real>::quiet_NaN()
        );

    Real ik1 = 0.0, ik2 = ikmax;

    while (ik2 - ik1 > epsilon<Real>) {
        Real ik = std::midpoint(ik1, ik2);

        if (weibullGustFactor(log1mp, ik) > gf)
            ik2 = ik;
        else
            ik1 = ik;
    }

    Real ik = std::midpoint(ik1, ik2), λ = x * pow(log1mp, -ik);

    return std::pair(1 / ik, λ);
}
