#include "carlos.hpp"

#include <algorithm>
#include <cmath>
#include <iostream>
#include <limits>
#include <random>
#include <stdexcept>

void require(bool condition, const char* message) {
    if (!condition) {
        throw std::runtime_error(message);
    }
}

void requireNear(double actual, double expected, double tolerance, const char* message) {
    if (!std::isfinite(actual) || std::abs(actual - expected) > tolerance) {
        std::cerr << message << ": actual=" << actual << ", expected=" << expected
                  << ", tolerance=" << tolerance << '\n';
        throw std::runtime_error(message);
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

struct Moments {
    double mean;
    double variance;
};

// Numerical integration is independent of the closed-form implementation.
Moments quadratureMoments(double T, const VasicekParameters& rates) {
    constexpr int intervals = 20000;
    const double h = T / intervals;
    double meanSum = 0.0;
    double varianceSum = 0.0;
    for (int i = 0; i <= intervals; ++i) {
        const double t = i * h;
        const double decay = std::exp(-rates.meanReversion * t);
        const double B = rates.meanReversion == 0.0 ? t :
            -std::expm1(-rates.meanReversion * t) / rates.meanReversion;
        const double weight = (i == 0 || i == intervals) ? 1.0 : (i % 2 == 0 ? 2.0 : 4.0);
        meanSum += weight * (rates.initialRate * decay + rates.longRunRate * (1.0 - decay));
        varianceSum += weight * rates.volatility * rates.volatility * B * B;
    }
    return {meanSum * h / 3.0, varianceSum * h / 3.0};
}

double normalCdf(double x) {
    return 0.5 * std::erfc(-x / std::sqrt(2.0));
}

double analyticalPrice(double S0, double K, double T, bool call, Moments rateIntegral) {
    const double bondPrice = std::exp(-rateIntegral.mean + 0.5 * rateIntegral.variance);
    const double totalVariance = 0.2 * 0.2 * T + rateIntegral.variance;
    const double totalStddev = std::sqrt(totalVariance);
    const double d1 = (std::log(S0 / K) + rateIntegral.mean + 0.5 * 0.2 * 0.2 * T) / totalStddev;
    const double d2 = d1 - totalStddev;
    return call ? S0 * normalCdf(d1) - K * bondPrice * normalCdf(d2) :
        K * bondPrice * normalCdf(-d2) - S0 * normalCdf(-d1);
}

struct SampleStatistics {
    int count = 0;
    double mean = 0.0;
    double m2 = 0.0;

    void add(double x) {
        ++count;
        const double delta = x - mean;
        mean += delta / count;
        m2 += delta * (x - mean);
    }

    double standardError() const {
        return std::sqrt(m2 / (count - 1) / count);
    }
};

void checkPrices(double T, const VasicekParameters& rates, unsigned int seed) {
    constexpr int samples = 250000;
    const Moments integral = quadratureMoments(T, rates);
    const double stddev = std::sqrt(integral.variance);
    std::mt19937 generator(seed);
    SampleStatistics calls, puts, discountedStock, discounts;

    for (int i = 0; i < samples; ++i) {
        const double I = stddev == 0.0 ? integral.mean :
            integral.mean + stddev * std::normal_distribution<double>{}(generator);
        const double z = std::normal_distribution<double>{}(generator);
        const double discount = std::exp(-I);
        // In discounted units the accumulated rate cancels from the stock.
        const double stock = 100.0 * std::exp(-0.5 * 0.2 * 0.2 * T + 0.2 * std::sqrt(T) * z);
        calls.add(std::max(stock - 100.0 * discount, 0.0));
        puts.add(std::max(100.0 * discount - stock, 0.0));
        discountedStock.add(stock);
        discounts.add(discount);
    }

    const double call = monteCarloOptionPricing(100.0, 100.0, T, samples, true, rates, seed);
    const double put = monteCarloOptionPricing(100.0, 100.0, T, samples, false, rates, seed);
    requireNear(call, calls.mean, 1e-9, "Pathwise call discounting mismatch");
    requireNear(put, puts.mean, 1e-9, "Pathwise put discounting mismatch");
    requireNear(call, analyticalPrice(100.0, 100.0, T, true, integral),
        7.0 * calls.standardError() + 1e-10, "Call analytical benchmark");
    requireNear(put, analyticalPrice(100.0, 100.0, T, false, integral),
        7.0 * puts.standardError() + 1e-10, "Put analytical benchmark");
    requireNear(discountedStock.mean, 100.0, 7.0 * discountedStock.standardError(), "Discounted stock martingale");
    requireNear(discounts.mean, std::exp(-integral.mean + 0.5 * integral.variance),
        7.0 * discounts.standardError() + 1e-12, "Zero-coupon bond benchmark");
    requireNear(call - put, discountedStock.mean - 100.0 * discounts.mean, 1e-9, "Sample put-call parity");
}

int main() {
    try {
        const VasicekParameters example{0.05, 0.05, 1.0, 0.01};
        for (const double T : {0.0, 0.000001, 0.25, 1.0, 3.0}) {
            for (const double kappa : {0.0, 1e-8, 0.00333, 0.00999, 0.01, 0.01001, 1.0, 4.0}) {
                const VasicekParameters rates{0.02, 0.07, kappa, 0.03};
                const auto actual = integratedRateDistribution(T, rates);
                const auto expected = quadratureMoments(T, rates);
                requireNear(actual.mean, expected.mean, 1e-12, "Integrated-rate mean");
                requireNear(actual.stddev * actual.stddev, expected.variance,
                    1e-10 * expected.variance + 1e-30, "Integrated-rate variance");
            }
        }

        const auto constant = integratedRateDistribution(1.0, {0.05, 0.05, 1.0, 0.0});
        requireNear(constant.mean, 0.05, 1e-15, "Constant-rate mean");
        require(constant.stddev == 0.0, "Constant rate must have zero uncertainty.");
        requireNear(analyticalPrice(100.0, 100.0, 1.0, true, {0.05, 0.0}),
            10.450583572185565, 1e-12, "Black-Scholes call reference");
        requireNear(analyticalPrice(100.0, 100.0, 1.0, false, {0.05, 0.0}),
            5.573526022256971, 1e-12, "Black-Scholes put reference");
        for (const double S0 : {80.0, 100.0, 120.0}) {
            for (const bool call : {false, true}) {
                const double expected = call ? std::max(S0 - 100.0, 0.0) : std::max(100.0 - S0, 0.0);
                require(monteCarloOptionPricing(S0, 100.0, 0.0, 1, call, example, 42) == expected,
                    "Expiry payoff mismatch.");
            }
        }

        const double first = monteCarloOptionPricing(100.0, 100.0, 1.0, 1000, true, example, 42);
        require(first == monteCarloOptionPricing(100.0, 100.0, 1.0, 1000, true, example, 42),
            "Identical seeds must reproduce the estimate.");
        require(monteCarloOptionPricing(100.0, 0.0, 1.0, 100, false, example, 42) == 0.0,
            "Zero-strike put must be worthless.");

        checkPrices(1.0, {0.05, 0.05, 1.0, 0.0}, 41);
        checkPrices(1.0, {0.02, 0.07, 0.7, 0.0}, 42);
        checkPrices(1.0, example, 43);
        checkPrices(2.0, {0.03, 0.07, 0.0, 0.05}, 44);
        checkPrices(4.0, {0.05, 0.05, 0.05, 0.25}, 45);
        checkPrices(0.25, {-0.02, -0.01, 1.0, 0.02}, 46);
        checkPrices(3.0, {0.02, 0.07, 1e-8, 0.03}, 47);

        const double nan = std::numeric_limits<double>::quiet_NaN();
        const double infinity = std::numeric_limits<double>::infinity();
        requireInvalidArgument([&] { integratedRateDistribution(-1.0, example); });
        requireInvalidArgument([&] { integratedRateDistribution(nan, example); });
        requireInvalidArgument([&] { integratedRateDistribution(infinity, example); });
        requireInvalidArgument([] { integratedRateDistribution(1.0, {0.05, 0.05, -1.0, 0.01}); });
        requireInvalidArgument([] { integratedRateDistribution(1.0, {0.05, 0.05, 1.0, -0.01}); });
        requireInvalidArgument([&] { integratedRateDistribution(1.0, {nan, 0.05, 1.0, 0.01}); });
        requireInvalidArgument([&] { integratedRateDistribution(1.0, {0.05, infinity, 1.0, 0.01}); });
        requireInvalidArgument([&] { integratedRateDistribution(1.0, {0.05, 0.05, nan, 0.01}); });
        requireInvalidArgument([&] { integratedRateDistribution(1.0, {0.05, 0.05, 1.0, infinity}); });
        requireInvalidArgument([&] { monteCarloOptionPricing(100.0, 100.0, 1.0, 0, true, example, 42); });
        requireInvalidArgument([&] { monteCarloOptionPricing(0.0, 100.0, 1.0, 100, true, example, 42); });
        requireInvalidArgument([&] { monteCarloOptionPricing(100.0, -1.0, 1.0, 100, true, example, 42); });
        requireInvalidArgument([&] { monteCarloOptionPricing(infinity, 100.0, 1.0, 100, true, example, 42); });
        requireInvalidArgument([&] { monteCarloOptionPricing(100.0, nan, 1.0, 100, true, example, 42); });

        std::cout << "All integrated-rate, pricing, reproducibility, and input checks passed.\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "Test failure: " << error.what() << '\n';
        return 1;
    }
}
