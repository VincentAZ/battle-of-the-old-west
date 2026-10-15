#include "OldWestRegion.h"
#include "OldWestBattlefield.h"
#include "Components/StaticMeshComponent.h"
#include "Components/HierarchicalInstancedStaticMeshComponent.h"
#include "Engine/StaticMeshActor.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "Materials/MaterialInterface.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "Core/json.hpp"
#include "OldWestRegionalPlacements.inl"

namespace
{
const TCHAR* Names[]={TEXT("Sonoran Desert"),TEXT("Black Hills pine"),TEXT("River bottomland")};
const TCHAR* Grounds[]={TEXT("DesertGround"),TEXT("PineGround"),TEXT("RiverGround")};
UMaterialInterface* Material(const FString& Name)
{
    const FString Path=TEXT("/Game/Art/Western/Regions/Materials/M_Region_")+Name+TEXT(".M_Region_")+Name;
    return LoadObject<UMaterialInterface>(nullptr,*Path);
}
UStaticMesh* Mesh(const FString& Name)
{
    const FString Path=TEXT("/Game/Art/Western/Regions/Meshes/SM_Region_")+Name+TEXT(".SM_Region_")+Name;
    auto* Result=LoadObject<UStaticMesh>(nullptr,*Path);
    if(!Result)UE_LOG(LogTemp,Error,TEXT("OLDWEST_REGION_ERROR Missing %s"),*Path);
    return Result;
}
bool IsRouteScenery(const AStaticMeshActor* Actor)
{
    const auto* Component=Actor->GetStaticMeshComponent();
    const UStaticMesh* Asset=Component?Component->GetStaticMesh():nullptr;
    return Asset&&(Asset->GetPathName()==TEXT("/Game/Art/WaterDepotV2/Meshes/SM_rock_07.SM_rock_07")||
                   Asset->GetPathName()==TEXT("/Game/Art/WaterDepotV2/Meshes/SM_coast_rocks_05.SM_coast_rocks_05"));
}
TArray<FBox> TroubleRoutes()
{
    TArray<FBox> Routes;
    for(int32 Side=0;Side<2;++Side)
    {
        const float Direction=Side==0?1.f:-1.f;
        const FVector End=AOldWestBattlefield::EventPosition(Side,-1);
        const FVector Last=AOldWestBattlefield::EventPosition(Side,2);
        FBox Box(ForceInit);
        Box+=End;Box+=Last;
        Box+=Last+FVector(230*Direction,220,0); // Existing entry staging.
        Box+=End+FVector(240*Direction,0,0);
        Box+=End+FVector(240*Direction,1860*Direction,0); // Entire grounded fuse.
        // Current Trouble miniatures fit a 190cm maximum horizontal dimension. Retain
        // 25cm clearance beyond their half-extent; no queue position changes.
        Routes.Add(Box.ExpandBy(FVector(120,120,0)));
    }
    return Routes;
}
bool OverlapsRoute(const FVector& Center,const FVector& Extent,const TArray<FBox>& Routes)
{
    for(const FBox& Route:Routes)
        if(Center.X+Extent.X>=Route.Min.X&&Center.X-Extent.X<=Route.Max.X&&
           Center.Y+Extent.Y>=Route.Min.Y&&Center.Y-Extent.Y<=Route.Max.Y)return true;
    return false;
}
}

AOldWestRegion::AOldWestRegion()
{
    RootComponent=CreateDefaultSubobject<USceneComponent>(TEXT("RegionRoot"));
    PrimaryActorTick.bCanEverTick=false;
}

void AOldWestRegion::Clear()
{
    for(const auto& Pair:RouteRocks)if(AActor* Actor=Pair.Key.Get())
    {
        Actor->SetActorHiddenInGame(Pair.Value.Hidden);
        Actor->SetActorEnableCollision(Pair.Value.Collision);
    }
    RouteRocks.Reset();
    LandingFoundations.Reset();
    if(IsValid(LandingTerrain))LandingTerrain->SetMaterial(0,LandingOriginalMaterial);
    LandingMaterial=nullptr;LandingOriginalMaterial=nullptr;LandingTerrain=nullptr;
    if(IsValid(Terrain))
    {
        Terrain->SetMaterial(0,OriginalMaterial);
        Terrain->SetVisibility(OriginalVisible);
    }
    for(const auto& Part:Parts)if(IsValid(Part))Part->DestroyComponent();
    for(const auto& Part:Trees)if(IsValid(Part))Part->DestroyComponent();
    Parts.Reset();Trees.Reset();TreeCount=0;Terrain=nullptr;OriginalMaterial=nullptr;
}

