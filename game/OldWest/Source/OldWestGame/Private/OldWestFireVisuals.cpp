#include "OldWestFireVisuals.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "GameFramework/Actor.h"
#include "Materials/MaterialInterface.h"
#include "Materials/MaterialInstanceDynamic.h"

FBoxSphereBounds UOldWestFireSheet::CalcBounds(const FTransform& LocalToWorld) const
{
    // The shader derives these dimensions from transformed native 100 cm axes.
    // BoundsScale alone cannot expand a zero-thickness plane into its swept
    // yaw/tilt volume, and would disappear at some orbit/capture angles.
    const double Width = LocalToWorld.TransformVector(FVector(100, 0, 0)).Size();
    const double Height = LocalToWorld.TransformVector(FVector(0, 100, 0)).Size();
    const FVector Base = LocalToWorld.GetLocation() - FVector(0, 0, Height * .5);
    const double Radius = Width * .56 + Height * .60;
    return FBoxSphereBounds(FBox(Base - FVector(Radius, Radius, 1),
        Base + FVector(Radius, Radius, Height * (Smoke ? 1.45 : 1.) + 1)));
}

UOldWestFireVisuals::UOldWestFireVisuals()
{
    PrimaryComponentTick.bCanEverTick = true;
    PrimaryComponentTick.bStartWithTickEnabled = false;
    PrimaryComponentTick.TickInterval = 1.f / 30.f;
}

void UOldWestFireVisuals::ClearSheets()
{
    for (UOldWestFireSheet* Sheet : Sheets) if (IsValid(Sheet)) Sheet->DestroyComponent();
    Sheets.Reset(); Instances.Reset(); Phases.Reset(); Rates.Reset(); SmokeOrigins.Reset();
}

void UOldWestFireVisuals::OnComponentDestroyed(bool bDestroyingHierarchy)
{
    ClearSheets();
    Super::OnComponentDestroyed(bDestroyingHierarchy);
}

void UOldWestFireVisuals::Build(float WidthCm, float HeightCm, float Phase,
    float EmissionScale, bool IncludeSmoke, bool RuinPlume)
{
    ClearSheets();
    IsExtinguished = false;
    SmokeOnly = false;
    IsRuinPlume = RuinPlume;
    SmokeClock = Phase * 7.f;
    SmokeWidth = WidthCm;
    SmokeRise = HeightCm;
    SetComponentTickEnabled(RuinPlume);
    AActor* Owner = GetOwner();
    UStaticMesh* Plane = LoadObject<UStaticMesh>(nullptr, TEXT("/Engine/BasicShapes/Plane.Plane"));
    UMaterialInterface* Fire = LoadObject<UMaterialInterface>(nullptr,
        TEXT("/Game/Art/Effects/Materials/M_Fire_Flipbook.M_Fire_Flipbook"));
    UMaterialInterface* Smoke = IncludeSmoke ? LoadObject<UMaterialInterface>(nullptr,
        RuinPlume ? TEXT("/Game/Art/Camps/Ruins/M_Ruin_Smoke.M_Ruin_Smoke") :
        TEXT("/Game/Art/Effects/Materials/M_Smoke_Flipbook.M_Smoke_Flipbook")) : nullptr;
    if (!Owner || !Plane || !Fire || (IncludeSmoke && !Smoke))
    {
        UE_LOG(LogTemp, Error, TEXT("OLDWEST_FIRE_VISUAL_ERROR Missing owner/plane/flipbook material"));
        return;
    }
    WidthCm = FMath::Max(5.f, WidthCm);
    HeightCm = FMath::Max(5.f, HeightCm);
    for (int32 I = 0; I < (RuinPlume ? 21 : IncludeSmoke ? 5 : 3); ++I)
    {
        const bool IsSmoke = I >= 3;
        const float Width = RuinPlume && IsSmoke ? WidthCm * (.42f + .09f * ((I-3)%3)) : IsSmoke ? HeightCm * .65f : WidthCm * (I == 1 ? 1.05f : .88f);
        const float Height = RuinPlume && IsSmoke ? HeightCm * (.68f + .14f * ((I-3)%3)) : IsSmoke ? HeightCm * .65f : HeightCm * (I == 1 ? 1.f : .90f);
        const float LayerPhase = Phase + (IsSmoke ? .13f + (I - 3) * (RuinPlume ? .167f : .5f) : I / 3.f);
        const float Rate = IsSmoke ? (RuinPlume ? .075f : .11f) : .36f;
        // Offset within the fuel footprint, never bob the entire fire off its
        // base. The smoke material alone adds a bounded rising displacement.
        const FVector Base = RuinPlume && IsSmoke ?
            FVector(((I-3)%3-1) * WidthCm * .16f, ((I-3)%3 == 1 ? .16f : -.13f) * WidthCm, 0) : IsSmoke ? FVector((I - 3.5f) * WidthCm * .09f, WidthCm * .06f, HeightCm * .60f) :
            FVector((I - 1) * WidthCm * .15f, (I == 1 ? -.08f : .06f) * WidthCm, 0);
        UOldWestFireSheet* Sheet = NewObject<UOldWestFireSheet>(Owner);
        Owner->AddInstanceComponent(Sheet);
        Sheet->SetupAttachment(this);
        Sheet->Smoke = IsSmoke;
        Sheet->SetStaticMesh(Plane);
        Sheet->SetRelativeLocation(Base + FVector(0, 0, Height * .5f));
        Sheet->SetRelativeRotation(FRotator(0, 0, 90));
        Sheet->SetRelativeScale3D(FVector(Width / 100.f, Height / 100.f, 1));
        Sheet->SetCollisionEnabled(ECollisionEnabled::NoCollision);
        Sheet->SetCanEverAffectNavigation(false);
        // A single portrait must retain the same atlas detail as a full gallery.
        // These two small shared flipbooks use custom shader UVs; distance-only
        // streaming otherwise left just a 64px sheet for every animation frame.
        // Component residency respects the resource's allowed mip/LOD limits.
        Sheet->bForceMipStreaming = true;
        Sheet->SetCastShadow(false);
        Sheet->SetReceivesDecals(false);
        Sheet->SetTranslucentSortPriority(IsSmoke ? 0 : 1);
        UMaterialInstanceDynamic* Instance = UMaterialInstanceDynamic::Create(IsSmoke ? Smoke : Fire, Sheet);
        Instance->SetScalarParameterValue(TEXT("EmissionScale"), EmissionScale);
        Instance->SetScalarParameterValue(TEXT("Phase"), LayerPhase);
        Instance->SetScalarParameterValue(TEXT("CyclesPerSecond"), Rate);
        Instance->SetScalarParameterValue(TEXT("OpacityScale"), IsSmoke ? .23f : .58f);
        Instance->SetScalarParameterValue(TEXT("SoftIntersectionCm"), FMath::Max(1.f, Height * .025f));
        Sheet->SetMaterial(0, Instance);
        Sheet->RegisterComponent();
        Sheets.Add(Sheet); Instances.Add(Instance); Phases.Add(LayerPhase); Rates.Add(Rate); SmokeOrigins.Add(Base);
    }
    if (IsRuinPlume) UpdateSmokeParticles(0.f);
}

