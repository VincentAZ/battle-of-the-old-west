#pragma once
#include "json.hpp"

namespace oldwest {
// Negative presentation IDs encode the selected water bundle, never entities.
inline bool IsWaterBundle(int card) { return card <= -4001 && card >= -4999; }
inline int WaterBundleCount(int card) { return IsWaterBundle(card) ? -4000-card : 0; }
// The same authoritative actions are offered by the context menu and by drag.
// This is a presentation filter; execution still checks revision and legality.
inline bool FieldActionMatches(const nlohmann::ordered_json& action, int card) {
    const auto& command=action["command"];
    const std::string type=command.value("type",std::string());
    if(card==-4000)return action.value("cost",0)>0;
    if(IsWaterBundle(card))return action.value("cost",0)==WaterBundleCount(card) &&
        action.value("cost",0)>0;
    if(card==-3000)return type=="draw";
    if(card==-3001)return type=="end_turn";
    if(card==-3002)return action.value("category",std::string())=="choice" || action.value("cost",0)>0 || type=="silo" ||
        (type=="junk"&&action.value("label",std::string()).find("Hip Flask")!=std::string::npos);
    if(card==-3004)return type=="junk";
    if(card<=0)return true;
    for(const auto& gesture:action.value("gestures",nlohmann::ordered_json::array()))
        for(const auto& alias:gesture["cards"])if(alias==card)return true;
    if(action.value("category",std::string())=="choice")
        return action.value("choice_source",0)==card||!action.contains("target")||action.value("target",0)==card;
    return command.value("source",command.value("card",0))==card;
}
}
