#include "bino.hpp"
#include "bsm.hpp"
#include "gui_common.hpp"

#include <algorithm>
#include <iomanip>
#include <set>
#include <utility>

namespace {
struct GreekCurve {
    std::string axis = "spot";
    std::vector<double> values;
    std::vector<Contract> contracts;
};

void writeGreekCurve(const GreekCurve& curve) {
    std::cout << "{\"axis\":\"" << curve.axis << "\",\"values\":";
    writeArray(curve.values);
    for (const auto& [name, member] : {
             std::pair{"delta", &Contract::delta}, {"gamma", &Contract::gamma},
             {"theta", &Contract::theta}, {"vega", &Contract::vega}, {"rho", &Contract::rho}}) {
        std::cout << ",\"" << name << "\":[";
        for (std::size_t i = 0; i < curve.contracts.size(); ++i) {
            if (i != 0) {
                std::cout << ',';
            }
            if (curve.contracts[i].greeksAvailable) {
                std::cout << curve.contracts[i].*member;
            } else {
                std::cout << "null";
            }
        }
        std::cout << ']';
    }
    std::cout << '}';
}
}

int main(int argc, char* argv[]) {
    try {
        if (argc != 8 && argc != 10 && argc != 11) {
            throw std::invalid_argument(
                "Usage: pricing_gui.exe bsm|binomial spot strike years rate volatility call|put "
                "[BSM: axis minimum maximum | binomial: steps european|american]");
        }
        const std::string method(argv[1]);
        if ((method != "bsm" && method != "binomial") ||
            (method == "bsm" && argc != 8 && argc != 11) || (method == "binomial" && argc != 10)) {
            throw std::invalid_argument("BSM optionally takes axis/minimum/maximum; binomial requires steps and exercise style.");
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
        GreekCurve greekCurve;

        if (method == "bsm") {
            if (argc == 11) {
                greekCurve.axis = argv[8];
            }
            double selected = 0.0, minimum = 0.0, maximum = 0.0;
            if (greekCurve.axis == "spot") {
                selected = spot;
                minimum = 0.01;
                maximum = 1e9;
            } else if (greekCurve.axis == "strike") {
                selected = strike;
                maximum = 1e9;
            } else if (greekCurve.axis == "maturity") {
                selected = maturity;
                maximum = 30.0;
            } else if (greekCurve.axis == "rate") {
                selected = rate;
                minimum = -0.5;
                maximum = 0.5;
            } else if (greekCurve.axis == "volatility") {
                selected = sigma;
                maximum = 3.0;
            } else {
                throw std::invalid_argument("Greek axis must be spot, strike, maturity, rate or volatility.");
            }
            const double low = argc == 11 ? readDouble(argv[9], minimum, maximum) : std::max(0.01, spot * 0.5);
            const double high = argc == 11 ? readDouble(argv[10], minimum, maximum) : std::min(1e9, spot * 1.5);
            if (low >= high || selected < low || selected > high) {
                throw std::invalid_argument("Greek sweep must have increasing bounds containing the selected input.");
            }
            std::set<double> grid{low, high, selected};
            if (greekCurve.axis == "spot" && strike >= low && strike <= high) {
                grid.insert(strike);
            }
            for (int i = 1; i < 120; ++i) {
                grid.insert(low + (high - low) * i / 120.0);
            }
            for (const double value : grid) {
                greekCurve.values.push_back(value);
                greekCurve.contracts.push_back(blackScholesOptionPricing(
                    greekCurve.axis == "spot" ? value : spot,
                    greekCurve.axis == "strike" ? value : strike,
                    greekCurve.axis == "rate" ? value : rate,
                    greekCurve.axis == "volatility" ? value : sigma,
                    greekCurve.axis == "maturity" ? value : maturity, call));
            }
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
            std::cout << "},\"greek_curve\":";
            writeGreekCurve(greekCurve);
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
