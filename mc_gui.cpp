#include <algorithm>
#include <charconv>
#include <chrono>
#include <cmath>
#include <iomanip>
#include <iostream>
#include <random>
#include <stdexcept>
#include <string>
#include <vector>

double readDouble(const char* text, double minimum, double maximum) {
    std::size_t end = 0;
    const std::string input(text);
    const double value = std::stod(input, &end);
    if (end != input.size() || !std::isfinite(value) || value < minimum || value > maximum) {
        throw std::invalid_argument("Numeric input is invalid or outside the GUI's supported range.");
    }
    return value;
}

unsigned int readInteger(const char* text) {
    const std::string input(text);
    unsigned int value = 0;
    const auto result = std::from_chars(input.data(), input.data() + input.size(), value);
    if (result.ec != std::errc{} || result.ptr != input.data() + input.size()) {
        throw std::invalid_argument("Simulation count and seed must be unsigned integers.");
    }
    return value;
}

struct Statistics {
    unsigned int count = 0;
    double mean = 0.0;
    double m2 = 0.0;

    void add(double value) {
        ++count;
        const double delta = value - mean;
        mean += delta / count;
        m2 += delta * (value - mean);
    }

    double standardError() const {
        return std::sqrt(m2 / (count - 1) / count);
    }
};

double blackScholes(double spot, double strike, double maturity, double rate, double sigma, bool call) {
    const double discountedStrike = strike * std::exp(-rate * maturity);
    if (maturity == 0.0 || sigma == 0.0) {
        return std::max(call ? spot - discountedStrike : discountedStrike - spot, 0.0);
    }
    if (strike == 0.0) {
        return call ? spot : 0.0;
    }
    const double scale = sigma * std::sqrt(maturity);
    const double d1 = (std::log(spot / strike) + (rate + 0.5 * sigma * sigma) * maturity) / scale;
    const double d2 = d1 - scale;
    const auto cdf = [](double x) { return 0.5 * std::erfc(-x / std::sqrt(2.0)); };
    return call ? spot * cdf(d1) - discountedStrike * cdf(d2) :
        discountedStrike * cdf(-d2) - spot * cdf(-d1);
}

template <typename Value>
void writeArray(const std::vector<Value>& values) {
    std::cout << '[';
    for (std::size_t i = 0; i < values.size(); ++i) {
        if (i != 0) {
            std::cout << ',';
        }
        std::cout << values[i];
    }
    std::cout << ']';
}

void writeHistogram(const std::vector<double>& values) {
    const auto [low, high] = std::minmax_element(values.begin(), values.end());
    const double span = *high - *low;
    const int bins = span == 0.0 ? 1 : 40;
    const double width = span == 0.0 ? std::max(0.01, std::abs(*low) * 0.01) : span / bins;
    std::vector<double> centers;
    std::vector<unsigned int> counts(bins, 0);
    for (int i = 0; i < bins; ++i) {
        centers.push_back(span == 0.0 ? *low : *low + (i + 0.5) * width);
    }
    for (const double value : values) {
        const int bin = span == 0.0 ? 0 : std::min(bins - 1, static_cast<int>((value - *low) / width));
        ++counts[bin];
    }
    std::cout << "{\"centers\":";
    writeArray(centers);
    std::cout << ",\"counts\":";
    writeArray(counts);
    std::cout << ",\"width\":" << width << '}';
}

int main(int argc, char* argv[]) {
    try {
        if (argc != 9) {
            throw std::invalid_argument("Usage: mc_gui.exe spot strike years rate volatility simulations seed call|put");
        }
        const double spot = readDouble(argv[1], 0.01, 1e9);
        const double strike = readDouble(argv[2], 0.0, 1e9);
        const double maturity = readDouble(argv[3], 0.0, 30.0);
        const double rate = readDouble(argv[4], -0.5, 0.5);
        const double sigma = readDouble(argv[5], 0.0, 3.0);
        const unsigned int simulations = readInteger(argv[6]);
        const unsigned int seed = readInteger(argv[7]);
        const std::string option(argv[8]);
        if (simulations < 2 || simulations > 1000000 || (option != "call" && option != "put")) {
            throw std::invalid_argument("Use 2 to 1000000 simulations and option type call or put.");
        }
        const bool call = option == "call";
        const double benchmark = blackScholes(spot, strike, maturity, rate, sigma, call);
        const double drift = (rate - 0.5 * sigma * sigma) * maturity;
        const double diffusion = sigma * std::sqrt(maturity);
        const double discount = std::exp(-rate * maturity);
        std::mt19937 generator(seed);
        std::normal_distribution<double> normal;
        Statistics statistics;
        std::vector<double> terminalPrices, payoffs, estimates, errors;
        std::vector<unsigned int> checkpoints;
        terminalPrices.reserve(simulations);
        payoffs.reserve(simulations);
        unsigned int nonzero = 0;
        unsigned int nextCheckpoint = 2;
        const auto start = std::chrono::steady_clock::now();

        // Same direct terminal GBM calculation as the saved simple pricer.
        for (unsigned int n = 1; n <= simulations; ++n) {
            const double shock = diffusion == 0.0 ? 0.0 : normal(generator);
            const double terminal = spot * std::exp(drift + diffusion * shock);
            const double payoff = discount * std::max(call ? terminal - strike : strike - terminal, 0.0);
            if (!std::isfinite(terminal) || !std::isfinite(payoff)) {
                throw std::overflow_error("Simulation exceeded the supported numerical range.");
            }
            terminalPrices.push_back(terminal);
            payoffs.push_back(payoff);
            nonzero += payoff > 0.0;
            statistics.add(payoff);
            if (n == nextCheckpoint || n == simulations) {
                checkpoints.push_back(n);
                estimates.push_back(statistics.mean);
                errors.push_back(statistics.standardError());
                nextCheckpoint = std::max(n + 1, static_cast<unsigned int>(std::ceil(n * 1.08)));
            }
        }
        const double elapsed = std::chrono::duration<double, std::milli>(
            std::chrono::steady_clock::now() - start).count();
        if (!std::isfinite(statistics.mean) || !std::isfinite(statistics.standardError()) ||
            !std::isfinite(benchmark)) {
            throw std::overflow_error("Pricing statistics exceeded the supported numerical range.");
        }

        std::cout << std::setprecision(17);
        std::cout << "{\"inputs\":{\"spot\":" << spot << ",\"strike\":" << strike
                  << ",\"maturity\":" << maturity << ",\"rate\":" << rate
                  << ",\"volatility\":" << sigma << ",\"simulations\":" << simulations
                  << ",\"seed\":" << seed << ",\"option\":\"" << option << "\"},"
                  << "\"price\":" << statistics.mean << ",\"standard_error\":" << statistics.standardError()
                  << ",\"black_scholes\":" << benchmark << ",\"simulation_ms\":" << elapsed
                  << ",\"nonzero_payoffs\":" << nonzero << ",\"convergence\":{\"n\":";
        writeArray(checkpoints);
        std::cout << ",\"price\":";
        writeArray(estimates);
        std::cout << ",\"standard_error\":";
        writeArray(errors);
        std::cout << "},\"terminal_histogram\":";
        writeHistogram(terminalPrices);
        std::cout << ",\"payoff_histogram\":";
        writeHistogram(payoffs);
        std::cout << "}\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "Pricing failed: " << error.what() << '\n';
        return 1;
    }
}
