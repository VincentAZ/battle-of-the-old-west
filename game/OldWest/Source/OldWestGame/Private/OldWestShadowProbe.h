#pragma once
#include "CoreMinimal.h"
class UWorld;
#if !UE_BUILD_SHIPPING
// Local visual diagnosis only. No map/asset saves or game-state changes.
FString RunOldWestShadowProbe(UWorld* World, const FString& Category);
#endif
