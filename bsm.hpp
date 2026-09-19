#pragma once

struct Contract {
    double premium = 0.0;
    int dte = 0;
    double delta = 0.0;
    double gamma = 0.0;
    double theta = 0.0;
    double vega = 0.0;
    double rho = 0.0;
    double volatility = 0.0;
    double intrinsic_value = 0.0;
    bool greeksAvailable = false;
};

Contract blackScholesOptionPricing(double S0, double K, double r, double sigma, double T, bool isCallOption);
