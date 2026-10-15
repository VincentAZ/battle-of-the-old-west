#pragma once
#include <cstdint>
#include <memory>
#include <string>

// Portable authoritative OldWest rules. No Unreal or rendering dependencies.
// Commands and views use UTF-8 JSON. Only ViewJson/LegalActionsJson are safe to
// transmit to players. SaveJson contains all private information and RNG state.
namespace oldwest {
class Engine {
public:
    // options: {"ruleset":"base_2024", "first_player":0|1|-1}.
    // Catalog must contain cards[] and rulesets as documented in game/data.
    explicit Engine(const std::string& catalogJson, std::uint64_t seed,
                    const std::string& optionsJson = "{}");
    ~Engine();
    Engine(Engine&&) noexcept;
    Engine& operator=(Engine&&) noexcept;
    Engine(const Engine&) = delete;
    Engine& operator=(const Engine&) = delete;

    // Returns {ok,error?,revision}. Rejected commands leave authoritative state
    // unchanged, including random state. Revisions increase only on acceptance.
    // Commands are discoverable in LegalActionsJson; clients need not synthesize
    // rules. Choice commands are {type:"choose",option:<opaque option ID>}.
    std::string Apply(int player, const std::string& commandJson);
    // Battlefield punks always have name="Punk", type="person", punk=true,
    // with no top-level card_id. An authorized Wanted Poster Board owner additionally
    // receives private_peek:{card_id,name,type,flip_available,flip_reason,flip_cost?};
    // flip_cost is the effective person cost. That object is inspection data,
    // not a replacement for the punk's displayed identity or battlefield type.
    // Own hand events include play_availability:{cost,event_slot,available,reason},
    // using the same discounted payment and queue checks as LegalActionsJson.
    std::string ViewJson(int player) const;
    // JSON array of {label,command:{...},category,cost?,source?,target?}.
    // An activation may also carry gestures:[{cards:[drag handles],command,
    // placement?|target?|event_slot?,label,cost}]. Each nested command is legal
    // independently: activate_drop activates and accepts the advertised first
    // choice in one revision, with normal follow-up choices left pending.
    // Gesture metadata contains public destinations, never predicted draws.
    std::string LegalActionsJson(int player) const;
    // Catalog annotations and supported rulesets for setup UI.
    std::string CatalogJson() const;
    // Server persistence/testing only. Never expose these strings to clients.
    std::string SaveJson() const;
    // Cosmetic sidecar only: never used by rules, legal actions or AI. Only the
    // viewer-filtered map is safe to transmit; persistence is server-private.
    std::string CosmeticViewJson(int player) const;
    std::string CosmeticSaveJson() const;
    bool RestoreCosmeticJson(const std::string& json);
    bool RestoreJson(const std::string& savedJson, std::string* error = nullptr);
    std::string ValidateJson() const;
    bool Forfeit(int player);
    bool IsFinished() const;
    int Winner() const; // -1 ongoing/draw; ViewJson.status differentiates these.

private:
    struct Impl;
    std::unique_ptr<Impl> impl_;
};
}
