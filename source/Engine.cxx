#include <Milsim/Engine.hxx>

template<typename T> Vector3<T> cone(const Vector3<T> & v, const T σ) {
    static std::random_device rd;
    static std::mt19937 randgen(rd());

    std::normal_distribution gauss(0.0, σ);
    std::uniform_real_distribution uniform(-std::numbers::pi_v<T>, std::numbers::pi_v<T>);

    auto n = v.normal(); auto left = Vector3<T>(n.y, -n.x, 0).normal();
    auto α = std::fabs(gauss(randgen)), β = uniform(randgen);

    return v.rot(left, α).rot(n, β);
}

Voxel & VoxelData::set(int i, PyObject * o) {
    int x, y, z; get_xyz(i, &x, &y, &z);
    if (63 <= z) return water; // ignore z = 63

    auto d = z < 62 ? 1.0 : std::numeric_limits<double>::infinity();

    if (o == nullptr) o = defaultMaterial;

    auto [iter, _] = data.insert_or_assign(i, Voxel(o, d));
    return iter->second;
}

Voxel & VoxelData::get(int x, int y, int z) {
    if (63 <= z) return water;

    auto i = get_pos(x, y, z); auto iter = data.find(i);
    return iter == data.end() ? set(i, defaultMaterial) : iter->second;
}

uint64_t Object::gidx = 0;

void Engine::clear() {
    temperature = 0;
    pressure    = 101325;
    humidity    = 0.3;

    wind.x = wind.y = wind.z = 0;

    update();

    _lag = _peak = 0.0;

    objects.clear();
    Object::flush();

    vxlData.clear();
}

