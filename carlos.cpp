#include "carlos.hpp"

#include <algorithm>
#include <iostream>
#include <cmath>
#include <random>
#include <stdexcept>

// Function to generate normally distributed random numbers
double generateGaussianNoise(double mean, double stddev, std::mt19937& generator) {
    std::normal_distribution<double> distribution(mean, stddev);
    return distribution(generator);
}

// Function to calculate the payoff of a European call option
double callOptionPayoff(double S, double K) {
    return std::max(S - K, 0.0);
}

// Function to calculate the payoff of a European put option
double putOptionPayoff(double S, double K) {
    return std::max(K - S, 0.0);
}

IntegratedRateDistribution integratedRateDistribution(double T, const VasicekParameters& rates) {
    if (!std::isfinite(T) || T < 0.0 ||
        !std::isfinite(rates.initialRate) || !std::isfinite(rates.longRunRate) ||
        !std::isfinite(rates.meanReversion) || rates.meanReversion < 0.0 ||
        !std::isfinite(rates.volatility) || rates.volatility < 0.0) {
        throw std::invalid_argument("Maturity and rate parameters must be finite; maturity, mean reversion and rate volatility must be nonnegative.");
    }
    if (T == 0.0) {
        return {0.0, 0.0};
    }

    const double kappa = rates.meanReversion;
    const double x = kappa * T;
    if (!std::isfinite(x)) {
        throw std::overflow_error("Mean reversion times maturity is too large.");
    }
    const double B = x == 0.0 ? T : -std::expm1(-x) / kappa;
    const double mean = rates.initialRate * B + rates.longRunRate * (T - B);
    double stddev = 0.0;

    if (rates.volatility > 0.0) {
        if (x < 0.01) {
            // Taylor expansion avoids cancellation and includes the kappa=0 limit.
            const double varianceFactor = 1.0 / 3.0 + x * (-1.0 / 4.0 +
                x * (7.0 / 60.0 + x * (-1.0 / 24.0 + x * (31.0 / 2520.0))));
            stddev = rates.volatility * T * std::sqrt(T * varianceFactor);
        } else {
            const double varianceTime = T - 2.0 * B - std::expm1(-2.0 * x) / (2.0 * kappa);
            stddev = (rates.volatility / kappa) * std::sqrt(varianceTime);
        }
    }
    if (!std::isfinite(mean) || !std::isfinite(stddev)) {
        throw std::overflow_error("Integrated-rate distribution is outside the supported numerical range.");
    }
    return {mean, stddev};
}

double getVolatility() {
    return 0.2;  // Constant volatility
}

// Risk-neutral Vasicek rates, independent equity shocks, and no dividends.
double monteCarloOptionPricing(
    double S0, double K, double T, int numSimulations, bool isCallOption,
    const VasicekParameters& rates, unsigned int seed) {
    if (!std::isfinite(S0) || S0 <= 0.0 || !std::isfinite(K) || K < 0.0 || numSimulations <= 0) {
        throw std::invalid_argument("Spot must be positive, strike nonnegative, and simulations positive; prices must be finite.");
    }
    const IntegratedRateDistribution rateIntegral = integratedRateDistribution(T, rates);
    if (T == 0.0) {
        return isCallOption ? callOptionPayoff(S0, K) : putOptionPayoff(S0, K);
    }

    std::mt19937 generator(seed);
    double discountedPayoffSum = 0.0;
    const double sigma = getVolatility();
    const double stockDrift = -0.5 * sigma * sigma * T;
    const double diffusion = sigma * std::sqrt(T);

    for (int i = 0; i < numSimulations; ++i) {
        const double accumulatedRate = rateIntegral.stddev == 0.0 ? rateIntegral.mean :
            rateIntegral.mean + rateIntegral.stddev * generateGaussianNoise(0.0, 1.0, generator);
        const double S = S0 * std::exp(accumulatedRate + stockDrift +
            diffusion * generateGaussianNoise(0.0, 1.0, generator));
        const double payoff = isCallOption ? callOptionPayoff(S, K) : putOptionPayoff(S, K);

        // Discount each payoff with the same rate integral used for stock growth.
        discountedPayoffSum += std::exp(-accumulatedRate) * payoff;
        if (!std::isfinite(S) || !std::isfinite(discountedPayoffSum)) {
            throw std::overflow_error("Simulated price or discounted payoff is outside the supported numerical range.");
        }
    }

    return discountedPayoffSum / static_cast<double>(numSimulations);
}

#ifndef CARLOS_NO_MAIN
int main() {
    try {
        const double S0 = 100.0;
        const double K = 100.0;
        const double T = 1.0;
        const int numSimulations = 100000;
        const unsigned int seed = 42;
        const VasicekParameters rates{
            .initialRate = 0.05,
            .longRunRate = 0.05,
            .meanReversion = 1.0,
            .volatility = 0.01
        };

        const double callPrice = monteCarloOptionPricing(S0, K, T, numSimulations, true, rates, seed);
        const double putPrice = monteCarloOptionPricing(S0, K, T, numSimulations, false, rates, seed);

        std::cout << "Illustrative risk-neutral Vasicek rates (independent stock shocks)\n";
        std::cout << "European Call Option Price: " << callPrice << '\n';
        std::cout << "European Put Option Price: " << putPrice << '\n';
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "Pricing failed: " << error.what() << '\n';
        return 1;
    }
}
#endif