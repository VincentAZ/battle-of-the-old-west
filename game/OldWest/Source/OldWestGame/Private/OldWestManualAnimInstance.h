#pragma once
#include "CoreMinimal.h"
#include "Animation/AnimSingleNodeInstance.h"
#include "OldWestManualAnimInstance.generated.h"

// A single-node player with one optional captured-pose entry blend. The
// component's manual clock sets sequence time; this instance never advances it.
UCLASS(Transient, NotBlueprintable)
class UOldWestManualAnimInstance : public UAnimSingleNodeInstance
{
    GENERATED_BODY()
public:
    TArray<FTransform> EntryLocalPose;
    float EntryAlpha = 1.f;
protected:
    virtual FAnimInstanceProxy* CreateAnimInstanceProxy() override;
};
