#include "bino.hpp"
#include "bsm.hpp"
#include "gui_common.hpp"

#include <algorithm>
#include <iomanip>
#include <set>

int main(int argc, char* argv[]) {
    try {
        if (argc != 8 && argc != 10) {
            throw std::invalid_argument(
                "Usage: pricing_gui.exe bsm|binomial spot strike years rate volatility call|put [steps european|american]");
        }
        const std::string method(argv[1]);
        if ((method != "bsm" && method != "binomial") ||
            (method == "bsm" && argc != 8) || (method == "binomial" && argc != 10)) {
            throw std::invalid_argument("BSM takes no tree arguments; binomial requires steps and exercise style.");
        }
        const double spot = readDouble(argv[2], 0.01, 1e9);
        const double strike = readDouble(argv[3], 0.0, 1e9);
        const double maturity = readDouble(argv[4], 0.0, 30.0);
        const double rate = readDouble(argv[5], -0.5, 0.5);
        const double sigma = readDouble(argv[6], 0.0, 3.0);
        const std::string option(argv[7]);
        if (option != "call" && option != "put") {
            throw std::invalid_argument("Option type must be call or put.");
        }
        const bool call = option == "call";
        const Contract contract = blackScholesOptionPricing(spot, strike, rate, sigma, maturity, call);
        int steps = 0;
        std::string exercise = "european";
        std::vector<double> spots, spotPrices, vols, volPrices, europeanPrices, americanPrices;
        std::vector<int> checkpoints;
        BinomialParameters parameters{};

        if (method == "bsm") {
            for (int i = 0; i <= 60; ++i) {
                const double value = spot * (0.5 + i / 60.0);
                spots.push_back(value);
                spotPrices.push_back(blackScholesOptionPricing(value, strike, rate, sigma, maturity, call).premium);
            }
            const double maxVol = std::min(3.0, std::max(0.6, 1.5 * sigma));
            for (int i = 0; i <= 40; ++i) {
                const double value = maxVol * i / 40.0;
                vols.push_back(value);
                volPrices.push_back(blackScholesOptionPricing(spot, strike, rate, value, maturity, call).premium);
            }
        } else {
            const unsigned int count = readInteger(argv[8]);
            exercise = argv[9];
            if (count < 1 || count > 1000 || (exercise != "european" && exercise != "american")) {
                throw std::invalid_argument("Use 1 to 1000 tree steps and exercise style european or american.");
            }
            steps = static_cast<int>(count);
            std::set<int> grid{1, 2, 3, 5, 10, 20, 25, 50, 75, 100, 125, 250, 500, 750, 1000, steps};
            if (steps > 1) {
                grid.insert(steps - 1);
            }
            for (const int n : grid) {
                if (n > steps) {
                    break;
                }
                const BinomialOptionPricing european(spot, strike, rate, maturity, sigma, n, call, false);
                const BinomialOptionPricing american(spot, strike, rate, maturity, sigma, n, call, true);
                checkpoints.push_back(n);
                europeanPrices.push_back(european.price());
                americanPrices.push_back(american.price());
                parameters = european.parameters();
            }
        }

        // Complete all calculations before writing JSON so failures never leave partial success output.
        std::cout << std::setprecision(17);
        std::cout << "{\"inputs\":{\"spot\":" << spot << ",\"strike\":" << strike
                  << ",\"maturity\":" << maturity << ",\"rate\":" << rate
                  << ",\"volatility\":" << sigma << ",\"option\":\"" << option
                  << "\",\"dividend_yield\":0,\"exercise\":\"" << exercise << "\"";
        if (method == "binomial") {
            std::cout << ",\"steps\":" << steps;
        }
        std::cout << "},\"method\":\"" << method << "\",\"black_scholes\":" << contract.premium;
        if (method == "bsm") {
            const double discountedStrike = strike * std::exp(-rate * maturity);
            std::cout << ",\"price\":" << contract.premium << ",\"intrinsic_value\":" << contract.intrinsic_value
                      << ",\"lower_bound\":" << std::max(call ? spot - discountedStrike : discountedStrike - spot, 0.0)
                      << ",\"greeks\":";
            if (contract.greeksAvailable) {
                std::cout << "{\"delta\":" << contract.delta << ",\"gamma\":" << contract.gamma
                          << ",\"theta\":" << contract.theta << ",\"vega\":" << contract.vega
                          << ",\"rho\":" << contract.rho << '}';
            } else {
                std::cout << "null";
            }
            std::cout << ",\"spot_curve\":{\"spot\":";
            writeArray(spots);
            std::cout << ",\"price\":";
            writeArray(spotPrices);
            std::cout << "},\"volatility_curve\":{\"volatility\":";
            writeArray(vols);
            std::cout << ",\"price\":";
            writeArray(volPrices);
            std::cout << '}';
        } else {
            const double european = europeanPrices.back();
            const double american = americanPrices.back();
            std::cout << ",\"price\":" << (exercise == "american" ? american : european)
                      << ",\"european_price\":" << european << ",\"american_price\":" << american
                      << ",\"early_exercise_premium\":" << american - european
                      << ",\"european_error\":" << european - contract.premium
                      << ",\"tree_parameters\":{\"dt\":" << parameters.dt
                      << ",\"up\":" << parameters.up << ",\"down\":" << parameters.down
                      << ",\"up_probability\":" << parameters.upProbability << "},\"convergence\":{\"steps\":";
            writeArray(checkpoints);
            std::cout << ",\"european\":";
            writeArray(europeanPrices);
            std::cout << ",\"american\":";
            writeArray(americanPrices);
            std::cout << '}';
        }
        std::cout << "}\n";
    } catch (const std::exception& error) {
        std::cerr << "Pricing failed: " << error.what() << '\n';
        return 1;
    }
}
