#include "OldWestPreferences.h"
#include "AudioDevice.h"
#include "Engine/Engine.h"
#include "Engine/GameViewportClient.h"
#include "Engine/World.h"
#include "GameFramework/GameUserSettings.h"
#include "HAL/PlatformTime.h"
#include "Kismet/KismetSystemLibrary.h"
#include "Misc/CommandLine.h"
#include "Misc/ConfigCacheIni.h"
#include "Misc/Parse.h"
#include "UnrealClient.h"

namespace {
UGameUserSettings* UserSettings() { return GEngine ? GEngine->GetGameUserSettings() : nullptr; }
constexpr const TCHAR* AudioSection = TEXT("OldWest.Audio");
}

void FOldWestPreferences::Initialize()
{
    if (GConfig) GConfig->GetFloat(AudioSection, TEXT("MasterVolume"), Volume, GGameUserSettingsIni);
    if (GConfig) GConfig->GetBool(TEXT("OldWest.Interface"), TEXT("CardHover"), CardHover, GGameUserSettingsIni);
    Volume = FMath::IsFinite(Volume) ? FMath::Clamp(Volume, 0.f, 1.f) : 1.f;
    if(GConfig)GConfig->GetFloat(TEXT("OldWest.Interface"),TEXT("EnemySpeed"),EnemySpeed,GGameUserSettingsIni);
    EnemySpeed=FMath::IsFinite(EnemySpeed)?FMath::Clamp(EnemySpeed,.25f,2.f):.5f;
#if !UE_BUILD_SHIPPING
    const bool Automated = FParse::Param(FCommandLine::Get(), TEXT("OldWestTestBot"))
        || FParse::Param(FCommandLine::Get(), TEXT("OldWestLifecycleTest"))
        || FParse::Param(FCommandLine::Get(), TEXT("OldWestVisualTest"));
    FString IsolatedIni;
    PersistenceAllowed = !Automated || (FParse::Value(FCommandLine::Get(), TEXT("GameUserSettingsINI="), IsolatedIni)
        && !IsolatedIni.IsEmpty());
#endif
}

FOldWestPreferencesValues FOldWestPreferences::Read(UWorld* World) const
{
    FOldWestPreferencesValues Result;
    if (UGameUserSettings* Settings = UserSettings())
    {
        Result.Resolution = Settings->GetScreenResolution();
        Result.WindowMode = Settings->GetFullscreenMode();
        Result.Quality = Settings->GetOverallScalabilityLevel();
        Result.FrameLimit = Settings->GetFrameRateLimit();
    }
    // Command-line window size and an OS resize can differ from saved settings.
    if (!Pending && World && World->GetGameViewport() && World->GetGameViewport()->Viewport)
    {
        FViewport* Viewport = World->GetGameViewport()->Viewport;
        const FIntPoint Actual = Viewport->GetSizeXY();
        if (Actual.X > 0 && Actual.Y > 0) Result.Resolution = Actual;
        Result.WindowMode = Viewport->GetWindowMode();
    }
    Result.Volume = Volume;
    Result.CardHover = CardHover;
    return Result;
}

TArray<FIntPoint> FOldWestPreferences::Resolutions(UWorld* World) const
{
    TArray<FIntPoint> Available;
    UKismetSystemLibrary::GetSupportedFullscreenResolutions(Available);
    Available.AddUnique(FIntPoint(1280, 720));
    Available.AddUnique(FIntPoint(1600, 900));
    Available.AddUnique(FIntPoint(1920, 1080));
    Available.AddUnique(Read(World).Resolution);
    Available.RemoveAll([](const FIntPoint& Size) { return Size.X < 640 || Size.Y < 360 || Size.X > 7680 || Size.Y > 4320; });
    Available.Sort([](const FIntPoint& A, const FIntPoint& B) { return A.X == B.X ? A.Y < B.Y : A.X < B.X; });
    return Available;
}