void Engine::update() {
    using namespace Fundamentals;

    auto t = temperature, p = pressure, φ = humidity; auto & w = wind;

    // 1) Here we assume Dalton’s law.

    // https://en.wikipedia.org/wiki/Density_of_air#Humid_air
    auto p₁ = φ * vaporPressureOfWater<double>(t), p₂ = p - p₁;

    auto ε = gasConstant<double> * (t - absoluteZero<double>);

    _density = (p₁ * molarMassWaterVapor<double> + p₂ * molarMassDryAir<double>) / ε;
    _ppo2    = 0.20946 * p₂;

    // 2) Here we assume Amagat’s law.

    // https://en.wikipedia.org/wiki/Heat_capacity_ratio#Relation_with_degrees_of_freedom
    constexpr double γ₁ = 1.333333, γ₂ = 1.4;

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

void Engine::step(const double t1, const double t2) {
    using namespace std::chrono;

    const auto T1 = steady_clock::now();

    for (auto it = objects.begin(); it != objects.end(); next(t1, t2, it));

    const auto T2 = steady_clock::now();

    auto diff = duration_cast<microseconds>(T2 - T1).count();
    _lag  = (_lag + diff) / 2;
    _peak = std::max(_peak, double(diff));
}

void Engine::next(double t1, const double t2, ObjectIterator & it) {
    using namespace Fundamentals;

    Object & o = *it;

    Voxel * voxel = nullptr; Material * M = nullptr;
    Vector3d r(o.position), v(o.velocity), n;

    uint64_t N = 1;

    bool stuck = false;

    while (t1 < t2 && N < 10000 && !stuck) {
        N++;

        int64_t X = std::floor(r.x), Y = std::floor(r.y), Z = std::ceil(r.z);

        if (n.x != 0 && v.x < 0) X--;
        if (n.y != 0 && v.y < 0) Y--;
        if (n.z != 0 && v.z > 0) Z++;

        auto state = Terminal::flying;

        if (is_valid_position(X, Y, Z) && get_solid(X, Y, Z, map)) {
            voxel = &vxlData.get(X, Y, Z); M = voxel->material();

            auto θ = acos(-(v, n) / v.abs());

            state = M->deflecting <= θ && random<double>() < M->ricochet ? Terminal::ricochet
                                                                         : Terminal::penetration;

            if (state != Terminal::flying) {
                constexpr double hitEffectThresholdEnergy = 5.0;

                trace(o.index(), r, v.abs() / o.v0(), false);

                if (hitEffectThresholdEnergy <= o.energy())
                    stuck = Py_True == onBlockHit(
                        o.object(), r.x, r.y, r.z, v.x, v.y, v.z, X, Y, Z,
                        o.thrower(), o.energy(), o.area
                    );
            }

            if (state == Terminal::ricochet) v -= n * (2 * (v, n));

            if (state == Terminal::penetration) v = cone(v, 0.05);
        }

        // `dr` depends only on direction, not the absolute value of `v`
        // That’s why all direction changes need to be made before this point.
        double x = v.x > 0 ? std::floor(r.x) + 1 : std::ceil(r.x) - 1;
        double y = v.y > 0 ? std::floor(r.y) + 1 : std::ceil(r.y) - 1;
        double z = v.z > 0 ? std::floor(r.z) + 1 : std::ceil(r.z) - 1;

        double dx = x - r.x, dy = y - r.y, dz = z - r.z;

        if (std::abs(dx) < 1e-20) dx = sign(v.x);
        if (std::abs(dy) < 1e-20) dy = sign(v.y);
        if (std::abs(dz) < 1e-20) dz = sign(v.z);

        double idt; std::tie(idt, n) = max(
            [](auto & w1, auto & w2){ return w1.first < w2.first; },
            std::pair(m2b<double> * v.x / dx, Vector3d(-sign(v.x), 0, 0)),
            std::pair(m2b<double> * v.y / dy, Vector3d(0, -sign(v.y), 0)),
            std::pair(m2b<double> * v.z / dz, Vector3d(0, 0, -sign(v.z)))
        );

        double dt = std::min(idt < 1e-9 ? INFINITY : 1 / idt, t2 - t1);
        auto dr = v * (m2b<double> * dt);

        if (state == Terminal::ricochet) v *= 0.6;

        if (state == Terminal::penetration) {
            // http://panoptesv.com/RPGs/Equipment/Weapons/Projectile_physics.php
            auto depth = dr.abs() * b2m<double>;
            auto E₀    = 0.5 * o.mass * v.norm();
            auto drag  = 1;
            auto xc    = o.mass / (drag * M->density * o.area);
            auto xmax  = xc * log(1 + (E₀ * drag * M->density) / (M->strength * o.mass));

            double ΔE = 0; // energy that will be absorbed by block

            if (xmax > depth) {
                auto ε = exp(-drag * o.area * M->density * depth / o.mass);
                auto E = E₀ * ε - M->strength * o.mass * (1 - ε) / (drag * M->density);
                ΔE = E₀ - E;

                v *= std::sqrt(E / E₀);
            } else {
                ΔE = E₀; stuck = true;
                v.x = v.y = v.z = 0.0;
            }

            if (voxel->isub(ΔE * (M->durability / M->absorption)))
                onDestroy(o.thrower(), X, Y, Z);
        }

        Ray<double> ray(r, dr); Arc<double> arc{}; int target = -1;

        for (size_t i = 0; i < players.size(); i++) {
            auto & player = players[i];
            if (!player.valid()) continue;

            auto retval = player.intersect(ray);
            if (retval < arc) { arc = retval; target = i; }
        }

        if (0 <= target) {
            auto w = arc.begin(ray);

            stuck = Py_True == onPlayerHit(
                o.object(), w.x, w.y, w.z, v.x, v.y, v.z, X, Y, Z,
                o.thrower(), o.energy(), o.area, target, arc.index
            );

            trace(o.index(), w, v.abs() / o.v0(), false);
        }

        auto m  = o.mass;
        auto u  = wind - v;
        auto CD = drag(o.model(), o.ballistic, u.abs() / _mach);
        auto F  = g<double> * m + u * (0.5 * _density * u.abs() * CD * o.area);

        auto dv = F * (dt / m);

        t1 += dt; r += dr; v += dv;
    }

    o.position.set(r); o.velocity.set(v);

    if (!stuck) trace(o.index(), r, v.abs() / o.v0(), false);

    //if (t2 - o.timestamp() > 10) printf("%ld: time out\n", o.index());
    //if (o.velocity.abs() <= 1e-3) printf("%ld: speed too low (%f m/s)\n", o.index(), o.velocity.abs());
    //if (!is_valid_position(o.position.x, o.position.y, o.position.z)) printf("%ld: out of map (%f, %f, %f)\n", o.index, o.position.x, o.position.y, o.position.z);

    auto P = t2 - o.timestamp() <= 10;
    auto Q = o.velocity.abs() > 1e-2;
    auto R = is_valid_position(o.position.x, o.position.y, o.position.z);

    if (P && Q && R && !stuck) ++it; else it = objects.erase(it);
}
