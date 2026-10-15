#pragma once

#include "CoreMinimal.h"

class SWidget;
class UWorld;

// The containing HUD chooses the size. Identical, visible cards share a 384px
// render target; scenes are created lazily and retire after leaving the screen.
// A concealed punk intentionally discards CardId before lookup or scene creation.
TSharedRef<SWidget> MakeOldWestCardPortrait(UWorld* World, const FString& CardId,
    const FString& CardType, bool HiddenPunk = false);

// Nonshipping visual-test evidence: live scene IDs, captures, animated parts,
// compiler queues and later-frame captures after a zero-queue observation.
FString GetOldWestCardPortraitDebug(UWorld* World);

#if !UE_BUILD_SHIPPING
// Test-only visual condition changes on an already-visible camp preview.
// This does not create a scene, access a gameplay entity, or change game state.
bool SetOldWestCardPortraitCondition(UWorld* World, const FString& CardId, int32 Damage, bool Destroyed);
// Close facial/expression review on an existing public portrait scene.
bool SetOldWestCardPortraitDetail(UWorld* World, const FString& CardId, bool Enabled, const FString& Expression);
#endif
