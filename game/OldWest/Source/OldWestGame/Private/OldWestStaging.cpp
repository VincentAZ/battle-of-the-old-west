#include "OldWestDisplayNames.h"
#include "OldWestStaging.h"
#include "OldWestRegion.h"
#include "OldWestBattlefield.h"
#include "Components/StaticMeshComponent.h"
#include "Components/TextRenderComponent.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "Materials/MaterialInterface.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Core/json.hpp"
using J=nlohmann::ordered_json;
namespace { FString Text(const std::string& S){return OldWestDisplay::Text(FString(UTF8_TO_TCHAR(S.c_str())));} }

AOldWestStaging::AOldWestStaging()
{
    RootComponent=CreateDefaultSubobject<USceneComponent>(TEXT("StagingRoot"));
    PrimaryActorTick.bCanEverTick=true;
    PrimaryActorTick.TickGroup=TG_PostUpdateWork;
}
FVector AOldWestStaging::HandPosition(int32 Side,bool Event,int32 Index)
{
    const float Rear=Side==0?1.f:-1.f;
    return FVector((Side==0?-1.f:1.f)*((Event?-1300.f:150.f)+(Index%5)*260.f),
        2500.f+Rear*(2320.f+(Index/5)*320.f),0);
}
FVector AOldWestStaging::UtilityPosition(int32 Side,int32 Index)
{
    return FVector((Side==0?1.f:-1.f)*(2100.f+(Index%2)*620.f),
        2500.f+(Side==0?1.f:-1.f)*(1700.f+(Index/2)*380.f),0);
}
void AOldWestStaging::Mark(const FVector& P,const FVector& Size,const TCHAR* Material)
{
    auto* Part=NewObject<UStaticMeshComponent>(this);Part->SetupAttachment(RootComponent);
    Part->SetStaticMesh(LoadObject<UStaticMesh>(nullptr,TEXT("/Engine/BasicShapes/Cube.Cube")));
    // Dark symbolic lane marks keep the same shape readable against snow.
    const TCHAR* Surface=Region&&Region->IsWinter()&&FCString::Strcmp(Material,TEXT("StencilledChalk"))==0?TEXT("TreeChar"):Material;
    const FString Path=FString(TEXT("/Game/Art/Camps/Materials/M_Camp_"))+Surface+TEXT(".M_Camp_")+Surface;
    Part->SetMaterial(0,LoadObject<UMaterialInterface>(nullptr,*Path));
    FVector Grounded=P;FHitResult Hit;
    if(GetWorld()->LineTraceSingleByChannel(Hit,P+FVector(0,0,1500),P-FVector(0,0,1500),ECC_Visibility))Grounded.Z=Hit.ImpactPoint.Z+P.Z;
    Part->SetRelativeLocation(Grounded);Part->SetRelativeScale3D(Size/100.f);
    Part->SetCollisionEnabled(ECollisionEnabled::NoCollision);Part->RegisterComponent();GroundParts.Add(Part);
}
void AOldWestStaging::Sign(const FString& Value,const FVector& P,int32 Side,FColor Color,float Size)
{
    // Render headings in the HUD so scenery cannot occlude or tilt the text.
    FieldLabels.Add({Value,P,Side});
}
void AOldWestStaging::BuildFuseGround(int32 Side)
{
    // Sourced tarred fibre cord; dimensions/ties are symbolic countdown marks.
    // Evidence: research/western-presentation/fuse-line.json. No gameplay state.
    auto* Cord=LoadObject<UStaticMesh>(nullptr,TEXT("/Game/Art/Western/Trouble/Fuse/SM_WesternFuseCord.SM_WesternFuseCord"));
    FuseCordMaterial=LoadObject<UMaterialInterface>(nullptr,TEXT("/Game/Art/Western/Trouble/Fuse/M_WesternFuseCord.M_WesternFuseCord"));
    FuseAshMaterial=LoadObject<UMaterialInterface>(nullptr,TEXT("/Game/Art/Western/Trouble/Fuse/M_WesternFuseAsh.M_WesternFuseAsh"));
    if(!Cord||!FuseCordMaterial||!FuseAshMaterial)
    {UE_LOG(LogTemp,Error,TEXT("OLDWEST_FUSE_ERROR Missing authored fuse assets"));return;}
    const float Rear=Side==0?1.f:-1.f;
    const FVector End=AOldWestBattlefield::EventPosition(Side,-1)+FVector(240*Rear,0,0);
    // Ground each short piece independently so the cord follows terrain.
    auto Ground=[this](FVector P)
    {
        FHitResult Hit;
        if(GetWorld()->LineTraceSingleByChannel(Hit,P+FVector(0,0,1500),P-FVector(0,0,1500),ECC_Visibility))P.Z=Hit.ImpactPoint.Z;
        P.Z+=5.f;return P;
    };
    for(int32 I=0;I<31;++I)
    {
        const float D0=I*60.f,D1=(I+1)*60.f;
        const FVector A=Ground(End+FVector(12*FMath::Sin(D0/140),Rear*D0,0));
        const FVector B=Ground(End+FVector(12*FMath::Sin(D1/140),Rear*D1,0));
        auto* Part=NewObject<UStaticMeshComponent>(this);AddInstanceComponent(Part);Part->SetupAttachment(RootComponent);
        Part->SetStaticMesh(Cord);Part->SetMaterial(0,FuseCordMaterial);
        Part->SetRelativeLocation((A+B)*.5f);Part->SetRelativeRotation((B-A).Rotation());
        Part->SetRelativeScale3D(FVector((B-A).Size()/100.f,2.f,2.f));
        Part->SetCollisionEnabled(ECollisionEnabled::NoCollision);Part->SetCanEverAffectNavigation(false);
        Part->RegisterComponent();GroundParts.Add(Part);FuseSegments.Add(Part);
        FuseSegmentSides.Add(Side);FuseSegmentDistances.Add((D0+D1)*.5f);
    }
    for(int32 Slot=0;Slot<3;++Slot)
    {
        const FVector P=AOldWestBattlefield::EventPosition(Side,Slot)+FVector(240*Rear,0,6);
        // One, two, three pale ties give a readable countdown without box slots.
        for(int32 I=0;I<=Slot;++I)
            Mark(P+FVector(0,(I-Slot*.5f)*22,0),FVector(54,8,5),TEXT("StencilledChalk"));
    }
}
void AOldWestStaging::Tick(float DeltaSeconds)
{
    Super::Tick(DeltaSeconds);
    if(FuseSegments.IsEmpty())return;
    TSet<int32> Keep;
    float LastLive[2]={-1,-1};
    // Follow the actual rendered public tokens, including cinematic advance
    // and push-back, instead of jumping ahead to the final network snapshot.
    for(TActorIterator<AOldWestUnit> It(GetWorld());It;++It)
    {
        const AOldWestUnit* Unit=*It;
        if(Unit->EntityId<=0||!Unit->IsEventToken()||Unit->IsHidden()||Unit->IsPreviewOnly()||
           Unit->Tags.Contains(TEXT("OldWestHandStaging"))||Unit->GetVisualCardId()==TEXT("hip_flask"))continue;
        const int32 Side=Unit->Side;if(Side<0||Side>1)continue;
        const float Rear=Side==0?1.f:-1.f;
        const FVector End=AOldWestBattlefield::EventPosition(Side,-1);
        const FVector Position=Unit->GetActorLocation();
        const float Distance=(Position.Y-End.Y)*Rear;
        if(FMath::Abs(Position.X-End.X)>180||Distance< -30||Distance>1860)continue;
        Keep.Add(Unit->EntityId);LastLive[Side]=FMath::Max(LastLive[Side],Distance);
        auto& Ember=FuseEmbers.FindOrAdd(Unit->EntityId);
        if(!IsValid(Ember))
        {
            Ember=NewObject<UStaticMeshComponent>(this);AddInstanceComponent(Ember);Ember->SetupAttachment(RootComponent);
            Ember->SetStaticMesh(LoadObject<UStaticMesh>(nullptr,TEXT("/Engine/BasicShapes/Sphere.Sphere")));
            auto* Material=LoadObject<UMaterialInterface>(nullptr,TEXT("/Game/Art/Western/Trouble/Fuse/M_WesternFuseEmber.M_WesternFuseEmber"));
            if(!Material){UE_LOG(LogTemp,Error,TEXT("OLDWEST_FUSE_ERROR Missing ember material"));}
            auto* Glow=Material?UMaterialInstanceDynamic::Create(Material,this):nullptr;
            Ember->SetMaterial(0,Glow);FuseGlow.Add(Unit->EntityId,Glow);
            Ember->SetCollisionEnabled(ECollisionEnabled::NoCollision);Ember->SetCanEverAffectNavigation(false);Ember->RegisterComponent();
        }
        FVector P(End.X+240*Rear+12*FMath::Sin(Distance/140),Position.Y,Position.Z+10);
        // The token sits 240cm beside the cord, on a potentially different
        // slope. Follow the actual grounded cord, preserving the token's Y.
        // Using its rendered segment also avoids a terrain trace every tick.
        float Nearest=MAX_flt;
        for(int32 I=0;I<FuseSegments.Num();++I)
        {
            if(FuseSegmentSides[I]!=Side||!IsValid(FuseSegments[I]))continue;
            const float Gap=FMath::Abs(FuseSegmentDistances[I]-Distance);
            if(Gap>=Nearest)continue;
            const FVector Center=FuseSegments[I]->GetComponentLocation();
            const FVector Axis=FuseSegments[I]->GetForwardVector();
            if(FMath::Abs(Axis.Y)<UE_SMALL_NUMBER)continue;
            Nearest=Gap;
            P=Center+Axis*((Position.Y-Center.Y)/Axis.Y)+FVector(0,0,5);
        }
        Ember->SetRelativeLocation(P);
        const float Pulse=.5f+.5f*FMath::Sin(GetWorld()->GetTimeSeconds()*13+Unit->EntityId);
        Ember->SetRelativeScale3D(FVector(.17f+Pulse*.04f,.17f+Pulse*.04f,.10f+Pulse*.06f));
        if(UMaterialInstanceDynamic* Glow=FuseGlow.FindRef(Unit->EntityId))Glow->SetScalarParameterValue(TEXT("Glow"),4+Pulse*3);
    }
    TArray<int32> Remove;
    for(const auto& Pair:FuseEmbers)if(!Keep.Contains(Pair.Key))
    {if(IsValid(Pair.Value))Pair.Value->DestroyComponent();Remove.Add(Pair.Key);}
    for(int32 Id:Remove){FuseEmbers.Remove(Id);FuseGlow.Remove(Id);}
    for(int32 I=0;I<FuseSegments.Num();++I)
    {
        const float End=LastLive[FuseSegmentSides[I]];
        auto* Material=End>=0&&FuseSegmentDistances[I]>End?FuseAshMaterial.Get():FuseCordMaterial.Get();
        if(FuseSegments[I]->GetMaterial(0)!=Material)FuseSegments[I]->SetMaterial(0,Material);
    }
}
FString AOldWestStaging::GetFuseDebug() const
{
    J Result={{"segments",FuseSegments.Num()},{"cord_segments",J::array()},{"embers",J::array()},{"noncolliding",true}};
    for(int32 I=0;I<FuseSegments.Num();++I)if(IsValid(FuseSegments[I]))
    {
        const auto* Part=FuseSegments[I].Get();
        Result["noncolliding"]=Result["noncolliding"].get<bool>()&&Part->GetCollisionEnabled()==ECollisionEnabled::NoCollision;
        // Read the real mesh transform so native tests can independently
        // compare the glowing marker with the cord it is meant to follow.
        const FVector C=Part->GetComponentLocation(),A=Part->GetForwardVector();
        Result["cord_segments"].push_back({{"side",FuseSegmentSides[I]},
            {"center",{C.X,C.Y,C.Z}},{"axis",{A.X,A.Y,A.Z}},
            {"length_cm",100*Part->GetComponentScale().X}});
    }
    for(const auto& Pair:FuseEmbers)if(IsValid(Pair.Value))
    {
        const FVector P=Pair.Value->GetComponentLocation();
        Result["embers"].push_back({{"id",Pair.Key},{"location",{P.X,P.Y,P.Z}}});
    }
    return FString(UTF8_TO_TCHAR(Result.dump().c_str()));
}
void AOldWestStaging::BuildGround(int32 Seat)
{
    if(!IsValid(Region))Region=GetWorld()->SpawnActor<AOldWestRegion>();
    if(IsValid(Region))Region->ApplyMatch(SeenMatch);
    for(AOldWestUnit* Unit:Utilities)if(IsValid(Unit))Unit->Destroy();
    Utilities.Reset();
    for(AOldWestUnit* Unit:WaterBundles)if(IsValid(Unit))Unit->Destroy();
    WaterBundles.Reset();
    for(UStaticMeshComponent* Part:GroundParts)if(IsValid(Part))Part->DestroyComponent();
    GroundParts.Reset();
    FuseSegments.Reset();FuseSegmentSides.Reset();FuseSegmentDistances.Reset();
    for(const auto& Pair:FuseEmbers)if(IsValid(Pair.Value))Pair.Value->DestroyComponent();
    FuseEmbers.Reset();FuseGlow.Reset();
    FieldLabels.Reset();
    for(int32 Side=0;Side<2;++Side)
    {
        const float Rear=Side==0?1.f:-1.f;
        const float Mirror=Side==0?-1.f:1.f;
        Sign(Side==Seat?TEXT("YOUR HAND / CREW"):TEXT("OPPONENT HAND / ?"),
            FVector(650*Mirror,2500+Rear*2650,75),Seat,FColor(160,220,207));
        if(Side==Seat)Sign(TEXT("YOUR HAND / TROUBLE"),FVector(-850*Mirror,2500+Rear*2650,75),Seat,FColor(255,200,90));
        Sign(Side==Seat?TEXT("YOUR DRIFTERS"):TEXT("ENEMY DRIFTERS"),FVector(2900*Rear,2500+Rear*1050,340),Seat,FColor(230,216,170));
        BuildFuseGround(Side);
        Sign(TEXT("PLAY NOW"),AOldWestBattlefield::EventPosition(Side,-1)+FVector(420*Rear,0,30),Seat,FColor(255,200,90));
        Sign(Side==Seat?TEXT("YOUR FUSE LINE"):TEXT("ENEMY FUSE LINE"),
            AOldWestBattlefield::EventPosition(Side,2)+FVector(310*Rear,Rear*330,50),Seat,FColor(255,200,90));
        for(int32 Col=0;Col<3;++Col)for(int32 Row=0;Row<2;++Row)
        {
            const FVector P=AOldWestBattlefield::DeploymentPosition(Side,Col,Row);
            for(float X:{-150.f,150.f})Mark(P+FVector(X,0,4),FVector(5,180,4),TEXT("StencilledChalk"));
            for(float Y:{-90.f,90.f})Mark(P+FVector(0,Y,4),FVector(300,5,4),TEXT("StencilledChalk"));
        }
    }
    const TCHAR* Names[]={TEXT("SUPPLY"),TEXT("PASS TURN"),TEXT("HIP FLASK"),TEXT("LEDGER"),TEXT("HOCK")};
    const TCHAR* Props[]={TEXT("field_supply"),TEXT("field_pass"),TEXT("field_silo"),TEXT("field_choices"),TEXT("field_scrap")};
    for(int32 I=0;I<5;++I)
    {
        auto* Unit=GetWorld()->SpawnActor<AOldWestUnit>();
        Unit->ConfigureEvent(-3000-I,Seat,Names[I],Props[I]);
        Unit->Tags.Add(TEXT("OldWestFieldUtility"));Unit->SetActorLocation(UtilityPosition(Seat,I));
        Utilities.Add(Unit);
    }
}
void AOldWestStaging::ApplySnapshot(const FString& Payload)
{
    J Data;try{Data=J::parse(TCHAR_TO_UTF8(*Payload));}catch(...){return;}
    if(!Data.contains("view"))return;
    const auto& View=Data["view"];const int32 Seat=Data.value("seat",0);
    const FString Match=Text(Data.value("match_id",std::string()));
    if(SeenSeat!=Seat||SeenMatch!=Match){SeenSeat=Seat;SeenMatch=Match;BuildGround(Seat);}
    const int32 Water=View["players"][Seat].value("water",0)>0?1:0;
    // One physical source represents the available pool; the destination determines payment.
    while(WaterBundles.Num()>Water){WaterBundles.Pop()->Destroy();}
    while(WaterBundles.Num()<Water)
    {
        auto* Unit=GetWorld()->SpawnActor<AOldWestUnit>();
        Unit->ConfigureEvent(-4000,Seat,TEXT("WHISKEY"),TEXT("field_water"));
        Unit->Tags.Add(TEXT("OldWestWaterBundle"));
        WaterBundles.Add(Unit);
    }
    for(int32 I=0;I<WaterBundles.Num();++I)
    {
        FVector P=UtilityPosition(Seat,2)+FVector((Seat==0?1.f:-1.f)*(-240.f-(I%4)*160.f),(Seat==0?1.f:-1.f)*(I/4)*180.f,0);
        FHitResult Ground;
        if(GetWorld()->LineTraceSingleByChannel(Ground,P+FVector(0,0,1500),P-FVector(0,0,1500),ECC_Visibility))P.Z=Ground.ImpactPoint.Z;
        WaterBundles[I]->SetActorLocation(P);
    }
    TSet<int32> Keep;int32 People=0,Events=0;
    for(const auto& Card:View["players"][Seat]["hand"])
    {
        const int32 Id=Card.value("id",0);if(Id<=0)continue;Keep.Add(Id);
        const bool Event=Card.value("type",std::string())!="person";
        auto& Unit=Hand.FindOrAdd(Id);
        if(!IsValid(Unit))
        {
            Unit=GetWorld()->SpawnActor<AOldWestUnit>();
            const FString Name=Text(Card.value("name",std::string()));
            const FString CardId=Text(Card.value("card_id",std::string()));
            if(Event)Unit->ConfigureEvent(Id,Seat,Name,CardId);
            else Unit->Configure(Id,Seat,Name,false,false,CardId,false,
                Text(Card.value("visual_id",Card.value("card_id",std::string()))));
            Unit->Tags.Add(TEXT("OldWestHandStaging"));
            Unit->SetCondition(0,false,true);
        }
        FVector Position=HandPosition(Seat,Event,Event?Events++:People++);FHitResult Ground;
        if(GetWorld()->LineTraceSingleByChannel(Ground,Position+FVector(0,0,1500),Position-FVector(0,0,1500),ECC_Visibility))Position.Z=Ground.ImpactPoint.Z;
        Unit->SetActorLocation(Position);
    }
    TArray<int32> Remove;
    for(const auto& Pair:Hand)if(!Keep.Contains(Pair.Key))
    {if(IsValid(Pair.Value))Pair.Value->Destroy();Remove.Add(Pair.Key);}
    for(int32 Id:Remove)Hand.Remove(Id);
    const int32 Count=View["players"][1-Seat].value("hand_count",0);
    // Count only: never create hidden models and then cover them with a '?'.
    while(Unknowns.Num()<Count)
    {
        auto* Box=NewObject<UStaticMeshComponent>(this);Box->SetupAttachment(RootComponent);
        Box->SetStaticMesh(LoadObject<UStaticMesh>(nullptr,TEXT("/Engine/BasicShapes/Cube.Cube")));
        Box->SetMaterial(0,LoadObject<UMaterialInterface>(nullptr,TEXT("/Game/Art/Camps/Materials/M_Camp_DustCanvas.M_Camp_DustCanvas")));
        Box->SetRelativeScale3D(FVector(1.2f,.9f,1.4f));Box->SetCollisionEnabled(ECollisionEnabled::NoCollision);Box->RegisterComponent();Unknowns.Add(Box);
        auto* Label=NewObject<UTextRenderComponent>(this);Label->SetupAttachment(RootComponent);
        Label->SetText(FText::FromString(TEXT("?")));Label->SetWorldSize(120);Label->SetHorizontalAlignment(EHTA_Center);Label->RegisterComponent();UnknownLabels.Add(Label);
    }
    for(int32 I=0;I<Unknowns.Num();++I)
    {
        const FVector P=HandPosition(1-Seat,false,I);
        Unknowns[I]->SetVisibility(I<Count);Unknowns[I]->SetRelativeLocation(P+FVector(0,0,70));
        UnknownLabels[I]->SetVisibility(I<Count);UnknownLabels[I]->SetRelativeLocation(P+FVector(0,Seat==0?60.f:-60.f,145));
        UnknownLabels[I]->SetRelativeRotation(FRotator(0,Seat==0?90.f:-90.f,0));
    }
}
void AOldWestStaging::SetTextVisible(bool Visible)
{

    for(int32 I=0;I<UnknownLabels.Num();++I)
        if(IsValid(UnknownLabels[I]))UnknownLabels[I]->SetVisibility(Visible&&Unknowns.IsValidIndex(I)&&Unknowns[I]->IsVisible());
}
void AOldWestStaging::EndPlay(const EEndPlayReason::Type Reason)
{
    if(IsValid(Region))Region->Destroy();
    for(const auto& Pair:Hand)if(IsValid(Pair.Value))Pair.Value->Destroy();
    Hand.Reset();
    for(AOldWestUnit* Unit:Utilities)if(IsValid(Unit))Unit->Destroy();
    Utilities.Reset();
    for(AOldWestUnit* Unit:WaterBundles)if(IsValid(Unit))Unit->Destroy();
    WaterBundles.Reset();
    Super::EndPlay(Reason);
}

FString AOldWestStaging::GetRegionDebug() const
{
    return IsValid(Region)?Region->GetDebug():TEXT("null");
}
