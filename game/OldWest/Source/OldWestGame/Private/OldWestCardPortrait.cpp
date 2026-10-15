#include "OldWestStampedeVisuals.h"
#include "OldWestCardPortrait.h"
#include "OldWestCrewCatalog.h"
#include "OldWestTroubleCatalog.h"
#include "OldWestBattlefield.h"
#include "OldWestCampVisuals.h"
#include "OldWestFireVisuals.h"
#include "Core/json.hpp"
#include "Containers/Ticker.h"
#include "ContentStreaming.h"
#include "Misc/Paths.h"
#include "Animation/AnimSequence.h"
#include "Animation/AnimSingleNodeInstance.h"
#include "Components/PointLightComponent.h"
#include "Components/SceneCaptureComponent2D.h"
#include "Components/SkeletalMeshComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "Engine/TextureRenderTarget2D.h"
#include "Engine/Texture2D.h"
#if !UE_BUILD_SHIPPING
#include "Animation/MorphTarget.h"
#include "Engine/SkeletalMesh.h"
#endif
#include "Engine/World.h"
#include "Materials/MaterialInterface.h"
#include "Materials/Material.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Rendering/DrawElements.h"
#include "RenderCommandFence.h"
#include "Styling/CoreStyle.h"
#include "UObject/GCObject.h"
#include "UObject/Package.h"
#include "Widgets/SLeafWidget.h"
#if WITH_EDITOR
#include "AssetCompilingManager.h"
#include "ShaderCompiler.h"
#endif

namespace
{
using J = nlohmann::ordered_json;
constexpr double CaptureInterval = 1. / 15.;
const FName PreviewTag(TEXT("OldWestPortraitPreview"));

struct FPortraitCompilationState
{
    int32 ShaderJobs = 0, AssetJobs = 0;
    bool ShaderActive = false, Available = true;
    bool IsReady() const { return Available && ShaderJobs==0 && AssetJobs==0 && !ShaderActive; }
};

FPortraitCompilationState PortraitCompilationState()
{
    FPortraitCompilationState State;
#if WITH_EDITOR
    State.Available=GShaderCompilingManager!=nullptr;
    if(GShaderCompilingManager)
    {
        State.ShaderJobs=GShaderCompilingManager->GetNumRemainingJobs();
        State.ShaderActive=GShaderCompilingManager->IsCompiling();
    }
    // Includes pending shader-map finalization and primitive updates, not
    // merely worker jobs. Zero workers can still render a fallback material.
    State.AssetJobs=FAssetCompilingManager::Get().GetNumRemainingAssets();
#endif
    return State;
}

struct FPortraitRenderReadiness
{
    int32 ExpectedMeshes = 0, PendingPSOs = 0, MissingRegistrations = 0, MissingRenderStates = 0, DirtyRenderStates = 0, MissingProxies = 0;
    int32 ExpectedTextures = 0, PendingTextures = 0;
    bool IsReady() const { return ExpectedMeshes > 0 && PendingPSOs == 0 && MissingRegistrations == 0 && MissingRenderStates == 0 && DirtyRenderStates == 0 && MissingProxies == 0 && PendingTextures == 0; }
};

struct FMotion
{
    TWeakObjectPtr<UStaticMeshComponent> Part;
    FVector Position, Scale, Axis;
    FRotator Rotation;
    FString Kind;
    float Phase = 0.f, Rate = 1.f;
};

struct FPortraitScene : FGCObject
{
    TWeakObjectPtr<UWorld> World;
    FString Id, Type;
    TArray<TObjectPtr<AActor>> Actors;
    TObjectPtr<AActor> Stage = nullptr;
    TObjectPtr<USceneCaptureComponent2D> Capture = nullptr;
    TObjectPtr<UTextureRenderTarget2D> Target = nullptr;
    TObjectPtr<UOldWestCampVisuals> Camp = nullptr;
    TArray<FMotion> Motions;
    TWeakObjectPtr<UStaticMeshComponent> TroubleProp;
    FVector Origin, Focus;
    FSlateBrush Brush;
    double LastVisible = 0., LastCapture = -1., NextCapture = 0., Born = 0.;
    uint64 LastVisibleFrame = 0;
    int32 CaptureCount = 0, PersonCount = 0, CampDamage = 0;
    bool CampDestroyed = false;
    bool CompositionFitActive = false, CompositionFitFallback = false;
    int32 CompositionFitIterations = 0;
    bool Hidden = false;
    int32 CompleteRenderSubmissions = 0;
    uint64 LastCompleteRenderFrame = 0;
    FRenderCommandFence CompleteCaptureFence;
#if !UE_BUILD_SHIPPING
    mutable uint64 LastPaintedFrame = 0;
    mutable bool LastPaintedPlaceholder = true;
    bool DetailReview = false;
    FString DetailExpression;
    FTransform DetailOriginalCamera;
    FTransform DetailOriginalBody;
    TObjectPtr<UAnimationAsset> DetailOriginalAnimation = nullptr;
    float DetailOriginalTime = 0.f, DetailOriginalRate = 1.f;
    bool DetailOriginalPlaying = false, DetailOriginalLooping = false;
    bool DetailOriginalActorTick = false, DetailOriginalWeaponVisible = false;
    TMap<FName,float> DetailMorphs;
    int32 ConditionRevision = 0, ReadyCaptureCount = 0, CompilationZeroCapture = -1;
    uint64 CompilationZeroFrame = 0, LastReadyCaptureFrame = 0;

    void ResetCompilationReadiness()
    {
        ReadyCaptureCount=0; CompilationZeroCapture=-1;
        CompilationZeroFrame=0; LastReadyCaptureFrame=0;
    }
#endif

