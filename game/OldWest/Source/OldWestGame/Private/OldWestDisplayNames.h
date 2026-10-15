#pragma once
#include "CoreMinimal.h"
#include "OldWestWesternTerms.h"

// Render-layer lookup only. Never write these strings into catalogs, commands,
// AI contexts, saves or replicated snapshots.
namespace OldWestDisplay
{
inline FString Text(FString Value)
{
    // Legacy callers also use Text as a UTF-8 converter for serialized state.
    // Display substitutions must never rewrite its keys, IDs or command data.
    if (Value.StartsWith(TEXT("{")) || Value.StartsWith(TEXT("["))) return Value;
    return FString(UTF8_TO_TCHAR(OldWestWesternTerms::Translate(TCHAR_TO_UTF8(*Value)).c_str()));
}
inline FString Name(const FString& /*Id*/, const FString& Canonical)
{
    return Text(Canonical);
}
// Bare catalog type words never pass the prose-only table rows; label them here.
inline FString TypeLabel(const std::string& Type)
{
    if (Type == "camp") return TEXT("holding");
    if (Type == "person") return TEXT("crew member");
    if (Type == "event") return TEXT("Trouble");
    if (Type == "resource") return TEXT("supply");
    return Text(FString(UTF8_TO_TCHAR(Type.c_str())));
}
}
