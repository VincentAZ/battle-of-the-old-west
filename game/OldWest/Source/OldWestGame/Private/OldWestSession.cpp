#include "OldWestCosmetics.h"
#include "OldWestSession.h"
#include "Core/OldWestRules.h"
#include "Core/json.hpp"
#include "OldWestBattlefield.h"
#include "OldWestHUD.h"
#include "ReconnectStore.h"
#include "OldWestWorldInteraction.h"
#include "OldWestShadowProbe.h"
#include "Engine/Engine.h"
#include "Engine/GameViewportClient.h"
#include "Engine/NetDriver.h"
#include "Engine/NetConnection.h"
#include "Engine/World.h"
#include "Kismet/GameplayStatics.h"
#include "Kismet/KismetSystemLibrary.h"
#include "AudioMixerBlueprintLibrary.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "HAL/PlatformTime.h"
#include "HAL/PlatformMisc.h"
#include "HAL/PlatformProcess.h"
#include "HAL/FileManager.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "UnrealClient.h"
#if !UE_BUILD_SHIPPING
#include "Framework/Application/SlateApplication.h"
#include "Input/Events.h"
#endif

using J = nlohmann::ordered_json;
namespace {
std::string Utf8(const FString& S) { return std::string(TCHAR_TO_UTF8(*S)); }
FString Text(const std::string& S) { return FString(UTF8_TO_TCHAR(S.c_str())); }
FString AddressOf(const FURL& URL)
{
    FString Host = URL.Host.ToLower();
    if (Host.Contains(TEXT(":")) && !Host.StartsWith(TEXT("["))) Host = TEXT("[") + Host + TEXT("]");
    return Host.IsEmpty() ? FString() : FString::Printf(TEXT("%s:%d"), *Host, URL.Port);
}
#if !UE_BUILD_SHIPPING
void ConfigureLifecycleTimeout(UNetDriver* Driver)
{
    if (Driver && FParse::Param(FCommandLine::Get(), TEXT("OldWestLifecycleTest"))
        && !FParse::Param(FCommandLine::Get(), TEXT("OldWestProductionTimeouts")))
    {
        UE_LOG(LogTemp, Display, TEXT("OldWest lifecycle timeout: driver=%s previous=%.2f/%.2f"),
            *Driver->GetName(), Driver->ConnectionTimeout, Driver->InitialConnectTimeout);
        Driver->ConnectionTimeout = 5.f;
        Driver->InitialConnectTimeout = 10.f;
        Driver->TimeoutMultiplierForUnoptimizedBuilds = 1.f;
    }
}
#endif
}

void UOldWestGameInstance::LoadReconnectProfile()
{
    if (IsRunningDedicatedServer()) return;
    FString Profile = TEXT("default");
    const bool ExplicitProfile = FParse::Value(FCommandLine::Get(), TEXT("OldWestProfile="), Profile);
#if !UE_BUILD_SHIPPING
    // Multiple automated clients must never inherit the human player's seat.
    if (!ExplicitProfile && (FParse::Param(FCommandLine::Get(), TEXT("OldWestTestBot"))
        || FParse::Param(FCommandLine::Get(), TEXT("OldWestLifecycleTest"))
        || FParse::Param(FCommandLine::Get(), TEXT("OldWestVisualTest")) || !LifecycleControl.IsEmpty())) return;
#endif
    bool Valid = !Profile.IsEmpty() && Profile.Len() <= 64;
    for (const TCHAR C : Profile) if (!FChar::IsAlnum(C) && C != TEXT('_') && C != TEXT('-')) Valid = false;
    if (!Valid) { SessionNotice = TEXT("The selected local profile name is invalid."); return; }
    FString Root = FPaths::Combine(FPlatformProcess::UserSettingsDir(), TEXT("OldWest/Profiles"));
#if !UE_BUILD_SHIPPING
    if (ExplicitProfile) FParse::Value(FCommandLine::Get(), TEXT("OldWestProfileRoot="), Root);
#else
    (void)ExplicitProfile;
#endif
    ReconnectProfileDirectory = FPaths::ConvertRelativePathToFull(FPaths::Combine(Root, Profile));
    const auto Stored = oldwest::ReadReconnectProfile(Utf8(ReconnectProfileDirectory));
    if (Stored.status == oldwest::ReconnectReadStatus::Loaded)
    {
        LastAddress = Text(Stored.credentials.endpoint);
        LastServerSession = Text(Stored.credentials.serverSession);
        SeatToken = Text(Stored.credentials.token);
        ReconnectProfileLoaded = true;
#if !UE_BUILD_SHIPPING
        FirstTestToken = SeatToken;
#endif
    }
    else if (Stored.status != oldwest::ReconnectReadStatus::Missing)
        SessionNotice = TEXT("Saved reconnect information could not be loaded.");
}

void UOldWestGameInstance::SaveReconnectProfile()
{
    if (ReconnectProfileDirectory.IsEmpty() || LastAddress.IsEmpty() || LastServerSession.IsEmpty() || SeatToken.IsEmpty()) return;
    if (!oldwest::WriteReconnectProfile(Utf8(ReconnectProfileDirectory), {Utf8(LastAddress), Utf8(LastServerSession), Utf8(SeatToken)}))
        SessionNotice = TEXT("Your seat could not be saved. Keep this window open to retain reconnect access.");
}

void UOldWestGameInstance::Init()
{
    Super::Init();
    if (GEngine)
    {
        GEngine->OnNetworkFailure().AddUObject(this, &UOldWestGameInstance::OnNetworkFailure);
        GEngine->OnTravelFailure().AddUObject(this, &UOldWestGameInstance::OnTravelFailure);
    }
#if !UE_BUILD_SHIPPING
    FParse::Value(FCommandLine::Get(), TEXT("OldWestLifecycleControl="), LifecycleControl);
    FParse::Value(FCommandLine::Get(), TEXT("OldWestLifecycleReport="), LifecycleReport);
#endif
    LoadReconnectProfile();
    if (!IsRunningDedicatedServer())
    {
        Preferences.Initialize();
        PreferencesTicker = FTSTicker::GetCoreTicker().AddTicker(FTickerDelegate::CreateLambda([this](float) {
            Preferences.Tick(GetWorld());
            return true;
        }), 0.1f);
    }
}

void UOldWestGameInstance::Shutdown()
{
    FTSTicker::GetCoreTicker().RemoveTicker(PreferencesTicker);
    Preferences.Revert(GetWorld());
    if (GEngine)
    {
        GEngine->OnNetworkFailure().RemoveAll(this);
        GEngine->OnTravelFailure().RemoveAll(this);
    }
    Super::Shutdown();
}

void UOldWestGameInstance::RecordFailure(const FString& Message)
{
    PendingAddress.Empty();
    PendingServerSession.Empty();
    SessionNotice = Message;
    if (!SeatToken.IsEmpty()) SessionNotice.ReplaceInline(*SeatToken, TEXT("[private seat]"));
    if (AOldWestPlayerController* Player = Cast<AOldWestPlayerController>(GetFirstLocalPlayerController()))
    {
        Player->ClearSessionView();
        Player->ClientNotice(SessionNotice);
    }
    // UEngine's registered handler returns the client to its default map. Do not
    // schedule competing travel from inside the failure delegate.
}

