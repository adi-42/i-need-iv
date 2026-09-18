#pragma once

struct VasicekParameters {
    double initialRate;
    double longRunRate;
    double meanReversion;
    double volatility;
};

struct IntegratedRateDistribution {
    double mean;
    double stddev;
};

IntegratedRateDistribution integratedRateDistribution(double T, const VasicekParameters& rates);

double monteCarloOptionPricing(
    double S0, double K, double T, int numSimulations, bool isCallOption,
    const VasicekParameters& rates, unsigned int seed);
