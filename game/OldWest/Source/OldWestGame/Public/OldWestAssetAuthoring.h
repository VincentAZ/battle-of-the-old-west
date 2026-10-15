#pragma once

#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "OldWestAssetAuthoring.generated.h"

class UPhysicsAsset;
class USkeletalMesh;
class AActor;

/** Narrow editor asset authoring; no gameplay behavior or cooked asset mutation. */
UCLASS()
class OLDWESTGAME_API UOldWestAssetAuthoring : public UBlueprintFunctionLibrary
{
    GENERATED_BODY()
public:
    /** Transient editor-world presentation review only; never creates a game entity. */
    UFUNCTION(BlueprintCallable, Category="OldWest|Editor", meta=(DevelopmentOnly))
    static AActor* CreateCrewWoundPreview(UObject* WorldContext, FString VisualId, FString Pose, float Phase = 0.f, bool Concealed = false, AActor* Existing = nullptr);

    /** Read current native skinned geometry and pose from an owned editor preview. */
    UFUNCTION(BlueprintCallable, Category="OldWest|Editor", meta=(DevelopmentOnly))
    static FString DescribeCrewWoundPreview(AActor* Actor, bool IncludeGeometry = false);

    /** Refresh only an approved Crew mesh's same-directory skeleton; caller saves it. */
    UFUNCTION(BlueprintCallable, Category="OldWest|Editor", meta=(DevelopmentOnly))
    static bool RefreshCrewSkeletonReference(USkeletalMesh* Mesh);

    UFUNCTION(BlueprintCallable, Category="OldWest|Editor", meta=(DevelopmentOnly))
    static UPhysicsAsset* CreateSurvivorPhysicsAsset(bool bReplaceExisting = false, bool bAnatomicalWristFrames = true, bool bDrifter = false, bool bQuanah = false, FString WesternCharacter = TEXT(""));

    UFUNCTION(BlueprintCallable, Category="OldWest|Editor", meta=(DevelopmentOnly))
    static FString DescribeSurvivorPhysicsAsset(UPhysicsAsset* Asset);

    UFUNCTION(BlueprintCallable, Category="OldWest|Editor", meta=(DevelopmentOnly))
    static FString DescribeSurvivorLods();
};
