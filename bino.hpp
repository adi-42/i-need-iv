#pragma once

struct BinomialParameters {
    double dt;
    double up;
    double down;
    double upProbability;
};

class BinomialOptionPricing {
public:
    BinomialOptionPricing(double S, double K, double r, double T, double sigma,
                          int N, bool isCall, bool isAmerican, double q = 0.0);
    double price() const;
    BinomialParameters parameters() const;

private:
    double S, K, r, T, sigma, q;
    int N;
    bool isCall;
    bool isAmerican;
    double dt, jump, u, d, p, discountFactor;

    void calculateParameters();
    double stockAt(int step, int downMoves) const;
    double optionPayoff(double stock) const;
};
