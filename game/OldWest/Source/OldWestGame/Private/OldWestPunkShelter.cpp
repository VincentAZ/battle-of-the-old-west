#include "OldWestPunkShelter.h"
#include "OldWestBattlefield.h"
#include "Components/StaticMeshComponent.h"
#include "Components/PointLightComponent.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "Materials/MaterialInterface.h"
#include "GameFramework/PlayerController.h"
#include "Core/json.hpp"
using J=nlohmann::ordered_json;

AOldWestPunkShelter::AOldWestPunkShelter()
{
    PrimaryActorTick.bCanEverTick=true;
    RootComponent=CreateDefaultSubobject<USceneComponent>(TEXT("ShelterRoot"));
    Gate=CreateDefaultSubobject<USceneComponent>(TEXT("YardGate"));Gate->SetupAttachment(RootComponent);
}
UStaticMeshComponent* AOldWestPunkShelter::Part(const TCHAR* Mesh,const FVector& P,const FVector& D,const TCHAR* Mat,USceneComponent* Parent)
{
    auto* C=NewObject<UStaticMeshComponent>(this);C->SetupAttachment(Parent?Parent:RootComponent.Get());
    C->SetStaticMesh(LoadObject<UStaticMesh>(nullptr,Mesh));
    C->SetMaterial(0,LoadObject<UMaterialInterface>(nullptr,*(FString(TEXT("/Game/Art/Camps/Materials/M_Camp_"))+Mat+TEXT(".M_Camp_")+Mat)));
    C->SetRelativeLocation(P);C->SetRelativeScale3D(D/100.f);C->SetCollisionEnabled(ECollisionEnabled::NoCollision);C->RegisterComponent();Parts.Add(C);return C;
}
FVector AOldWestPunkShelter::Ground(const FVector& Local) const
{
    FVector P=GetActorTransform().TransformPosition(Local);FHitResult Hit;
    FCollisionQueryParams Q(SCENE_QUERY_STAT(PunkShelterGround),true);Q.AddIgnoredActor(this);
    for(const auto& Unit:Crew)Q.AddIgnoredActor(Unit);
    if(GetWorld()->LineTraceSingleByChannel(Hit,P+FVector(0,0,1500),P-FVector(0,0,2000),ECC_Visibility,Q))P.Z=Hit.ImpactPoint.Z;
    return P;
}
FVector AOldWestPunkShelter::Home(int32 I) const{return Ground(FVector(80+(I%2)*145,-195+(I/2)*185,0));}
FVector AOldWestPunkShelter::Pad(int32 I) const{return Ground(FVector(1050+(I/3)*300,-300+(I%3)*300,0));}
void AOldWestPunkShelter::Initialize(int32 Side)
{
    // Beside the board, outside all three formation lanes and event tracks.
    SetActorLocation(FVector(Side == 0 ? 2900.f : -2900.f, Side == 0 ? 3550.f : 1450.f, 0));
    SetActorRotation(FRotator(0, Side == 0 ? 180.f : 0.f, 0));
    FVector Base=Ground(FVector::ZeroVector);SetActorLocation(Base);
    const TCHAR* Cube=TEXT("/Engine/BasicShapes/Cube.Cube"),*Cylinder=TEXT("/Engine/BasicShapes/Cylinder.Cylinder");
    Part(Cube,FVector(-170,0,8),FVector(370,455,16),TEXT("Concrete"));
    Part(Cube,FVector(-345,0,120),FVector(18,440,240),TEXT("CorrodedSteel"));
    for(float Y:{-220.f,220.f})Part(Cube,FVector(-170,Y,120),FVector(360,18,240),TEXT("FadedTurquoise"));
    Part(Cube,FVector(-170,0,248),FVector(400,490,20),TEXT("Galvanized"));
    for(int I=0;I<18;++I)Part(Cube,FVector(-350+I*21,0,261),FVector(6,490,7),TEXT("DarkSteel"));
    for(float Y:{-170.f,170.f})Part(Cube,FVector(8,Y,118),FVector(22,100,236),TEXT("CorrodedSteel"));
    Part(Cube,FVector(8,0,220),FVector(24,240,45),TEXT("FadedTurquoise"));
    // Bunks and a shaded workbench give the crew a place to live between moves.
    for(float Y:{-150.f,150.f})for(float Z:{45.f,120.f}) {
        Part(Cube,FVector(-225,Y,Z),FVector(170,95,12),TEXT("DarkSteel"));
        Part(Cube,FVector(-225,Y,Z+10),FVector(158,87,12),TEXT("DustCanvas"));
    }
    for(float X:{0.f,300.f})for(float Y:{-320.f,-180.f})Part(Cube,FVector(X,Y,130),FVector(12,12,260),TEXT("DarkSteel"));
    Part(Cube,FVector(150,-250,262),FVector(330,165,8),TEXT("DustCanvas"));
    for(float Y:{-310.f,310.f})for(int X=0;X<=400;X+=80) {
        Part(Cube,FVector(X,Y,62),FVector(8,8,124),TEXT("CorrodedSteel"));
        if(X<400)for(float Z:{35.f,95.f})Part(Cube,FVector(X+40,Y,Z),FVector(80,6,8),TEXT("Galvanized"));
    }
    for(float Y:{-230.f,230.f})for(float Z:{35.f,95.f})Part(Cube,FVector(400,Y,Z),FVector(8,160,8),TEXT("Galvanized"));
    for(float Y:{-150.f,150.f})Part(Cube,FVector(400,Y,85),FVector(14,14,170),TEXT("FadedTurquoise"));
    Gate->SetRelativeLocation(FVector(400,-145,0));
    for(float Z:{30.f,105.f})Part(Cube,FVector(0,145,Z),FVector(10,290,10),TEXT("Galvanized"),Gate);
    for(int Y=0;Y<=290;Y+=29)Part(Cube,FVector(0,Y,68),FVector(8,8,125),TEXT("CorrodedSteel"),Gate);
    Part(Cylinder,FVector(80,260,46),FVector(65,65,92),TEXT("FadedRose"));
    Part(Cube,FVector(40,-260,86),FVector(115,70,12),TEXT("Wood"));
    for(float Y:{-285.f,-235.f})Part(Cube,FVector(40,Y,40),FVector(12,12,80),TEXT("DarkSteel"));
    Part(Cube,FVector(125,230,165),FVector(10,10,330),TEXT("DarkSteel"));
    Part(Cube,FVector(175,230,320),FVector(110,10,10),TEXT("DarkSteel"));
    PunchBag=Part(Cylinder,FVector(220,230,175),FVector(55,55,110),TEXT("Rubber"));
    for(int I=0;I<6;++I) {
        auto* Unit=GetWorld()->SpawnActor<AOldWestUnit>();Crew.Add(Unit);
        Unit->SetPreviewOnly(true);Unit->Configure(-1000-I,Side,TEXT("Shelter punk"),false,true);Unit->SetActorLocation(Home(I));Unit->SetCondition(0,false,true);
        Unit->AimAt(Ground(FVector(100,0,0)));Residents[I].Until=I*.6+1.;
    }
}
void AOldWestPunkShelter::Walk(int32 I,const FVector& To,EPhase Phase)
{
    Residents[I].Phase=Phase;
    // The shelter supplies its own clear gate/pad waypoints outside the board.
    // Battlefield obstacle routing can send these short walks down the event track.
    Residents[I].Until=Clock+Crew[I]->StageTravel(Crew[I]->GetActorLocation(),To,1.3f,false,true)+.12;
    ++Residents[I].Trips;
}
void AOldWestPunkShelter::Return(int32 I)
{
    ++Returns;Residents[I].Cooldown=Clock+3.;
    Walk(I,Ground(FVector(420,0,0)),EPhase::ReturnGate);
}
void AOldWestPunkShelter::SetSupply(int32 Count,int32 Revision,const TSet<int32>& BoardPunks)
{
    if(SeenRevision!=Revision&&PendingToken!=INDEX_NONE) {
        const int I=-1000-PendingToken;bool Added=false;
        for(int Id:BoardPunks)if(!SeenPunks.Contains(Id))Added=true;
        PendingToken=INDEX_NONE;
        if(Added){++Consumed;Residents[I].Phase=EPhase::Spent;Residents[I].Until=Clock+1.5;Crew[I]->SetActorHiddenInGame(true);}
        else Return(I);
    }
    SeenRevision=Revision;SeenPunks=BoardPunks;Available=FMath::Clamp(Count,0,6);
    int Keeping=0;
    for(int I=0;I<Crew.Num();++I) {
        const auto Phase=Residents[I].Phase;
        if(Phase==EPhase::Waiting||Phase==EPhase::ExitGate||Phase==EPhase::ExitPad||Phase==EPhase::Dragging||Phase==EPhase::Submitted) {
            if(Keeping++>=Available&&Phase!=EPhase::Submitted)Return(I);
        }
    }
}
bool AOldWestPunkShelter::CanDrag(int32 Token) const
{
    if(!IsToken(Token)||Available<=0||PendingToken!=INDEX_NONE)return false;
    return Residents[-1000-Token].Phase==EPhase::Waiting;
}
bool AOldWestPunkShelter::BeginDrag(int32 Token)
{
    if(!CanDrag(Token))return false;Residents[-1000-Token].Phase=EPhase::Dragging;return true;
}
void AOldWestPunkShelter::CancelDrag(int32 Token)
{
    if(IsToken(Token)&&Residents[-1000-Token].Phase==EPhase::Dragging)Return(-1000-Token);
}
void AOldWestPunkShelter::Submitted(int32 Token)
{
    if(IsToken(Token)){Residents[-1000-Token].Phase=EPhase::Submitted;PendingToken=Token;Residents[-1000-Token].Until=Clock+5.;}
}
void AOldWestPunkShelter::PreviewAt(int32 Token,const FVector& Position)
{
    if(IsToken(Token)&&Residents[-1000-Token].Phase==EPhase::Dragging)Crew[-1000-Token]->SetActorLocation(Position);
}
int32 AOldWestPunkShelter::Pick(APlayerController* Player,const FVector2D& Pixels) const
{
    FVector O,D;if(!Player->DeprojectScreenPositionToWorld(Pixels.X,Pixels.Y,O,D))return INDEX_NONE;
    float Best=TNumericLimits<float>::Max();int32 Result=INDEX_NONE;
    for(int I=0;I<Crew.Num();++I)if(CanDrag(-1000-I)) {
        FVector P,N;float T=1.f;
        FVector2D Center;
        if(Player->ProjectWorldLocationToScreen(Crew[I]->GetActorLocation()+FVector(0,0,85),Center)&&
           FMath::LineExtentBoxIntersection(Crew[I]->GetVisualBounds(),O,O+D*100000,FVector::ZeroVector,P,N,T)) {
            const float Distance=FVector2D::DistSquared(Center,Pixels);
            if(Distance<Best){Best=Distance;Result=-1000-I;}
        }
    }
    return Result;
}
TArray<TPair<int32,FVector>> AOldWestPunkShelter::ReadyPositions() const
{
    TArray<TPair<int32,FVector>> Result;
    for(int I=0;I<Crew.Num();++I)if(CanDrag(-1000-I))Result.Emplace(-1000-I,Crew[I]->GetVisualBounds().GetCenter()+FVector(0,0,110));
    return Result;
}
void AOldWestPunkShelter::Tick(float Dt)
{
    Super::Tick(Dt);Clock+=Dt;int Active=0;bool Open=false;
    for(int I=0;I<Crew.Num();++I) {
        auto& R=Residents[I];
        if(R.Phase==EPhase::ExitGate||R.Phase==EPhase::ExitPad||R.Phase==EPhase::Waiting||R.Phase==EPhase::Dragging||R.Phase==EPhase::Submitted)++Active;
        if(R.Phase!=EPhase::Home&&R.Phase!=EPhase::Spent)Open=true;
        if(Clock<R.Until)continue;
        switch(R.Phase) {
            case EPhase::ExitGate:Walk(I,Pad(I),EPhase::ExitPad);break;
            case EPhase::ExitPad:R.Phase=EPhase::Waiting;Crew[I]->AimAt(GetActorLocation()+GetActorForwardVector()*1300);break;
            case EPhase::ReturnGate:Walk(I,Home(I),EPhase::ReturnHome);break;
            case EPhase::ReturnHome:R.Phase=EPhase::Home;R.Until=Clock+1.;break;
            case EPhase::Submitted:PendingToken=INDEX_NONE;Return(I);break;
            case EPhase::Spent:Crew[I]->SetActorLocation(Home(I));Crew[I]->SetActorHiddenInGame(false);R.Phase=EPhase::Home;R.Cooldown=Clock+1.;break;
            case EPhase::Home:
                if(I==5){Crew[I]->AimAt(Ground(FVector(220,230,175)));Crew[I]->PlayAction(TEXT("attack"));Crew[I]->Impact->SetIntensity(0);R.Until=Clock+2.4;}
                else if(I<2){R.Roam=!R.Roam;R.Until=Clock+Crew[I]->StageTravel(Crew[I]->GetActorLocation(),Home(I)+GetActorRightVector()*(R.Roam?70:0),1.4f,false,true)+2.;++R.Trips;}
                else R.Until=Clock+2.;
                break;
            default:break;
        }
    }
    for(int I=0;I<Crew.Num()&&Active<Available;++I)if(Residents[I].Phase==EPhase::Home&&Clock>=Residents[I].Cooldown) {
        Walk(I,Ground(FVector(410,0,0)),EPhase::ExitGate);++Active;Open=true;
    }
    GateAngle=FMath::FInterpTo(GateAngle,Open?-105.f:0.f,Dt,3.f);Gate->SetRelativeRotation(FRotator(0,GateAngle,0));
    if(PunchBag)PunchBag->SetRelativeRotation(FRotator(FMath::Sin(Clock*3)*5,0,0));
}
void AOldWestPunkShelter::EndPlay(const EEndPlayReason::Type Reason)
{
    for(const auto& Unit:Crew)if(IsValid(Unit))Unit->Destroy();Crew.Empty();Super::EndPlay(Reason);
}
FString AOldWestPunkShelter::DebugState() const
{
    static const char* Phases[]={"home","exiting_gate","exiting_pad","waiting","dragging","submitted","returning_gate","returning_home","spent"};
    J R={{"available",Available},{"revision",SeenRevision},{"gate_angle",GateAngle},{"consumed",Consumed},{"returns",Returns},{"crew",J::array()}};
    for(int I=0;I<Crew.Num();++I){const FVector P=Crew[I]->GetActorLocation();R["crew"].push_back({{"token",-1000-I},{"phase",Phases[int(Residents[I].Phase)]},{"world",{P.X,P.Y,P.Z}},{"motion",J::parse(TCHAR_TO_UTF8(*Crew[I]->GetIdleDebug()))},{"trips",Residents[I].Trips},{"can_drag",CanDrag(-1000-I)},{"hidden",Crew[I]->IsHidden()},{"activity",I==5?"punching bag":I<2?"yard patrol":"resting by workbench"}});}
    return FString(UTF8_TO_TCHAR(R.dump().c_str()));
}
