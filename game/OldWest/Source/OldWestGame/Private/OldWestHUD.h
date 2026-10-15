#pragma once
#include "CoreMinimal.h"
#include "Widgets/SCompoundWidget.h"
#include "Core/json.hpp"
#include "OldWestPreferences.h"

class AOldWestPlayerController;
class AOldWestPunkShelter;
class AOldWestStaging;
class AOldWestUnit;
class SVerticalBox;
class SBox;
class SScrollBox;
class SComboButton;
class SOldWestSectionBody;
struct FOldWestSectionState;
class SOldWestDockPanel;
class SConstraintCanvas;
struct FOldWestDockPanelState;
class SOldWestHUD : public SCompoundWidget
{
public:
    SLATE_BEGIN_ARGS(SOldWestHUD) {} SLATE_ARGUMENT(TWeakObjectPtr<AOldWestPlayerController>, Owner) SLATE_END_ARGS()
    void Construct(const FArguments& Arguments);
    virtual void Tick(const FGeometry& Geometry, const double CurrentTime, const float DeltaTime) override;
    virtual FReply OnPreviewMouseButtonDown(const FGeometry& Geometry,const FPointerEvent& MouseEvent) override;
    virtual FReply OnMouseButtonDown(const FGeometry& Geometry, const FPointerEvent& MouseEvent) override;
    virtual FReply OnMouseButtonUp(const FGeometry& Geometry, const FPointerEvent& MouseEvent) override;
    virtual FReply OnMouseMove(const FGeometry& Geometry, const FPointerEvent& MouseEvent) override;
    virtual FReply OnMouseWheel(const FGeometry& Geometry, const FPointerEvent& MouseEvent) override;
    virtual FReply OnDragOver(const FGeometry& Geometry, const FDragDropEvent& Event) override;
    virtual FReply OnDrop(const FGeometry& Geometry, const FDragDropEvent& Event) override;
    virtual int32 OnPaint(const FPaintArgs& Args, const FGeometry& Geometry, const FSlateRect& CullingRect,
        FSlateWindowElementList& Elements, int32 Layer, const FWidgetStyle& Style, bool ParentEnabled) const override;
    bool InspectVisibleCard(int32 CardId);
    virtual FReply OnDragDetected(const FGeometry&, const FPointerEvent&) override;
    void CardActions(int32 CardId, FVector2D Position);
    void ClickCard(int32 CardId);
    int32 PressedWorldCard = INDEX_NONE;
    FVector2D WorldPressPosition;
    bool CameraMoved = false;
    void ToggleBattleOverview();
    void SetBattleOverview(bool Open);
    void DismissChoiceView();
    bool IsSoloPaused() const { return SettingsOpen || HelpOpen; }
#if !UE_BUILD_SHIPPING
    void PointerForVisualTest(const nlohmann::ordered_json& Command);
    void GalleryForVisualTest(const nlohmann::ordered_json& Command);
    bool InspectForVisualTest(int32 CardId);
    void SetRulesForVisualTest(bool Open);
    void SettingsForVisualTest(const nlohmann::ordered_json& Command);
    nlohmann::ordered_json VisualTestState() const;
#endif
private:
    TSharedPtr<FDragDropOperation> BeginDeployment(int32 Card);
    void EndDeployment();
    bool UpdateDeployment(const FVector2D& ScreenPosition);
    bool DropDeployment();
    void UpdateShelterDrag(const FVector2D& Position);
    bool OverBattlefield(const FVector2D& ScreenPosition) const;
    bool ProjectToHUD(const FVector& World, FVector2D& LocalPosition) const;
    float OverlayUnit() const;
    FSlateRect BattlefieldRect() const;
    void LayoutDeployment() const;
    FString DeploymentHintText() const;
    FSlateRect DeploymentHintRect() const;
    TSharedRef<SWidget> AnimatedCard(const nlohmann::ordered_json& Card, float PortraitHeight, bool Compact = false);
    void Rebuild();
    TSharedRef<SWidget> Label(const FString& Value, int32 Size = 16, FLinearColor Color = FLinearColor::White);
    TSharedRef<SWidget> Button(const FString& Value, TFunction<void()> OnClick, const FString& Tooltip = FString(), bool Enabled = true, bool CancelSound = false, float WrapAt = 0.f);
    void PlayUiSound(bool Cancel);
    bool SceneControlsVisible() const;
    TSharedRef<SWidget> CampSelection(const nlohmann::ordered_json& Player);
    TSharedRef<SWidget> MasterPanel(const nlohmann::ordered_json& Data);
    TSharedRef<SWidget> MasterActions(const nlohmann::ordered_json& Data);
    TSharedRef<SWidget> MasterCard(const nlohmann::ordered_json& Card, bool Hand = false);
    TSharedRef<SWidget> BattleSection(const FString& Key, const FString& Title, TSharedRef<SWidget> Content, bool ForceOpen = false);
    TSharedRef<SWidget> BattleHistory(const nlohmann::ordered_json& View, int32 Seat, bool Compact = false);
    bool SectionCollapsed(const FString& Key);
    TMap<FString,bool> BattleSections;
    TMap<FString,TSharedPtr<FOldWestSectionState>> SectionStates;
    TArray<TSharedPtr<SOldWestSectionBody>> SectionBodies;
    bool HistoryOpen = false;
    TMap<FString,float> BattleScrollOffsets;
    nlohmann::ordered_json DamageMarkers() const;
    nlohmann::ordered_json BattlefieldLabels() const;
    TMap<int32,FString> BattlefieldReadiness;
    TSet<int32> DiscardChoiceCards;
    int32 PaintDamageMarkers(const FGeometry& Geometry, FSlateWindowElementList& Elements, int32 Layer) const;
    FString CardGlanceText(const nlohmann::ordered_json& Card) const;
    TSharedRef<SWidget> CardInspector(const nlohmann::ordered_json& Card);
    TSharedRef<SWidget> AssetHistoryControl(const nlohmann::ordered_json& Card, bool InBattlePlan = false);
    bool CardHoverEnabled() const;
    void UpdateWorldHover(double CurrentTime);
    TSharedPtr<SBox> WorldHoverBox;
    TSharedPtr<SConstraintCanvas> HoverCanvas;
    FVector2D WorldHoverPosition = FVector2D::ZeroVector;
    int32 HoveredWorldCard = INDEX_NONE;
    FString WorldHoverText;
    TArray<TPair<nlohmann::ordered_json,TWeakPtr<SWidget>>> CardHoverTargets;
    double NextHoverCheck = 0.;
    double HoverSince = 0.;
    bool WorldHoverVisible = false;
    bool MasterActionsVisible = false;
    TSharedRef<SWidget> BattleOverview(const nlohmann::ordered_json& Data);
    FMargin OverviewResponsePadding() const;
    void AddDockPanel(TSharedRef<SConstraintCanvas> Canvas, const FString& Id, const FText& Title,
        FVector2D Position, FVector2D Size, FVector2D MinimumSize, TSharedRef<SWidget> Content,
        bool IsOverview = false, bool IsActions = false);
    void SavePanelLayout();
    void ResetPanelLayout();
    bool PanelGestureActive() const;
    TSharedRef<SWidget> CardDetails(const nlohmann::ordered_json& Card, int32 Seat);
    TSharedRef<SWidget> RulesHelp(const std::string& Ruleset);
    TSharedRef<SWidget> SettingsPanel();
    FOldWestPreferences* Preferences() const;
    void OpenSettings();
    void CloseSettings();
    void ApplySettingsDraft();
    void KeepSettings();
    void RevertSettings();
    const nlohmann::ordered_json* CardDefinition(const std::string& CardId) const;
    void Inspect(int32 CardId, bool Owned);
    FString CardDescription(const std::string& CardId) const;
    void Send(const nlohmann::ordered_json& Command);
    TWeakObjectPtr<AOldWestPlayerController> Owner;
    TSharedPtr<SVerticalBox> Root;
    TSharedPtr<SWidget> SceneHitArea;
    TSharedPtr<SWidget> Workspace;
    TWeakPtr<SWidget> MatchEndPanel;
    TArray<TSharedPtr<SOldWestDockPanel>> DockPanels;
    TMap<FString,TSharedPtr<FOldWestDockPanelState>> PanelStates;
    TMap<FString,float> PanelLayers;
    float FrontPanelLayer = 20.f;
    bool OverviewOpen = false;
    bool BattlePlanOpen = false;
    bool WarRoomOpen = false;
    TWeakPtr<SWidget> WarRoomSurface;
    bool AbilityReferenceOpen = true;
    TSharedRef<SWidget> AbilityReference(const nlohmann::ordered_json& Data);
    TSharedRef<SWidget> WarRoom(const nlohmann::ordered_json& Data);
    FString NewGameConfirmationMatch;
    FString LeaveConfirmationMatch;
    bool OwnStatsOpen=true,EnemyStatsOpen=true,FieldHistoryOpen=false;
    bool BattlefieldTextVisible=true;
    bool FieldHistoryAscending=true;
    int32 FieldHistoryTurn=0; // Zero follows the current turn.
    TArray<int32> FieldHistoryRenderedSequences;
    TSharedRef<SWidget> FieldStatus(const nlohmann::ordered_json& Data,bool Enemy);
    TWeakObjectPtr<AOldWestPunkShelter> PunkShelter;
    TWeakObjectPtr<AOldWestPunkShelter> EnemyPunkShelter;
    TWeakObjectPtr<AOldWestStaging> Staging;
    int32 StagingGeneration=-1;
    FString PunkShelterMatch;
    void UpdatePunkShelter();
    FString FramedFieldMatch;
    bool FrameFieldPending = false;
    TArray<TWeakPtr<SWidget>> FieldSurfaces;
#if !UE_BUILD_SHIPPING
    TArray<TPair<FString,TWeakPtr<SWidget>>> FieldButtons;
    TArray<TPair<FString,TWeakPtr<SWidget>>> StatusButtons;
    TWeakPtr<SComboButton> AssetHistoryButton;
    nlohmann::ordered_json AssetHistoryNote;
    TWeakPtr<SWidget> LastContextWidget;
    nlohmann::ordered_json LastContextActions=nlohmann::ordered_json::array();
#endif
    FString LastAnnouncedChoiceIdentity;
    struct FDropTarget {
        FVector World; FVector2D Screen; FVector2D LabelOffset = FVector2D::ZeroVector;
        nlohmann::ordered_json Command;
        nlohmann::ordered_json Alternatives=nlohmann::ordered_json::array();
        FString Label, DisplayLabel, BlockedReason;
        FVector2D LabelSize = FVector2D::ZeroVector;
        int32 TargetCard = 0, Side = -1, Column = -1, Row = -1, EventSlot = -99;
        bool Visible = false;
    };
    struct FPanelDropSurface {
        TWeakPtr<SWidget> Widget;
        int32 Card = 0, Side = -1, Column = -1, Row = -1, EventSlot = -99;
    };
    TArray<FPanelDropSurface> PanelDropSurfaces;
    TWeakPtr<SScrollBox> BattleDropScroll;
    bool DropMatchesSurface(const FDropTarget& Target, const FPanelDropSurface& Surface) const;
    bool DragKeepsPanels = false;
    int32 HoveredPanelSurface = INDEX_NONE;
    mutable TArray<FDropTarget> DropTargets;
    int32 DraggedCard = INDEX_NONE;
    TWeakObjectPtr<AOldWestUnit> DraggedWorldPreview;
    FVector DragWorldStart=FVector::ZeroVector;
    int32 HoveredDrop = INDEX_NONE;
    int32 DragRevision = -1;
    FString DragMatch;
    FString DragName;
    FVector2D DragPointer = FVector2D::ZeroVector;
    FKey CameraDrag;
#if !UE_BUILD_SHIPPING
    mutable nlohmann::ordered_json LastPaintObservation;
    mutable nlohmann::ordered_json PaintTransitions = nlohmann::ordered_json::array();
    mutable uint64 LastPaintFrame = 0;
    uint64 LayoutGeneration = 0;
    TArray<TPair<FString, TWeakPtr<SWidget>>> InviteButtons;
    TArray<TPair<FString, TWeakPtr<SWidget>>> CampOptionButtons;
    TArray<TPair<FString, TWeakPtr<SWidget>>> SoloButtons;
    TArray<TPair<FString, TWeakPtr<SWidget>>> HandCards;
    TArray<TPair<FString, TWeakPtr<SWidget>>> MasterTabs;
    TArray<TPair<FString, TWeakPtr<SWidget>>> SectionButtons;
    TArray<TPair<FString, TWeakPtr<SWidget>>> MasterCards;
    TArray<TPair<FString, TWeakPtr<SWidget>>> FormationSlots;
    TWeakPtr<SWidget> BattleScrollWidget;
    TArray<TPair<FString, TWeakPtr<SWidget>>> MasterActionButtons;
    TArray<TPair<FString, TWeakPtr<SWidget>>> RosterLanes;
    TArray<TPair<FString, TWeakPtr<SWidget>>> PlacementDragButtons;
    TArray<TPair<FString, TWeakPtr<SWidget>>> GalleryWidgets;
    TArray<TPair<FString, TWeakPtr<SWidget>>> CameraButtons;
    TArray<TPair<FString, TWeakPtr<SWidget>>> OverviewCards;
    TArray<FString> GalleryCards;
    TSet<FKey> TestPointerButtons;
    FVector2D TestPointerPosition = FVector2D::ZeroVector;
#endif
    nlohmann::ordered_json Catalog;
    TArray<FString> ChosenCamps;
    FString Address = TEXT("127.0.0.1:7777");
    int32 SeenGeneration = -1;
    int32 SelectedSource = 0;
    int32 InspectedCard = 0;
    int32 InspectorSide = -1;
    bool HelpOpen = false;
    nlohmann::ordered_json RulesContent;
    FString RulesQuery;
    nlohmann::ordered_json RulesVisibleCards=nlohmann::ordered_json::array();
    FString RulesCategory=TEXT("Rules");
    bool RulesAllCards=false;
    bool Dirty = true;
    bool IncludeExpansion = false;
    FString SelectedDifficulty = TEXT("normal");
    bool PendingChoice = false;
    bool SettingsOpen = false;
    int32 SeenPreferencesGeneration = -1;
    FOldWestPreferencesValues SettingsDraft;
};
