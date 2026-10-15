#pragma once
#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "OldWestPunkShelter.generated.h"
class AOldWestUnit;
class UStaticMeshComponent;
class USceneComponent;
class APlayerController;

// Local presentation of public punk placement opportunities. These residents
// are never rules entities and never carry an upcoming deck card's identity.
UCLASS()
class OLDWESTGAME_API AOldWestPunkShelter : public AActor
{
    GENERATED_BODY()
public:
    AOldWestPunkShelter();
    void Initialize(int32 Side);
    void SetSupply(int32 Count,int32 Revision,const TSet<int32>& BoardPunks);
    bool CanDrag(int32 Token) const;
    bool BeginDrag(int32 Token);
    void CancelDrag(int32 Token);
    void Submitted(int32 Token);
    void PreviewAt(int32 Token,const FVector& Position);
    int32 Pick(APlayerController* Player,const FVector2D& Pixels) const;
    FString DebugState() const;
    TArray<TPair<int32,FVector>> ReadyPositions() const;
    virtual void Tick(float DeltaSeconds) override;
    virtual void EndPlay(const EEndPlayReason::Type Reason) override;
    static bool IsToken(int32 Id){return Id<=-1000&&Id>-1006;}
private:
    enum class EPhase:uint8 { Home,ExitGate,ExitPad,Waiting,Dragging,Submitted,ReturnGate,ReturnHome,Spent };
    struct FResident { EPhase Phase=EPhase::Home; double Until=0,Cooldown=0; bool Roam=false; int32 Trips=0; };
    UPROPERTY(Transient) TArray<TObjectPtr<AOldWestUnit>> Crew;
    UPROPERTY(Transient) TArray<TObjectPtr<UStaticMeshComponent>> Parts;
    UPROPERTY(Transient) TObjectPtr<USceneComponent> Gate;
    UPROPERTY(Transient) TObjectPtr<UStaticMeshComponent> PunchBag;
    FResident Residents[6];
    int32 Available=0,SeenRevision=-1,PendingToken=INDEX_NONE,Consumed=0,Returns=0;
    TSet<int32> SeenPunks;
    double Clock=0;
    float GateAngle=0;
    FVector Ground(const FVector& Local) const;
    FVector Home(int32 Index) const;
    FVector Pad(int32 Index) const;
    void Walk(int32 Index,const FVector& To,EPhase Phase);
    void Return(int32 Index);
    UStaticMeshComponent* Part(const TCHAR* Mesh,const FVector& Position,const FVector& Size,const TCHAR* Material,USceneComponent* Parent=nullptr);
};
