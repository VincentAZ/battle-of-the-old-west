#pragma once

#include "CoreMinimal.h"
#include "Engine/GameInstance.h"
#include "Engine/EngineBaseTypes.h"
#include "GameFramework/GameModeBase.h"
#include "GameFramework/PlayerController.h"
#include "../Private/Core/OldWestRules.h"
#include "../Private/Core/OldWestAI.h"
#include "../Private/OldWestPreferences.h"
#include "Containers/Ticker.h"
#include <memory>
#include "OldWestSession.generated.h"

class SOldWestHUD;
class AOldWestBattlefield;

UCLASS()
class OLDWESTGAME_API UOldWestGameInstance : public UGameInstance
{
    GENERATED_BODY()
public:
    virtual void Init() override;
    virtual void Shutdown() override;
    FString SeatToken;
    FString LastAddress;
    FString LastServerSession;
    FString PendingAddress;
    FString PendingServerSession;
    FString SessionNotice;
    void SaveReconnectProfile();
    FOldWestPreferences Preferences;
    bool HasReconnectProfile() const { return !ReconnectProfileDirectory.IsEmpty(); }
    bool LoadedReconnectProfile() const { return ReconnectProfileLoaded; }
#if !UE_BUILD_SHIPPING
    FString LifecycleControl;
    FString LifecycleReport;
    FString FirstTestToken;
    int32 LifecycleSequence = 0;
    int32 NetworkFailures = 0;
    int32 SeatRejections = 0;
    bool TestBotPaused = true;
#endif
private:
    void OnNetworkFailure(UWorld* World, UNetDriver* Driver, ENetworkFailure::Type Failure, const FString& Error);
    void OnTravelFailure(UWorld* World, ETravelFailure::Type Failure, const FString& Error);
    void RecordFailure(const FString& Message);
    void LoadReconnectProfile();
    FString ReconnectProfileDirectory;
    bool ReconnectProfileLoaded = false;
    FTSTicker::FDelegateHandle PreferencesTicker;
};

UCLASS()
class OLDWESTGAME_API AOldWestPlayerController : public APlayerController
{
    GENERATED_BODY()
public:
    AOldWestPlayerController();
    virtual void BeginPlay() override;
    virtual void EndPlay(const EEndPlayReason::Type Reason) override;
    virtual void Tick(float DeltaSeconds) override;

    UFUNCTION(Server, Reliable) void ServerSubmit(const FString& Command, int32 ExpectedRevision, const FString& ExpectedMatch);
    UFUNCTION(Server, Reliable) void ServerRematch();
    UFUNCTION(Server, Reliable) void ServerNewGame(const FString& ExpectedMatch);
    UFUNCTION(Server, Reliable) void ServerClaimSeat(const FString& Token);
    UFUNCTION(Client, Reliable) void ClientRequestSeat(const FString& ServerSession);
    UFUNCTION(Client, Reliable) void ClientSeatRejected(const FString& Reason);
    UFUNCTION(Client, Reliable) void ClientWelcome(int32 Seat, const FString& Token);
    UFUNCTION(Client, Reliable) void ClientSync(const FString& Payload);
    UFUNCTION(Client, Reliable) void ClientSyncPart(int32 Batch, int32 Index, int32 Total, const FString& Part);
    void DeliverSnapshot(const FString& Payload);
    UFUNCTION(Client, Reliable) void ClientNotice(const FString& Message);

    void Submit(const FString& Command);
    void HostMatch(const FString& Ruleset = TEXT("base_2024"));
    void StartSinglePlayer(const FString& Ruleset, const FString& Difficulty);
    void JoinMatch(const FString& Address);
    void LeaveMatch();
    void QuitGame();
    void ClearSessionView();
    void ToggleCamera();
    void NavigateBattlefieldCamera(float OrbitX, float OrbitY, float PanX, float PanY, float Zoom, float Elevation = 0.f);
    void ResetBattlefieldCamera();
    void SetOverviewCamera(bool Enabled);
    bool HasAnalysisChoiceView() const;
    bool IsAnalysisChoiceFramed() const;
    void SetAnalysisChoiceFramed(bool Framed);
    bool IsCinematicBusy() const;
    int32 GetCinematicSequence() const;
    const FString& GetPresentationMatchId() const { return MatchId; }
    bool IsSoloPaused() const;
    FString GetCinematicCaption() const;
    void SkipCinematics();
    bool InspectWorldAtScreen(const FVector2D& Position);
    const FString& GetSnapshot() const { return Snapshot; }
    const FString& GetPresentationSnapshot() const { return PresentationSnapshot; }
    const FString& GetNotice() const { return Notice; }
    void DismissNotice() { Notice.Reset(); ++ViewGeneration; }
    int32 GetViewGeneration() const { return ViewGeneration; }