    FPortraitScene(UWorld* InWorld, const FString& InId, const FString& InType, bool InHidden)
        : World(InWorld), Id(InId), Type(InType), Hidden(InHidden)
    {
        static uint32 Serial = 0;
        // Separate the galleries from the playable field and each other. Their
        // show-only capture lists also exclude every other gallery and game actor.
        Origin = FVector(100000.f + float((Serial++) % 64) * 4000.f, 100000.f, 15000.f);
        Born = LastVisible = FPlatformTime::Seconds();
        Build();
    }
    ~FPortraitScene() override { Release(); }
    void AddReferencedObjects(FReferenceCollector& Collector) override
    {
        Collector.AddReferencedObjects(Actors);
        Collector.AddReferencedObject(Stage);
        Collector.AddReferencedObject(Capture);
        Collector.AddReferencedObject(Target);
        Collector.AddReferencedObject(Camp);
#if !UE_BUILD_SHIPPING
        Collector.AddReferencedObject(DetailOriginalAnimation);
#endif
    }
    FString GetReferencerName() const override { return TEXT("OldWestCardPortrait"); }
    void Release()
    {
        Brush.SetResourceObject(nullptr);
        if (Capture) Capture->TextureTarget = nullptr;
        for (AActor* Actor : Actors) if (IsValid(Actor)) Actor->Destroy();
        Actors.Empty();
        Stage = nullptr; Capture = nullptr; Target = nullptr; Camp = nullptr;
    }
    template<class T> T* Component()
    {
        T* C = NewObject<T>(Stage);
        Stage->AddInstanceComponent(C);
        C->SetupAttachment(Stage->GetRootComponent());
        C->RegisterComponent();
        return C;
    }
    UStaticMeshComponent* Part(const TCHAR* Shape, const FVector& Position,
        const FVector& Scale, const TCHAR* Material = TEXT("DarkSteel"), const FRotator& Rotation = FRotator::ZeroRotator)
    {
        UStaticMeshComponent* C = Component<UStaticMeshComponent>();
        const FString Path = FString(TEXT("/Engine/BasicShapes/")) + Shape + TEXT(".") + Shape;
        UStaticMesh* Mesh=LoadObject<UStaticMesh>(nullptr, *Path);
        if(!Mesh) UE_LOG(LogTemp,Error,TEXT("OLDWEST_PORTRAIT_ERROR Missing mesh %s for %s"),*Path,*Id);
        C->SetStaticMesh(Mesh);
        const FString Kind(Material);
        const FString PortraitName=Kind==TEXT("AmberLamp")?TEXT("Amber"):Kind==TEXT("StatusLight")?TEXT("Teal"):
            Kind==TEXT("Flame")?TEXT("Flame"):Kind==TEXT("PortraitGround")?TEXT("Ground"):FString();
        const FString Mat=PortraitName.IsEmpty()?FString(TEXT("/Game/Art/Camps/Materials/M_Camp_"))+Material:
            FString(TEXT("/Game/Art/CardPortraits/M_Portrait_"))+PortraitName;
        if (UMaterialInterface* M = LoadObject<UMaterialInterface>(nullptr, *(Mat + TEXT(".") + FPaths::GetBaseFilename(Mat)))) C->SetMaterial(0, M);
        else UE_LOG(LogTemp,Error,TEXT("OLDWEST_PORTRAIT_ERROR Missing material %s for %s"),*Mat,*Id);
        C->SetRelativeLocation(Position);
        C->SetRelativeRotation(Rotation);
        C->SetRelativeScale3D(Scale);
        C->SetCollisionEnabled(ECollisionEnabled::NoCollision);
        C->SetCastShadow(true);
        return C;
    }
    // An authored prop with its own materials, scaled to Height and standing on Position.
    UStaticMeshComponent* AssetMesh(const TCHAR* Path, const FVector& Position, float Height, const FRotator& Rotation = FRotator::ZeroRotator)
    {
        UStaticMeshComponent* C = Component<UStaticMeshComponent>();
        UStaticMesh* Mesh = LoadObject<UStaticMesh>(nullptr, Path);
        if (!Mesh) { UE_LOG(LogTemp,Error,TEXT("OLDWEST_PORTRAIT_ERROR Missing mesh %s for %s"),Path,*Id); return C; }
        C->SetStaticMesh(Mesh);
        const FBox B = Mesh->GetBoundingBox();
        const float Scale = Height / FMath::Max(1.f, static_cast<float>(B.GetSize().Z));
        C->SetRelativeLocation(Position - FVector(0, 0, B.Min.Z * Scale));
        C->SetRelativeRotation(Rotation);
        C->SetRelativeScale3D(FVector(Scale));
        C->SetCollisionEnabled(ECollisionEnabled::NoCollision);
        C->SetCastShadow(true);
        return C;
    }
    void Animate(UStaticMeshComponent* Part, const TCHAR* Kind, const FVector& Axis, float Phase = 0.f, float Rate = 1.f)
    {
        Motions.Add({Part, Part->GetRelativeLocation(), Part->GetRelativeScale3D(), Axis,
            Part->GetRelativeRotation(), Kind, Phase, Rate});
    }
    void Tank(FVector P, const TCHAR* Material, float Size = 1.f)
    {
        Part(TEXT("Cylinder"), P + FVector(0,0,45*Size), FVector(.65,.65,.85)*Size, Material);
        for (float Z : {9.f,75.f}) Part(TEXT("Cylinder"), P+FVector(0,0,Z*Size), FVector(.69,.69,.06)*Size, TEXT("Galvanized"));
        Part(TEXT("Cylinder"), P+FVector(0,0,91*Size), FVector(.15,.15,.1)*Size, TEXT("Copper"));
    }
    void Crate(FVector P, float Size = 1.f)
    {
        Part(TEXT("Cube"),P+FVector(0,0,24*Size),FVector(.75,.65,.48)*Size,TEXT("DustCanvas"));
        for (float X : {-27.f,27.f}) Part(TEXT("Cube"),P+FVector(X*Size,0,25*Size),FVector(.05,.69,.51)*Size,TEXT("DarkSteel"));
    }
    void Flag(FVector P, const TCHAR* Material, float Size = 1.f)
    {
        Part(TEXT("Cylinder"),P+FVector(0,0,100*Size),FVector(.025,.025,2)*Size,TEXT("Galvanized"));
        UStaticMeshComponent* Cloth = Part(TEXT("Cube"),P+FVector(34*Size,0,171*Size),FVector(.7,.025,.43)*Size,Material);
        Animate(Cloth,TEXT("flag"),FVector(0,6,0),P.X*.01f,1.6f);
    }
    void Beacon(FVector P, const TCHAR* Material)
    {
        Part(TEXT("Cylinder"),P+FVector(0,0,40),FVector(.12,.12,.8),TEXT("Copper"));
        UStaticMeshComponent* Rotor = Part(TEXT("Cube"),P+FVector(0,0,87),FVector(.58,.12,.15),Material);
        Animate(Rotor,TEXT("rotate"),FVector(0,0,45));
    }
    void Flame(FVector P, float Size = 1.f, float Phase = 0.f)
    {
        UOldWestFireVisuals* Fire = Component<UOldWestFireVisuals>();
        Fire->SetRelativeLocation(P + FVector(0, 0, 2));
        Fire->Build(95.f * Size, 115.f * Size, Phase * .173f, 1.f, true);
    }
    AOldWestUnit* Person(FVector P, bool Unarmed = false, float Scale = 1.f)
    {
        FActorSpawnParameters Params;
        Params.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
        AOldWestUnit* Unit = World->SpawnActor<AOldWestUnit>(Origin + P, FRotator::ZeroRotator, Params);
        if (!Unit) return nullptr;
        Actors.Add(Unit);
        Unit->Tags.Add(PreviewTag);
        Unit->SetPreviewOnly(true);
        // Dense outfit UV islands and thin hair masks need stable texture
        // detail even in a small portrait. This request belongs to the local
        // preview component and ends when its pooled scene is reclaimed.
        Unit->Body->bForceMipStreaming=true;
        Unit->Configure(-1000-PersonCount++, 0, TEXT(""), false, Hidden, Hidden ? TEXT("punk") : Id, Unarmed);
        Unit->SetPreviewOnly(true);
        Unit->SetCondition(0,false,true);
        Unit->SetActorScale3D(FVector(Scale));
        // A fixed gallery camera needs the actual animated pose even when it is
        // outside the main player's frustum.
        Unit->Body->VisibilityBasedAnimTickOption = EVisibilityBasedAnimTickOption::AlwaysTickPoseAndRefreshBones;
        // Portrait people use the reviewed mid-distance mesh rather than the
        // tactical reduction. Event crowds retain their existing smaller LOD.
        // New costume/robot assets retain their authored hero mesh until a
        // generated LOD has received its own deformation and visual review.
        // ForcedLOD is one-based: request1 means the existing hero LOD0.
        const bool HeroOnly = OldWestCrew::ForVisual(TCHAR_TO_UTF8(*Id)) || OldWestCrew::ForCopy(TCHAR_TO_UTF8(*Id)) || Hidden || Id==TEXT("punk") || Id==TEXT("blacksmith") || Id==TEXT("prospector")
            || Id==TEXT("gatling_gunner") || Id==TEXT("bounty_hunter") || Id==TEXT("quanah_parker") || Id==TEXT("lozen") || Id==TEXT("sarah-winnemucca");
        Unit->Body->SetForcedLOD(HeroOnly ? 1 : Type==TEXT("person") ? 2 : 3);
        if(UMaterialInterface* Steel=LoadObject<UMaterialInterface>(nullptr,TEXT("/Game/Art/CardPortraits/M_Portrait_Weapon.M_Portrait_Weapon")))
            for(int32 Slot=0;Slot<Unit->Weapon->GetNumMaterials();++Slot) Unit->Weapon->SetMaterial(Slot,Steel);
        return Unit;
    }
    void BuildPerson()
    {
        const bool Unarmed = Hidden || Id==TEXT("bartender") || Id==TEXT("hellfire_preacher") || Id==TEXT("prospector") || Id==TEXT("blacksmith") || Id==TEXT("con_man") || Id==TEXT("doc_holliday") || Id==TEXT("pinkerton_agent") || Id==TEXT("ringleader");
        Person(FVector::ZeroVector,Unarmed);
        Focus=Origin+FVector(0,0,111);
        if (Hidden) { Flag(FVector(70,45,0),TEXT("DustCanvas"),.7f); return; }
        // Approved Crew portraits are plain character studies; old canonical
        // occupation vignettes contain unreviewed sci-fi equipment.
        if (OldWestCrew::ForVisual(TCHAR_TO_UTF8(*Id)) || OldWestCrew::ForCopy(TCHAR_TO_UTF8(*Id))) return;
        // Every person receives a deliberate action/occupation vignette. The
        // survivor's breathing/weapon idle is real skeletal animation throughout.
        if (Id==TEXT("wyatt_earp")) { Person(FVector(40,80,0),true,.75f); Flag(FVector(-70,60,0),TEXT("FadedTurquoise")); }
        else if (Id==TEXT("bounty_hunter")) { Part(TEXT("Cube"),FVector(60,75,70),FVector(.6,.3,1.4),TEXT("Concrete")); Part(TEXT("Cone"),FVector(-47,28,63),FVector(.06,.06,.62),TEXT("Galvanized"),FRotator(30,20,0)); }
        else if (Id==TEXT("hellfire_preacher")) { Flag(FVector(70,65,0),TEXT("FadedRose")); Flame(FVector(-45,80,0),.6f); }
        else if (Id==TEXT("pinkerton_agent")) { Beacon(FVector(75,40,0),TEXT("StatusLight")); Part(TEXT("Sphere"),FVector(75,40,125),FVector(.35),TEXT("Copper")); }
        else if (Id==TEXT("regulator")) { Tank(FVector(55,50,0),TEXT("ClinicPaint"),.7f); Flame(FVector(-50,80,0),.6f); }
        else if (Id==TEXT("gatling_gunner")) { for (int I=0;I<5;++I) Part(TEXT("Cylinder"),FVector(-60+I*8,35,16),FVector(.035,.035,.3),TEXT("Copper")); Crate(FVector(60,50,0),.75f); }
        else if (Id==TEXT("widow_with_a_shotgun")) { for(int I=0;I<4;++I) Part(TEXT("Cube"),FVector((I-2)*35,65,13+I*4),FVector(.45,.45,.3),TEXT("Concrete"),FRotator(0,I*24,12)); }
        // Quanah uses the approved plain character study without Karli's flame/flag vignette.
        else if (Id==TEXT("quanah_parker")) {}
        else if (Id==TEXT("claim_jumper")) { Crate(FVector(-65,45,0),.75f); Crate(FVector(60,55,0),.5f); Tank(FVector(55,55,27),TEXT("FadedTurquoise"),.35f); }
        else if (Id==TEXT("augustus_powder_pike")) { for(int I=0;I<3;++I) Crate(FVector(-90+I*85,90,0),.6f); Beacon(FVector(75,30,0),TEXT("AmberLamp")); }
        else if (Id==TEXT("con_man")) { Part(TEXT("Cube"),FVector(65,70,82),FVector(.65,.04,1.2),TEXT("SmokedGlass"),FRotator(0,-18,0)); Flag(FVector(-60,65,0),TEXT("FadedTurquoise"),.75f); }
        else if (Id==TEXT("cornelius_ashby_railroad_baron")) { Tank(FVector(70,45,0),TEXT("CorrodedSteel"),.85f); Part(TEXT("Cylinder"),FVector(70,45,110),FVector(.2,.2,.85),TEXT("DarkSteel"),FRotator(0,0,65)); }
        else if (Id==TEXT("bartender")) { Tank(FVector(70,35,0),TEXT("FadedTurquoise"),.7f); Animate(Part(TEXT("Sphere"),FVector(70,35,95),FVector(.08,.08,.16),TEXT("StatusLight")),TEXT("drip"),FVector(0,0,-50)); }
        else if (Id==TEXT("doc_holliday")) { Tank(FVector(70,35,0),TEXT("ClinicPaint"),.7f); Beacon(FVector(-60,50,0),TEXT("StatusLight")); }
        else if (Id==TEXT("barn_burner")) { Tank(FVector(60,40,0),TEXT("FadedRose"),.7f); Flame(FVector(-40,70,0),1.f); }
        else if (Id==TEXT("ringleader")) { Flag(FVector(70,55,0),TEXT("FadedRose")); Person(FVector(-60,85,0),true,.65f); }
        // Blacksmith's real articulated chassis is the scene; its exposed
        // actuators and service spool replace the former human/tool-cube proxy.
        else if (Id==TEXT("blacksmith")) {}
        else if (Id==TEXT("sarah_winnemucca")) { Part(TEXT("Cube"),FVector(65,45,32),FVector(.45,1.3,.06),TEXT("DustCanvas")); for(float Y:{-17.f,108.f}) Part(TEXT("Cylinder"),FVector(65,Y,21),FVector(.03,.03,.45),TEXT("Galvanized")); Beacon(FVector(-60,50,0),TEXT("StatusLight")); }
        else if (Id==TEXT("prospector")) { Crate(FVector(65,40,0),.85f); for(int I=0;I<3;++I) { Tank(FVector(48+I*15,40,42),I%2?TEXT("StatusLight"):TEXT("ClinicPaint"),.15f); } Beacon(FVector(-55,55,0),TEXT("StatusLight")); }
        else if (Id==TEXT("rustler")) { Flag(FVector(-60,60,0),TEXT("FadedTurquoise"),.75f); Part(TEXT("Cube"),FVector(65,55,32),FVector(.6,.7,.65),TEXT("Concrete")); }
        else if (Id==TEXT("annie_oakley")) { Part(TEXT("Cube"),FVector(55,70,62),FVector(.85,.3,1.24),TEXT("Concrete")); Beacon(FVector(-65,65,0),TEXT("Copper")); }
        else if (Id==TEXT("duelist")) { Part(TEXT("Cube"),FVector(65,50,57),FVector(.08,.6,1.1),TEXT("Galvanized"),FRotator(0,-18,0)); Person(FVector(-55,90,0),true,.6f); }
        else if (Id==TEXT("charles_goodnight")) { Beacon(FVector(65,40,0),TEXT("StatusLight")); Flag(FVector(-60,60,0),TEXT("FadedTurquoise")); }
        else if (Id==TEXT("vigilante")) { Part(TEXT("Cube"),FVector(65,60,58),FVector(.6,.07,.8),TEXT("StencilledChalk")); Part(TEXT("Cylinder"),FVector(65,60,27),FVector(.035,.035,.55),TEXT("DarkSteel")); }
        else if (Id==TEXT("civil_war_veteran")) { Crate(FVector(60,40,0),.7f); Part(TEXT("Cube"),FVector(60,14,23),FVector(.24,.02,.07),TEXT("ClinicPaint")); Part(TEXT("Cube"),FVector(60,14,23),FVector(.07,.02,.24),TEXT("ClinicPaint")); }
        else if (Id==TEXT("poker_alice")) { Beacon(FVector(65,45,0),TEXT("AmberLamp")); Flag(FVector(-65,60,0),TEXT("FadedRose")); }
    }
    void BuildEvent()
    {
        Focus=Origin+FVector(0,0,105);
        if (Id==TEXT("hip_flask"))
        {
            // Hip Flask (Western presentation of the Hip Flask): an amber pint union-oval
            // flask, corked, slowly turning so its glass catches the light.
            Animate(AssetMesh(TEXT("/Game/Art/ActionProps/Meshes/SM_Action_HipFlask.SM_Action_HipFlask"),FVector(-20,0,0),165.f,FRotator(0,-30,0)),
                TEXT("rotate"),FVector(0,0,22));
            Crate(FVector(110,45,0));
        }
        else if(Id==TEXT("stampede"))
        {
            FActorSpawnParameters Params;
            Params.SpawnCollisionHandlingOverride=ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
            AOldWestUnit* Vehicle=World->SpawnActor<AOldWestUnit>(Origin,FRotator::ZeroRotator,Params);
            if(Vehicle) {
                Actors.Add(Vehicle); Vehicle->SetPreviewOnly(true);
                Vehicle->ConfigureEvent(-2000,0,TEXT(""),TEXT("stampede"));
                Vehicle->SetPreviewOnly(true);
            }
            Focus=Origin+FVector(0,0,115);
        }
        else if(const auto* Trouble=OldWestTrouble::ForCard(TCHAR_TO_UTF8(*Id)))
        {
            // The portrait uses the same documented miniature as the fuse.
            // Preserve its authored materials and geometry, with no proxy people.
            const FString Mesh=UTF8_TO_TCHAR(Trouble->Mesh);
            const FString Path=FString(TEXT("/Game/Art/Western/Trouble/"))+UTF8_TO_TCHAR(Trouble->Folder)+TEXT("/Meshes/")+Mesh+TEXT(".")+Mesh;
            TroubleProp=AssetMesh(*Path,FVector::ZeroVector,190.f);
        }
    }
    void Build()
    {
        if(!World.IsValid()) return;
        FActorSpawnParameters Params; Params.ObjectFlags|=RF_Transient;
        Params.SpawnCollisionHandlingOverride=ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
        Stage=World->SpawnActor<AActor>(Origin,FRotator::ZeroRotator,Params);
        if(!Stage) return;
        Actors.Add(Stage); Stage->Tags.Add(PreviewTag); Stage->SetActorEnableCollision(false);
        USceneComponent* Root=NewObject<USceneComponent>(Stage); Stage->AddInstanceComponent(Root);
        Stage->SetRootComponent(Root); Root->RegisterComponent(); Stage->SetActorLocation(Origin);
        float Radius=175.f;
        FBox FramingBounds(ForceInit);
        if(Type==TEXT("camp"))
        {
            Camp=Component<UOldWestCampVisuals>(); Camp->Build(Id); Camp->SetCondition(0,false);
            FBox Bounds=Camp->GetPortraitBounds();
            FramingBounds=Bounds;
            Focus=Bounds.IsValid?Bounds.GetCenter():Origin+FVector(0,0,160);
            Radius=Bounds.IsValid?FMath::Max(Bounds.GetExtent().Size(),250.f):400.f;
        }
        else if(Type==TEXT("person") || Hidden) { BuildPerson(); Radius=132.f; }
        else {
            BuildEvent(); Radius=Id==TEXT("stampede")?280.f:295.f;
            if(TroubleProp.IsValid())
            {
                FramingBounds=TroubleProp->Bounds.GetBox();
                Radius=FMath::Max(132.f,float(FramingBounds.GetExtent().Size()));
            }
            if (Id==TEXT("stampede")) for (AActor* Actor:Actors)
                if (auto* Unit=Cast<AOldWestUnit>(Actor)) FramingBounds=Unit->GetVisualBounds().ExpandBy(25.f);
        }
        // Ground continues beyond the frame. These are places within the
        // wasteland, rather than figures mounted on a circular display plinth.
        Part(TEXT("Plane"),FVector(0,0,-3),FVector(40,40,1),TEXT("PortraitGround"));
        const bool DetailedPerson=Type==TEXT("person"),CampPortrait=Type==TEXT("camp");
        for(int I=0;I<2;++I)
        {
            UPointLightComponent* Light=Component<UPointLightComponent>();
            const float CampLightScale=(CampPortrait || TroubleProp.IsValid())?FMath::Max(1.f,Radius/200.f):1.f;
            Light->SetRelativeLocation(FVector(I?200:-250,-280,I?200:400)*CampLightScale);
            // Holdings are lit as warm daylight with a near-neutral sky fill so their
            // documented paint, brick and roofing colours read at full strength
            // (full-colour art direction, October 7, 2026).
            Light->SetLightColor(DetailedPerson?(I?FLinearColor(.60f,.74f,.80f):FLinearColor(1.f,.86f,.68f)):
                (CampPortrait || TroubleProp.IsValid())?(I?FLinearColor(.80f,.88f,1.f):FLinearColor(1.f,.88f,.70f)):(I?FLinearColor(.45f,.75f,1.f):FLinearColor(1.f,.79f,.57f)));
            Light->bUseInverseSquaredFalloff=false;
            Light->LightFalloffExponent=2.f;
            Light->SetIntensity(I?2.f:4.f);
            Light->SetLightingChannels(false,false,true);
            Light->SetAttenuationRadius(FMath::Max(1600.f,Radius*5.f));
            Light->SetCastShadows(DetailedPerson && I==0);
            // A point-source shadow has a stable edge at the capture's 15 Hz.
            // Large stochastic VSM penumbras need temporal denoising and looked
            // visibly speckled on these small, deliberately history-free views.
            // SoftSourceRadius broadens the specular source without adding that
            // noisy area-shadow integration.
            if(DetailedPerson && I==0) { Light->SetSourceRadius(0.f); Light->SetSoftSourceRadius(45.f); }
        }
        Target=NewObject<UTextureRenderTarget2D>(GetTransientPackage());
        Target->ClearColor=FLinearColor(.016f,.023f,.027f,1.f);
        const int32 PortraitWidth=DetailedPerson?768:384,PortraitHeight=DetailedPerson?512:256;
        Target->InitCustomFormat(PortraitWidth,PortraitHeight,PF_B8G8R8A8,false); Target->UpdateResourceImmediate(true);
        Capture=Component<USceneCaptureComponent2D>();
        Capture->TextureTarget=Target; Capture->bCaptureEveryFrame=false; Capture->bCaptureOnMovement=false;
        Capture->bAlwaysPersistRenderingState=true;
        Capture->PrimitiveRenderMode=ESceneCapturePrimitiveRenderMode::PRM_UseShowOnlyList;
        Capture->ShowOnlyActors=Actors;
        Capture->CaptureSource=ESceneCaptureSource::SCS_FinalColorLDR;
        Capture->FOVAngle=35.f;
        Frame(Radius,FramingBounds);
        Capture->ShowFlags.SetAtmosphere(false); Capture->ShowFlags.SetFog(false);
        Capture->ShowFlags.SetDirectionalLights(false); Capture->ShowFlags.SetSkyLighting(false);
        Capture->ShowFlags.SetMotionBlur(false); Capture->ShowFlags.SetTemporalAA(false);
        Capture->ShowFlags.SetScreenSpaceReflections(false);
        auto& P=Capture->PostProcessSettings;
        P.bOverride_AutoExposureMethod=true; P.AutoExposureMethod=AEM_Manual;
        P.bOverride_AutoExposureApplyPhysicalCameraExposure=true; P.AutoExposureApplyPhysicalCameraExposure=false;
        P.bOverride_AutoExposureBias=true; P.AutoExposureBias=DetailedPerson?-.8f:(CampPortrait || TroubleProp.IsValid())?-.45f:-1.f;
        if(CampPortrait) { P.bOverride_ColorSaturation=true; P.ColorSaturation=FVector4(1.12f,1.12f,1.12f,1.f); }
        P.bOverride_DynamicGlobalIlluminationMethod=true; P.DynamicGlobalIlluminationMethod=EDynamicGlobalIlluminationMethod::None;
        P.bOverride_ReflectionMethod=true; P.ReflectionMethod=EReflectionMethod::None;
        P.bOverride_BloomIntensity=true; P.BloomIntensity=.12f;
        P.bOverride_VignetteIntensity=true; P.VignetteIntensity=.2f;
        Capture->PostProcessBlendWeight=1.f;
        Brush.SetResourceObject(Target); Brush.ImageSize=FVector2D(PortraitWidth,PortraitHeight); Brush.DrawAs=ESlateBrushDrawType::Image;
        // Portraits never participate in mouse picking or collision, including
        // dynamically added camp pieces.
        AdaptPreviewMaterials();
    }
    void Frame(float Radius,const FBox& FramingBounds)
    {
        CompositionFitActive=false; CompositionFitFallback=false; CompositionFitIterations=0;
        if(FramingBounds.IsValid) Focus=FramingBounds.GetCenter();
        const FVector Direction=FVector(-.55f,-1.f,.4f).GetSafeNormal();
        const FRotator CameraRotation=(-Direction).Rotation();
        float CameraDistance=Radius*3.3f;
        if(FramingBounds.IsValid)
        {
            // FOVAngle is horizontal; the 3:2 target has a tighter vertical
            // angle. Fit every real corner, allowing room for moving flags and
            // rotating mechanisms, rather than assuming a spherical multiplier.
            const FRotationMatrix Basis(CameraRotation);
            const FVector Forward=Basis.GetUnitAxis(EAxis::X),Right=Basis.GetUnitAxis(EAxis::Y),Up=Basis.GetUnitAxis(EAxis::Z);
            const float TanH=FMath::Tan(FMath::DegreesToRadians(Capture->FOVAngle*.5f)),TanV=TanH/1.5f;
            CameraDistance=100.f;
            for(int32 Corner=0;Corner<8;++Corner)
            {
                const FVector Point((Corner&1)?FramingBounds.Max.X:FramingBounds.Min.X,
                    (Corner&2)?FramingBounds.Max.Y:FramingBounds.Min.Y,(Corner&4)?FramingBounds.Max.Z:FramingBounds.Min.Z);
                const FVector Offset=Point-Focus;
                const float Depth=FVector::DotProduct(Offset,Forward);
                CameraDistance=FMath::Max(CameraDistance,float(FMath::Abs(FVector::DotProduct(Offset,Right))*1.15f/TanH-Depth));
                CameraDistance=FMath::Max(CameraDistance,float(FMath::Abs(FVector::DotProduct(Offset,Up))*1.15f/TanV-Depth));
            }
        }
        const FVector CameraPosition=Focus+Direction*CameraDistance;
        Capture->SetWorldLocation(CameraPosition); Capture->SetWorldRotation(CameraRotation);
        if(!Camp || !FramingBounds.IsValid) return;
        TArray<FVector> Solids,Flames;
        Camp->AppendPortraitFramingPoints(CameraPosition,Solids,Flames);
        // Preserve the reviewed framing of camps without visible flame sheets,
        // including extinguished ruins. Only burning camp portraits refit.
        if(Flames.IsEmpty()) return;
        const FRotationMatrix Basis(CameraRotation);
        const FVector Forward=Basis.GetUnitAxis(EAxis::X),Right=Basis.GetUnitAxis(EAxis::Y),Up=Basis.GetUnitAxis(EAxis::Z);
        const double TanH=FMath::Tan(FMath::DegreesToRadians(Capture->FOVAngle*.5f)),TanV=TanH/1.5;
        FVector Candidate=CameraPosition;
        for(int32 Attempt=0;Attempt<8;++Attempt)
        {
            CompositionFitIterations=Attempt+1;
            Solids.Reset(); Flames.Reset();
            Camp->AppendPortraitFramingPoints(Candidate,Solids,Flames);
            TArray<FVector> Points=Solids; Points.Append(Flames);
            if(Points.IsEmpty()) break;
            FBox SubjectBounds(ForceInit);
            for(const FVector& Point:Points) SubjectBounds+=Point;
            const FVector CandidateFocus=SubjectBounds.GetCenter();
            double Distance=100.;
            for(const FVector& Point:Points)
            {
                const FVector Offset=Point-CandidateFocus;
                const double Depth=FVector::DotProduct(Offset,Forward);
                // Extra 1% fitting slack allows the subsequent per-view
                // billboard recomputation to retain the existing 15% margin.
                Distance=FMath::Max(Distance,FMath::Abs(FVector::DotProduct(Offset,Right))*1.16/TanH-Depth);
                Distance=FMath::Max(Distance,FMath::Abs(FVector::DotProduct(Offset,Up))*1.16/TanV-Depth);
                Distance=FMath::Max(Distance,80.-Depth);
            }
            Candidate=CandidateFocus+Direction*Distance;
            // Moving the camera changes each sheet's own tilt/yaw. Validate
            // fresh full-sheet envelopes at the actual candidate, not the
            // previous iteration's points or an arbitrary shrink factor.
            Solids.Reset(); Flames.Reset();
            Camp->AppendPortraitFramingPoints(Candidate,Solids,Flames);
            Points=Solids; Points.Append(Flames);
            bool Fits=!Points.IsEmpty();
            for(const FVector& Point:Points)
            {
                const FVector Offset=Point-Candidate;
                const double Depth=FVector::DotProduct(Offset,Forward);
                Fits=Fits && Depth>=79.99
                    && FMath::Abs(FVector::DotProduct(Offset,Right))*1.15<=Depth*TanH
                    && FMath::Abs(FVector::DotProduct(Offset,Up))*1.15<=Depth*TanV;
            }
            if(Fits)
            {
                CompositionFitActive=true;
                Focus=CandidateFocus;
                Capture->SetWorldLocation(Candidate);
                return;
            }
        }
        // Keep the original complete-world-box view if a future shader/asset
        // cannot satisfy this bounded fit. Telemetry makes fallback explicit.
        CompositionFitFallback=true;
    }
    void AdaptPreviewMaterials()
    {
        TInlineComponentArray<UOldWestFireVisuals*> Fires;
        if(Stage) Stage->GetComponents(Fires);
        for(UOldWestFireVisuals* Fire:Fires) Fire->SetEmissionScale(1.f);
        for(AActor* Actor:Actors)
        {
            Actor->SetActorEnableCollision(false);
            TInlineComponentArray<UPrimitiveComponent*> Primitives; Actor->GetComponents(Primitives);
            for(UPrimitiveComponent* Primitive:Primitives)
            {
                Primitive->SetLightingChannels(false,false,true);
                if(Camp) if(auto* Static=Cast<UStaticMeshComponent>(Primitive))
                    if(Static->GetStaticMesh() && Static->GetStaticMesh()->GetPathName().StartsWith(TEXT("/Game/Art/Western/")))
                        Static->bForceMipStreaming=true;
                for(int32 Slot=0;Slot<Primitive->GetNumMaterials();++Slot) if(UMaterialInterface* Material=Primitive->GetMaterial(Slot))
                {
                    const FString Name=Material->GetMaterial()->GetName();
                    const FString Lamp=Name==TEXT("M_Camp_AmberLamp")?TEXT("Amber"):Name==TEXT("M_Camp_StatusLight")?TEXT("Teal"):FString();
                    if(!Lamp.IsEmpty())
                    {
                        const FString Path=TEXT("/Game/Art/CardPortraits/M_Portrait_")+Lamp;
                        if(UMaterialInterface* Replacement=LoadObject<UMaterialInterface>(nullptr,*(Path+TEXT(".")+FPaths::GetBaseFilename(Path)))) Primitive->SetMaterial(Slot,Replacement);
                    }
                    if(Name==TEXT("M_Portrait_Flame") || Name==TEXT("M_RepairBot_Atlas"))
                    {
                        auto* Instance=UMaterialInstanceDynamic::Create(Material->GetMaterial(),Stage);
                        Instance->SetScalarParameterValue(TEXT("EmissionScale"),1.f);
                        Primitive->SetMaterial(Slot,Instance);
                    }
                }
            }
        }
    }
    FPortraitRenderReadiness RenderReadiness() const
    {
        FPortraitRenderReadiness State;
        TSet<UTexture2D*> SeenTextures;
        for (const AActor* Actor : Actors) if (IsValid(Actor))
        {
            TInlineComponentArray<UPrimitiveComponent*> Primitives;
            Actor->GetComponents(Primitives);
            for (const UPrimitiveComponent* Primitive : Primitives)
            {
                if (!IsValid(Primitive) || !Primitive->ShouldRender()) continue;
                const UStaticMeshComponent* Static = Cast<UStaticMeshComponent>(Primitive);
                const USkeletalMeshComponent* Skeletal = Cast<USkeletalMeshComponent>(Primitive);
                if (!(Static && Static->GetStaticMesh()) && !(Skeletal && Skeletal->GetSkeletalMeshAsset())) continue;
                ++State.ExpectedMeshes;
                if (!Primitive->IsRegistered()) ++State.MissingRegistrations;
                if (Primitive->IsPSOPrecaching()) ++State.PendingPSOs;
                if (!Primitive->IsRenderStateCreated()) ++State.MissingRenderStates;
                if (Primitive->IsRenderStateDirty()) ++State.DirtyRenderStates;
                if (!Primitive->GetSceneProxy()) ++State.MissingProxies;
                if(Primitive->bForceMipStreaming)
                    for(int32 Slot=0;Slot<Primitive->GetNumMaterials();++Slot) if(UMaterialInterface* Material=Primitive->GetMaterial(Slot))
                    {
                        TArray<UTexture*> Used; Material->GetUsedTextures(Used);
                        for(UTexture* Texture:Used) if(UTexture2D* Map=Cast<UTexture2D>(Texture))
                        {
                            if(SeenTextures.Contains(Map)) continue;
                            SeenTextures.Add(Map); ++State.ExpectedTextures;
                            if(!Map->IsFullyStreamedIn()) ++State.PendingTextures;
                        }
                    }
            }
        }
        return State;
    }
    bool CanDisplayCapture() const
    {
        return CompleteRenderSubmissions >= 2 && GFrameCounter > LastCompleteRenderFrame && CompleteCaptureFence.IsFenceComplete() &&
            PortraitCompilationState().IsReady() && RenderReadiness().IsReady();
    }
    void Update(double Now)
    {
        if(!World.IsValid() || !IsValid(Capture) || GFrameCounter>LastVisibleFrame+2 || Now+.0005<NextCapture) return;
        // Manual scene captures have no player viewport to register their
        // streaming view. Without this, distant gallery people retain only
        // 64px texture mips, losing skin detail and bleeding outfit UV islands.
        // Keep the view only between visible captures; hidden galleries expire.
        const float Width=float(Target->SizeX);
        IStreamingManager::Get().AddViewInformation(Capture->GetComponentLocation(),Width,
            Width/FMath::Tan(FMath::DegreesToRadians(Capture->FOVAngle*.5f)),
            1.f,false,float(CaptureInterval*3),nullptr,World);
#if !UE_BUILD_SHIPPING
        if(!PortraitCompilationState().IsReady()) ResetCompilationReadiness();
        else if(CompilationZeroCapture<0)
        {
            CompilationZeroCapture=CaptureCount;
            CompilationZeroFrame=GFrameCounter;
        }
#endif
        const bool ReadyBeforeCapture = PortraitCompilationState().IsReady() && RenderReadiness().IsReady();
        if (!ReadyBeforeCapture) CompleteRenderSubmissions = 0;
        const float Time=float(Now-Born);
        for(const FMotion& M:Motions) if(UStaticMeshComponent* Part=M.Part.Get())
        {
            const float T=Time*M.Rate+M.Phase;
            const float Wave=FMath::Sin(T*2.f*PI), Cycle=FMath::Frac(T);
            if(M.Kind==TEXT("rotate")) Part->SetRelativeRotation(M.Rotation+FRotator(M.Axis.Y*T,M.Axis.Z*T,M.Axis.X*T));
            else if(M.Kind==TEXT("flag")) { Part->SetRelativeLocation(M.Position+M.Axis*Wave); Part->SetRelativeRotation(M.Rotation+FRotator(0,Wave*7.f,Wave*3.f)); }
            else if(M.Kind==TEXT("flame")) { Part->SetRelativeScale3D(M.Scale*FVector(1.f+.15f*Wave,1.f+.1f*Wave,.8f+.3f*FMath::Sin(T*8.f))); Part->SetRelativeLocation(M.Position+M.Axis*Wave*.4f); }
            else if(M.Kind==TEXT("drip")) Part->SetRelativeLocation(M.Position+M.Axis*Cycle);
            else if(M.Kind==TEXT("pass")) Part->SetRelativeLocation(M.Position+M.Axis*(Cycle-.5f));
            else if(M.Kind==TEXT("dust")) { Part->SetRelativeLocation(M.Position+M.Axis*Cycle); Part->SetRelativeScale3D(M.Scale*(.4f+FMath::Sin(Cycle*PI))); }
            else if(M.Kind==TEXT("lift")) Part->SetRelativeLocation(M.Position+M.Axis*(.5f+.5f*Wave));
        }
        Capture->CaptureScene(); LastCapture=Now; ++CaptureCount;
        // Cooked builds can defer render proxies while PSOs compile, even
        // though every asset is loaded. Keep capturing to warm the scene, but
        // publish only after two complete submissions on distinct frames.
        if (ReadyBeforeCapture && PortraitCompilationState().IsReady() && RenderReadiness().IsReady())
        {
            if (CompleteRenderSubmissions < 2 && GFrameCounter > LastCompleteRenderFrame)
            {
                ++CompleteRenderSubmissions;
                LastCompleteRenderFrame = GFrameCounter;
                if (CompleteRenderSubmissions == 2) CompleteCaptureFence.BeginFence();
            }
        }
        else CompleteRenderSubmissions = 0;
#if !UE_BUILD_SHIPPING
        // Capture submission can itself request a new material permutation.
        // Reset immediately if that happened. Count only captures on later
        // frames than the zero observation, never the observation frame itself.
        if(!PortraitCompilationState().IsReady()) ResetCompilationReadiness();
        else if(CompilationZeroCapture>=0 && GFrameCounter>CompilationZeroFrame && GFrameCounter>LastReadyCaptureFrame)
        {
            ++ReadyCaptureCount;
            LastReadyCaptureFrame=GFrameCounter;
        }
#endif
        // Preserve the cadence across tiny frame-time errors. Restarting a
        // 1/15 timer on each draw can turn a 30 Hz game into 10 Hz captures.
        // A long hidden/stalled interval starts fresh; never queue catch-up work.
        NextCapture=FMath::Max(NextCapture+CaptureInterval,Now-.0005);
        if(NextCapture<=Now-.0005) NextCapture=Now+CaptureInterval;
    }
};

struct FPortraitPool
{
    TMap<FString,TSharedPtr<FPortraitScene>> Scenes;
    FDelegateHandle Cleanup;
    FTSTicker::FDelegateHandle Sweep;
    FPortraitPool()
    {
        Sweep=FTSTicker::GetCoreTicker().AddTicker(FTickerDelegate::CreateLambda([this](float) { Prune(FPlatformTime::Seconds()); return true; }),.5f);
        Cleanup=FWorldDelegates::OnWorldCleanup.AddLambda([this](UWorld* World,bool,bool)
        {
            for(auto It=Scenes.CreateIterator();It;++It) if(It.Value()->World.Get()==World) { It.Value()->Release(); It.RemoveCurrent(); }
        });
    }
    ~FPortraitPool() { FTSTicker::GetCoreTicker().RemoveTicker(Sweep); FWorldDelegates::OnWorldCleanup.Remove(Cleanup); Scenes.Empty(); }
    void Prune(double Now)
    {
        for(auto It=Scenes.CreateIterator();It;++It)
            if(!It.Value()->World.IsValid() || (Now-It.Value()->LastVisible>1.5 && GFrameCounter>It.Value()->LastVisibleFrame+2)) { It.Value()->Release(); It.RemoveCurrent(); }
    }
    TSharedPtr<FPortraitScene> Get(UWorld* World,const FString& Id,const FString& Type,bool Hidden)
    {
        if(!World || World->bIsTearingDown || World->GetNetMode()==NM_DedicatedServer) return nullptr;
        const FString SafeId=Hidden?TEXT("concealed_punk"):Id;
        const FString SafeType=Hidden?TEXT("person"):Type;
        const FString Key=FString::Printf(TEXT("%p|%s|%s"),World,*SafeType,*SafeId);
        auto* Found=Scenes.Find(Key);
        if(Found) return *Found;
        TSharedPtr<FPortraitScene> Scene=MakeShared<FPortraitScene>(World,SafeId,SafeType,Hidden);
        Scenes.Add(Key,Scene); return Scene;
    }
};
FPortraitPool& Pool() { static FPortraitPool Instance; return Instance; }

class SOldWestCardPortrait : public SLeafWidget
{
public:
    SLATE_BEGIN_ARGS(SOldWestCardPortrait) {} SLATE_ARGUMENT(UWorld*,World) SLATE_ARGUMENT(FString,CardId) SLATE_ARGUMENT(FString,CardType) SLATE_ARGUMENT(bool,HiddenPunk) SLATE_END_ARGS()
    void Construct(const FArguments& Args)
    {
        World=Args._World; Hidden=Args._HiddenPunk;
        Id=Hidden?TEXT("concealed_punk"):Args._CardId; Type=Hidden?TEXT("person"):Args._CardType;
        SetCanTick(true); ForceVolatile(true); SetVisibility(EVisibility::HitTestInvisible);
    }
    void Tick(const FGeometry& Geometry,double CurrentTime,float DeltaTime) override
    {
        SLeafWidget::Tick(Geometry,CurrentTime,DeltaTime);
        const double Now=FPlatformTime::Seconds();
        Pool().Prune(Now);
        if(LastPaintFrame==MAX_uint64 || GFrameCounter>LastPaintFrame+2) { Scene.Reset(); return; }
        if(!Scene.IsValid() || !Scene->Capture) Scene=Pool().Get(World.Get(),Id,Type,Hidden);
        if(Scene) { Scene->LastVisible=Now; Scene->LastVisibleFrame=GFrameCounter; Scene->Update(Now); }
    }
    FVector2D ComputeDesiredSize(float) const override { return FVector2D(240,160); }
    int32 OnPaint(const FPaintArgs& Args,const FGeometry& Geometry,const FSlateRect& CullingRect,FSlateWindowElementList& Elements,int32 Layer,const FWidgetStyle& Style,bool Enabled) const override
    {
        const FSlateRect Bounds=Geometry.GetRenderBoundingRect();
        if(Bounds.Right>CullingRect.Left && Bounds.Left<CullingRect.Right && Bounds.Bottom>CullingRect.Top && Bounds.Top<CullingRect.Bottom)
        {
            LastPaintFrame=GFrameCounter;
            if(Scene) { Scene->LastVisible=FPlatformTime::Seconds(); Scene->LastVisibleFrame=GFrameCounter; }
            FSlateDrawElement::MakeBox(Elements,Layer,Geometry.ToPaintGeometry(),FCoreStyle::Get().GetBrush(TEXT("WhiteBrush")),
                ESlateDrawEffect::None,FLinearColor(.018f,.026f,.03f));
            const bool DisplayCapture = Scene.IsValid() && Scene->Target && Scene->CanDisplayCapture();
#if !UE_BUILD_SHIPPING
            if (Scene)
            {
                Scene->LastPaintedFrame = GFrameCounter;
                Scene->LastPaintedPlaceholder = !DisplayCapture;
            }
#endif
            if(DisplayCapture)
            {
                // The same portrait also appears in narrow hand cards and wide
                // inspectors. Preserve its camera aspect instead of stretching
                // a human body to each container's proportions.
                const FVector2D Size=Geometry.GetLocalSize();
                const float Width=FMath::Min(float(Size.X),float(Size.Y)*1.5f);
                const FVector2D ImageSize(Width,Width/1.5f);
                const FVector2D Offset=(Size-ImageSize)*.5f;
                FSlateDrawElement::MakeBox(Elements,Layer+1,Geometry.ToPaintGeometry(ImageSize,FSlateLayoutTransform(Offset)),
                    &Scene->Brush,ESlateDrawEffect::IgnoreTextureAlpha,FLinearColor::White);
            }
        }
        return Layer+1;
    }
private:
    TWeakObjectPtr<UWorld> World;
    FString Id,Type;
    bool Hidden=false;
    mutable uint64 LastPaintFrame=MAX_uint64;
    TSharedPtr<FPortraitScene> Scene;
};
}

