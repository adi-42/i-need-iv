#include "gui_common.hpp"

#include <algorithm>
#include <iomanip>

int main(int argc, char* argv[]) {
    try {
        if (argc != 12) {
            throw std::invalid_argument(
                "Usage: ppn_gui.exe capital annual_effective_yield days strike premium entry_index expiry_index lot_size call|put fractional|whole_lots premium_markup");
        }
        const double capital = readDouble(argv[1], 0.01, 1e12);
        const double yield = readDouble(argv[2], 0.0, 0.5);
        const unsigned int days = readInteger(argv[3]);
        const double strike = readDouble(argv[4], 0.01, 1e9);
        const double premium = readDouble(argv[5], 1e-8, 1e9);
        const double entry = readDouble(argv[6], 0.01, 1e9);
        const double expiry = readDouble(argv[7], 0.0, 1e9);
        const unsigned int lotSize = readInteger(argv[8]);
        const std::string option(argv[9]);
        const std::string sizing(argv[10]);
        const double markup = readDouble(argv[11], 0.0, 1.0);
        if (days < 1 || days > 3660 || lotSize < 1 || lotSize > 1000000 ||
            (option != "call" && option != "put") || (sizing != "fractional" && sizing != "whole_lots")) {
            throw std::invalid_argument("Invalid maturity, lot size, option type or sizing mode.");
        }

        const double years = days / 365.0;
        const double growth = std::pow(1.0 + yield, years);
        const double bondCost = capital / growth;
        const double optionBudget = capital - bondCost;
        const double purchasePremium = premium * (1.0 + markup);
        const double lotCost = purchasePremium * lotSize;
        const double affordableLots = optionBudget / lotCost;
        const double lots = sizing == "fractional" ? affordableLots : std::floor(affordableLots);
        const double units = lots * lotSize;
        const double optionSpend = units * purchasePremium;
        double cash = optionBudget - optionSpend;
        if (cash < -1e-12 * capital) {
            throw std::runtime_error("Option spending exceeds the available budget.");
        }
        cash = std::max(cash, 0.0);
        const auto optionPayoff = [&](double index) {
            return units * std::max(option == "call" ? index - strike : strike - index, 0.0);
        };
        const double payoff = optionPayoff(expiry);
        const double finalValue = capital + cash + payoff;
        const double fixedIncome = capital * growth;
        const double notionalRatio = units * entry / capital;
        const double budgetFraction = optionBudget / capital;
        const double minimumCapital = budgetFraction > 0.0 ? lotCost / budgetFraction : 0.0;

        std::vector<double> indexValues{entry, expiry, strike}, finalValues;
        const double low = std::min(0.7 * entry, 0.9 * expiry);
        const double high = std::max(1.3 * entry, 1.1 * expiry);
        for (int i = 0; i <= 80; ++i) {
            indexValues.push_back(low + (high - low) * i / 80.0);
        }
        std::sort(indexValues.begin(), indexValues.end());
        indexValues.erase(std::unique(indexValues.begin(), indexValues.end()), indexValues.end());
        for (const double index : indexValues) {
            const double value = capital + cash + optionPayoff(index);
            if (!std::isfinite(value)) {
                throw std::overflow_error("PPN scenario exceeds the supported numerical range.");
            }
            finalValues.push_back(value);
        }
        for (const double value : {bondCost, optionBudget, lots, units, cash, payoff, finalValue,
                                   fixedIncome, notionalRatio, minimumCapital}) {
            if (!std::isfinite(value)) {
                throw std::overflow_error("PPN cashflows exceed the supported numerical range.");
            }
        }

        std::cout << std::setprecision(17)
                  << "{\"inputs\":{\"capital\":" << capital << ",\"bond_yield\":" << yield
                  << ",\"days\":" << days << ",\"strike\":" << strike << ",\"premium\":" << premium
                  << ",\"entry_index\":" << entry << ",\"expiry_index\":" << expiry
                  << ",\"lot_size\":" << lotSize << ",\"option\":\"" << option
                  << "\",\"sizing\":\"" << sizing << "\",\"premium_markup\":" << markup << "},"
                  << "\"bond_cost\":" << bondCost << ",\"option_budget\":" << optionBudget
                  << ",\"purchase_premium\":" << purchasePremium << ",\"lots\":" << lots
                  << ",\"units\":" << units << ",\"option_spend\":" << optionSpend
                  << ",\"idle_cash\":" << cash << ",\"option_payoff\":" << payoff
                  << ",\"option_pnl\":" << payoff - optionSpend << ",\"final_value\":" << finalValue
                  << ",\"portfolio_return\":" << (finalValue - capital) / capital
                  << ",\"fixed_income_value\":" << fixedIncome
                  << ",\"excess_over_fixed_income\":" << finalValue - fixedIncome
                  << ",\"underlying_return\":" << expiry / entry - 1.0
                  << ",\"notional_ratio\":" << notionalRatio << ",\"minimum_capital_one_lot\":";
        if (budgetFraction > 0.0) {
            std::cout << minimumCapital;
        } else {
            std::cout << "null";
        }
        std::cout << ",\"curve\":{\"index\":";
        writeArray(indexValues);
        std::cout << ",\"final_value\":";
        writeArray(finalValues);
        std::cout << "}}\n";
    } catch (const std::exception& error) {
        std::cerr << "PPN calculation failed: " << error.what() << '\n';
        return 1;
    }
}
