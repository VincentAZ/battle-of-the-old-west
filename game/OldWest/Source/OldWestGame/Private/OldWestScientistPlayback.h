#pragma once
#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "OldWestScientistPlayback.generated.h"

class AOldWestUnit;
class UStaticMeshComponent;
class UAnimSequence;
struct FOldWestScientistPlaybackState;
struct FOldWestScientistStateDeleter
{
    void operator()(FOldWestScientistPlaybackState* State) const;
};

// These values come exclusively from matched public reveal_discard metadata.
struct FOldWestAnalysisSample
{
    int32 Index = -1;
    int32 Handle = 0;
    FString Name;
    FString Effect;
};

UCLASS()
class UOldWestScientistPlayback : public UActorComponent
{
    GENERATED_BODY()
public:
    UOldWestScientistPlayback();
    virtual ~UOldWestScientistPlayback() override;
    bool Begin(AOldWestUnit* Unit, const FString& MatchId, int32 AbilitySequence,
        const TArray<FOldWestAnalysisSample>& PublicSamples);
    // Index=-1 and Handle=0 is an explicitly accepted public Skip. This is
    // never called because a private menu closed or an effect later appeared.
    bool SetDecision(const FString& MatchId, int32 AbilitySequence, int32 Index, int32 Handle);
    bool FinishWithoutDecision(const FString& MatchId, int32 AbilitySequence, const FString& Reason);
    // Director calls exactly once in PostUpdateWork, including nonbusy choice
    // waits. Component tick stays disabled, so no second animation clock exists.
    bool Advance(float DeltaSeconds);
    bool IsAwaitingChoice() const;
    bool IsComplete() const;
    bool IsActive() const;
    FString GetPhaseName() const;
    FBox GetSceneBounds() const;
    TArray<FVector> GetVisibilityPoints() const;
    bool IsCaseLidObstructing(const FVector& CameraPosition) const;
    FString GetDebugJson() const;
    void Cancel(const FString& Reason, bool ResumeLivingIdle = true);
    virtual void EndPlay(const EEndPlayReason::Type Reason) override;
private:
    bool LoadBundle();
    bool SampleCurrent(int32 Phase, double Seconds);
    bool PhaseBoundary(int32 Previous, int32 Following);
    void Release(const FString& Reason, bool ResumeLivingIdle, bool Completed);
    UPROPERTY(Transient) TObjectPtr<AOldWestUnit> Performer;
    UPROPERTY(Transient) TArray<TObjectPtr<UStaticMeshComponent>> Parts;
    UPROPERTY(Transient) TMap<FName, TObjectPtr<UAnimSequence>> Clips;
    TUniquePtr<FOldWestScientistPlaybackState, FOldWestScientistStateDeleter> State;
};
