#pragma once
#include <string_view>

// Reviewed expansion presentation assets. Canonical rules never read this map.
// Add entries only with sourced mesh/base reviews and native import evidence.
namespace OldWestExpansionHoldings
{
struct FEntry
{
    const char* CampId;
    const char* Asset;
    const char* Key;
    float PresentationScale;
    // Optional mesh-space centimetre support points measured from reviewed geometry.
    float DamageFirePoints[2][3] = {};
    // A complete authored ruin may already contain all surviving material.
    bool RuinIncludesDebris = false;
    // Wide setting bases remain visible even when their structure collapses.
    bool PortraitIncludesBase = false;
    // Local centimetres: half-width, half-depth, outer transition distance.
    // Zero transition leaves fitting disabled until its base is reviewed.
    float GroundFitExtent[3] = {};
    // Reviewed rock landforms use fractured meshes without building fire/soot.
    bool GeologicalConditions = false;
};
inline constexpr FEntry Entries[] = {
    {"rustlers_corral", "RustlersCorral", "holding-rustlers-corral", 1.0f, {}, true, true},
    {"quaker_settlement", "QuakerSettlement", "holding-quaker-settlement", 1.0f, {}, true, true},
    {"dance_hall", "DanceHall", "holding-dance-hall", 1.0f, {}, true, true},
    // October 9 completion pass: measured source supports, imported reviewed assets.
    {"apothecary", "Apothecary", "holding-apothecary", 1.0f,
        {{60.0000f, 40.0000f, 308.5680f}, {-60.0000f, -40.0000f, 308.5680f}}, true, true},
    {"boarding_house", "BoardingHouse", "holding-boarding-house", 1.0f,
        {{60.0000f, 40.0000f, 528.6988f}, {-60.0000f, -40.0000f, 515.5282f}}, true, true},
    {"boot_hill", "BootHill", "holding-boot-hill", 1.0f,
        {{60.0000f, 40.0000f, 22.5694f}, {-60.0000f, -40.0000f, 22.5061f}}, true, true},
    {"cattlemen_s_club", "CattlemensClub", "holding-cattlemens-club", 1.0f,
        {{60.0000f, 40.0000f, 480.6822f}, {-60.0000f, -40.0000f, 383.2693f}}, true, true},
    {"coal_yard", "CoalYard", "holding-coal-yard", 1.0f,
        {{60.0000f, 40.0000f, 13.0000f}, {-60.0000f, -40.0000f, 229.8331f}}, true, true},
    {"crimp_house", "CrimpHouse", "holding-crimp-house", 1.0f,
        {{60.0000f, 40.0000f, 437.2461f}, {-60.0000f, -40.0000f, 433.2461f}}, true, true},
    {"horse_trader", "HorseTrader", "holding-horse-trader", 1.0f,
        {{60.0000f, 40.0000f, 328.2599f}, {-60.0000f, -40.0000f, 328.2599f}}, true, true},
    {"nitro_works", "NitroWorks", "holding-nitro-works", 1.0f,
        {{60.0000f, 40.0000f, 271.0058f}, {-60.0000f, -40.0000f, 329.7090f}}, true, true},
    {"packer_s_cabin", "PackersCabin", "holding-packers-cabin", 1.0f,
        {{60.0000f, 40.0000f, 262.0618f}, {-60.0000f, -40.0000f, 262.0618f}}, true, true},
    {"pawn_shop", "PawnShop", "holding-pawn-shop", 1.0f,
        {{60.0000f, 40.0000f, 508.4078f}, {-60.0000f, -40.0000f, 499.6078f}}, true, true},
    {"revival_tent", "RevivalTent", "holding-revival-tent", 1.0f,
        {{60.0000f, 40.0000f, 201.3515f}, {-60.0000f, -40.0000f, 201.3515f}}, true, true},
    {"timber_ram", "TimberRam", "holding-timber-ram", 1.0f,
        {{43.6852f, 13.4201f, 32.0144f}, {-56.1554f, -13.9748f, 24.7207f}}, true, true},
    {"vigilance_committee", "VigilanceCommittee", "holding-vigilance-committee", 1.0f,
        {{60.0000f, 40.0000f, 403.4223f}, {-60.0000f, -40.0000f, 403.4223f}}, true, true},
    {"wagon_fort", "WagonFort", "holding-wagon-fort", 1.0f,
        {{185.0433f, 157.3649f, 22.4504f}, {-181.9060f, -150.5421f, 27.8551f}}, true, true},
    // bounty-office/damage-roof-points.json: measured slate-roof intersections.
    {"bounty_office", "BountyOffice", "holding-bounty-office", 1.0f,
        {{-70.f, -65.f, 260.9473f}, {70.f, 65.f, 260.9473f}}, true, true,
        {225.f, 230.f, 55.f}},
    // smugglers-landing/damage-roof-points.json: timber floor and closed cargo.
    {"smuggler_s_landing", "SmugglersLanding", "holding-smugglers-landing", 1.0f,
        {{150.f, 150.f, 19.625f}, {-170.f, 145.f, 115.875f}}, true, true},
    // robbers-roost/damage-roof-points.json: measured bark-roof intersections.
    {"robbers_roost", "RobbersRoost", "holding-robbers-roost", 1.0f,
        {{-75.f, -60.f, 354.5527f}, {75.f, 75.f, 354.986f}}, true, true,
        {275.f, 240.f, 60.f}},
    // gallows/damage-roof-points.json: exact sloping wooden-roof intersections.
    {"gallows", "Gallows", "holding-gallows", 1.0f,
        {{-65.f, -30.f, 353.7528f}, {65.f, 100.f, 301.7528f}}, true, true,
        {205.f, 260.f, 60.f}},
    // Reviewed sedimentary conditions and documented render-only apron fitting.
    {"lookout_ridge", "LookoutRidge", "holding-lookout-ridge", 1.0f,
        {}, true, true, {305.f, 195.f, 60.f}, true},
    // pony-express-station/damage-roof-points.json: measured wood-shingle intersections.
    {"pony_express_station", "PonyExpressStation", "holding-pony-express-station", 1.0f,
        {{-70.f, -90.f, 250.2625f}, {70.f, 90.f, 250.2625f}}, true, true,
        {200.f, 280.f, 60.f}},
    // chuckwagon/damage-roof-points.json: exact canvas intersections.
    {"chuckwagon", "Chuckwagon", "holding-chuckwagon", 1.0f,
        {{-25.f, 20.f, 204.6174f}, {25.f, 65.f, 203.6786f}}, true, true,
        {100.f, 255.f, 65.f}},
    // free-homestead/damage-roof-points.json: measured shingle-roof intersections.
    {"free_homestead", "FreeHomestead", "holding-free-homestead", 1.0f,
        {{-80.f, -85.f, 332.1483f}, {80.f, 85.f, 332.6142f}}, true, true,
        {240.f, 210.f, 60.f}},
    // courthouse/damage-roof-points.json: exact main-roof intersections.
    {"courthouse", "Courthouse", "holding-courthouse", 1.0f,
        {{-80.f, -130.f, 226.6641f}, {80.f, 130.f, 226.6641f}}, true, true,
        {250.f, 305.f, 60.f}},
    {"rockslide_ridge", "RockslideRidge", "holding-rockslide-ridge", 1.0f,
        {}, true, true, {305.f, 275.f, 50.f}, true},
    {"wanted_poster_board", "WantedPosterBoard", "holding-wanted-poster-board", 2.54f / 4.5f},
    // gunsmith/damage-roof-points.json: exact triangle intersections, not guessed height.
    {"gunsmith", "Gunsmith", "holding-gunsmith", 1.0f,
        {{-95.f, -35.f, 517.9707f}, {95.f, 35.f, 517.9707f}}},
    // jailhouse/damage-roof-points.json: exact slate surface intersections.
    {"jailhouse", "Jailhouse", "holding-jailhouse", 1.0f,
        {{70.f, -35.f, 357.5028f}, {-70.f, 35.f, 357.5027f}}},
    // post-office/damage-roof-points.json: exact wood-shingle intersections.
    {"post_office", "PostOffice", "holding-post-office", 1.0f,
        {{70.f, -35.f, 212.5216f}, {-70.f, 35.f, 212.5575f}}, false, false,
        {225.f, 133.f, 60.f}},
    // army-surgeons-tent/damage-roof-points.json: exact canvas-fly intersections.
    {"army_surgeon_s_tent", "ArmySurgeonsTent", "holding-army-surgeons-tent", 1.0f,
        {{-70.f, -35.f, 220.643f}, {70.f, 35.f, 219.2237f}}, true, true,
        {145.f, 180.f, 60.f}},
};
inline const FEntry* ForCamp(std::string_view Id)
{
    for (const auto& Entry : Entries) if (Id == Entry.CampId) return &Entry;
    return nullptr;
}
}
