#pragma once

#include "CoreMinimal.h"
#include "GenericPlatform/GenericWindow.h"
#include "Scalability.h"

class UWorld;

struct FOldWestPreferencesValues
{
    FIntPoint Resolution = FIntPoint(1920, 1080);
    EWindowMode::Type WindowMode = EWindowMode::Windowed;
    int32 Quality = 3;
    float FrameLimit = 60.f;
    float Volume = 1.f;
    bool CardHover = true;
};

// Local presentation preferences. Owned by the game instance so a display trial
// still expires while a controller is replaced during travel or disconnection.
class FOldWestPreferences
{
public:
    void Initialize();
    FOldWestPreferencesValues Read(UWorld* World) const;
    TArray<FIntPoint> Resolutions(UWorld* World) const;
    bool Apply(UWorld* World, const FOldWestPreferencesValues& Values);
    void Keep();
    void Revert(UWorld* World);
    void Tick(UWorld* World);
    void ApplyAudio(UWorld* World) const;
    bool IsPending() const { return Pending; }
    int32 SecondsRemaining() const;
    int32 Generation() const { return ChangeGeneration; }
    const FString& Message() const { return Status; }
    bool CanPersist() const { return PersistenceAllowed; }
    float GetEnemySpeed() const { return EnemySpeed; }
    void SetEnemySpeed(float Value);
private:
    void Save();
    FOldWestPreferencesValues Before;
    Scalability::FQualityLevels BeforeQuality;
    float Volume = 1.f;
    bool CardHover = true;
    float EnemySpeed = .5f;
    double Deadline = 0.;
    int32 ChangeGeneration = 0;
    bool Pending = false;
    bool PersistenceAllowed = true;
    FString Status;
};