void UOldWestFireVisuals::UpdateSmokeParticles(float DeltaTime)
{
    SmokeClock += DeltaTime;
    for (int32 I = 3; I < Sheets.Num(); ++I)
    {
        if (!IsValid(Sheets[I]) || !IsValid(Instances[I])) continue;
        const int32 Particle = I - 3;
        const float Life = 5.8f + FMath::Fmod(Particle * 1.713f, 2.6f);
        const float Age = FMath::Fmod(SmokeClock + FMath::Fmod(Particle * .618034f, 1.f) * Life, Life);
        const float T = Age / Life;
        const float Width = SmokeWidth * (.24f + .012f * (Particle % 4)) * (.50f + T * 2.1f);
        const float Height = Width * 1.2f;
        // Buoyant puffs visibly rise, spread and curl downwind. New puffs
        // replace dissipated ones at each of three independent fuel sources.
        const float Curl = FMath::Sin(Age * 1.8f + Particle * 1.73f) - FMath::Sin(Particle * 1.73f);
        FVector Base = SmokeOrigins[I];
        Base.X += FMath::Sin(Particle * 2.39f) * SmokeWidth * .045f;
        Base.Y += FMath::Cos(Particle * 1.73f) * SmokeWidth * .045f;
        Base.X += SmokeWidth * .50f * T * T + Curl * 13.f * T;
        Base.Y += SmokeWidth * .18f * T + FMath::Sin(Age * 1.3f + Particle) * 10.f * T;
        Base.Z += SmokeRise * T;
        Sheets[I]->SetRelativeLocation(Base + FVector(0, 0, Height * .5f));
        Sheets[I]->SetRelativeScale3D(FVector(Width / 100.f, Height / 100.f, 1.f));
        Instances[I]->SetScalarParameterValue(TEXT("CyclesPerSecond"), 0.f);
        Instances[I]->SetScalarParameterValue(TEXT("Phase"), T);
        Phases[I] = T;
        Rates[I] = 0.f;
        if (I == 3) SmokeSample = FVector(Age, Base.Z, Width);
    }
}

void UOldWestFireVisuals::TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* ThisTickFunction)
{
    Super::TickComponent(DeltaTime, TickType, ThisTickFunction);
    if (IsRuinPlume && !IsExtinguished && IsVisible()) UpdateSmokeParticles(DeltaTime);
}

FVector UOldWestFireVisuals::GetSmokeSample() const
{
    return IsRuinPlume && !IsExtinguished ? SmokeSample : FVector::ZeroVector;
}

void UOldWestFireVisuals::SetExtinguished(bool Extinguished)
{
    IsExtinguished = Extinguished;
    SetComponentTickEnabled(IsRuinPlume && !Extinguished && IsVisible());
    for (UOldWestFireSheet* Sheet : Sheets)
        if (IsValid(Sheet)) Sheet->SetVisibility(!Extinguished && IsVisible() && (!SmokeOnly || Sheet->Smoke));
}