void UOldWestGameInstance::OnNetworkFailure(UWorld* World, UNetDriver* Driver, ENetworkFailure::Type Failure, const FString& Error)
{
    if ((World && World->GetGameInstance() != this) || !Driver || Driver->GetNetMode() != NM_Client) return;
    if (Driver->NetDriverName != NAME_GameNetDriver && Driver->NetDriverName != NAME_PendingNetDriver) return;
#if !UE_BUILD_SHIPPING
    ++NetworkFailures;
#endif
    FString Message = Failure == ENetworkFailure::ConnectionTimeout
        ? TEXT("Connection to the host timed out.")
        : Failure == ENetworkFailure::PendingConnectionFailure
        ? TEXT("Could not connect. Check the address and that the host's game is open.")
        : TEXT("Connection to the host ended.");
    if (!SeatToken.IsEmpty()) Message += TEXT(" Join the same address to resume your seat.");
    RecordFailure(Message);
}

void UOldWestGameInstance::OnTravelFailure(UWorld* World, ETravelFailure::Type Failure, const FString& Error)
{
    if (!World || World->GetGameInstance() != this || World->GetNetMode() == NM_DedicatedServer) return;
    RecordFailure(TEXT("Could not open the match. Please check the address and try again."));
}

AOldWestGameMode::AOldWestGameMode()
{
    PlayerControllerClass = AOldWestPlayerController::StaticClass();
    DefaultPawnClass = nullptr;
    bStartPlayersAsSpectators = true;
    PrimaryActorTick.bCanEverTick = true;
}
AOldWestGameMode::~AOldWestGameMode() = default;

void AOldWestGameMode::InitGame(const FString& MapName, const FString& Options, FString& ErrorMessage)
{
    Super::InitGame(MapName, Options, ErrorMessage);
    SinglePlayer = UGameplayStatics::ParseOption(Options, TEXT("SinglePlayer")) == TEXT("1");
    Hosted = SinglePlayer || UGameplayStatics::HasOption(Options, TEXT("Match")) || GetNetMode() != NM_Standalone;
    ServerSessionId = FGuid::NewGuid().ToString(EGuidFormats::Digits);
    if (!FFileHelper::LoadFileToString(Catalog, *(FPaths::ProjectContentDir() / TEXT("Data/cards.json"))))
    {
        ErrorMessage = TEXT("The card catalog is missing. Rebuild the game data.");
        return;
    }
    try
    {
        if (SinglePlayer)
        {
            if (GetNetMode() != NM_Standalone || UGameplayStatics::HasOption(Options, TEXT("listen")))
                throw std::runtime_error("Single player requires an offline world.");
            SelectedAIDifficulty = UGameplayStatics::ParseOption(Options, TEXT("AIDifficulty"));
            if (SelectedAIDifficulty.IsEmpty()) SelectedAIDifficulty = TEXT("normal");
            if (SelectedAIDifficulty != TEXT("easy") && SelectedAIDifficulty != TEXT("normal") && SelectedAIDifficulty != TEXT("hard"))
                throw std::runtime_error("Unknown AI difficulty.");
#if !UE_BUILD_SHIPPING
            FastAITest = FParse::Param(FCommandLine::Get(), TEXT("OldWestLifecycleTest"))
                && FParse::Param(FCommandLine::Get(), TEXT("OldWestVisualTest"))
                && FParse::Value(FCommandLine::Get(), TEXT("OldWestAITestDelay="), AICadence);
            AICadence = FMath::Clamp(AICadence, 0.03f, 5.f);
#endif
        }
        const FString Option = UGameplayStatics::ParseOption(Options, TEXT("Ruleset"));
        SelectedRuleset = Option.IsEmpty() ? TEXT("base_2024") : Option;
        if (!J::parse(Utf8(Catalog)).at("rulesets").contains(Utf8(SelectedRuleset)))
            throw std::runtime_error("Unknown match ruleset.");
        StartNewRulesGame();
    }
    catch (const std::exception& E) { ErrorMessage = Text(E.what()); }
}

void AOldWestGameMode::StartNewRulesGame()
{
    const FGuid Seed = FGuid::NewGuid();
    uint64 Value = (static_cast<uint64>(Seed.A) << 32) | Seed.B;
#if !UE_BUILD_SHIPPING
    if (FParse::Param(FCommandLine::Get(), TEXT("OldWestLifecycleTest"))
        && FParse::Param(FCommandLine::Get(), TEXT("OldWestVisualTest"))
        && FParse::Value(FCommandLine::Get(), TEXT("OldWestTestSeed="), Value))
    {
        UE_LOG(LogTemp, Display, TEXT("OldWest visual test seed: %llu"), static_cast<unsigned long long>(Value));
    }
#endif
    Rules = std::make_unique<oldwest::Engine>(Utf8(Catalog), Value, J({{"ruleset", Utf8(SelectedRuleset)}}).dump());
    if (SinglePlayer)
    {
        const auto Difficulty = SelectedAIDifficulty == TEXT("easy") ? oldwest::AIDifficulty::Easy
            : SelectedAIDifficulty == TEXT("hard") ? oldwest::AIDifficulty::Hard : oldwest::AIDifficulty::Normal;
        AI = std::make_unique<oldwest::AIPlayer>(Utf8(Catalog), Difficulty, Value ^ 0x7261646c616e6473ULL);
    }
    AISuspended = false;
    AIThinkDelay = AICadence;
#if !UE_BUILD_SHIPPING
    AIActions = AIChoices = 0;
#endif
    MatchId = FGuid::NewGuid().ToString(EGuidFormats::Digits);
    RematchVotes[0] = RematchVotes[1] = false;
}

int32 AOldWestGameMode::SeatForToken(const FString& Token) const
{
    if (!Token.IsEmpty()) for (int32 I = 0; I < 2; ++I) if (Tokens[I] == Token) return I;
    return INDEX_NONE;
}

void AOldWestGameMode::PreLogin(const FString& Options, const FString& Address, const FUniqueNetIdRepl& UniqueId, FString& ErrorMessage)
{
    Super::PreLogin(Options, Address, UniqueId, ErrorMessage);
    if (!ErrorMessage.IsEmpty()) return;
    if (SinglePlayer) { ErrorMessage = TEXT("This is an offline single-player match."); return; }
    // Credentials never travel in FURL, whose options are logged by UE on both
    // ends. Admit a bounded number of unseated controllers for reliable RPC auth.
    if (PendingSeatClaims.Num() >= 8) ErrorMessage = TEXT("Too many connections are awaiting authentication. Please try again.");
}

FString AOldWestGameMode::InitNewPlayer(APlayerController* NewPlayerController, const FUniqueNetIdRepl& UniqueId, const FString& Options, const FString& Portal)
{
    FString Error = Super::InitNewPlayer(NewPlayerController, UniqueId, Options, Portal);
    if (!Error.IsEmpty()) return Error;
    AOldWestPlayerController* Player = Cast<AOldWestPlayerController>(NewPlayerController);
    if (!Player) return TEXT("Invalid player controller.");
    Player->AssignedSeat = INDEX_NONE;
    return FString();
}

void AOldWestGameMode::PostLogin(APlayerController* NewPlayer)
{
    Super::PostLogin(NewPlayer);
#if !UE_BUILD_SHIPPING
    ConfigureLifecycleTimeout(GetWorld()->GetNetDriver());
#endif
    if (AOldWestPlayerController* Player = Cast<AOldWestPlayerController>(NewPlayer))
    {
        if (!Hosted || SinglePlayer)
        {
            Player->AssignedSeat = 0;
            Seats[0] = Player;
            Player->ClientWelcome(0, FString());
            SyncPlayers();
            return;
        }
        PendingSeatClaims.Add(Player, FPlatformTime::Seconds() + 10.0);
        Player->ClientRequestSeat(ServerSessionId);
    }
}

