#include "bino.hpp"

#include <algorithm>
#include <cmath>
#include <iostream>
#include <stdexcept>
#include <vector>

//improvements TODO:
// use pointers to return stuff
// add an option chain
// print the entire tree
// optimized calculateParameters() func for r, sigma

BinomialOptionPricing::BinomialOptionPricing(double S, double K, double r, double T, double sigma,
                                           int N, bool isCall, bool isAmerican, double q)
    : S(S), K(K), r(r), T(T), sigma(sigma), q(q), N(N), isCall(isCall), isAmerican(isAmerican) {
    if (!std::isfinite(S) || !std::isfinite(K) || !std::isfinite(r) ||
        !std::isfinite(T) || !std::isfinite(sigma) || !std::isfinite(q) ||
        S <= 0.0 || K < 0.0 || T < 0.0 || sigma < 0.0 || N < 1) {
        throw std::invalid_argument("Binomial inputs must be finite, with positive spot/steps and nonnegative strike, maturity and volatility.");
    }
    calculateParameters();
}

void BinomialOptionPricing::calculateParameters() {
    dt = T / N;
    jump = sigma * std::sqrt(dt);
    u = std::exp((r - q) * dt + jump);
    d = std::exp((r - q) * dt - jump);
    discountFactor = std::exp(-r * dt);
    if (!std::isfinite(u) || !std::isfinite(d) || !std::isfinite(discountFactor) ||
        d == 0.0 || discountFactor == 0.0) {
        throw std::overflow_error("Binomial parameters exceed the supported numerical range.");
    }
    if (T == 0.0 || sigma == 0.0) {
        // price() handles these non-branching cases directly.
        p = 0.5;
    } else {
        if (u == d) {
            throw std::overflow_error("Binomial up/down factors are indistinguishable at double precision.");
        }
        p = (std::exp((r - q) * dt) - d) / (u - d);
        if (!std::isfinite(p) || p < 0.0 || p > 1.0) {
            throw std::overflow_error("Binomial probability is outside the supported numerical range.");
        }
    }
}

double BinomialOptionPricing::stockAt(int step, int downMoves) const {
    if (step == 0) {
        return S;
    }
    const double stock = std::exp(std::log(S) + (r - q) * dt * step + jump * (step - 2.0 * downMoves));
    if (!std::isfinite(stock)) {
        throw std::overflow_error("Binomial node exceeds the supported numerical range.");
    }
    return stock;
}

double BinomialOptionPricing::optionPayoff(double stock) const {
    return std::max(isCall ? stock - K : K - stock, 0.0);
}

double BinomialOptionPricing::price() const {
    if (T == 0.0) {
        return optionPayoff(S);
    }
    if (sigma == 0.0) {
        double best = 0.0;
        const int first = isAmerican ? 0 : N;
        for (int step = first; step <= N; ++step) {
            const double value = std::exp(-r * dt * step) * optionPayoff(stockAt(step, 0));
            if (!std::isfinite(value)) {
                throw std::overflow_error("Deterministic option price exceeds the supported numerical range.");
            }
            best = std::max(best, value);
        }
        return best;
    }

    std::vector<double> optionValues(static_cast<std::size_t>(N) + 1);
    for (int i = 0; i <= N; ++i) {
        optionValues[i] = optionPayoff(stockAt(N, i));
    }
    for (int step = N - 1; step >= 0; --step) {
        for (int i = 0; i <= step; ++i) {
            optionValues[i] = (p * optionValues[i] + (1.0 - p) * optionValues[i + 1]) * discountFactor;
            if (isAmerican) {
                optionValues[i] = std::max(optionValues[i], optionPayoff(stockAt(step, i)));
            }
        }
    }
    if (!std::isfinite(optionValues[0])) {
        throw std::overflow_error("Binomial price exceeds the supported numerical range.");
    }
    return optionValues[0];
}

BinomialParameters BinomialOptionPricing::parameters() const {
    return {dt, u, d, p};
}

#ifndef PRICERS_NO_MAIN
int main() {
    const double S = 100.0;
    const double K = 100.0;
    const double r = 0.05;
    const double T = 1.0;
    const double sigma = 0.2;
    const int N = 100;
    const bool isCall = false;
    const double q = 0.03;

    for (const bool american : {true, false}) {
        const BinomialOptionPricing option(S, K, r, T, sigma, N, isCall, american, q);
        std::cout << "The " << (american ? "American " : "European ") << (isCall ? "call" : "put")
                  << " option price is: " << option.price() << '\n';
    }
}
#endif