void UOldWestFireVisuals::SetSmokeOnly(bool Enabled, float Opacity)
{
    if (SmokeOnly != Enabled && !IsRuinPlume)
    {
        for (UOldWestFireSheet* Sheet : Sheets)
            if (IsValid(Sheet) && Sheet->Smoke)
            {
                const float Height = Sheet->GetRelativeScale3D().Y * 100.f;
                Sheet->AddRelativeLocation(FVector(0, 0, (Enabled ? -1.f : 1.f) * Height * (.60f / .65f)));
            }
    }
    SmokeOnly=Enabled;
    for(int32 I=0;I<Sheets.Num();++I)if(IsValid(Sheets[I])&&Sheets[I]->Smoke&&Instances.IsValidIndex(I)&&IsValid(Instances[I]))
        Instances[I]->SetScalarParameterValue(TEXT("OpacityScale"),Opacity >= 0.f ? FMath::Clamp(Opacity, 0.f, 1.f) : Enabled?(IsRuinPlume?.72f:.55f):.23f);
    SetExtinguished(IsExtinguished);
}

void UOldWestFireVisuals::OnVisibilityChanged()
{
    Super::OnVisibilityChanged();
    // Restore sheet flags even when callers show the parent without requesting
    // visibility propagation after extinguishing it while hidden.
    SetExtinguished(IsExtinguished);
}

void UOldWestFireVisuals::SetEmissionScale(float Scale, float SmokeScale)
{
    // Portraits retain the all-layer override. World flame radiance can be
    // calibrated independently without turning dark smoke into emissive fog.
    const float ResolvedSmokeScale = SmokeScale < 0.f ? Scale : SmokeScale;
    for (int32 I = 0; I < Instances.Num(); ++I)
        if (IsValid(Instances[I]) && Sheets.IsValidIndex(I) && IsValid(Sheets[I]))
            Instances[I]->SetScalarParameterValue(TEXT("EmissionScale"),
                FMath::Max(0.f, Sheets[I]->Smoke ? ResolvedSmokeScale : Scale));
}

int32 UOldWestFireVisuals::GetVisiblePartCount() const
{
    int32 Count = 0;
    for (const UOldWestFireSheet* Sheet : Sheets) if (IsValid(Sheet) && Sheet->IsVisible()) ++Count;
    return Count;
}

uint32 UOldWestFireVisuals::GetAnimationSignature() const
{
    if (IsExtinguished || !GetWorld()) return 0;
    // These are the actual material Time/Rate/Phase inputs; transform-only
    // telemetry cannot observe shader animation. Rendered pixel motion remains
    // an independent requirement in the portrait harness.
    const double Time = GetWorld()->GetTimeSeconds();
    uint32 Result = 0;
    for (int32 I = 0; I < Sheets.Num(); ++I)
    {
        const double Cycle = Time * Rates[I] + Phases[I];
        const int32 InterpolatedFrame = FMath::FloorToInt((Cycle - FMath::FloorToDouble(Cycle)) * (I >= 3 ? 63. : 35.) * 1024.);
        Result = HashCombineFast(Result, GetTypeHash(InterpolatedFrame));
    }
    return Result;
}

void UOldWestFireVisuals::AppendPortraitFlamePoints(const FVector& CameraLocation, TArray<FVector>& Points) const
{
    for (const UOldWestFireSheet* Sheet : Sheets)
    {
        if (!IsValid(Sheet) || !Sheet->IsVisible() || Sheet->Smoke) continue;
        const FTransform& Transform = Sheet->GetComponentTransform();
        const double Width = Transform.TransformVector(FVector(100, 0, 0)).Size();
        const double Height = Transform.TransformVector(FVector(0, 100, 0)).Size();
        const FVector Base = Transform.GetLocation() - FVector(0, 0, Height * .5);
        const FVector View = CameraLocation - Base;
        const double Horizontal = FMath::Max(View.Size2D(), .001);
        const FVector Toward = Horizontal < .01 ? FVector(0, -1, 0) : FVector(View.X / Horizontal, View.Y / Horizontal, 0);
        const FVector Right(-Toward.Y, Toward.X, 0);
        const double Tilt = FMath::Clamp(FMath::Atan2(View.Z, Horizontal), 0., .6108652382);
        const FVector Up = FVector(0, 0, FMath::Cos(Tilt)) - Toward * FMath::Sin(Tilt);
        // Same world axes, base and per-view tilt as M_Fire_Flipbook WPO.
        // At normalized height y, abs(drift) <= .045*Width*y*y.
        // Since y*y <= y on [0,1], this trapezoid encloses every phase
        // and the entire sheet, including transparent atlas padding.
        Points.Add(Base - Right * (Width * .5));
        Points.Add(Base + Right * (Width * .5));
        Points.Add(Base + Up * Height - Right * (Width * .545));
        Points.Add(Base + Up * Height + Right * (Width * .545));
    }
}

FBox UOldWestFireVisuals::GetVisualBounds() const
{
    FBox Result(ForceInit);
    for (const UOldWestFireSheet* Sheet : Sheets)
        if (IsValid(Sheet) && Sheet->IsVisible()) Result += Sheet->Bounds.GetBox();
    return Result;
}