void AOldWestGameMode::Tick(float DeltaSeconds)
{
    Super::Tick(DeltaSeconds);
    TArray<TWeakObjectPtr<AOldWestPlayerController>> Expired;
    for (auto It = PendingSeatClaims.CreateIterator(); It; ++It)
    {
        if (!It.Key().IsValid()) It.RemoveCurrent();
        else if (FPlatformTime::Seconds() >= It.Value()) Expired.Add(It.Key());
    }
    for (const auto& Player : Expired) RejectSeat(Player.Get(), TEXT("Seat authentication timed out. Please join again."));
    TickAI(DeltaSeconds);
}

int32 AOldWestGameMode::ParticipantCount() const
{
    return static_cast<int32>(Seats[0].IsValid()) + static_cast<int32>(SinglePlayer || Seats[1].IsValid());
}

void AOldWestGameMode::TickAI(float DeltaSeconds)
{
    if (!SinglePlayer || !Rules || !AI || AISuspended || Rules->IsFinished() || !Seats[0].IsValid()) return;
    if (Seats[0]->IsSoloPaused() || (!FastAITest && Seats[0]->IsCinematicBusy())) { AIThinkDelay = AICadence; return; }
    const auto* GI=Cast<UOldWestGameInstance>(GetGameInstance());
    AIThinkDelay -= DeltaSeconds*(FastAITest||!GI?1.f:GI->Preferences.GetEnemySpeed());
    if (AIThinkDelay > 0.f) return;
    AIThinkDelay = AICadence;
    try
    {
        // The policy sees exactly the AI seat's view and legal actions. Never
        // supply a saved engine state, the human hand, or the shuffled deck.
        const std::string Legal = Rules->LegalActionsJson(1);
        if (J::parse(Legal).empty()) return;
        const std::string View = Rules->ViewJson(1);
        const std::string Choice = AI->Choose(View, Legal);
        if (Choice.empty()) throw std::runtime_error("No AI decision despite available legal actions.");
        J Command = J::parse(Choice);
        Command["revision"] = J::parse(View).at("revision");
        const J Result = J::parse(Rules->Apply(1, Command.dump()));
        if (!Result.value("ok", false)) throw std::runtime_error(Result.value("error", std::string("AI action rejected.")));
#if !UE_BUILD_SHIPPING
        ++AIActions;
        if (Command.value("type", std::string()) == "choose") ++AIChoices;
#endif
        SyncPlayers();
    }
    catch (const std::exception& E)
    {
        AISuspended = true;
        UE_LOG(LogTemp, Error, TEXT("OLDWEST_AI_ERROR %s"), *Text(E.what()));
        Seats[0]->ClientNotice(TEXT("The AI could not complete its move. Leave and start another match."));
    }
}

void AOldWestGameMode::RejectSeat(AOldWestPlayerController* Player, const FString& Reason)
{
    if (!Player || !PendingSeatClaims.Contains(Player)) return;
    PendingSeatClaims.Remove(Player);
    Player->ClientSeatRejected(Reason);
    // The client returns to its menu immediately. Also close an uncooperative
    // provisional connection without ever assigning it a seat or private view.
    Player->SetLifeSpan(0.75f);
}

void AOldWestGameMode::ClaimSeat(AOldWestPlayerController* Player, const FString& Token)
{
    if (!Hosted || !Player || !PendingSeatClaims.Contains(Player) || Player->AssignedSeat != INDEX_NONE) return;
    int32 Seat = INDEX_NONE;
    if (!Token.IsEmpty())
    {
        if (Token.Len() == 32) Seat = SeatForToken(Token);
        if (Seat == INDEX_NONE) { RejectSeat(Player, TEXT("The saved seat could not be authenticated for this server session.")); return; }
        if (Seats[Seat].IsValid()) { RejectSeat(Player, TEXT("That seat is already connected.")); return; }
    }
    else
    {
        for (int32 I = 0; I < 2; ++I) if (Tokens[I].IsEmpty()) { Seat = I; break; }
        if (Seat == INDEX_NONE) { RejectSeat(Player, TEXT("Both seats are occupied or reserved for reconnecting players.")); return; }
        Tokens[Seat] = FGuid::NewGuid().ToString(EGuidFormats::Digits);
    }
    PendingSeatClaims.Remove(Player);
    Player->AssignedSeat = Seat;
    Seats[Seat] = Player;
    Player->ClientWelcome(Seat, Tokens[Seat]);
    SyncPlayers();
}

void AOldWestGameMode::Logout(AController* Exiting)
{
    if (AOldWestPlayerController* Player = Cast<AOldWestPlayerController>(Exiting)) PendingSeatClaims.Remove(Player);
    for (int32 I = 0; I < 2; ++I) if (Seats[I].Get() == Exiting)
    {
        Seats[I].Reset();
        RematchVotes[I] = false;
    }
    Super::Logout(Exiting);
    SyncPlayers();
}

void AOldWestGameMode::SyncPlayers()
{
    if (!Rules) return;
    const int32 Connected = ParticipantCount();
    for (int32 P = 0; P < 2; ++P) if (AOldWestPlayerController* Player = Seats[P].Get())
    {
        J Payload = {{"hosted", Hosted}, {"connected", Connected}, {"seat", P}, {"match_id", Utf8(MatchId)},
            {"mode", SinglePlayer ? "single_player" : Hosted ? "multiplayer" : "menu"},
            {"ai_difficulty", SinglePlayer ? Utf8(SelectedAIDifficulty) : std::string()},
            {"cosmetics", J::parse(Rules->CosmeticViewJson(P))}, {"view", J::parse(Rules->ViewJson(P))}, {"actions", Hosted && Connected == 2 ? J::parse(Rules->LegalActionsJson(P)) : J::array()},
            {"rematch_votes", J::array({RematchVotes[0], RematchVotes[1]})}};
#if !UE_BUILD_SHIPPING
        if (SinglePlayer) { Payload["ai_actions"] = AIActions; Payload["ai_choices"] = AIChoices; }
#endif
        Player->DeliverSnapshot(Text(Payload.dump()));
    }
}

void AOldWestGameMode::Submit(AOldWestPlayerController* Sender, const FString& Command, int32 ExpectedRevision, const FString& ExpectedMatch)
{
    const int32 P = Sender ? Sender->AssignedSeat : INDEX_NONE;
    if (!Hosted || !Rules || P < 0 || P > 1 || Seats[P].Get() != Sender) return;
    if (ExpectedMatch != MatchId)
    {
        Sender->ClientNotice(TEXT("That action belongs to an earlier match. Please choose again."));
        SyncPlayers();
        return;
    }
    if (ParticipantCount() != 2)
    {
        Sender->ClientNotice(TEXT("Waiting for the other player to connect."));
        return;
    }
    try
    {
        if (Command.Len() > 65536) throw std::runtime_error("Command too large");
        J Cmd = J::parse(Utf8(Command));
        Cmd["revision"] = ExpectedRevision;
        J Result = J::parse(Rules->Apply(P, Cmd.dump()));
        if (!Result.value("ok", false)) Sender->ClientNotice(Text(Result.value("error", std::string("Action rejected"))));
    }
    catch (const std::exception&) { Sender->ClientNotice(TEXT("The action could not be read. Please try again.")); }
    SyncPlayers();
}