TSharedRef<SWidget> MakeOldWestCardPortrait(UWorld* World,const FString& CardId,const FString& CardType,bool HiddenPunk)
{
    return SNew(SOldWestCardPortrait).World(World).CardId(CardId).CardType(CardType).HiddenPunk(HiddenPunk);
}

#if !UE_BUILD_SHIPPING
bool SetOldWestCardPortraitCondition(UWorld* World,const FString& CardId,int32 Damage,bool Destroyed)
{
    for(auto& Pair:Pool().Scenes)
    {
        auto& Scene=*Pair.Value;
        if(Scene.World.Get()==World && Scene.Id==CardId && Scene.Camp)
        {
            ++Scene.ConditionRevision;
            Scene.ResetCompilationReadiness();
            Scene.CompleteRenderSubmissions = 0;
            Scene.CampDamage=FMath::Clamp(Damage,0,2); Scene.CampDestroyed=Destroyed;
            Scene.Camp->SetCondition(Scene.CampDamage,Destroyed,true);
            Scene.AdaptPreviewMaterials();
            Scene.Frame(0.f,Scene.Camp->GetPortraitBounds());
            return true;
        }
    }
    return false;
}

bool SetOldWestCardPortraitDetail(UWorld* World,const FString& CardId,bool Enabled,const FString& Expression)
{
    TMap<FString,float> Requested;
    if(Expression==TEXT("blink")) Requested.Add(TEXT("Eyes_Closed_Max"),1.f);
    else if(Expression==TEXT("jaw-open")) { Requested.Add(TEXT("Jaw_Lower"),.6f); Requested.Add(TEXT("Mouth_Large_Opened"),.35f); }
    else if(Expression==TEXT("smile")) Requested.Add(TEXT("Smile_Lips_Closed"),.8f);
    else if(Expression==TEXT("brows-raised")) { Requested.Add(TEXT("Eyebrows_Raised_Left"),.85f); Requested.Add(TEXT("Eyebrows_Raised_Right"),.85f); }
    else if(Expression==TEXT("brows-frown")) { Requested.Add(TEXT("Eyebrows_Frown_Left"),.85f); Requested.Add(TEXT("Eyebrows_Frown_Right"),.85f); }
    else if(Expression!=TEXT("neutral")) return false;
    for(auto& Pair:Pool().Scenes)
    {
        auto& S=*Pair.Value;
        if(S.World.Get()!=World || S.Id!=CardId || S.Type!=TEXT("person") || S.Hidden || !S.Capture) continue;
        AOldWestUnit* Person=nullptr;
        for(AActor* Actor:S.Actors) if(AOldWestUnit* Unit=Cast<AOldWestUnit>(Actor)) { Person=Unit; break; }
        if(!Person || !Person->Body->GetSkeletalMeshAsset() || Person->Body->GetBoneIndex(TEXT("Head"))==INDEX_NONE) return false;
        TMap<FName,float> Morphs;
        for(const auto& RequestedMorph:Requested)
        {
            UMorphTarget* Found=nullptr;
            for(UMorphTarget* Morph:Person->Body->GetSkeletalMeshAsset()->GetMorphTargets())
                if(Morph && Morph->GetName().EndsWith(RequestedMorph.Key)) { Found=Morph; break; }
            if(!Found) return false;
            Morphs.Add(Found->GetFName(),RequestedMorph.Value);
        }
        if(Enabled && !S.DetailReview)
        {
            UAnimSingleNodeInstance* Previous=Person->Body->GetSingleNodeInstance();
            UAnimSequence* Idle=LoadObject<UAnimSequence>(nullptr,TEXT("/Game/Art/Survivors/SurvivorA/Animations/RA_MM_Idle.RA_MM_Idle"));
            if(!Previous || !Idle) return false;
            S.DetailOriginalCamera=S.Capture->GetComponentTransform();
            S.DetailOriginalBody=Person->Body->GetRelativeTransform();
            S.DetailOriginalAnimation=Previous->GetAnimationAsset();
            S.DetailOriginalTime=Previous->GetCurrentTime(); S.DetailOriginalRate=Previous->GetPlayRate();
            S.DetailOriginalPlaying=Previous->IsPlaying(); S.DetailOriginalLooping=Previous->IsLooping();
            S.DetailOriginalActorTick=Person->IsActorTickEnabled(); S.DetailOriginalWeaponVisible=Person->Weapon->IsVisible();
            // Hold a real neutral animation pose for comparable expression
            // captures. The ordinary animated gallery is checked separately.
            Person->SetActorTickEnabled(false); Person->Weapon->SetVisibility(false);
            Person->Body->PlayAnimation(Idle,false);
            UAnimSingleNodeInstance* Instance=Person->Body->GetSingleNodeInstance();
            Instance->SetRootMotionMode(ERootMotionMode::IgnoreRootMotion);
            Instance->SetPosition(2.f,false); Instance->SetPlaying(false);
            Person->Body->TickAnimation(0.f,false); Person->Body->RefreshBoneTransforms();
        }
        if(Enabled)
        {
            const FVector Focus=Person->Body->GetSocketLocation(TEXT("Head"))+FVector(0,0,8);
            const FVector Position=Focus+FVector(-12,-88,3);
            S.Capture->SetWorldLocation(Position); S.Capture->SetWorldRotation((Focus-Position).Rotation());
        }
        else if(S.DetailReview)
        {
            S.Capture->SetWorldTransform(S.DetailOriginalCamera);
            Person->Body->PlayAnimation(S.DetailOriginalAnimation,S.DetailOriginalLooping);
            UAnimSingleNodeInstance* Instance=Person->Body->GetSingleNodeInstance();
            Instance->SetRootMotionMode(ERootMotionMode::IgnoreRootMotion);
            Instance->SetPosition(S.DetailOriginalTime,false); Instance->SetPlayRate(S.DetailOriginalRate);
            Instance->SetPlaying(S.DetailOriginalPlaying);
            Person->Body->SetRelativeTransform(S.DetailOriginalBody);
            Person->Body->TickAnimation(0.f,false); Person->Body->RefreshBoneTransforms();
            Person->Weapon->SetVisibility(S.DetailOriginalWeaponVisible);
            Person->SetActorTickEnabled(S.DetailOriginalActorTick);
            S.DetailOriginalAnimation=nullptr;
        }
        Person->Body->ClearMorphTargets(); S.DetailMorphs.Empty();
        if(Enabled) for(const auto& Morph:Morphs)
        {
            Person->Body->SetMorphTarget(Morph.Key,Morph.Value);
            S.DetailMorphs.Add(Morph.Key,Morph.Value);
        }
        S.DetailReview=Enabled; S.DetailExpression=Enabled?Expression:FString();
        ++S.ConditionRevision; S.ResetCompilationReadiness(); S.CompleteRenderSubmissions=0;
        return true;
    }
    return false;
}
#endif

