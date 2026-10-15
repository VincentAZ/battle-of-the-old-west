#include "OldWestManualAnimInstance.h"
#include "Animation/AnimSingleNodeInstanceProxy.h"
#include "Animation/AnimInstanceProxy.h"
#include "BoneContainer.h"

namespace
{
class FManualPoseProxy final : public FAnimSingleNodeInstanceProxy
{
    TArray<FTransform> Entry;
    float Alpha = 1.f;
public:
    explicit FManualPoseProxy(UAnimInstance* Instance) : FAnimSingleNodeInstanceProxy(Instance) {}
    virtual void PreUpdate(UAnimInstance* Instance, float DeltaSeconds) override
    {
        FAnimSingleNodeInstanceProxy::PreUpdate(Instance, DeltaSeconds);
        const auto* Manual = CastChecked<UOldWestManualAnimInstance>(Instance);
        // Copy on the game thread before evaluation; workers never read mutable
        // component/instance fields. The manual caller evaluates with dt=0.
        Entry = Manual->EntryLocalPose;
        Alpha = FMath::Clamp(Manual->EntryAlpha, 0.f, 1.f);
    }
    virtual bool Evaluate(FPoseContext& Output) override
    {
        const bool Result = FAnimSingleNodeInstanceProxy::Evaluate(Output);
        if (Alpha < 1.f)
            for (const FCompactPoseBoneIndex Bone : Output.Pose.ForEachBoneIndex())
            {
                const int32 MeshIndex = Output.Pose.GetBoneContainer().MakeMeshPoseIndex(Bone).GetInt();
                if (Entry.IsValidIndex(MeshIndex))
                {
                    FTransform Blended;
                    Blended.Blend(Entry[MeshIndex], Output.Pose[Bone], Alpha);
                    Blended.NormalizeRotation();
                    Output.Pose[Bone] = Blended;
                }
            }
        return Result;
    }
};
}

FAnimInstanceProxy* UOldWestManualAnimInstance::CreateAnimInstanceProxy()
{
    return new FManualPoseProxy(this);
}
