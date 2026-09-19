#include "bino.hpp"
#include "bsm.hpp"

#include <algorithm>
#include <cmath>
#include <functional>
#include <iostream>
#include <limits>
#include <stdexcept>

void requireNear(double actual, double expected, double tolerance) {
    if (!std::isfinite(actual) || std::abs(actual - expected) > tolerance) {
        std::cerr << "actual=" << actual << ", expected=" << expected << '\n';
        throw std::runtime_error("Price mismatch.");
    }
}

template <typename Function>
void requireInvalidArgument(Function function) {
    try {
        function();
    } catch (const std::invalid_argument&) {
        return;
    }
    throw std::runtime_error("Expected std::invalid_argument.");
}

// Full-tree recursion and the original factors provide a separate small-grid reference.
double recursiveTree(int steps, double rate, double dividend, bool call, bool american) {
    const double dt = 1.0 / steps;
    const double up = std::exp((rate - dividend) * dt + 0.2 * std::sqrt(dt));
    const double down = std::exp((rate - dividend) * dt - 0.2 * std::sqrt(dt));
    const double p = (std::exp((rate - dividend) * dt) - down) / (up - down);
    std::function<double(int, int)> value = [&](int step, int downMoves) {
        const double stock = 100 * std::pow(up, step - downMoves) * std::pow(down, downMoves);
        const double payoff = std::max(call ? stock - 105 : 105 - stock, 0.0);
        if (step == steps) {
            return payoff;
        }
        const double continuation = std::exp(-rate * dt) *
            (p * value(step + 1, downMoves) + (1 - p) * value(step + 1, downMoves + 1));
        return american ? std::max(payoff, continuation) : continuation;
    };
    return value(0, 0);
}

int main() {
    try {
        for (const int steps : {1, 2, 7}) {
            for (const double rate : {-0.02, 0.05}) {
                for (const double dividend : {0.0, 0.03}) {
                    for (const bool call : {false, true}) {
                        for (const bool american : {false, true}) {
                            const BinomialOptionPricing tree(100, 105, rate, 1, 0.2, steps, call, american, dividend);
                            const auto parameters = tree.parameters();
                            const double probability = (std::exp((rate - dividend) * parameters.dt) - parameters.down) /
                                                       (parameters.up - parameters.down);
                            requireNear(parameters.upProbability, probability, 0.0);
                            requireNear(tree.price(), recursiveTree(steps, rate, dividend, call, american), 2e-11);
                        }
                    }
                }
            }
        }
        const auto cdf = [](double x) { return 0.5 * std::erfc(-x / std::sqrt(2.0)); };
        const double d1 = (0.05 - 0.03 + 0.5 * 0.2 * 0.2) / 0.2;
        const double d2 = d1 - 0.2;
        for (const bool call : {false, true}) {
            const double sign = call ? 1.0 : -1.0;
            const double reference = sign * (100 * std::exp(-0.03) * cdf(sign * d1) -
                                             100 * std::exp(-0.05) * cdf(sign * d2));
            const BinomialOptionPricing tree(100, 100, 0.05, 1, 0.2, 1000, call, false, 0.03);
            requireNear(tree.price(), reference, 0.01);
        }
        const BinomialOptionPricing deterministicCall(120, 100, 0.05, 1, 0, 100, true, true, 0.1);
        requireNear(deterministicCall.price(), 20, 0);

        const auto regular = blackScholesOptionPricing(100, 100, 0.05, 0.2, 1, true);
        if (!regular.greeksAvailable) {
            throw std::runtime_error("Regular BSM Greeks were omitted.");
        }
        for (const auto& boundary : {
                 blackScholesOptionPricing(100, 100, 0.05, 0, 1, true),
                 blackScholesOptionPricing(100, 100, 0.05, 0.2, 0, true),
                 blackScholesOptionPricing(100, 0, 0.05, 0.2, 1, true)}) {
            if (boundary.greeksAvailable) {
                throw std::runtime_error("Boundary Greeks must be explicitly marked unavailable.");
            }
        }
        const double nan = std::numeric_limits<double>::quiet_NaN();
        requireInvalidArgument([] { blackScholesOptionPricing(0, 100, 0.05, 0.2, 1, true); });
        requireInvalidArgument([] { blackScholesOptionPricing(100, 100, 0.05, -0.2, 1, true); });
        requireInvalidArgument([&] { blackScholesOptionPricing(100, 100, nan, 0.2, 1, true); });
        requireInvalidArgument([] { BinomialOptionPricing(100, 100, 0.05, 1, 0.2, 0, true, false); });
        requireInvalidArgument([] { BinomialOptionPricing(100, 100, 0.05, -1, 0.2, 10, true, false); });
        requireInvalidArgument([&] { BinomialOptionPricing(100, 100, 0.05, 1, 0.2, 10, true, false, nan); });
        std::cout << "All shared-pricer, dividend, exercise, and validation checks passed.\n";
    } catch (const std::exception& error) {
        std::cerr << "Pricer test failed: " << error.what() << '\n';
        return 1;
    }
}
