#pragma once
#include "CoreMinimal.h"
#include "Core/json.hpp"

namespace OldWestReadiness {
// Read only public card state. Readiness is independent of water, targets,
// ownership of the current turn, and other activation prerequisites.
inline FString State(const nlohmann::ordered_json& Card)
{
    if(Card.value("zone",std::string())!="board"||Card.value("destroyed",false))return TEXT("none");
    if(Card.value("ready",false))return TEXT("ready");
    if(Card.value("type",std::string())!="camp"&&Card.value("damage",0)>0)return TEXT("damaged");
    if(Card.value("uses",0)>0)return TEXT("spent");
    return TEXT("recovering");
}
inline FString Label(const nlohmann::ordered_json& Card)
{
    const FString S=State(Card);
    if(S==TEXT("ready"))return TEXT("Ready");
    if(S==TEXT("spent"))return TEXT("Spent");
    if(S==TEXT("recovering"))return TEXT("Recovering");
    if(S==TEXT("damaged"))return TEXT("Not ready");
    return FString();
}
}