void AOldWestGameMode::RequestNewGame(AOldWestPlayerController* Sender, const FString& ExpectedMatch)
{
    const int32 P = Sender ? Sender->AssignedSeat : INDEX_NONE;
    if (!Hosted || !Rules || ExpectedMatch != MatchId || P < 0 || P > 1 || Seats[P].Get() != Sender) return;
    if (!Rules->IsFinished()) Rules->Forfeit(P);
    SyncPlayers();
    RequestRematch(Sender);
}

void AOldWestGameMode::RequestRematch(AOldWestPlayerController* Sender)
{
    const int32 P = Sender ? Sender->AssignedSeat : INDEX_NONE;
    if (!Hosted || !Rules || !Rules->IsFinished() || P < 0 || P > 1 || Seats[P].Get() != Sender) return;
    if (ParticipantCount() != 2)
    {
        Sender->ClientNotice(TEXT("Both players must reconnect before starting a rematch."));
        return;
    }
    RematchVotes[P] = true;
    if (SinglePlayer || (RematchVotes[0] && RematchVotes[1])) StartNewRulesGame();
    SyncPlayers();
}

AOldWestPlayerController::AOldWestPlayerController()
{
    bShowMouseCursor = true;
    bEnableClickEvents = true;
    PrimaryActorTick.bCanEverTick = true;
    bAutoManageActiveCameraTarget = false;
}

void AOldWestPlayerController::BeginPlay()
{
    Super::BeginPlay();
    if (!IsLocalController()) return;
#if !UE_BUILD_SHIPPING
    ConfigureLifecycleTimeout(GetWorld()->GetNetDriver());
    TestPlayer = FParse::Param(FCommandLine::Get(), TEXT("OldWestTestBot"));
    FParse::Value(FCommandLine::Get(), TEXT("OldWestReport="), TestReport);
    FParse::Value(FCommandLine::Get(), TEXT("OldWestCapturePrefix="), TestCapturePrefix);
    FParse::Value(FCommandLine::Get(), TEXT("OldWestTestDelay="), TestCadence);
    TestCadence = FMath::Max(0.16f, TestCadence);
    TestRandom.Initialize(20260906);
#endif
    if (const UOldWestGameInstance* GI = Cast<UOldWestGameInstance>(GetGameInstance()))
    {
        Notice = GI->SessionNotice;
        GI->Preferences.ApplyAudio(GetWorld());
    }
    Battlefield = GetWorld()->SpawnActor<AOldWestBattlefield>();
    if (Battlefield) Battlefield->Initialize(this);
    if (GetWorld()->GetGameViewport())
    {
        HUD = SNew(SOldWestHUD).Owner(this);
        GetWorld()->GetGameViewport()->AddViewportWidgetContent(HUD.ToSharedRef(), 20);
    }
    FInputModeGameAndUI Mode;
    Mode.SetHideCursorDuringCapture(false);
    Mode.SetLockMouseToViewportBehavior(EMouseLockMode::DoNotLock);
    SetInputMode(Mode);
    if (!Snapshot.IsEmpty() && Battlefield) Battlefield->ApplySnapshot(PresentationSnapshot);
}

void AOldWestPlayerController::EndPlay(const EEndPlayReason::Type Reason)
{
    if (HUD.IsValid() && GetWorld() && GetWorld()->GetGameViewport())
        GetWorld()->GetGameViewport()->RemoveViewportWidgetContent(HUD.ToSharedRef());
    HUD.Reset();
    if (IsValid(Battlefield)) Battlefield->Destroy();
    Battlefield = nullptr;
    Super::EndPlay(Reason);
}

void AOldWestPlayerController::Tick(float DeltaSeconds)
{
    Super::Tick(DeltaSeconds);
#if !UE_BUILD_SHIPPING
    // Observe the real PlayerInput result, separately from Slate's handled reply.
    // No callbacks or direct controller InputKey calls are made by this probe.
    if (IsLocalController() && VisualTestPendingKey.IsValid() &&
        WasInputKeyJustPressed(VisualTestPendingKey))
    {
        VisualTestKeyObservedSequence = VisualTestKeyDownSequence;
        VisualTestKeyObservedFrame = GFrameCounter;
        VisualTestPendingKey = FKey();
    }
#endif
    if (IsLocalController() && WasInputKeyJustPressed(EKeys::Tab)) ToggleCamera();
    if (IsLocalController() && HUD.IsValid() && WasInputKeyJustPressed(EKeys::G)) HUD->ToggleBattleOverview();
    if (IsLocalController() && HUD.IsValid() && WasInputKeyJustPressed(EKeys::Escape)) HUD->DismissChoiceView();
    if (IsLocalController()) TickLifecycleTest(DeltaSeconds);
    if (IsLocalController() && TestPlayer) TickTestPlayer(DeltaSeconds);
}

void AOldWestPlayerController::TickTestPlayer(float DeltaSeconds)
{
#if !UE_BUILD_SHIPPING
    if (TestFinished || Snapshot.IsEmpty()) return;
    if (const UOldWestGameInstance* GI = Cast<UOldWestGameInstance>(GetGameInstance()))
        if (!GI->LifecycleControl.IsEmpty() && GI->TestBotPaused) return;
    TestDelay -= DeltaSeconds;
    if (TestDelay > 0.f) return;
    TestDelay = TestCadence;
    try
    {
        const J Data = J::parse(Utf8(Snapshot));
        const J& View = Data.at("view");
        const std::string Status = View.value("status", std::string());
        if (!TestCapturePrefix.IsEmpty() && TestCaptureStage < 3)
        {
            const bool Capture = (TestCaptureStage == 0 && Status == "selection") ||
                (TestCaptureStage == 1 && View.value("turn", 0) >= 4) ||
                (TestCaptureStage == 2 && View.value("turn", 0) >= 10);
            if (Capture)
            {
                const FString Filename = FString::Printf(TEXT("%s-%d.png"), *TestCapturePrefix, TestCaptureStage++);
                FScreenshotRequest::RequestScreenshot(Filename, true, false);
                TestDelay = 2.f;
                return;
            }
        }
        if (Status == "won" || Status == "draw")
        {
            if (!TestReport.IsEmpty()) FFileHelper::SaveStringToFile(Snapshot, *TestReport);
            UE_LOG(LogTemp, Display, TEXT("OLDWEST_TEST_FINISHED seat=%d revision=%d winner=%d"),
                AssignedSeat, Revision, View.value("winner", -1));
            TestFinished = true;
            return;
        }
        if (Data.value("connected", 0) != 2 || Data["actions"].empty()) return;
        TArray<int32> Candidates;
        for (int32 I = 0; I < static_cast<int32>(Data["actions"].size()); ++I)
        {
            const std::string Category = Data["actions"][I].value("category", std::string());
            const int32 Weight = Category == "ability" ? 5 : Category == "turn" ? 3 : 1;
            for (int32 N = 0; N < Weight; ++N) Candidates.Add(I);
        }
        const int32 Pick = Candidates[TestRandom.RandRange(0, Candidates.Num() - 1)];
        Submit(Text(Data["actions"][Pick]["command"].dump()));
    }
    catch (const std::exception& E)
    {
        UE_LOG(LogTemp, Error, TEXT("OLDWEST_TEST_ERROR %s"), *Text(E.what()));
        TestFinished = true;
    }
#endif
}