bool FOldWestPreferences::Apply(UWorld* World, const FOldWestPreferencesValues& Values)
{
    UGameUserSettings* Settings = UserSettings();
    if (!Settings || Pending) return false;
    if (!PersistenceAllowed) { Status = TEXT("Settings are unavailable for this automated session."); ++ChangeGeneration; return false; }
    if (!Resolutions(World).Contains(Values.Resolution) || Values.WindowMode < EWindowMode::Fullscreen
        || Values.WindowMode > EWindowMode::Windowed || Values.Quality < -1 || Values.Quality > 3
        || !FMath::IsFinite(Values.FrameLimit) || Values.FrameLimit < 0.f || Values.FrameLimit > 360.f
        || !FMath::IsFinite(Values.Volume) || Values.Volume < 0.f || Values.Volume > 1.f)
    {
        Status = TEXT("Choose a supported display size and settings."); ++ChangeGeneration; return false;
    }
    Before = Read(World);
    BeforeQuality = Settings->ScalabilityQuality;
    Pending = Before.Resolution != Values.Resolution || Before.WindowMode != Values.WindowMode;
    Deadline = FPlatformTime::Seconds() + 15.;
    Settings->SetScreenResolution(Values.Resolution);
    Settings->SetFullscreenMode(Values.WindowMode);
    if (Values.Quality >= 0) Settings->SetOverallScalabilityLevel(Values.Quality);
    Settings->SetFrameRateLimit(Values.FrameLimit);
    Volume = Values.Volume;
    CardHover = Values.CardHover;
    // ApplySettings would save an unconfirmed display mode. Keep these separate.
    Settings->ApplyNonResolutionSettings();
    if (Pending) Settings->ApplyResolutionSettings(false);
    ApplyAudio(World);
    Status = Pending ? TEXT("Keep this display setting?") : TEXT("Settings saved.");
    if (!Pending) { Settings->ConfirmVideoMode(); Save(); }
    ++ChangeGeneration;
    return true;
}

void FOldWestPreferences::Keep()
{
    if (!Pending) return;
    Pending = false;
    if (UGameUserSettings* Settings = UserSettings()) Settings->ConfirmVideoMode();
    Save();
    Status = TEXT("Settings saved.");
    ++ChangeGeneration;
}

void FOldWestPreferences::Revert(UWorld* World)
{
    if (!Pending) return;
    Pending = false;
    if (UGameUserSettings* Settings = UserSettings())
    {
        Settings->SetScreenResolution(Before.Resolution);
        Settings->SetFullscreenMode(Before.WindowMode);
        Settings->ScalabilityQuality = BeforeQuality;
        Settings->SetFrameRateLimit(Before.FrameLimit);
        Settings->ApplyNonResolutionSettings();
        Settings->ApplyResolutionSettings(false);
        Settings->ConfirmVideoMode();
    }
    Volume = Before.Volume;
    CardHover = Before.CardHover;
    ApplyAudio(World);
    // UGameEngine::PreExit saves settings before UGameInstance::Shutdown.
    // Persist the restored values too, so a window close during a trial cannot
    // leave the engine's early shutdown save pointing at an unconfirmed mode.
    Save();
    Status = TEXT("Previous settings restored.");
    ++ChangeGeneration;
}

void FOldWestPreferences::Tick(UWorld* World)
{
    if (Pending && FPlatformTime::Seconds() >= Deadline) Revert(World);
}

int32 FOldWestPreferences::SecondsRemaining() const
{
    return Pending ? FMath::Max(0, FMath::CeilToInt(Deadline - FPlatformTime::Seconds())) : 0;
}

void FOldWestPreferences::ApplyAudio(UWorld* World) const
{
    if (World) if (FAudioDeviceHandle Device = World->GetAudioDevice()) Device->SetTransientPrimaryVolume(Volume);
}

void FOldWestPreferences::Save()
{
    if (!PersistenceAllowed) return;
    if (GConfig) GConfig->SetFloat(AudioSection, TEXT("MasterVolume"), Volume, GGameUserSettingsIni);
    if (GConfig) GConfig->SetBool(TEXT("OldWest.Interface"), TEXT("CardHover"), CardHover, GGameUserSettingsIni);
    if (GConfig) GConfig->SetFloat(TEXT("OldWest.Interface"),TEXT("EnemySpeed"),EnemySpeed,GGameUserSettingsIni);
    if (UGameUserSettings* Settings = UserSettings()) Settings->SaveSettings();
    if (GConfig) GConfig->Flush(false, GGameUserSettingsIni);
}

void FOldWestPreferences::SetEnemySpeed(float Value)
{
    if(!FMath::IsFinite(Value))return;
    EnemySpeed=FMath::Clamp(Value,.25f,2.f);
    Save();
}
