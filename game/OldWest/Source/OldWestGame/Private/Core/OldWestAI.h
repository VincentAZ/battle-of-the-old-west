#pragma once
#include <cstdint>
#include <memory>
#include <string>

namespace oldwest {
enum class AIDifficulty { Easy, Normal, Hard };

// A fair opponent: inputs are the same catalog, private player view, and legal
// action list available to a human client. Never pass an authoritative save.
// Difficulty changes decisions only; it does not change the game rules.
class AIPlayer {
public:
    AIPlayer(const std::string& catalogJson, AIDifficulty difficulty, std::uint64_t seed);
    ~AIPlayer();
    AIPlayer(AIPlayer&&) noexcept;
    AIPlayer& operator=(AIPlayer&&) noexcept;
    AIPlayer(const AIPlayer&) = delete;
    AIPlayer& operator=(const AIPlayer&) = delete;

    // Returns an unchanged command from legalActionsJson, or empty when there
    // are no actions / malformed inputs. Repeated queries for the same view and
    // action list return the same decision, without consuming more randomness.
    // Call again after each accepted command, including pending choices.
    std::string Choose(const std::string& viewJson, const std::string& legalActionsJson);
    void Reset(std::uint64_t seed);
private:
    struct Impl;
    std::unique_ptr<Impl> impl_;
};
}