void AOldWestPlayerController::TickLifecycleTest(float DeltaSeconds)
{
#if !UE_BUILD_SHIPPING
    UOldWestGameInstance* GI = Cast<UOldWestGameInstance>(GetGameInstance());
    if (!GI || GI->LifecycleControl.IsEmpty() || GI->LifecycleReport.IsEmpty()) return;
    LifecycleDelay -= DeltaSeconds;
    if (LifecycleDelay > 0.f) return;
    LifecycleDelay = 0.1f;
    static const bool ProfileReports = FParse::Param(FCommandLine::Get(), TEXT("OldWestVisualTest")) &&
        FParse::Param(FCommandLine::Get(), TEXT("OldWestPresentationProfile"));
    auto ProfileNow = []() { return ProfileReports ? FPlatformTime::Seconds() : 0.; };
    const double ProfileBegin = ProfileNow();
    double ScreenshotEnqueueMs = 0.;
    bool ScreenshotRequested = false;
    FString Control;
    if (FFileHelper::LoadFileToString(Control, *GI->LifecycleControl))
    {
        try
        {
            const J Command = J::parse(Utf8(Control));
            const int32 Sequence = Command.at("sequence");
            if (Sequence > GI->LifecycleSequence)
            {
                GI->LifecycleSequence = Sequence; // Persists through controller/map replacement.
                const std::string Action = Command.at("action");
                if (Action == "pause") GI->TestBotPaused = true;
                else if (Action == "resume") GI->TestBotPaused = false;
                else if (Action == "leave") LeaveMatch();
                else if (Action == "join") JoinMatch(Text(Command.at("address").get<std::string>()));
                else if (Action == "host") HostMatch(Text(Command.value("ruleset", std::string("base_2024"))));
                else if (Action == "single_player") StartSinglePlayer(Text(Command.value("ruleset", std::string("base_2024"))),
                    Text(Command.value("difficulty", std::string("normal"))));
                else if (Action == "rematch") ServerRematch();
                else if (Action == "claim_seat" && FParse::Param(FCommandLine::Get(), TEXT("OldWestManualSeatClaim")))
                    ServerClaimSeat(Text(Command.at("token").get<std::string>()));
                else if (Action == "submit") ServerSubmit(Text(Command.at("command").dump()),
                    Command.at("revision").get<int32>(), Text(Command.at("match_id").get<std::string>()));
                else if ((Action == "inspect" || Action == "rules" || Action == "camera" || Action == "screenshot" || Action == "skip_cinematics"
                    || Action == "quit" || Action == "start_audio_capture" || Action == "stop_audio_capture" || Action == "pick_at" || Action == "settings"
                    || Action == "ui_pointer" || Action == "ui_key" || Action == "ui_text" || Action == "portrait_gallery" || Action == "battle_overview" || Action == "shadow_probe")
                    && FParse::Param(FCommandLine::Get(), TEXT("OldWestVisualTest")))
                {
                    // Explicit local opt-in, compiled out of shipping builds.
                    // These commands affect only inspection, camera and capture.
                    if (Action == "inspect")
                    {
                        if (!HUD.IsValid() || !HUD->InspectForVisualTest(Command.at("card").get<int32>()))
                            ClientNotice(TEXT("Visual test cannot inspect an unavailable card."));
                    }
                    else if (Action == "rules" && HUD.IsValid()) HUD->SetRulesForVisualTest(Command.value("open", true));
                    else if (Action == "settings" && HUD.IsValid()) HUD->SettingsForVisualTest(Command);
                    else if (Action == "ui_pointer" && HUD.IsValid()) HUD->PointerForVisualTest(Command);
                    else if(Action=="ui_text"&&FSlateApplication::IsInitialized())
                    {
                        const FString Input=Text(Command.value("text",std::string()));
                        if(Input.Len()<=256)for(TCHAR Character:Input)
                            FSlateApplication::Get().ProcessKeyCharEvent(FCharacterEvent(Character,FModifierKeysState(),0,false));
                    }
                    else if (Action == "ui_key")
                    {
                        const std::string Name = Command.value("key", std::string());
                        const std::string Phase = Command.value("phase", std::string());
                        const FKey Key = Name == "Escape" ? EKeys::Escape : Name == "Tab" ? EKeys::Tab :
                            Name == "G" ? EKeys::G : Name == "Up" ? EKeys::Up : Name == "Down" ? EKeys::Down :
                            Name == "Enter" ? EKeys::Enter : Name == "End" ? EKeys::End : Name == "BackSpace" ? EKeys::BackSpace : FKey();
                        const bool Valid = Key.IsValid() && (Phase == "down" || Phase == "up") &&
                            FSlateApplication::IsInitialized() && GetWorld()->GetGameViewport();
                        J Result = {{"accepted", Valid}, {"key", Name}, {"phase", Phase},
                            {"command_sequence", Sequence}, {"dispatch_frame", GFrameCounter}};
                        if (Valid)
                        {
                            auto& App = FSlateApplication::Get();
                            // Explicitly model keyboard focus in the game viewport. This
                            // does not test typing into text fields or arbitrary UI focus.
                            const bool KeepFocus=Command.value("preserve_focus",false);
                            if(!KeepFocus)App.SetUserFocusToGameViewport(0);
                            const FKeyEvent Event(Key, FModifierKeysState(), 0, false, 0, 0);
                            if (Phase == "down")
                            {
                                VisualTestPendingKey = Key;
                                VisualTestKeyDownSequence = Sequence;
                            }
                            Result["slate_handled"] = Phase == "down" ?
                                App.ProcessKeyDownEvent(Event) : App.ProcessKeyUpEvent(Event);
                            Result["focus_target"] = KeepFocus?"existing_widget":"game_viewport";
                        }
                        else Result["error"] = "Only Escape, Tab, G, Up and Down down/up are permitted in an initialized local game viewport.";
                        VisualTestKeyReport = Text(Result.dump());
                    }
                    else if (Action == "portrait_gallery" && HUD.IsValid()) HUD->GalleryForVisualTest(Command);
                    else if (Action == "battle_overview" && HUD.IsValid()) HUD->SetBattleOverview(Command.value("open", true));
                    else if (Action == "shadow_probe") ShadowProbeReport = RunOldWestShadowProbe(GetWorld(), Text(Command.value("category", std::string("restore"))));
                    else if (Action == "camera") ToggleCamera();
                    else if (Action == "skip_cinematics") SkipCinematics();
                    else if (Action == "quit") QuitGame();
                    else if (Action == "pick_at") InspectWorldAtScreen(FVector2D(Command.at("x").get<double>(), Command.at("y").get<double>()));
                    else if (Action == "start_audio_capture") UAudioMixerBlueprintLibrary::StartRecordingOutput(this, 60.f);
                    else if (Action == "stop_audio_capture") UAudioMixerBlueprintLibrary::StopRecordingOutput(this,
                        EAudioRecordingExportType::WavFile, Text(Command.at("name").get<std::string>()), Text(Command.at("directory").get<std::string>()));
                    else if (Action == "screenshot")
                    {
                        const double EnqueueBegin = ProfileNow();
                        FScreenshotRequest::RequestScreenshot(Text(Command.at("filename").get<std::string>()), true, false);
                        ScreenshotEnqueueMs = (ProfileNow() - EnqueueBegin) * 1000.;
                        ScreenshotRequested = true;
                    }
                }
#if DO_ENABLE_NET_TEST
                else if (Action == "packet_loss")
                {
                    if (UNetDriver* Driver = GetWorld()->GetNetDriver())
                    {
                        FPacketSimulationSettings Settings;
                        Settings.PktLoss = Settings.PktIncomingLoss = FMath::Clamp(Command.at("percent").get<int32>(), 0, 100);
                        Driver->SetPacketSimulationSettings(Settings);
                    }
                }
#endif
            }
        }
        catch (const std::exception&) { ClientNotice(TEXT("Invalid lifecycle test command.")); }
    }
    const double ProfileAfterControl = ProfileNow();
    J State = {{"sequence", GI->LifecycleSequence}, {"seat", AssignedSeat},
        {"has_seat_token", !GI->SeatToken.IsEmpty()}, {"same_seat_token", !GI->FirstTestToken.IsEmpty() && GI->FirstTestToken == GI->SeatToken},
        {"last_address", Utf8(GI->LastAddress)}, {"pending_address", Utf8(GI->PendingAddress)},
        {"last_server_session", Utf8(GI->LastServerSession)}, {"seat_challenge", Utf8(GI->PendingServerSession)},
        {"profile_enabled", GI->HasReconnectProfile()}, {"profile_loaded", GI->LoadedReconnectProfile()},
        {"seat_rejections", GI->SeatRejections},
        {"network_failures", GI->NetworkFailures}, {"notice", Utf8(Notice)}, {"bot_paused", GI->TestBotPaused},
        {"snapshot", Snapshot.IsEmpty() ? J::object() : J::parse(Utf8(Snapshot))}};
    if (UNetDriver* Driver = GetWorld()->GetNetDriver())
    {
        State["network"] = {{"connection_timeout", Driver->ConnectionTimeout},
            {"initial_timeout", Driver->InitialConnectTimeout},
            {"timeout_multiplier", Driver->TimeoutMultiplierForUnoptimizedBuilds},
            {"timeouts_disabled", static_cast<bool>(Driver->bNoTimeouts)}};
        if (Driver->ServerConnection)
            State["network"]["effective_timeout"] = Driver->ServerConnection->GetTimeoutValue();
        State["network"]["peers"] = J::array();
        auto RecordPeer = [&State](UNetConnection* Connection)
        {
            if (!Connection) return;
            J Peer = {{"effective_timeout", Connection->GetTimeoutValue()},
                {"state", static_cast<int32>(Connection->GetConnectionState())},
                {"seconds_since_receive", FPlatformTime::Seconds() - Connection->LastReceiveRealtime},
                {"incoming_packets", Connection->InTotalPackets}, {"outgoing_packets", Connection->OutTotalPackets}};
#if DO_ENABLE_NET_TEST
            Peer["simulated_outgoing_loss"] = Connection->PacketSimulationSettings.PktLoss;
            Peer["simulated_incoming_loss"] = Connection->PacketSimulationSettings.PktIncomingLoss;
#endif
            State["network"]["peers"].push_back(MoveTemp(Peer));
        };
        if (Driver->ServerConnection) RecordPeer(Driver->ServerConnection);
        else for (UNetConnection* Connection : Driver->ClientConnections) RecordPeer(Connection);
    }
    const double ProfileAfterBase = ProfileNow();
    if (FParse::Param(FCommandLine::Get(), TEXT("OldWestVisualTest")) && HUD.IsValid()) State["hud"] = HUD->VisualTestState();
    const double ProfileAfterHud = ProfileNow();
    double CinematicBuildMs = 0., CinematicParseMs = 0.;
    if (FParse::Param(FCommandLine::Get(), TEXT("OldWestVisualTest")) && Battlefield)
    {
        const double BuildBegin = ProfileNow();
        const FString CinematicDebug = Battlefield->GetCinematicDebug();
        const double ParseBegin = ProfileNow();
        State["cinematic"] = J::parse(Utf8(CinematicDebug));
        CinematicBuildMs = (ParseBegin - BuildBegin) * 1000.;
        CinematicParseMs = (ProfileNow() - ParseBegin) * 1000.;
    }
    if (!ShadowProbeReport.IsEmpty()) State["shadow_probe"] = J::parse(Utf8(ShadowProbeReport));
    if (!VisualTestKeyReport.IsEmpty())
    {
        J Key = J::parse(Utf8(VisualTestKeyReport));
        Key["controller_observed_down_sequence"] = VisualTestKeyObservedSequence;
        Key["controller_observed_frame"] = VisualTestKeyObservedFrame;
        Key["down_sequence"] = VisualTestKeyDownSequence;
        const std::string Name = Key.value("key", std::string());
        const FKey Code = Name == "Escape" ? EKeys::Escape : Name == "Tab" ? EKeys::Tab :
            Name == "G" ? EKeys::G : Name == "Up" ? EKeys::Up : Name == "Down" ? EKeys::Down : FKey();
        Key["controller_is_down"] = Code.IsValid() && IsInputKeyDown(Code);
        State["ui_key"] = MoveTemp(Key);
    }
    // Export the preceding completed write. Current serialization/write cost
    // cannot be truthfully embedded in the bytes that have already been saved.
    if (ProfileReports)
        State["lifecycle_profile_previous_report"] = LifecycleProfileReport.IsEmpty() ? J(nullptr) : J::parse(Utf8(LifecycleProfileReport));
    const double SerializeBegin = ProfileNow();
    const FString Serialized = Text(State.dump());
    const double WriteBegin = ProfileNow();
    const FString Temporary = GI->LifecycleReport + TEXT(".tmp");
    const bool Saved = FFileHelper::SaveStringToFile(Serialized, *Temporary, FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM);
    const double ReplaceBegin = ProfileNow();
    bool Replaced = false;
    if (Saved) Replaced = IFileManager::Get().Move(*GI->LifecycleReport, *Temporary, true, true);
    const double ProfileEnd = ProfileNow();
    if (ProfileReports)
    {
        const J Profile = {{"native_frame", GFrameCounter}, {"command_sequence", GI->LifecycleSequence},
            {"cinematic_sequence", Battlefield ? Battlefield->GetCinematicSequence() : INDEX_NONE},
            {"match_id", Utf8(MatchId)}, {"report_characters", Serialized.Len()}, {"saved", Saved}, {"replaced", Replaced},
            {"control_read_dispatch_ms", (ProfileAfterControl - ProfileBegin) * 1000.},
            {"snapshot_network_build_ms", (ProfileAfterBase - ProfileAfterControl) * 1000.},
            {"hud_build_ms", (ProfileAfterHud - ProfileAfterBase) * 1000.},
            {"cinematic_build_and_internal_dump_ms", CinematicBuildMs}, {"cinematic_parse_ms", CinematicParseMs},
            {"full_report_serialize_ms", (WriteBegin - SerializeBegin) * 1000.},
            {"file_write_ms", (ReplaceBegin - WriteBegin) * 1000.},
            {"atomic_replace_ms", (ProfileEnd - ReplaceBegin) * 1000.},
            {"total_control_report_ms", (ProfileEnd - ProfileBegin) * 1000.},
            {"screenshot_requested", ScreenshotRequested}, {"screenshot_enqueue_ms", ScreenshotEnqueueMs},
            {"capture_semantics", "Enqueue measures only FScreenshotRequest dispatch. GPU readback, image encoding and file completion occur later; correlate native frame timings and external screenshot completion latency."}};
        LifecycleProfileReport = Text(Profile.dump());
    }
#endif
}

