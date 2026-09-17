#include <iostream>
#include <cmath>
#include <random>
#include <vector>

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

// Example time-dependent rate function
double getRate(double t) {
    // Test with constant rate first to verify multi-step approach
    return 0.05;  // Constant rate
    // return 0.05 + 0.02 * t;  // Uncomment for time-dependent rate
}

// Example time-dependent volatility function
double getVolatility(double t) {
    // Test with constant volatility first to verify multi-step approach
    return 0.2;  // Constant volatility
    // return 0.2 + 0.1 * t;  // Uncomment for time-dependent volatility
}

// Monte Carlo Simulation with dynamic r and sigma using multi-step approach
double monteCarloOptionPricing(double S0, double K, double T, int numSimulations, bool isCallOption) {
    double payoffSum = 0.0;
    int numSteps = 100;  // Number of time steps
    double dt = T / numSteps;  // Time increment

    for (int i = 0; i < numSimulations; ++i) {
        double S = S0;  // Start with initial stock price

        // Simulate price path with time-dependent parameters
        for (int step = 0; step < numSteps; ++step) {
            double t = step * dt;  // Current time
            double r = getRate(t);  // Rate at current time
            double sigma = getVolatility(t);  // Volatility at current time

            // Exact GBM solution for each time step (not Euler approximation)
            S = S * std::exp((r - 0.5 * sigma * sigma) * dt + sigma * std::sqrt(dt) * generateGaussianNoise(0.0, 1.0));
        }

        // Calculate the payoff for this path
        double payoff = isCallOption ? callOptionPayoff(S, K) : putOptionPayoff(S, K);

        // Accumulate the payoff
        payoffSum += payoff;
    }

    // Calculate the average payoff and discount it to present value
    // For discounting, we could integrate the rate over time or use an average
    double averagePayoff = payoffSum / static_cast<double>(numSimulations);
    double avgRate = getRate(T / 2.0);  // Use rate at midpoint for discounting
    return std::exp(-avgRate * T) * averagePayoff;
}

int main() {
    // Option parameters
    double S0 = 100.0;   // Initial stock price
    double K = 100.0;    // Strike price
    double T = 1.0;      // Time to maturity (1 year)
    int numSimulations = 100000; // Number of simulations

    // Calculate option prices with dynamic r and sigma
    double callPrice = monteCarloOptionPricing(S0, K, T, numSimulations, true);
    double putPrice = monteCarloOptionPricing(S0, K, T, numSimulations, false);

    // Output the results
    std::cout << "European Call Option Price: " << callPrice << std::endl;
    std::cout << "European Put Option Price: " << putPrice << std::endl;

    return 0;
}