    // Set on the server during login. Never accept a seat sent with an action.
    int32 AssignedSeat = INDEX_NONE;
private:
    void TickTestPlayer(float DeltaSeconds);
    void TickLifecycleTest(float DeltaSeconds);
    FString Snapshot;
    FString PresentationSnapshot;
    FString IncomingSnapshot;
    int32 OutgoingSnapshotBatch = 0;
    int32 IncomingSnapshotBatch = -1;
    int32 IncomingSnapshotPart = 0;
    int32 IncomingSnapshotTotal = 0;
    FString MatchId;
    FString Notice;
    int32 Revision = -1;
    int32 ViewGeneration = 0;
    double LastSubmission = -100.;
    TSharedPtr<SOldWestHUD> HUD;
    UPROPERTY(Transient) TObjectPtr<AOldWestBattlefield> Battlefield;
    float TestDelay = 0.f;
    bool TestPlayer = false;
    bool TestFinished = false;
    FString TestReport;
    FString TestCapturePrefix;
    int32 TestCaptureStage = 0;
    float TestCadence = 0.16f;
    FRandomStream TestRandom;
    float LifecycleDelay = 0.f;
#if !UE_BUILD_SHIPPING
    FString ShadowProbeReport;
    FString LifecycleProfileReport;
    FString VisualTestKeyReport;
    FKey VisualTestPendingKey;
    int32 VisualTestKeyDownSequence = 0;
    int32 VisualTestKeyObservedSequence = 0;
    uint64 VisualTestKeyObservedFrame = 0;
#endif
};

UCLASS()
class OLDWESTGAME_API AOldWestGameMode : public AGameModeBase
{
    GENERATED_BODY()
public:
    AOldWestGameMode();
    virtual ~AOldWestGameMode() override;
    virtual void Tick(float DeltaSeconds) override;
    virtual void InitGame(const FString& MapName, const FString& Options, FString& ErrorMessage) override;
    virtual void PreLogin(const FString& Options, const FString& Address, const FUniqueNetIdRepl& UniqueId, FString& ErrorMessage) override;
    virtual FString InitNewPlayer(APlayerController* NewPlayerController, const FUniqueNetIdRepl& UniqueId, const FString& Options, const FString& Portal) override;
    virtual void PostLogin(APlayerController* NewPlayer) override;
    virtual void Logout(AController* Exiting) override;
    void Submit(AOldWestPlayerController* Sender, const FString& Command, int32 ExpectedRevision, const FString& ExpectedMatch);
    void RequestRematch(AOldWestPlayerController* Sender);
    void RequestNewGame(AOldWestPlayerController* Sender, const FString& ExpectedMatch);
    void SyncPlayers();
    void ClaimSeat(AOldWestPlayerController* Player, const FString& Token);
private:
    void RejectSeat(AOldWestPlayerController* Player, const FString& Reason);
    void StartNewRulesGame();
    void TickAI(float DeltaSeconds);
    int32 ParticipantCount() const;
    int32 SeatForToken(const FString& Token) const;
    TWeakObjectPtr<AOldWestPlayerController> Seats[2];
    FString Tokens[2];
    bool RematchVotes[2] = {false, false};
    bool Hosted = false;
    bool SinglePlayer = false;
    bool AISuspended = false;
    FString SelectedAIDifficulty = TEXT("normal");
    float AIThinkDelay = 0.75f;
    float AICadence = 0.75f;
    bool FastAITest = false;
#if !UE_BUILD_SHIPPING
    int32 AIActions = 0;
    int32 AIChoices = 0;
#endif
    FString Catalog;
    FString SelectedRuleset = TEXT("base_2024");
    FString MatchId;
    FString ServerSessionId;
    TMap<TWeakObjectPtr<AOldWestPlayerController>, double> PendingSeatClaims;
    std::unique_ptr<oldwest::Engine> Rules;
    std::unique_ptr<oldwest::AIPlayer> AI;
};