void AOldWestRegion::ClearTroubleRoutes()
{
    // Cosmetic exclusions for a reconstructed landscape, not a change to the
    // terrain or authoritative board. Restore map actors when the scene ends.
    // Evidence: art/western/trouble/route-clearance-v001/brief.json.
    const auto Routes=TroubleRoutes();
    for(TActorIterator<AStaticMeshActor> It(GetWorld());It;++It)
    {
        if(!IsRouteScenery(*It))continue;
        FVector Center,Extent;It->GetActorBounds(false,Center,Extent);
        if(!OverlapsRoute(Center,Extent,Routes))continue;
        RouteRocks.Add(TWeakObjectPtr<AActor>(*It),{It->IsHidden(),It->GetActorEnableCollision()});
        It->SetActorHiddenInGame(true);
        It->SetActorEnableCollision(false);
    }
}

void AOldWestRegion::SetLandingFoundation(UObject* Key, const FVector& Origin, const FVector& Frame, bool Enabled)
{
    if(!Key)return;
    const TWeakObjectPtr<UObject> WeakKey(Key);
    if(!Enabled)
    {
        if(LandingFoundations.Remove(WeakKey))UpdateLandingFoundations();
        return;
    }
    if(const auto* Previous=LandingFoundations.Find(WeakKey))
        if(Previous->Origin.Equals(Origin,.001)&&Previous->Frame.Equals(Frame,.001))return;
    LandingFoundations.Add(WeakKey,{Origin,Frame});
    UpdateLandingFoundations();
}

void AOldWestRegion::UpdateLandingFoundations()
{
    for(auto It=LandingFoundations.CreateIterator();It;++It)
        if(!It.Key().IsValid())It.RemoveCurrent();
    if(LandingFoundations.IsEmpty())
    {
        if(IsValid(LandingTerrain))LandingTerrain->SetMaterial(0,LandingOriginalMaterial);
        LandingMaterial=nullptr;LandingOriginalMaterial=nullptr;LandingTerrain=nullptr;
        return;
    }
    if(!LandingMaterial)
    {
        LandingTerrain=Region==2&&Parts.Num()>0?Parts[0]:Terrain;
        if(!IsValid(LandingTerrain)||Region<0)return;
        const TCHAR* Name=Region==0?TEXT("Desert"):Region==1?TEXT("Pine"):TEXT("River");
        const FString Asset=FString(TEXT("M_LandingTerrain_"))+Name;
        const FString Path=TEXT("/Game/Art/Western/ExpansionHoldings/LandingTerrainFitV002/")+Asset+TEXT(".")+Asset;
        auto* Material=LoadObject<UMaterialInterface>(nullptr,*Path);
        if(!Material)return;
        LandingOriginalMaterial=LandingTerrain->GetMaterial(0);
        LandingMaterial=UMaterialInstanceDynamic::Create(Material,this);
        LandingTerrain->SetMaterial(0,LandingMaterial);
    }
    int32 Slot=0;
    for(const auto& Pair:LandingFoundations)
    {
        if(Slot>=6)break; // At most the six public holding positions.
        LandingMaterial->SetVectorParameterValue(*FString::Printf(TEXT("LandingOrigin%d"),Slot),FLinearColor(Pair.Value.Origin));
        LandingMaterial->SetVectorParameterValue(*FString::Printf(TEXT("LandingFrame%d"),Slot),
            FLinearColor(Pair.Value.Frame));
        ++Slot;
    }
    for(;Slot<6;++Slot)
        LandingMaterial->SetVectorParameterValue(*FString::Printf(TEXT("LandingFrame%d"),Slot),FLinearColor::Transparent);
}

