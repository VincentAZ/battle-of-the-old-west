#include "OldWestShadowProbe.h"
#if !UE_BUILD_SHIPPING
#include "Core/json.hpp"
#include "OldWestBattlefield.h"
#include "Components/PrimitiveComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Components/LightComponent.h"
#include "Components/LocalLightComponent.h"
#include "Engine/StaticMesh.h"
#include "EngineUtils.h"

FString RunOldWestShadowProbe(UWorld* World, const FString& Category)
{
    using J = nlohmann::ordered_json;
    static TMap<TWeakObjectPtr<UPrimitiveComponent>, bool> Saved;
    // Restore exact observed flags before each isolated comparison.
    for (const auto& Entry : Saved)
        if (Entry.Key.IsValid()) Entry.Key->SetCastShadow(Entry.Value);
    Saved.Empty();
    J Report = {{"category", std::string(TCHAR_TO_UTF8(*Category))}, {"frame", GFrameCounter},
        {"diagnostic_only", true}, {"disabled", J::array()}, {"casters", J::array()}, {"lights", J::array()}};
    for (TActorIterator<AActor> It(World); It; ++It)
    {
        AActor* Actor = *It;
        TInlineComponentArray<ULightComponent*> Lights; Actor->GetComponents(Lights);
        for (ULightComponent* Light : Lights)
        {
            if (Actor->ActorHasTag(TEXT("OldWestPortraitPreview"))) continue;
            const FVector Position = Light->GetComponentLocation(), Direction = Light->GetForwardVector();
            const ULocalLightComponent* Local = Cast<ULocalLightComponent>(Light);
            Report["lights"].push_back({{"actor", std::string(TCHAR_TO_UTF8(*Actor->GetName()))},
                {"type", std::string(TCHAR_TO_UTF8(*Light->GetClass()->GetName()))},
                {"location", {Position.X,Position.Y,Position.Z}}, {"direction", {Direction.X,Direction.Y,Direction.Z}},
                {"intensity", Light->Intensity}, {"cast_shadows", !!Light->CastShadows},
                {"attenuation_radius", Local ? Local->AttenuationRadius : 0.f}});
        }
        TInlineComponentArray<UPrimitiveComponent*> Components; Actor->GetComponents(Components);
        for (UPrimitiveComponent* Component : Components)
        {
            if (!Component->CastShadow) continue;
            FString Group = Actor->ActorHasTag(TEXT("OldWestPortraitPreview")) ? TEXT("portraits") :
                Actor->IsA<AOldWestUnit>() ? TEXT("units") : TEXT("world");
            FString MeshName;
            if (const UStaticMeshComponent* Static = Cast<UStaticMeshComponent>(Component))
                if (const UStaticMesh* Mesh = Static->GetStaticMesh())
                {
                    MeshName = Mesh->GetPathName();
                    if (Mesh->GetName() == TEXT("SM_ContinuousTerrain")) Group = TEXT("terrain");
                }
            const FBoxSphereBounds& Bounds = Component->Bounds;
            J Row = {{"actor", std::string(TCHAR_TO_UTF8(*Actor->GetName()))},
                {"component", std::string(TCHAR_TO_UTF8(*Component->GetName()))},
                {"group", std::string(TCHAR_TO_UTF8(*Group))}, {"mesh", std::string(TCHAR_TO_UTF8(*MeshName))},
                {"visible", Component->IsVisible()}, {"hidden_in_game", !!Component->bHiddenInGame},
                {"cast_hidden_shadow", !!Component->bCastHiddenShadow},
                {"center", {Bounds.Origin.X, Bounds.Origin.Y, Bounds.Origin.Z}},
                {"extent", {Bounds.BoxExtent.X, Bounds.BoxExtent.Y, Bounds.BoxExtent.Z}}};
            Report["casters"].push_back(Row);
            if (Category == Group || Category == TEXT("all"))
            {
                Saved.Add(Component, !!Component->CastShadow);
                Component->SetCastShadow(false);
                Report["disabled"].push_back(MoveTemp(Row));
            }
        }
    }
    return FString(UTF8_TO_TCHAR(Report.dump().c_str()));
}
#endif
