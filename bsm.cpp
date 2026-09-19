#include "bsm.hpp"

#include <algorithm>
#include <cmath>
#include <iostream>
#include <limits>
#include <numbers>
#include <stdexcept>

namespace {
double cumulativeStandardNormal(double x) {
    return 0.5 * std::erfc(-x / std::sqrt(2.0));
}
}

Contract blackScholesOptionPricing(double S0, double K, double r, double sigma, double T, bool isCallOption) {
    if (!std::isfinite(S0) || !std::isfinite(K) || !std::isfinite(r) ||
        !std::isfinite(sigma) || !std::isfinite(T) || S0 <= 0.0 || K < 0.0 ||
        sigma < 0.0 || T < 0.0) {
        throw std::invalid_argument("BSM requires finite inputs, positive spot and nonnegative strike, volatility and maturity.");
    }
    const double discountedStrike = K * std::exp(-r * T);
    if (!std::isfinite(discountedStrike) || T * 365.2425 > std::numeric_limits<int>::max()) {
        throw std::overflow_error("BSM inputs exceed the supported numerical range.");
    }

    Contract con;
    con.dte = static_cast<int>(T * 365.2425);
    con.volatility = sigma;
    con.intrinsic_value = std::max(isCallOption ? S0 - K : K - S0, 0.0);
    if (T == 0.0 || sigma == 0.0 || K == 0.0) {
        con.premium = std::max(isCallOption ? S0 - discountedStrike : discountedStrike - S0, 0.0);
        return con;
    }

    const double rootT = std::sqrt(T);
    const double scale = sigma * rootT;
    const double d1 = (std::log(S0) - std::log(K) + (r + 0.5 * sigma * sigma) * T) / scale;
    const double d2 = d1 - scale;
    const double density = std::exp(-0.5 * d1 * d1) / std::sqrt(2.0 * std::numbers::pi);
    const double sign = isCallOption ? 1.0 : -1.0;
    con.premium = sign * (S0 * cumulativeStandardNormal(sign * d1) -
                          discountedStrike * cumulativeStandardNormal(sign * d2));
    con.delta = sign * cumulativeStandardNormal(sign * d1);
    con.gamma = density / (S0 * scale);
    con.theta = -S0 * density * sigma / (2.0 * rootT) -
                sign * r * discountedStrike * cumulativeStandardNormal(sign * d2);
    con.vega = S0 * density * rootT;
    con.rho = sign * discountedStrike * T * cumulativeStandardNormal(sign * d2);
    for (const double value : {con.premium, con.delta, con.gamma, con.theta, con.vega, con.rho}) {
        if (!std::isfinite(value)) {
            throw std::overflow_error("BSM price or Greeks exceeded the supported numerical range.");
        }
    }
    con.greeksAvailable = true;
    return con;
}

#ifndef PRICERS_NO_MAIN
int main() {
    const double S0 = 100.0;
    const double K = 100.0;
    const double r = 0.05;
    const double sigma = 0.2;
    const double T = 1.0;

    for (const bool call : {true, false}) {
        const auto con = blackScholesOptionPricing(S0, K, r, sigma, T, call);
        std::cout << "European " << (call ? "Call" : "Put") << " Option Price: " << con.premium
                  << ", dte: " << con.dte;
        if (con.greeksAvailable) {
            std::cout << ", delta: " << con.delta << ", gamma: " << con.gamma
                      << ", theta: " << con.theta << ", vega: " << con.vega << ", rho: " << con.rho;
        } else {
            std::cout << ", Greeks omitted for boundary inputs";
        }
        std::cout << ", input volatility: " << con.volatility << ", intrinsic value: " << con.intrinsic_value << '\n';
    }
}
#endif
