#pragma once
#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "OldWestBattlefield.generated.h"

class AOldWestPlayerController;
class ACineCameraActor;
class USkeletalMeshComponent;
class UStaticMeshComponent;
class UStaticMesh;
class UTextRenderComponent;
class UPointLightComponent;
class UAudioComponent;
class UPhysicalMaterial;
class UMaterialInterface;
class UOldWestCampVisuals;
class UOldWestStampedeVisuals;
struct FOldWestPresentation;
class USceneComponent;
class UAnimSequence;
class UAnimationAsset;
DECLARE_DELEGATE_OneParam(FOldWestManualInterrupted, const FString&);

UCLASS()
class OLDWESTGAME_API AOldWestUnit : public AActor
{
    GENERATED_BODY()
public:
    AOldWestUnit();
    void Configure(int32 Id, int32 Side, const FString& Name, bool IsCamp, bool IsPunk, const FString& CardId = FString(), bool ForceUnarmed = false, const FString& VisualOverride = TEXT(""));
    bool BeginManualPresentation(UObject* Owner, const FOldWestManualInterrupted& Interrupted);
    bool OwnsManualPresentation(const UObject* Owner) const { return ManualPoseOwner.Get() == Owner && Owner != nullptr; }
    bool HasManualPresentation() const { return ManualPoseOwner.IsValid(); }
    bool SampleManualPresentation(UObject* Owner, UAnimSequence* Clip, double Seconds, float EntryAlpha, const FString& Phase);
    bool SetManualPresentationRifle(UObject* Owner, const FTransform& BodyRelative, bool Held);
    FVector ManualPresentationPalm(const UObject* Owner, bool Right) const;
    void EndManualPresentation(UObject* Owner, bool ResumeLivingIdle, bool Completed);
    void InterruptManualPresentation(const FString& Reason);
    const FString& GetManualPresentationPhase() const { return ManualPhase; }
    bool IsManualPresentationRifleHeld() const { return HasManualPresentation() && ManualRifleHeld; }
    FString GetManualPresentationDebug() const;
    void ConfigureEvent(int32 Id, int32 Side, const FString& Name, const FString& CardId);
    void MoveEventEquipment(const FVector& Location);
    FVector EventPropPoint(const FVector& LocalCentimeters) const;
    float StageTravel(const FVector& From, const FVector& To, float Seconds, bool Withdraw = false, bool DirectRoute = false);
    void SetCondition(int32 Damage, bool Destroyed, bool Ready);
    void PlayAction(const FString& Kind, const FVector& Direction = FVector::ZeroVector);
    void ResetPose();
    void AimAt(const FVector& Target);
    void SetPreviewOnly(bool Enabled);
    bool IsPreviewOnly() const { return PreviewOnly; }
    bool IsRaider() const { return Raider; }
    bool IsEventToken() const { return EventToken; }
    FBox GetVisualBounds() const;
    FBox GetSelectionBounds() const { return GetVisualBounds(); }
    FString GetIdleDebug() const;
#if !UE_BUILD_SHIPPING
    // Read-only completed actor-tick snapshot, emitted only for visual tests.
    void SampleCompletedWeaponObservation(const FString& MatchId, int32 Sequence,
        const FString& Kind, float Elapsed, bool Busy);
    virtual void DispatchPhysicsCollisionHit(const FRigidBodyCollisionInfo& MyInfo,
        const FRigidBodyCollisionInfo& OtherInfo, const FCollisionImpactData& Collision) override;
#endif
    FVector GetPresentationFocus() const;
    float GetRootDrift() const;
    FString GetPhysicsDebug() const;
    bool IsRagdollSettled(FString* FailureReason = nullptr) const;
    bool IsRagdoll() const { return Ragdoll; }
    bool IsVisuallyDead() const { return Dead; }
    int32 GetVisualDamage() const { return VisualDamage; }
    const FString& GetUnitName() const { return DisplayName; }
    virtual void Tick(float DeltaSeconds) override;
    UPROPERTY(VisibleAnywhere) TObjectPtr<USkeletalMeshComponent> Body;
    UPROPERTY(VisibleAnywhere) TObjectPtr<USkeletalMeshComponent> WoundBandage;
    UPROPERTY(VisibleAnywhere) TObjectPtr<UStaticMeshComponent> Structure;
    UPROPERTY(VisibleAnywhere) TObjectPtr<UOldWestCampVisuals> CampVisuals;
    UPROPERTY(VisibleAnywhere) TObjectPtr<UOldWestStampedeVisuals> StampedeVisuals;
    UPROPERTY(VisibleAnywhere) TObjectPtr<UStaticMeshComponent> Weapon;
    UPROPERTY(VisibleAnywhere) TObjectPtr<UTextRenderComponent> Caption;
    UPROPERTY(VisibleAnywhere) TObjectPtr<UPointLightComponent> Impact;
    int32 EntityId = 0;
    int32 Side = 0;
    bool Camp = false;
    const FString& GetVisualCardId() const { return VisualCardId; }
private:
    TWeakObjectPtr<UObject> ManualPoseOwner;
    FOldWestManualInterrupted ManualInterrupted;
    TArray<FTransform> ManualEntryPose;
    TWeakObjectPtr<USceneComponent> ManualWeaponParent;
    FName ManualWeaponSocket;
    FTransform ManualWeaponRelative, ManualBodyRelative;
    bool ManualWeaponVisible=false, ManualWeaponHidden=false, ManualBodyTick=false, ManualBodyPause=false;
    bool ManualRifleHeld=false;
    int32 ManualBodyLOD=0;
    FString ManualPhase;
    FString ManualLastReleaseReason;
    uint64 ManualSampleFrame=MAX_uint64;
    double ManualSampleSeconds=0.;
    float ManualEntryAlpha=1.f;
    UPROPERTY(Transient) TObjectPtr<UAnimationAsset> ManualPreviousAsset;
    FString ManualPreviousActiveClip;
    float ManualPreviousTime=0.f, ManualPreviousRate=1.f;
    bool ManualPreviousPlaying=false, ManualPreviousLooping=false;
    void PlayClip(const TCHAR* Name, bool Loop);
    void PlayIdle();
    void ApplyInjuredPose();
    void UpdateWoundBandage();
    FVector PalmContact(const TCHAR* SideName) const;
    void AlignWeaponToHands();
    void StartRagdoll();
    void ResetRagdollPoseSamples();
    void SampleRagdollPose(float DeltaSeconds);
    struct FRagdollPoseObservation
    {
        FName Bone;
        FVector PreviousCenter = FVector::ZeroVector;
        FVector CurrentCenter = FVector::ZeroVector;
        FQuat PreviousRotation = FQuat::Identity;
        FQuat CurrentRotation = FQuat::Identity;
        double Speed = 0.;
        double AngularSpeed = 0.;
    };
    TArray<FRagdollPoseObservation> RagdollPoseSamples;
    uint64 RagdollPoseFrame = MAX_uint64;
    uint64 RagdollPosePreviousFrame = MAX_uint64;
    float RagdollPoseDeltaSeconds = 0.f;
    double RagdollPoseMaxSpeed = 0.;
    double RagdollPoseMaxAngularSpeed = 0.;
    bool RagdollPoseSampleValid = false;
    bool RagdollPoseCacheComplete = false;
    UPROPERTY(Transient) TObjectPtr<UPhysicalMaterial> RagdollMaterial;
    UPROPERTY(Transient) TArray<TObjectPtr<UStaticMeshComponent>> EventParts;
    UPROPERTY(Transient) TObjectPtr<UMaterialInterface> EventEffectMaterial;
    UPROPERTY(Transient) TArray<TObjectPtr<UStaticMeshComponent>> EventWheels;
    UPROPERTY(Transient) TObjectPtr<UStaticMeshComponent> EventTurret;
    double EventWheelTravelCm = 0.;
    float EventWheelRadiusCm = 14.f;
    FString DisplayName;
    FString VisualCardId;
    FString CanonicalCardId;
    FString IdleClip = TEXT("MF_Rifle_Idle_ADS");
    FString ActiveClip;
    float IdlePhase = 0.f;
    float IdleRate = 1.f;
    float AmbientActivity = 0.f;
    int32 VisualDamage = -1;
    float AnimationTime = 0.f;
    bool Dead = false;
    bool Punk = false;
    bool Unarmed = false;
    bool Ragdoll = false;
    bool Raider = false;
    bool PreviewOnly = false;
    bool EventToken = false;
    bool Travelling = false, WithdrawAfterTravel = false;
    FVector TravelFrom = FVector::ZeroVector, TravelTo = FVector::ZeroVector;
    float TravelElapsed = 0.f, TravelDuration = 1.f;
    TArray<FVector> TravelRoute;
    float TravelLength = 0.f;
    float TravelStrideSpeed = 185.f;
    bool WeaponContactsValid = false;
    FVector WeaponRightGripLocal = FVector(-1.8f, -1.f, -.7f);
    FVector WeaponLeftGripLocal = FVector(1.8f, 30.f, 2.8f);
    FVector WeaponRightPalmWorld = FVector::ZeroVector;
    FVector WeaponLeftPalmWorld = FVector::ZeroVector;
#if !UE_BUILD_SHIPPING
    FString RagdollInitialPhysics;
    uint64 RagdollContactId = 0, RagdollContactEvents = 0;
    double RagdollContactStartSeconds = 0.;
    FString CompletedWeaponObservation;
    uint64 CompletedWeaponObservationFrame = MAX_uint64;
    uint64 WeaponAlignmentFrame = MAX_uint64;
    uint32 WeaponAlignmentBoneRevision = 0;
    uint32 WeaponAlignmentBoneFrame = 0;
#endif
    float RagdollDelay = -1.f;
    FVector FallDirection = FVector::ZeroVector;
    FName PelvisBone = TEXT("Hips");
    FTransform RootFrame = FTransform::Identity;
    FRotator Facing = FRotator::ZeroRotator;
};