FString GetOldWestCardPortraitDebug(UWorld* World)
{
    J Result={{"scenes",J::array()},{"scene_count",0},{"capture_fps",15},{"resolution",{384,256}}};
#if !UE_BUILD_SHIPPING
    const double Now=FPlatformTime::Seconds();
    const FPortraitCompilationState Compilation=PortraitCompilationState();
    Result["compilation"]={{"telemetry_version",1},{"available",Compilation.Available},
        {"mode",WITH_EDITOR?"editor_compilers":"cooked_runtime"},
        {"shader_jobs",Compilation.ShaderJobs},{"asset_jobs",Compilation.AssetJobs},
        {"shader_active",Compilation.ShaderActive},{"ready",Compilation.IsReady()},
        {"frame",GFrameCounter},{"required_post_zero_captures",2}};
    for(const auto& Pair:Pool().Scenes)
    {
        const FPortraitScene& S=*Pair.Value;
        if(S.World.Get()!=World) continue;
        // Exclude a capture submitted on this very frame. The later screenshot
        // is then ordered after at least two post-zero capture frames, even if
        // a slow editor submits a portrait on every game frame.
        const int32 SettledCaptures=FMath::Max(0,S.ReadyCaptureCount-(GFrameCounter<=S.LastReadyCaptureFrame?1:0));
        const FPortraitRenderReadiness RenderState = S.RenderReadiness();
        J RenderReady = {{"expected_meshes", RenderState.ExpectedMeshes}, {"pending_psos", RenderState.PendingPSOs},
            {"expected_textures",RenderState.ExpectedTextures},{"pending_textures",RenderState.PendingTextures},
            {"missing_registrations", RenderState.MissingRegistrations},
            {"missing_render_states", RenderState.MissingRenderStates}, {"dirty_render_states", RenderState.DirtyRenderStates},
            {"missing_proxies", RenderState.MissingProxies},
            {"resources_ready", RenderState.IsReady()}, {"complete_submissions", S.CompleteRenderSubmissions},
            {"last_complete_submission_frame", S.LastCompleteRenderFrame},
            {"ordered_capture_fence_complete", S.CompleteRenderSubmissions >= 2 && S.CompleteCaptureFence.IsFenceComplete()}, {"display_ready", S.CanDisplayCapture()},
            {"last_painted_frame", S.LastPaintedFrame}, {"last_painted_placeholder", S.LastPaintedPlaceholder}};
        J People=J::array(),Vehicles=J::array(),DetailWeights=J::object(),PersonTextures=J::array();
        TSet<UTexture2D*> SeenPersonTextures;
        for(AActor* Actor:S.Actors) if(AOldWestUnit* Unit=Cast<AOldWestUnit>(Actor))
        {
            try { (Unit->IsRaider()?Vehicles:People).push_back(J::parse(TCHAR_TO_UTF8(*Unit->GetIdleDebug()))); } catch(...) {}
            if(S.DetailReview) for(const auto& Morph:S.DetailMorphs)
                DetailWeights[TCHAR_TO_UTF8(*Morph.Key.ToString())]=Unit->Body->GetMorphTarget(Morph.Key);
            for(int32 Slot=0;Slot<Unit->Body->GetNumMaterials();++Slot) if(UMaterialInterface* Material=Unit->Body->GetMaterial(Slot))
            {
                TArray<UTexture*> Used; Material->GetUsedTextures(Used);
                for(UTexture* Texture:Used) if(UTexture2D* Map=Cast<UTexture2D>(Texture))
                {
                    if(SeenPersonTextures.Contains(Map)) continue;
                    SeenPersonTextures.Add(Map);
                    const int32 Resident=Map->GetNumResidentMips(),Missing=FMath::Max(0,Map->GetNumMips()-Resident);
                    PersonTextures.push_back({{"path",TCHAR_TO_UTF8(*Map->GetPathName())},
                        {"platform_mips",Map->GetNumMips()},{"resident_mips",Resident},
                        {"fully_streamed_in",Map->IsFullyStreamedIn()},
                        {"wanted_mips",Map->GetCachedNumWantedLODs()},
                        {"estimated_resident_top_size",{FMath::Max(1,Map->GetSizeX()>>Missing),FMath::Max(1,Map->GetSizeY()>>Missing)}}});
                }
            }
        }
        uint32 MotionHash=0;
        TInlineComponentArray<UStaticMeshComponent*> Parts;
        if(S.Stage) S.Stage->GetComponents(Parts);
        for(AActor* Actor:S.Actors)if(AOldWestUnit* Unit=Cast<AOldWestUnit>(Actor);Unit&&Unit->IsRaider())Unit->GetComponents(Parts);
        for(UStaticMeshComponent* Part:Parts)
            MotionHash=HashCombineFast(MotionHash,GetTypeHash(Part->GetRelativeTransform().ToHumanReadableString()));
        for (AActor* Actor : S.Actors)
            if (AOldWestUnit* Unit = Cast<AOldWestUnit>(Actor); Unit && Unit->IsRaider())
            {
                TInlineComponentArray<USkeletalMeshComponent*> Herd;
                Unit->GetComponents(Herd);
                for (USkeletalMeshComponent* Animal : Herd)
                    for (const FTransform& Bone : Animal->GetBoneSpaceTransforms())
                        MotionHash = HashCombineFast(MotionHash, GetTypeHash(Bone.ToHumanReadableString()));
            }
        // Read-only residency evidence: shader completion alone does not mean
        // the animated atlas has enough resident detail for a close portrait.
        J FireTextures=J::array();
        TSet<UTexture2D*> SeenFireTextures;
        for(UStaticMeshComponent* Part:Parts) if(Cast<UOldWestFireSheet>(Part))
        {
            UMaterialInterface* Material=Part->GetMaterial(0);
            if(!Material) continue;
            TArray<UTexture*> Used;
            Material->GetUsedTextures(Used);
            for(UTexture* Texture:Used) if(UTexture2D* Atlas=Cast<UTexture2D>(Texture))
            {
                if(SeenFireTextures.Contains(Atlas)) continue;
                SeenFireTextures.Add(Atlas);
                const auto& Residency=Atlas->GetStreamableResourceState();
                const int32 Resident=Atlas->GetNumResidentMips();
                const int32 Missing=FMath::Max(0,Atlas->GetNumMips()-Resident);
                FireTextures.push_back({{"path",TCHAR_TO_UTF8(*Atlas->GetPathName())},
                    {"platform_size",{Atlas->GetSizeX(),Atlas->GetSizeY()}},
                    {"platform_mips",Atlas->GetNumMips()},{"resident_mips",Resident},
                    {"requested_mips",Residency.NumRequestedLODs},{"max_mips",Residency.MaxNumLODs},
                    {"wanted_mips",Atlas->GetCachedNumWantedLODs()},
                    {"estimated_resident_top_size",{FMath::Max(1,Atlas->GetSizeX()>>Missing),FMath::Max(1,Atlas->GetSizeY()>>Missing)}},
                    {"streamable",Atlas->IsStreamable()}});
            }
        }
        int32 FireSheets=0;
        TInlineComponentArray<UOldWestFireVisuals*> Fires;
        if(S.Stage) S.Stage->GetComponents(Fires);
        for(const UOldWestFireVisuals* Fire:Fires)
        {
            FireSheets+=Fire->GetVisiblePartCount();
            MotionHash=HashCombineFast(MotionHash,Fire->GetAnimationSignature());
        }
        J CampBounds=nullptr,CampCoverage=nullptr,CampComposition=nullptr;
        J CampVisibleMeshes=J::array();
        int32 CampVisibleParts=0;
        float CampMaxAbsGroundGap=0.f;
        if(S.Camp)
        {
            TInlineComponentArray<UStaticMeshComponent*> Components;
            S.Stage->GetComponents(Components);
            for (const UStaticMeshComponent* Mesh : Components)
                if (Mesh->GetAttachParent() == S.Camp && Mesh->IsVisible() && Mesh->GetStaticMesh())
                {
                    const FTransform Pose = Mesh->GetRelativeTransform();
                    const FVector Position = Pose.GetLocation(), Scale = Pose.GetScale3D();
                    const FQuat Rotation = Pose.GetRotation();
                    const FBox MeshBounds = Mesh->Bounds.GetBox();
                    const FVector MeshMin = MeshBounds.Min-S.Origin, MeshMax = MeshBounds.Max-S.Origin;
                    J Slots = J::array();
                    for (int32 Slot = 0; Slot < Mesh->GetNumMaterials(); ++Slot)
                        Slots.push_back(Mesh->GetMaterial(Slot) ? TCHAR_TO_UTF8(*Mesh->GetMaterial(Slot)->GetPathName()) : "");
                    CampVisibleMeshes.push_back({{"mesh",TCHAR_TO_UTF8(*Mesh->GetStaticMesh()->GetPathName())},
                        {"position",{Position.X,Position.Y,Position.Z}},{"scale",{Scale.X,Scale.Y,Scale.Z}},
                        {"rotation",{Rotation.X,Rotation.Y,Rotation.Z,Rotation.W}},{"materials",Slots},
                        {"bounds",{{"min",{MeshMin.X,MeshMin.Y,MeshMin.Z}},
                                   {"max",{MeshMax.X,MeshMax.Y,MeshMax.Z}}}},
                        {"collision",int32(Mesh->GetCollisionEnabled())}});
                }
            S.Camp->GetVisibleGroundingDebug(CampVisibleParts,CampMaxAbsGroundGap);
            const FBox Bounds=S.Camp->GetPortraitBounds();
            if(Bounds.IsValid)
            {
                const FVector Min=Bounds.Min-S.Origin,Max=Bounds.Max-S.Origin;
                CampBounds={{"min",{Min.X,Min.Y,Min.Z}},{"max",{Max.X,Max.Y,Max.Z}}};
                if(S.Capture)
                {
                    FVector2D ProjectedMin(1.e6,1.e6),ProjectedMax(-1.e6,-1.e6);
                    const double TanH=FMath::Tan(FMath::DegreesToRadians(S.Capture->FOVAngle*.5f));
                    for(int32 Corner=0;Corner<8;++Corner)
                    {
                        const FVector Point((Corner&1)?Bounds.Max.X:Bounds.Min.X,(Corner&2)?Bounds.Max.Y:Bounds.Min.Y,(Corner&4)?Bounds.Max.Z:Bounds.Min.Z);
                        const FVector View=S.Capture->GetComponentTransform().InverseTransformPosition(Point);
                        const FVector2D Projected(View.Y/FMath::Max(View.X,1.)/TanH,View.Z/FMath::Max(View.X,1.)/(TanH/1.5));
                        ProjectedMin.X=FMath::Min(ProjectedMin.X,Projected.X);ProjectedMin.Y=FMath::Min(ProjectedMin.Y,Projected.Y);
                        ProjectedMax.X=FMath::Max(ProjectedMax.X,Projected.X);ProjectedMax.Y=FMath::Max(ProjectedMax.Y,Projected.Y);
                    }
                    CampCoverage={{"min",{ProjectedMin.X,ProjectedMin.Y}},{"max",{ProjectedMax.X,ProjectedMax.Y}}};
                    // Retain full world/culling coverage above. The composition
                    // record explicitly names the solid/flame subject policy;
                    // smoke overflow never becomes a false full-bounds pass.
                    TArray<FVector> Solids,Flames;
                    S.Camp->AppendPortraitFramingPoints(S.Capture->GetComponentLocation(),Solids,Flames);
                    FVector2D SubjectMin(1.e6,1.e6),SubjectMax(-1.e6,-1.e6);
                    double MinimumDepth=1.e12;
                    FBox CompositionBounds(ForceInit);
                    auto RecordPoints=[&](const TArray<FVector>& Points)
                    {
                        J Encoded=J::array();
                        for(const FVector& Point:Points)
                        {
                            CompositionBounds+=Point;
                            const FVector Local=Point-S.Origin;
                            Encoded.push_back({Local.X,Local.Y,Local.Z});
                            const FVector View=S.Capture->GetComponentTransform().InverseTransformPosition(Point);
                            MinimumDepth=FMath::Min(MinimumDepth,View.X);
                            const FVector2D Projected(View.Y/FMath::Max(View.X,1.)/TanH,View.Z/FMath::Max(View.X,1.)/(TanH/1.5));
                            SubjectMin.X=FMath::Min(SubjectMin.X,Projected.X);SubjectMin.Y=FMath::Min(SubjectMin.Y,Projected.Y);
                            SubjectMax.X=FMath::Max(SubjectMax.X,Projected.X);SubjectMax.Y=FMath::Max(SubjectMax.Y,Projected.Y);
                        }
                        return Encoded;
                    };
                    J SolidPoints=RecordPoints(Solids),FlamePoints=RecordPoints(Flames);
                    const FVector Position=S.Capture->GetComponentLocation()-S.Origin;
                    const FVector Forward=S.Capture->GetForwardVector(),Right=S.Capture->GetRightVector(),Up=S.Capture->GetUpVector();
                    const FVector CompositionMin=CompositionBounds.IsValid?CompositionBounds.Min-S.Origin:FVector::ZeroVector;
                    const FVector CompositionMax=CompositionBounds.IsValid?CompositionBounds.Max-S.Origin:FVector::ZeroVector;
                    CampComposition={{"semantics","solid_bounds_and_full_flame_sheets_v1"},{"smoke_policy","rendered_soft_overflow"},
                        {"solid_points",MoveTemp(SolidPoints)},{"flame_points",MoveTemp(FlamePoints)},
                        {"excluded_smoke_sheets",FireSheets-Flames.Num()/4},
                        {"bounds",{{"min",{CompositionMin.X,CompositionMin.Y,CompositionMin.Z}},{"max",{CompositionMax.X,CompositionMax.Y,CompositionMax.Z}}}},
                        {"coverage",{{"min",{SubjectMin.X,SubjectMin.Y}},{"max",{SubjectMax.X,SubjectMax.Y}}}},
                        {"minimum_depth_cm",MinimumDepth},{"camera_location",{Position.X,Position.Y,Position.Z}},
                        {"camera_forward",{Forward.X,Forward.Y,Forward.Z}},{"camera_right",{Right.X,Right.Y,Right.Z}},{"camera_up",{Up.X,Up.Y,Up.Z}},
                        {"horizontal_fov_degrees",S.Capture->FOVAngle},{"aspect_ratio",1.5},
                        {"fit_active",S.CompositionFitActive},{"fit_fallback",S.CompositionFitFallback},{"fit_iterations",S.CompositionFitIterations},
                        {"full_culling_envelope_overflows",ProjectedMin.X< -1. || ProjectedMin.Y< -1. || ProjectedMax.X>1. || ProjectedMax.Y>1.}};
                }
            }
        }
        Result["scenes"].push_back({{"card_id",TCHAR_TO_UTF8(*S.Id)},{"type",TCHAR_TO_UTF8(*S.Type)},
            {"target_size",{S.Target?S.Target->SizeX:0,S.Target?S.Target->SizeY:0}},
            {"capture_interval_seconds",CaptureInterval},
            {"captures",S.CaptureCount},{"actors",S.Actors.Num()},{"skeletal_loops",S.PersonCount},
            {"condition_revision",S.ConditionRevision},{"compilation_zero_capture",S.CompilationZeroCapture},
            {"detail_review",S.DetailReview},{"detail_expression",TCHAR_TO_UTF8(*S.DetailExpression)},{"detail_morph_weights",DetailWeights},
            {"person_textures",PersonTextures},
            {"compilation_zero_frame",S.CompilationZeroFrame},{"post_zero_submissions",S.ReadyCaptureCount},{"post_zero_captures",SettledCaptures},
            {"last_ready_capture_frame",S.LastReadyCaptureFrame},
            {"capture_ready",Compilation.IsReady() && SettledCaptures>=2 && S.CanDisplayCapture()},
            {"render_readiness",MoveTemp(RenderReady)},
            {"trouble_mesh",S.TroubleProp.IsValid() && S.TroubleProp->GetStaticMesh()?TCHAR_TO_UTF8(*S.TroubleProp->GetStaticMesh()->GetPathName()):""},
            {"trouble_collision",S.TroubleProp.IsValid()?int32(S.TroubleProp->GetCollisionEnabled()):-1},
            {"vehicles",Vehicles},{"animated_props",S.Motions.Num()+FireSheets+Vehicles.size()},{"fire_sheets",FireSheets},{ "fire_textures",FireTextures},{"motion_signature",MotionHash},{"people",People},{"camp_part_count",S.Camp?S.Camp->GetPartCount():0},{"camp_damage",S.CampDamage},{"camp_destroyed",S.CampDestroyed},{"camp_bounds",CampBounds},{"camp_frame_coverage",CampCoverage},{"camp_composition",MoveTemp(CampComposition)},{"camp_animated_parts",S.Camp?S.Camp->GetAnimatedPartCount():0},
            {"camp_visible_parts",CampVisibleParts},{"camp_visible_meshes",CampVisibleMeshes},{"camp_ruin_smoke_parts",S.Camp?S.Camp->GetVisibleRuinSmokeParts():0},{"camp_max_abs_part_ground_gap_cm",CampMaxAbsGroundGap},
            {"hidden_punk",S.Hidden},{"visible_age",Now-S.LastVisible},{"visible_frames_ago",GFrameCounter-S.LastVisibleFrame},{"loop_time",Now-S.Born},
            {"show_only_count",S.Capture?S.Capture->ShowOnlyActors.Num():0}});
    }
    Result["scene_count"]=Result["scenes"].size();
#endif
    return FString(UTF8_TO_TCHAR(Result.dump().c_str()));
}
