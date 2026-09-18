#include <algorithm>
#include <iostream>
#include <cmath>
#include <random>

// Function to generate normally distributed random numbers
double generateGaussianNoise(double mean, double stddev) {
    static std::random_device rd;
    static std::mt19937 generator(rd());
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

double getRate() {
    return 0.05;  // Constant rate
}

double getVolatility() {
    return 0.2;  // Constant volatility
}

// Sample the terminal GBM price directly for constant r and sigma.
double monteCarloOptionPricing(double S0, double K, double T, int numSimulations, bool isCallOption) {
    double payoffSum = 0.0;
    const double r = getRate();
    const double sigma = getVolatility();
    const double drift = (r - 0.5 * sigma * sigma) * T;
    const double diffusion = sigma * std::sqrt(T);

    for (int i = 0; i < numSimulations; ++i) {
        const double S = S0 * std::exp(drift + diffusion * generateGaussianNoise(0.0, 1.0));

        double payoff = isCallOption ? callOptionPayoff(S, K) : putOptionPayoff(S, K);

        // Accumulate the payoff
        payoffSum += payoff;
    }

    // Calculate the average payoff and discount it to present value
    double averagePayoff = payoffSum / static_cast<double>(numSimulations);
    return std::exp(-r * T) * averagePayoff;
}

int main() {
    // Option parameters
    double S0 = 100.0;   // Initial stock price
    double K = 100.0;    // Strike price
    double T = 1.0;      // Time to maturity (1 year)
    int numSimulations = 100000; // Number of simulations

    // Calculate option prices with constant r and sigma
    double callPrice = monteCarloOptionPricing(S0, K, T, numSimulations, true);
    double putPrice = monteCarloOptionPricing(S0, K, T, numSimulations, false);

    // Output the results
    std::cout << "European Call Option Price: " << callPrice << std::endl;
    std::cout << "European Put Option Price: " << putPrice << std::endl;

    return 0;
}