void AOldWestRegion::ApplyMatch(const FString& Match)
{
    if(Match.IsEmpty()||Match==SeenMatch)return;
    Clear();SeenMatch=Match;
    // Explicit byte hash is stable across platforms and both seats. No random
    // draw from the authoritative rules engine is consumed by scenery.
    uint32 Hash=2166136261u;
    for(TCHAR C:Match){Hash^=static_cast<uint32>(C);Hash*=16777619u;}
    Region=Hash%3;
#if !UE_BUILD_SHIPPING
    // Review-only override requires the existing visual-test flag. Ordinary
    // games always select exactly one scene from their public match identity.
    int32 Review=-1;
    if(FParse::Param(FCommandLine::Get(),TEXT("OldWestVisualTest"))&&
       FParse::Value(FCommandLine::Get(),TEXT("OldWestRegionReview="),Review)&&Review>=0&&Review<3)Region=Review;
#endif
    for(TActorIterator<AStaticMeshActor> It(GetWorld());It;++It)
    {
        auto* Component=It->GetStaticMeshComponent();
        if(Component&&Component->GetStaticMesh()&&Component->GetStaticMesh()->GetName()==TEXT("SM_ContinuousTerrain"))
        {Terrain=Component;break;}
    }
    if(!Terrain){UE_LOG(LogTemp,Error,TEXT("OLDWEST_REGION_ERROR Missing continuous terrain"));return;}
    OriginalMaterial=Terrain->GetMaterial(0);OriginalVisible=Terrain->IsVisible();
    auto* Ground=Material(Grounds[Region]);
    if(!Ground){UE_LOG(LogTemp,Error,TEXT("OLDWEST_REGION_ERROR Missing regional ground material"));return;}
    if(Region!=2)Terrain->SetMaterial(0,Ground);
    else
    {
        for(const TCHAR* Name:{TEXT("RiverTerrain"),TEXT("RiverWater")})
        {
            auto* Asset=Mesh(Name);if(!Asset)continue;
            auto* Part=NewObject<UStaticMeshComponent>(this);AddInstanceComponent(Part);
            Part->SetupAttachment(RootComponent);Part->SetStaticMesh(Asset);
            Part->SetWorldTransform(Terrain->GetComponentTransform());
            Part->SetCollisionEnabled(ECollisionEnabled::NoCollision);Part->SetCanEverAffectNavigation(false);
            Part->RegisterComponent();Parts.Add(Part);
        }
        if(Parts.Num()==2)Terrain->SetVisibility(false); // Collider remains unchanged.
    }
    ClearTroubleRoutes();
    if(Region==0)
    {
        // Source-grounded decorative dunes and cacti; the original playing
        // surface and collider remain untouched. See desert-v002.json.
        for(const TCHAR* Name:{TEXT("DesertDuneV004_0"),TEXT("DesertDuneV004_1"),TEXT("DesertCactiV004")})
        {
            auto* Asset=Mesh(Name);if(!Asset)continue;
            auto* Part=NewObject<UStaticMeshComponent>(this);AddInstanceComponent(Part);
            Part->SetupAttachment(RootComponent);Part->SetStaticMesh(Asset);
            Part->SetWorldTransform(FTransform::Identity);
            Part->SetCollisionEnabled(ECollisionEnabled::NoCollision);Part->SetCanEverAffectNavigation(false);
            Part->RegisterComponent();Parts.Add(Part);
        }
    }
    // A broad clear playing area and walk-in routes stay free of new geometry.
    // Noncolliding HISM scenery remains beyond that area, including at maximum
    // crown extent. Natural woodland spacing replaces solid rings of trees.
    if(Region>0)
    {
        const int32 Variants=3;
        for(int32 I=0;I<Variants;++I)
        {
            FString Name=Region==1?FString::Printf(TEXT("Ponderosa%d"),I):
                (I==2?FString(TEXT("Willow")):FString::Printf(TEXT("Cottonwood%d"),I));
            auto* Asset=Mesh(Name);if(!Asset)continue;
            auto* Part=NewObject<UHierarchicalInstancedStaticMeshComponent>(this);AddInstanceComponent(Part);
            Part->SetupAttachment(RootComponent);Part->SetStaticMesh(Asset);
            Part->SetCollisionEnabled(ECollisionEnabled::NoCollision);Part->SetCanEverAffectNavigation(false);
            Part->RegisterComponent();Trees.Add(Part);
        }
        // Pre-grounded from the actual source surface; the deliberately small
        // gameplay collider cannot trace the distant woodland terrain.
        const TArrayView<const FRegionalTreePlacement> Placements=Region==1?
            MakeArrayView(PineTrees):MakeArrayView(RiverTrees);
        for(const auto& P:Placements)
        {
            if(!Trees.IsValidIndex(P.Variant))continue;
            Trees[P.Variant]->AddInstance(FTransform(FRotator(0,P.Yaw,0),FVector(P.X,P.Y,P.Z),FVector(P.Scale)),true);
            ++TreeCount;
        }
    }
    UE_LOG(LogTemp,Display,TEXT("OLDWEST_REGION_READY %s trees=%d"),Names[Region],TreeCount);
}

