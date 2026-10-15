#pragma once
#include <string_view>

// Cosmetic lookup only: canonical event identity, costs and timing stay in Core.
namespace OldWestTrouble
{
struct FEntry { const char* CardId; const char* Key; const char* Mesh; const char* Folder="Landscapes"; float CaptionHeight=190; };
inline constexpr FEntry Entries[] = {
    {"hard_winter", "trouble-hard-winter", "SM_Trouble_HardWinter"},
    {"box_canyon", "trouble-box-canyon", "SM_Trouble_BoxCanyon"},
    {"prairie_fire", "trouble-prairie-fire", "SM_Trouble_PrairieFire"},
    {"cholera", "trouble-cholera", "SM_Trouble_Quarantine", "Objects", 235},
    {"poker_night", "trouble-poker-night", "SM_Trouble_PokerNight", "Objects", 80},
    {"cannonade", "trouble-cannonade", "SM_Trouble_Cannonade", "Schemes", 160},
    {"ambush", "trouble-ambush", "SM_Trouble_Ambush", "Schemes", 125},
    {"gold_rush", "trouble-gold-rush", "SM_Trouble_GoldRush", "Schemes", 100},
    {"run_out_of_town", "trouble-run-out-of-town", "SM_Trouble_DynamiteCrate", "Schemes", 120},
    {"curfew", "trouble-curfew", "SM_Trouble_Curfew", "Schemes", 320},
};
inline const FEntry* ForCard(std::string_view Id)
{
    for (const auto& Entry : Entries) if (Id == Entry.CardId) return &Entry;
    return nullptr;
}
}
