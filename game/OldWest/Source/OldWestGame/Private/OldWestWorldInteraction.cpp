#include "OldWestWorldInteraction.h"
#include "OldWestBattlefield.h"
#include "Components/SkeletalMeshComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "GameFramework/PlayerController.h"

int32 OldWestWorldInteraction::PickVisibleUnitAtScreen(APlayerController* Player, const FVector2D& Position)
{
    if (!IsValid(Player) || !Player->IsLocalController() || !Player->GetWorld()) return INDEX_NONE;
    int32 Width = 0, Height = 0;
    Player->GetViewportSize(Width, Height);
    if (!FMath::IsFinite(Position.X) || !FMath::IsFinite(Position.Y) ||
        Position.X < 0 || Position.Y < 0 || Position.X >= Width || Position.Y >= Height) return INDEX_NONE;
    FVector Origin, Direction;
    if (!Player->DeprojectScreenPositionToWorld(Position.X, Position.Y, Origin, Direction)) return INDEX_NONE;
    const FVector End = Origin + Direction.GetSafeNormal() * 100000.f;

    // Terrain and authored props occlude picks. Gameplay actors intentionally
    // have no visibility collision, so their presentation bounds are tested
    // separately without changing ground placement or ragdoll physics.
    FCollisionQueryParams Query(SCENE_QUERY_STAT(OldWestWorldPicking), true);
    for (TActorIterator<AOldWestUnit> It(Player->GetWorld()); It; ++It) Query.AddIgnoredActor(*It);
    FHitResult Occlusion;
    float Closest = Player->GetWorld()->LineTraceSingleByChannel(Occlusion, Origin, End, ECC_Visibility, Query)
        ? Occlusion.Time : 1.f;
    int32 Selected = INDEX_NONE;
    // Camp parts already expose their authored collision on the Camera
    // channel. A whole-camp box includes empty space below roofs/canopies and
    // can incorrectly intercept the ray over a visibly exposed person.
    FCollisionQueryParams CampQuery(SCENE_QUERY_STAT(OldWestCampPicking), true);
    for(TActorIterator<AOldWestUnit> It(Player->GetWorld());It;++It)
        if(!It->Camp||It->IsHidden()||It->IsPreviewOnly()||It->ActorHasTag(TEXT("OldWestPortraitPreview")))CampQuery.AddIgnoredActor(*It);
    FHitResult CampHit;
    if(Player->GetWorld()->LineTraceSingleByChannel(CampHit,Origin,End,ECC_Camera,CampQuery) && CampHit.Time<=Closest) {
        Closest=CampHit.Time;
        const AOldWestUnit* HitUnit=Cast<AOldWestUnit>(CampHit.GetActor());
        if(HitUnit&&HitUnit->Camp)Selected=HitUnit->EntityId;
    }
    for (TActorIterator<AOldWestUnit> It(Player->GetWorld()); It; ++It)
    {
        AOldWestUnit* Unit = *It;
        if (!IsValid(Unit) || Unit->Camp || Unit->ActorHasTag(TEXT("OldWestDragPreview")) || Unit->IsHidden() || Unit->IsPreviewOnly() || Unit->ActorHasTag(TEXT("OldWestPortraitPreview"))) continue;
        const UPrimitiveComponent* Surface = Unit->Camp
            ? static_cast<UPrimitiveComponent*>(Unit->Structure.Get())
            : static_cast<UPrimitiveComponent*>(Unit->Body.Get());
        if (!Surface || (!Unit->Camp && !Unit->IsEventToken() && !Surface->IsVisible())) continue;
        const FBox Bounds = Unit->GetSelectionBounds();
        FVector HitLocation, HitNormal;
        float HitTime = 1.f;
        if (Bounds.IsValid && FMath::LineExtentBoxIntersection(Bounds, Origin, End, FVector::ZeroVector,
            HitLocation, HitNormal, HitTime) && HitTime >= 0.f && HitTime < Closest)
        {
            Closest = HitTime;
            Selected = Unit->EntityId;
        }
    }
    return Selected;
}
