#include <iostream>
#include <vector>
#include <cmath>
#include <algorithm>

//improvements TODO:
// use pointers to return stuff
// add an option chain
// print the entire tree
// optimized calculateParameters() func for r, sigma

class BinomialOptionPricing {
public:
    BinomialOptionPricing(double S, double K, double r, double T, double sigma, int N, bool isCall, bool isAmerican, double q = 0.0)
        : S(S), K(K), r(r), T(T), sigma(sigma), N(N), isCall(isCall), isAmerican(isAmerican), q(q) {
        calculateParameters();
    }

    double price() {
        std::vector<double> optionValues(N + 1);

        // Calculate option values at maturity (node values of the tree)
        for (int i = 0; i <= N; ++i) {
            double ST = S * std::pow(u, N - i) * std::pow(d, i); //price at time T
            optionValues[i] = optionPayoff(ST);
        }

        // Backward induction to get the option price at t=0
        for (int step = N - 1; step >= 0; --step) {
            for (int i = 0; i <= step; ++i) {
                optionValues[i] = (p * optionValues[i] + (1 - p) * optionValues[i + 1]) * discountFactor;
                
                // For American options, check for early exercise
                if (isAmerican) {
                    double ST = S * std::pow(u, step - i) * std::pow(d, i);
                    optionValues[i] = std::max(optionValues[i], optionPayoff(ST));
                }
            }
        }

        return optionValues[0];
    }

private:
    double S, K, r, T, sigma, q;
    int N;
    bool isCall;
    bool isAmerican;
    double u, d, p, discountFactor;

    void calculateParameters() {
        double dt = T / N;
        u = std::exp((r - q) * dt + sigma * std::sqrt(dt));
        d = std::exp((r - q) * dt - sigma * std::sqrt(dt));
        p = (std::exp((r - q) * dt) - d) / (u - d);
        discountFactor = std::exp(-r * dt);
    }

    double optionPayoff(double ST) const {
        if (isCall) {
            return std::max(0.0, ST - K);
        } else {
            return std::max(0.0, K - ST);
        }
    }
};

int main() {
    double S = 100.0;    // Current stock price
    double K = 100.0;     // Option strike price
    double r = 0.05;     // Risk-free rate
    double T = 1.0;      // Time to maturity (in years)
    double sigma = 0.2;  // Volatility
    int N = 100;         // Number of time steps
    bool isCall = false; // False for Put option
    bool isAmerican = true; // True for American, False for European
    double q = 0.03;     // Dividend yield

    BinomialOptionPricing americanOption(S, K, r, T, sigma, N, isCall, isAmerican, q);
    double americanOptionPrice = americanOption.price();
    
    std::cout << "The American " << (isCall ? "call" : "put") << " option price is: " << americanOptionPrice << std::endl;


    isAmerican = false; // True for American, False for European

    BinomialOptionPricing europeanOption(S, K, r, T, sigma, N, isCall, isAmerican, q);
    double europeanOptionPrice = europeanOption.price();

    std::cout << "The European " << (isCall ? "call" : "put") << " option price is: " << europeanOptionPrice << std::endl;

    return 0;
}