void AOldWestPlayerController::ServerSubmit_Implementation(const FString& Command, int32 ExpectedRevision, const FString& ExpectedMatch)
{
    const double Now = FPlatformTime::Seconds();
    if (Now - LastSubmission < 0.08) return;
    LastSubmission = Now;
    if (AOldWestGameMode* Mode = GetWorld()->GetAuthGameMode<AOldWestGameMode>()) Mode->Submit(this, Command, ExpectedRevision, ExpectedMatch);
}
void AOldWestPlayerController::ServerNewGame_Implementation(const FString& ExpectedMatch)
{
    if (AOldWestGameMode* Mode = GetWorld()->GetAuthGameMode<AOldWestGameMode>()) Mode->RequestNewGame(this, ExpectedMatch);
}
void AOldWestPlayerController::ServerRematch_Implementation()
{
    if (AOldWestGameMode* Mode = GetWorld()->GetAuthGameMode<AOldWestGameMode>()) Mode->RequestRematch(this);
}
void AOldWestPlayerController::ServerClaimSeat_Implementation(const FString& Token)
{
    if (AOldWestGameMode* Mode = GetWorld()->GetAuthGameMode<AOldWestGameMode>()) Mode->ClaimSeat(this, Token);
}
void AOldWestPlayerController::ClientRequestSeat_Implementation(const FString& ServerSession)
{
#if !UE_BUILD_SHIPPING
    // This RPC has a live post-travel driver, including after reconnects.
    // Apply the opt-in test timeout here as well as during BeginPlay.
    ConfigureLifecycleTimeout(GetWorld()->GetNetDriver());
#endif
    UOldWestGameInstance* GI = Cast<UOldWestGameInstance>(GetGameInstance());
    if (!GI) return;
    GI->PendingServerSession = ServerSession;
    Notice = TEXT("Confirming your seat...");
    ++ViewGeneration;
#if !UE_BUILD_SHIPPING
    if (FParse::Param(FCommandLine::Get(), TEXT("OldWestManualSeatClaim"))) return;
#endif
    const FString Endpoint = GI->PendingAddress.IsEmpty() ? AddressOf(GetWorld()->URL) : GI->PendingAddress;
    // A fresh server at the same address has a new public session ID. Never
    // send its predecessor's credential, and never put credentials in FURL.
    const bool SameSession = Endpoint == GI->LastAddress && ServerSession == GI->LastServerSession;
    ServerClaimSeat(SameSession ? GI->SeatToken : FString());
}
void AOldWestPlayerController::ClientSeatRejected_Implementation(const FString& Reason)
{
    if (UOldWestGameInstance* GI = Cast<UOldWestGameInstance>(GetGameInstance()))
    {
        GI->PendingAddress.Empty();
        GI->PendingServerSession.Empty();
        GI->SessionNotice = Reason;
#if !UE_BUILD_SHIPPING
        ++GI->SeatRejections;
#endif
    }
    ClearSessionView();
    UGameplayStatics::OpenLevel(this, FName(TEXT("/Game/Maps/WaterDepotV2")));
}
void AOldWestPlayerController::ClientWelcome_Implementation(int32 Seat, const FString& Token)
{
    AssignedSeat = Seat;
    if (!Token.IsEmpty() && GetNetMode() != NM_Client)
    {
        // A listen host's server disappears when its process exits. Retain the
        // useful remote-client profile rather than replacing it with this token.
        if (UOldWestGameInstance* GI = Cast<UOldWestGameInstance>(GetGameInstance()))
        {
            GI->PendingAddress.Empty();
            GI->PendingServerSession.Empty();
            GI->SessionNotice.Empty();
            Notice.Empty();
        }
        return;
    }
    if (!Token.IsEmpty())
        if (UOldWestGameInstance* GI = Cast<UOldWestGameInstance>(GetGameInstance()))
        {
            GI->SeatToken = Token;
            GI->LastAddress = GI->PendingAddress.IsEmpty() ? AddressOf(GetWorld()->URL) : GI->PendingAddress;
            GI->LastServerSession = GI->PendingServerSession;
            GI->PendingAddress.Empty();
            GI->PendingServerSession.Empty();
            GI->SessionNotice.Empty();
            Notice.Empty();
#if !UE_BUILD_SHIPPING
            if (GI->FirstTestToken.IsEmpty()) GI->FirstTestToken = Token;
#endif
            GI->SaveReconnectProfile();
            if (!GI->SessionNotice.IsEmpty()) Notice = GI->SessionNotice;
        }
}
void AOldWestPlayerController::DeliverSnapshot(const FString& Payload)
{
    // FString may serialize as wide characters. Keep each reliable RPC well
    // below Unreal's 64 KiB partial-bunch ceiling, including large turn journals.
    constexpr int32 PartChars=8192;
    const int32 Total=FMath::Max(1,FMath::DivideAndRoundUp(Payload.Len(),PartChars));
    const int32 Batch=++OutgoingSnapshotBatch;
    for(int32 Index=0;Index<Total;++Index)ClientSyncPart(Batch,Index,Total,Payload.Mid(Index*PartChars,PartChars));
}
void AOldWestPlayerController::ClientSyncPart_Implementation(int32 Batch,int32 Index,int32 Total,const FString& Part)
{
    if(Total<1||Total>16384||Index<0||Index>=Total||Part.Len()>8192||Batch<IncomingSnapshotBatch)return;
    if(Index==0) {
        IncomingSnapshotBatch=Batch;IncomingSnapshotTotal=Total;IncomingSnapshotPart=0;IncomingSnapshot.Empty();
    }
    if(Batch!=IncomingSnapshotBatch||Total!=IncomingSnapshotTotal||Index!=IncomingSnapshotPart)return;
    IncomingSnapshot+=Part;++IncomingSnapshotPart;
    if(IncomingSnapshotPart==IncomingSnapshotTotal) {
        // No view generation, rules revision, HUD or cinematic changes until
        // the complete public snapshot is reassembled and validated.
        ClientSync_Implementation(IncomingSnapshot);
        IncomingSnapshot.Empty();IncomingSnapshotPart=0;IncomingSnapshotTotal=0;
    }
}
void AOldWestPlayerController::ClientSync_Implementation(const FString& Payload)
{
    try
    {
        const J Data = J::parse(Utf8(Payload));
        if (Data.at("seat").get<int32>() != AssignedSeat) return;
        const FString IncomingMatch = Text(Data.at("match_id").get<std::string>());
        const int32 IncomingRevision = Data.at("view").at("revision");
        if (IncomingMatch == MatchId && IncomingRevision < Revision) return;
        if (IncomingMatch != MatchId)
        {
            TestFinished = false;
            TestDelay = 0.f;
            Notice.Empty();
            if (const UOldWestGameInstance* GI = Cast<UOldWestGameInstance>(GetGameInstance())) Notice = GI->SessionNotice;
        }
        MatchId = IncomingMatch;
        Revision = IncomingRevision;
    }
    catch (const std::exception&) { return; }
    Snapshot = Payload;
    PresentationSnapshot = Text(OldWestCosmetics::Present(J::parse(Utf8(Payload))).dump());
    ++ViewGeneration;
    if (Battlefield) Battlefield->ApplySnapshot(PresentationSnapshot);
}
void AOldWestPlayerController::ClientNotice_Implementation(const FString& Message)
{
    Notice = Message;
    ++ViewGeneration;
}
void AOldWestPlayerController::Submit(const FString& Command)
{
    Notice.Empty();
    ServerSubmit(Command, Revision, MatchId);
}
void AOldWestPlayerController::ClearSessionView()
{
    Snapshot.Empty();PresentationSnapshot.Empty();IncomingSnapshot.Empty();IncomingSnapshotBatch=-1;IncomingSnapshotPart=0;IncomingSnapshotTotal=0;
    MatchId.Empty();
    Revision = -1;
    AssignedSeat = INDEX_NONE;
    TestFinished = false;
    ++ViewGeneration;
}
void AOldWestPlayerController::HostMatch(const FString& Ruleset)
{
    FString LocalCatalog;
    bool Valid = false;
    if (FFileHelper::LoadFileToString(LocalCatalog, *(FPaths::ProjectContentDir() / TEXT("Data/cards.json"))))
    {
        try { Valid = J::parse(Utf8(LocalCatalog)).at("rulesets").contains(Utf8(Ruleset)); }
        catch (const std::exception&) { }
    }
    for (const TCHAR C : Ruleset) if (!FChar::IsAlnum(C) && C != TEXT('_')) Valid = false;
    if (!Valid) { ClientNotice(TEXT("That ruleset is not available in this game data.")); return; }
    if (UOldWestGameInstance* GI = Cast<UOldWestGameInstance>(GetGameInstance()))
    {
        GI->PendingAddress.Empty(); GI->PendingServerSession.Empty(); GI->SessionNotice.Empty();
    }
    ClearSessionView();
    UGameplayStatics::OpenLevel(this, FName(TEXT("/Game/Maps/WaterDepotV2")), true,
        TEXT("listen?Match=1?game=/Script/OldWestGame.OldWestGameMode?Ruleset=") + Ruleset);
}
void AOldWestPlayerController::StartSinglePlayer(const FString& Ruleset, const FString& Difficulty)
{
    FString LocalCatalog;
    bool Valid = false;
    if (FFileHelper::LoadFileToString(LocalCatalog, *(FPaths::ProjectContentDir() / TEXT("Data/cards.json"))))
    {
        try { Valid = J::parse(Utf8(LocalCatalog)).at("rulesets").contains(Utf8(Ruleset)); }
        catch (const std::exception&) { }
    }
    for (const TCHAR C : Ruleset) if (!FChar::IsAlnum(C) && C != TEXT('_')) Valid = false;
    if (!Valid) { ClientNotice(TEXT("That ruleset is not available in this game data.")); return; }
    if (Difficulty != TEXT("easy") && Difficulty != TEXT("normal") && Difficulty != TEXT("hard"))
    { ClientNotice(TEXT("Choose Easy, Normal, or Hard.")); return; }
    if (UOldWestGameInstance* GI = Cast<UOldWestGameInstance>(GetGameInstance()))
    {
        GI->PendingAddress.Empty();
        GI->PendingServerSession.Empty();
        GI->SessionNotice.Empty();
    }
    ClearSessionView();
    UGameplayStatics::OpenLevel(this, FName(TEXT("/Game/Maps/WaterDepotV2")), true,
        TEXT("SinglePlayer=1?game=/Script/OldWestGame.OldWestGameMode?Ruleset=") + Ruleset + TEXT("?AIDifficulty=") + Difficulty);
}
void AOldWestPlayerController::JoinMatch(const FString& Address)
{
    FString Host = Address.TrimStartAndEnd();
    bool ValidCharacters = !Host.IsEmpty() && Host.Len() <= 253;
    for (const TCHAR C : Host)
        if (!FChar::IsAlnum(C) && C != TEXT('.') && C != TEXT('-') && C != TEXT(':') && C != TEXT('[') && C != TEXT(']')) ValidCharacters = false;
    const FURL Parsed(nullptr, *(TEXT("unreal://") + Host), TRAVEL_Absolute);
    if (!ValidCharacters || !Parsed.Valid || Parsed.Host.IsEmpty() || Parsed.Port <= 0 || Parsed.Port > 65535)
    {
        ClientNotice(TEXT("Enter the host's address, such as 192.0.2.20:7777.")); return;
    }
    Host = AddressOf(Parsed);
    // Keep the protocol: without it, UE can interpret a bare DNS hostname as a
    // map or protocol name rather than a remote game endpoint.
    FString URL = TEXT("unreal://") + Host;
    if (UOldWestGameInstance* GI = Cast<UOldWestGameInstance>(GetGameInstance()))
    {
        // A failed attempt at another server must not destroy the previous seat.
        GI->PendingAddress = Host;
        GI->PendingServerSession.Empty();
        GI->SessionNotice.Empty();
    }
    ClearSessionView();
    Notice = TEXT("Connecting to the match...");
    ClientTravel(URL, TRAVEL_Absolute);
}
void AOldWestPlayerController::LeaveMatch()
{
    bool WasSolo = false;
    try { WasSolo = J::parse(Utf8(Snapshot)).value("mode", std::string()) == "single_player"; }
    catch (const std::exception&) { }
    if (UOldWestGameInstance* GI = Cast<UOldWestGameInstance>(GetGameInstance()))
    {
        GI->PendingAddress.Empty();
        GI->PendingServerSession.Empty();
        GI->SessionNotice = WasSolo || GI->LastAddress.IsEmpty() ? FString() : TEXT("Your seat is reserved. Join the same address to resume.");
    }
    ClearSessionView();
    UGameplayStatics::OpenLevel(this, FName(TEXT("/Game/Maps/WaterDepotV2")));
}
void AOldWestPlayerController::ToggleCamera()
{
    if (Battlefield) Battlefield->ToggleCamera();
}
void AOldWestPlayerController::NavigateBattlefieldCamera(float OrbitX, float OrbitY, float PanX, float PanY, float Zoom, float Elevation)
{
    if (Battlefield && !IsSoloPaused()) Battlefield->NavigateCamera(OrbitX, OrbitY, PanX, PanY, Zoom, Elevation);
}
void AOldWestPlayerController::ResetBattlefieldCamera()
{
    if (Battlefield) Battlefield->ResetCamera();
}
void AOldWestPlayerController::SetOverviewCamera(bool Enabled)
{
    if (Battlefield) Battlefield->SetOverviewCamera(Enabled);
}
bool AOldWestPlayerController::HasAnalysisChoiceView() const
{
    return Battlefield && Battlefield->HasAnalysisChoiceView();
}
bool AOldWestPlayerController::IsAnalysisChoiceFramed() const
{
    return Battlefield && Battlefield->IsAnalysisChoiceFramed();
}
void AOldWestPlayerController::SetAnalysisChoiceFramed(bool Framed)
{
    if (Battlefield) Battlefield->SetAnalysisChoiceFramed(Framed);
}
void AOldWestPlayerController::QuitGame()
{
    if (UOldWestGameInstance* GI = Cast<UOldWestGameInstance>(GetGameInstance())) GI->Preferences.Revert(GetWorld());
    UKismetSystemLibrary::QuitGame(this, this, EQuitPreference::Quit, false);
}
bool AOldWestPlayerController::IsCinematicBusy() const
{
    return Battlefield && Battlefield->IsCinematicBusy();
}
int32 AOldWestPlayerController::GetCinematicSequence() const
{
    return Battlefield ? Battlefield->GetCinematicSequence() : INDEX_NONE;
}
bool AOldWestPlayerController::IsSoloPaused() const
{
    return HUD.IsValid() && HUD->IsSoloPaused();
}
FString AOldWestPlayerController::GetCinematicCaption() const
{
    return Battlefield ? Battlefield->GetCinematicCaption() : FString();
}
void AOldWestPlayerController::SkipCinematics()
{
    if (Battlefield) Battlefield->SkipCinematics();
}
bool AOldWestPlayerController::InspectWorldAtScreen(const FVector2D& Position)
{
    const int32 Entity = OldWestWorldInteraction::PickVisibleUnitAtScreen(this, Position);
    return Entity != INDEX_NONE && HUD.IsValid() && HUD->InspectVisibleCard(Entity);
}
