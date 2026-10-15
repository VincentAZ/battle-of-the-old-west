#pragma once

#include "CoreMinimal.h"

class APlayerController;

namespace OldWestWorldInteraction
{
// Viewport pixels, not the HUD's scaled logical coordinates. Returns only a
// local rendered entity handle; the inspector independently checks visibility
// against the current authorized snapshot before displaying card details.
int32 PickVisibleUnitAtScreen(APlayerController* Player, const FVector2D& Position);
}
