#pragma once

#include <charconv>
#include <cmath>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

inline double readDouble(const char* text, double minimum, double maximum) {
    std::size_t end = 0;
    const std::string input(text);
    const double value = std::stod(input, &end);
    if (end != input.size() || !std::isfinite(value) || value < minimum || value > maximum) {
        throw std::invalid_argument("Numeric input is invalid or outside the GUI's supported range.");
    }
    return value;
}

inline unsigned int readInteger(const char* text) {
    const std::string input(text);
    unsigned int value = 0;
    const auto result = std::from_chars(input.data(), input.data() + input.size(), value);
    if (result.ec != std::errc{} || result.ptr != input.data() + input.size()) {
        throw std::invalid_argument("Counts and seed must be unsigned integers.");
    }
    return value;
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