FString AOldWestRegion::GetDebug() const
{
    using J=nlohmann::ordered_json;
    bool Noncolliding=true;
    for(const auto& Part:Parts)Noncolliding&=Part->GetCollisionEnabled()==ECollisionEnabled::NoCollision;
    for(const auto& Part:Trees)Noncolliding&=Part->GetCollisionEnabled()==ECollisionEnabled::NoCollision;
    J Result={{"index",Region},{"name",Region>=0?TCHAR_TO_UTF8(Names[Region]):""},
        {"match_id",TCHAR_TO_UTF8(*SeenMatch)},{"tree_count",TreeCount},{"visual_parts",Parts.Num()},
        {"noncolliding_scenery",Noncolliding},{"original_collider_retained",IsValid(Terrain)&&Terrain->GetCollisionEnabled()!=ECollisionEnabled::NoCollision}};
    Result["landing_foundations"]=J::array();
    const auto Routes=TroubleRoutes();
    Result["trouble_routes"]=J::array();
    for(const FBox& Box:Routes)Result["trouble_routes"].push_back({
        {"min_xy",{Box.Min.X,Box.Min.Y}},{"max_xy",{Box.Max.X,Box.Max.Y}}});
    Result["route_rocks"]=J::array();
    int32 VisibleRouteRocks=0,SceneryRocks=0;
    for(TActorIterator<AStaticMeshActor> It(GetWorld());It;++It)
    {
        if(!IsRouteScenery(*It))continue;
        ++SceneryRocks;
        FVector Center,Extent;It->GetActorBounds(false,Center,Extent);
        if(!OverlapsRoute(Center,Extent,Routes))continue;
        if(!It->IsHidden()&&It->GetStaticMeshComponent()->IsVisible())++VisibleRouteRocks;
        const auto* Original=RouteRocks.Find(TWeakObjectPtr<AActor>(*It));
        Result["route_rocks"].push_back({{"actor",TCHAR_TO_UTF8(*It->GetName())},
            {"center",{Center.X,Center.Y,Center.Z}},{"extent",{Extent.X,Extent.Y,Extent.Z}},
            {"hidden",It->IsHidden()},{"collision",It->GetActorEnableCollision()},
            {"original_hidden",Original?Original->Hidden:It->IsHidden()},
            {"original_collision",Original?Original->Collision:It->GetActorEnableCollision()}});
    }
    Result["scenery_rock_count"]=SceneryRocks;
    Result["visible_route_rocks"]=VisibleRouteRocks;
    for(const auto& Pair:LandingFoundations)
        if(Pair.Key.IsValid())Result["landing_foundations"].push_back({
            {"origin",{Pair.Value.Origin.X,Pair.Value.Origin.Y,Pair.Value.Origin.Z}},
            {"frame",{Pair.Value.Frame.X,Pair.Value.Frame.Y,Pair.Value.Frame.Z}},
            {"profile","split_wet_dry_v002"}});
    Result["landing_material"]=LandingMaterial?TCHAR_TO_UTF8(*LandingMaterial->GetPathName()):"";
    const auto* Surface=Region==2&&Parts.Num()>0?Parts[0].Get():Terrain.Get();
    const auto* SurfaceMaterial=IsValid(Surface)?Surface->GetMaterial(0):nullptr;
    Result["surface_material"]=SurfaceMaterial?TCHAR_TO_UTF8(*SurfaceMaterial->GetPathName()):"";
    Result["landing_restore_material"]=LandingOriginalMaterial?TCHAR_TO_UTF8(*LandingOriginalMaterial->GetPathName()):"";
    return FString(UTF8_TO_TCHAR(Result.dump().c_str()));
}

FString AOldWestRegion::GetRouteSceneryDebug(UWorld* World)
{
    using J=nlohmann::ordered_json;
    J Result=J::array();
    if(World)for(TActorIterator<AStaticMeshActor> It(World);It;++It)
    {
        if(!IsRouteScenery(*It))continue;
        FVector Center,Extent;It->GetActorBounds(false,Center,Extent);
        const auto* Part=It->GetStaticMeshComponent();
        Result.push_back({{"actor",TCHAR_TO_UTF8(*It->GetName())},
            {"mesh",TCHAR_TO_UTF8(*Part->GetStaticMesh()->GetPathName())},
            {"center",{Center.X,Center.Y,Center.Z}},{"extent",{Extent.X,Extent.Y,Extent.Z}},
            {"hidden",It->IsHidden()},{"visible",Part->IsVisible()},
            {"actor_collision",It->GetActorEnableCollision()},
            {"component_collision",static_cast<int32>(Part->GetCollisionEnabled())}});
    }
    return FString(UTF8_TO_TCHAR(Result.dump().c_str()));
}

void AOldWestRegion::EndPlay(const EEndPlayReason::Type Reason)
{
    Clear();Super::EndPlay(Reason);
}