UCLASS()
class OLDWESTGAME_API AOldWestBattlefield : public AActor
{
    GENERATED_BODY()
public:
    AOldWestBattlefield();
    virtual ~AOldWestBattlefield() override;
    void Initialize(AOldWestPlayerController* Player);
    void ApplySnapshot(const FString& Payload);
    void ToggleCamera();
    // Orbit/pan use mouse pixels; Zoom uses wheel steps (positive zooms in).
    void NavigateCamera(float OrbitX, float OrbitY, float PanX, float PanY, float Zoom, float Elevation = 0.f);
    void ResetCamera();
    void SetOverviewCamera(bool Enabled);
    bool HasAnalysisChoiceView() const;
    bool IsAnalysisChoiceFramed() const;
    void SetAnalysisChoiceFramed(bool Framed);
    // PersonPosition is the final battlefield row (0 front, 1 rear, 2 camp).
    // Returned Z is the authored ground plane; GroundedDeploymentPosition traces terrain.
    static FVector DeploymentPosition(int32 Side, int32 Column, int32 PersonPosition);
    // Slot -1 is the immediate-play (printed 0) space; 0..2 are countdown 1..3.
    static FVector EventPosition(int32 Side, int32 Slot);
    FVector GroundedDeploymentPosition(int32 Side, int32 Column, int32 PersonPosition) const;
    bool IsCinematicBusy() const;
    int32 GetCinematicSequence() const;
    void SkipCinematics();
    FString GetCinematicDebug() const;
    FString GetCinematicCaption() const;
    virtual void EndPlay(const EEndPlayReason::Type Reason) override;
    virtual void Tick(float DeltaSeconds) override;
private:
#if !UE_BUILD_SHIPPING
    void ObserveCompletedActorTick(UWorld* World, ELevelTick TickType, float DeltaSeconds);
    FDelegateHandle CompletedActorTickHandle;
#endif
    void SetOverview();
    void UpdateShotFocus();
    bool RetainAnalysisChoiceView();
    bool IsShotObstructed(const FVector& Focus, const FVector& Position, int32 Target, FString* Detail = nullptr) const;
    FVector ChooseShotPosition(const FVector& Focus, const FVector& Preferred, int32 Target) const;
    void ReconcileUnits();
    void UpdateCinematicLODs();
    void BeginNextBeat();
    void RecordShotCompletion(const TCHAR* Reason);
    void ResolveImpact();
    bool IsScientistBeat() const;
    bool StartScientistBeat();
    void FrameScientistScene(int32 Key);
    void AdvanceScientistScenes(float DeltaSeconds);
    void CancelScientistScenes(const TCHAR* Reason, int32 Source = 0, bool ResumeLivingIdle = true);
    void ClearActionEffects();
    void StageActionEffects(bool ImpactPhase);
    void UpdateActionEffects(float DeltaSeconds);
    void FocusAction(int32 Source, int32 Target, const FString& Kind, int32 Revision);
    TWeakObjectPtr<AOldWestPlayerController> Controller;
    UPROPERTY(Transient) TObjectPtr<ACineCameraActor> Camera;
    UPROPERTY(Transient) TMap<int32, TObjectPtr<AOldWestUnit>> Units;
    UPROPERTY(Transient) TObjectPtr<UAudioComponent> Ambience;
    UPROPERTY(Transient) TObjectPtr<UStaticMesh> BonusWhiskeyMesh;
    UPROPERTY(Transient) TObjectPtr<UStaticMesh> RevealBandanaMesh;
    UPROPERTY(Transient) TArray<TObjectPtr<UObject>> DeliveryAssets;
    TSharedPtr<FOldWestPresentation> Presentation;
    FVector DesiredCamera = FVector(-2000, 5300, 1550);
    FVector DesiredFocus = FVector(0, 2500, 140);
    FVector CameraFocus = FVector(0, 2500, 140);
    FVector TacticalFocus = FVector(0, 2500, 140);
    float TacticalYaw = 57.53f;
    float TacticalPitch = 26.61f;
    float TacticalDistance = 4373.f;
    bool CameraInitialized = false;
    bool CameraCustomized = false;
    bool DefaultFramingPending = false;
    int32 FramingHandRows = 1;
    int32 Seat = 0;
    bool AlternateAngle = true;
    bool BirdOverview = false;
    int32 ChoiceViewSequence = 0, ChoiceViewSource = 0, DismissedChoiceViewSequence = 0;
    bool ChoiceViewFramed = false;
    FVector ChoiceViewPosition = FVector::ZeroVector, ChoiceViewFocus = FVector::ZeroVector;
    FVector SavedTacticalFocus = FVector::ZeroVector;
    float SavedTacticalYaw = 0.f, SavedTacticalPitch = 0.f, SavedTacticalDistance = 0.f;
};
