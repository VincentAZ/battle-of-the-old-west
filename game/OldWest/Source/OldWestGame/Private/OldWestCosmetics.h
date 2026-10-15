#pragma once
#include "Core/json.hpp"
#include "OldWestCrewCatalog.h"
#include <map>
#include <string>
#include <set>

// Local presentation copy. Canonical snapshots, action commands, catalog entries,
// saves and AI inputs never pass through this adapter.
namespace OldWestCosmetics {
using J=nlohmann::ordered_json;
inline std::string Visual(const J& card) {
    if(card.value("punk",false))return "punk";
    // Selection offers and catalog previews carry a string definition `id`;
    // live cards carry `card_id` plus a numeric instance `id`.
    const auto id=card.find("id");
    const auto canonical=card.value("card_id",
        id!=card.end() && id->is_string()?id->get<std::string>():std::string());
    const auto visual=card.value("visual_id",canonical);
    if(const auto* entry=OldWestCrew::Resolve(canonical,visual))return entry->Visual;
    // Catalog previews have no physical copy: use the first appearance only.
    if(const auto* entry=OldWestCrew::ForCopy(canonical))return entry->Visual;
    return canonical;
}
inline const char* Name(const std::string& visual) {
    if(const auto* entry=OldWestCrew::ForVisual(visual))return entry->Name;
    return nullptr;
}
inline J Present(J payload) {
    if(!payload.contains("view"))return payload;
    const J tags=payload.value("cosmetics",J::object());
    std::map<int,std::pair<std::string,std::string>> names;
    auto card=[&](J& c) {
        if(!c.is_object()||!c.contains("id")||!c["id"].is_number_integer())return;
        c.erase("visual_id");
        if(c.value("punk",false)||!c.contains("card_id"))return;
        const int id=c["id"];const auto key=std::to_string(id);
        if(tags.is_object()&&tags.contains(key)&&tags[key].is_string())c["visual_id"]=tags[key];
        const auto visual=Visual(c);
        c["visual_id"]=visual;
        const auto canonicalName=c.value("name",std::string());
        const char* display=Name(visual);
        names[id]={canonicalName,display?display:canonicalName};
        if(display)c["name"]=display;
    };
    for(auto& p:payload["view"]["players"]) {
        if(p.contains("hand"))for(auto& c:p["hand"])card(c);
        for(auto& col:p["columns"])for(auto& c:col)card(c);
        for(auto& c:p["queue"])card(c);
    }
    for(auto& p:payload["view"]["players"])for(auto& col:p["columns"])for(auto& c:col)
        if(c.contains("protected_by"))for(auto& guard:c["protected_by"]) {
            const auto n=names.find(guard.value("id",0));if(n!=names.end())guard["name"]=n->second.second;
        }
    auto label=[&](J& action) {
        if(!action.contains("label")||!action["label"].is_string())return;
        auto text=action["label"].get<std::string>();const auto cmd=action.value("command",J::object());
        std::size_t cursor=0;std::set<int> used;
        // Target-only gestures (e.g. "Damage Pinkerton Agent") can have a named
        // source of the same canonical type. Consume the target's occurrence
        // first even when that target keeps its original name.
        for(const char* key:{"card","target","source","choice_source","replace"}) {
            const int id=cmd.value(key,action.value(key,0));
            if(!used.insert(id).second)continue;
            const auto n=names.find(id);if(n==names.end()||n->second.first.empty())continue;
            const auto at=text.find(n->second.first,cursor);if(at==std::string::npos)continue;
            text.replace(at,n->second.first.size(),n->second.second);cursor=at+n->second.second.size();
        }
        action["label"]=text;
    };
    if(payload.contains("actions"))for(auto& action:payload["actions"]) {
        label(action);if(action.contains("gestures"))for(auto& gesture:action["gestures"])label(gesture);
    }
    // Choice targets and their sources are already public affordances in the
    // legal action list. Resolve each option by its opaque ID, never by a
    // global name substitution that could rename the other physical copy.
    auto& choice=payload["view"]["choice"];
    if(choice.is_object() && payload.contains("actions")) {
        for(const auto& action:payload["actions"]) {
            if(choice.contains("options"))for(auto& option:choice["options"])
                if(action.value("command",J::object()).value("option",std::string())==option.value("id",std::string()))
                    option["label"]=action["label"];
            const auto found=names.find(action.value("choice_source",0));
            if(found!=names.end() && found->second.first!=found->second.second && choice.contains("prompt")) {
                auto prompt=choice["prompt"].get<std::string>();
                const auto at=prompt.find(found->second.first);
                if(at!=std::string::npos)prompt.replace(at,found->second.first.size(),found->second.second);
                choice["prompt"]=prompt;
            }
        }
    }
    return payload;
}
}
