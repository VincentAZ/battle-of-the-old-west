// CPU rehearsal bridge: exposes only each player's authorized ViewJson and
// LegalActionsJson. Every requested mutation must match an offered command.
#include "OldWestRules.h"
#include "json.hpp"
#include <fstream>
#include <iostream>
#include <iterator>
using J = nlohmann::ordered_json;
int main(int argc, char** argv) {
    try {
        if (argc != 3) throw std::runtime_error("Usage: bridge cards.json seed");
        std::ifstream file(argv[1]);
        if (!file) throw std::runtime_error("Missing catalog");
        const std::string catalog((std::istreambuf_iterator<char>(file)), {});
        oldwest::Engine engine(catalog, std::stoull(argv[2]), J{{"ruleset", "boomtown"}}.dump());
        auto publicState = [&]() {
            J result = J::array();
            for (int seat = 0; seat < 2; ++seat)
                result.push_back({{"seat", seat}, {"view", J::parse(engine.ViewJson(seat))},
                                  {"actions", J::parse(engine.LegalActionsJson(seat))}});
            return result;
        };
        std::cout << J{{"public_snapshots", publicState()}}.dump() << std::endl;
        std::string line;
        while (std::getline(std::cin, line)) {
            const J request = J::parse(line);
            const int seat = request.at("seat").get<int>();
            if (seat < 0 || seat > 1) throw std::runtime_error("Invalid seat");
            const J command = request.at("command");
            const J options = J::parse(engine.LegalActionsJson(seat));
            bool offered = false;
            for (const auto& option : options) if (option.at("command") == command) offered = true;
            if (!offered) throw std::runtime_error("Requested command is not publicly offered");
            const J accepted = J::parse(engine.Apply(seat, command.dump()));
            if (!accepted.value("ok", false)) throw std::runtime_error("Offered command rejected");
            std::cout << J{{"accepted", accepted}, {"public_snapshots", publicState()}}.dump() << std::endl;
        }
        return 0;
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n'; return 1;
    }
}
