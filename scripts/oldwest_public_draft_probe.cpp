// CPU-only draft discovery for the native action showcase. This utility reads
// only each player's public view and offered legal selection actions. It never
// reads SaveJson, deck order, private entities or restores injected state.
#include "OldWestRules.h"
#include "json.hpp"
#include <fstream>
#include <iostream>
#include <iterator>
#include <set>

using J = nlohmann::ordered_json;
std::string read(const char* path) {
    std::ifstream file(path);
    if (!file) throw std::runtime_error(std::string("Cannot read ") + path);
    return std::string(std::istreambuf_iterator<char>(file), {});
}

int main(int argc, char** argv) {
    try {
        if (argc != 4) throw std::runtime_error("Usage: draft_probe cards.json scenario_manifest.json maximum_seed");
        const std::string catalog = read(argv[1]);
        const J manifest = J::parse(read(argv[2]));
        const std::uint64_t limit = std::stoull(argv[3]);
        J found = J::object();
        for (std::uint64_t seed = 1; seed <= limit; ++seed) {
            oldwest::Engine engine(catalog, seed, J{{"ruleset", manifest.at("ruleset")}}.dump());
            J offers = J::array();
            for (int player = 0; player < 2; ++player) {
                const J view = J::parse(engine.ViewJson(player));
                J ids = J::array();
                for (const auto& card : view["players"][player]["offers"]) ids.push_back(card["id"]);
                offers.push_back(ids);
            }
            for (const auto& scenario : manifest.at("scenarios")) {
                const std::string name = scenario.at("name");
                if (found.contains(name) || scenario.value("preferred_camps", J::array()).empty()) continue;
                for (int player = 0; player < 2; ++player) {
                    std::set<std::string> available;
                    for (const auto& card : offers[player]) available.insert(card.get<std::string>());
                    bool complete = true;
                    for (const auto& wanted : scenario["preferred_camps"])
                        complete &= available.count(wanted.get<std::string>()) != 0;
                    if (!complete) continue;
                    found[name] = {{"seed", seed}, {"target_player", player}, {"public_offers", offers},
                        {"legal_selection_actions", J::parse(engine.LegalActionsJson(player))}};
                    break;
                }
            }
            bool complete = true;
            for (const auto& scenario : manifest.at("scenarios"))
                if (!scenario.value("preferred_camps", J::array()).empty() && !found.contains(scenario.at("name").get<std::string>())) complete = false;
            if (complete) break;
        }
        std::cout << J{{"scope", "CPU-only public draft discovery; not rendered action coverage"},
            {"maximum_seed", limit}, {"ruleset", manifest.at("ruleset")}, {"scenarios", found}}.dump(2) << '\n';
        return 0;
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
