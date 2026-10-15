#pragma once

#include "CoreMinimal.h"
#include "Core/json.hpp"
#include "Styling/SlateTypes.h"
#include "Widgets/SCompoundWidget.h"

class SBox;

// Presentation state, in the owning canvas's logical units. Keep this shared
// object across HUD rebuilds; Size always remembers the expanded dimensions.
struct FOldWestDockPanelState
{
    FVector2D Position = FVector2D(24, 24);
    FVector2D Size = FVector2D(360, 420);
    bool bCollapsed = false;
};

DECLARE_DELEGATE_TwoParams(FOnOldWestDockPanelChanged, const FOldWestDockPanelState&, bool /* bFinished */);

// Put this in a top-left-anchored SConstraintCanvas slot whose Offset attribute
// calls GetCanvasOffset(). Bounds uses that same canvas's coordinates, not
// viewport pixels. The content should wrap and/or scroll when given less room.
class SOldWestDockPanel : public SCompoundWidget
{
public:
    SLATE_BEGIN_ARGS(SOldWestDockPanel)
        : _Title(FText::GetEmpty())
        , _Bounds(FSlateRect(0, 0, 1864, 1024))
        , _MinSize(FVector2D(260, 160))
        , _ContentPadding(FMargin(8, 6, 8, 22))
    {}
        SLATE_ARGUMENT(FString, PanelId)
        SLATE_ATTRIBUTE(FText, Title)
        SLATE_ARGUMENT(TSharedPtr<FOldWestDockPanelState>, State)
        SLATE_ATTRIBUTE(FSlateRect, Bounds)
        SLATE_ARGUMENT(FVector2D, MinSize)
        SLATE_ARGUMENT(FMargin, ContentPadding)
        SLATE_EVENT(FOnOldWestDockPanelChanged, OnStateChanged)
        SLATE_EVENT(FSimpleDelegate, OnActivated)
        SLATE_DEFAULT_SLOT(FArguments, Content)
    SLATE_END_ARGS()

    void Construct(const FArguments& Arguments);
    FMargin GetCanvasOffset() const;
    FVector2D GetEffectiveSize() const;
    const FOldWestDockPanelState& GetState() const { return *State; }
    bool IsInteracting() const { return Interaction != EInteraction::None; }
    static constexpr float HeaderHeight = 30.f;

    // Programmatic changes use the same finite-value and viewport constraints.
    // bNotify=false is useful for restoring saved presentation preferences.
    void SetState(const FOldWestDockPanelState& NewState, bool bNotify = true);
    void SetBounds(TAttribute<FSlateRect> NewBounds);
    void SetCollapsed(bool bCollapsed);

    // Geometry is in Reference's local units (e.g. HUD telemetry coordinates).
    // Hidden content/grip rectangles are null rather than stale cached geometry.
    nlohmann::ordered_json GetDebugGeometry(const FGeometry& Reference) const;
    const FString& GetPanelId() const { return PanelId; }

    virtual void Tick(const FGeometry& Geometry, double CurrentTime, float DeltaTime) override;
    virtual bool SupportsKeyboardFocus() const override { return true; }
    virtual FReply OnPreviewMouseButtonDown(const FGeometry&, const FPointerEvent&) override;
    virtual FReply OnMouseButtonDown(const FGeometry&, const FPointerEvent&) override;
    virtual FReply OnMouseButtonUp(const FGeometry&, const FPointerEvent&) override;
    virtual FReply OnMouseButtonDoubleClick(const FGeometry&, const FPointerEvent&) override;
    virtual FReply OnMouseMove(const FGeometry&, const FPointerEvent&) override;
    virtual FReply OnMouseWheel(const FGeometry&, const FPointerEvent&) override;
    virtual FCursorReply OnCursorQuery(const FGeometry&, const FPointerEvent&) const override;
    virtual FReply OnKeyDown(const FGeometry&, const FKeyEvent&) override;
    virtual void OnMouseCaptureLost(const FCaptureLostEvent&) override;

private:
    enum class EInteraction : uint8 { None, Move, Resize };
    FSlateRect ValidBounds() const;
    bool ClampState();
    void RefreshSize();
    void NotifyChanged(bool bFinished);
    void FinishInteraction(bool bCancel);
    FReply BeginInteraction(EInteraction Mode, const FGeometry&, const FPointerEvent&);
    FReply ToggleCollapsed();
    bool Over(const TSharedPtr<SWidget>& Widget, const FPointerEvent& Event) const;
    FVector2D ResizeDirection(const FGeometry&, const FPointerEvent&) const;

    FString PanelId;
    TSharedPtr<FOldWestDockPanelState> State;
    TAttribute<FSlateRect> Bounds;
    FVector2D MinSize;
    FOnOldWestDockPanelChanged OnStateChanged;
    FSimpleDelegate OnActivated;
    TSharedPtr<SBox> SizeBox;
    TSharedPtr<SWidget> Header;
    TSharedPtr<SWidget> CollapseButton;
    TSharedPtr<SWidget> ContentArea;
    TSharedPtr<SWidget> ResizeGrip;
    TArray<TPair<FVector2D,TSharedPtr<SWidget>>> EdgeHandles;
    FSlateBrush FrameBrush;
    FSlateBrush HeaderBrush;
    FButtonStyle HeaderButtonStyle;

    EInteraction Interaction = EInteraction::None;
    FOldWestDockPanelState StartState;
    FGeometry StartGeometry;
    FVector2D StartPointer = FVector2D::ZeroVector;
    FVector2D ResizeAxes = FVector2D::ZeroVector;
    bool bInteractionChanged = false;
    uint32 MoveCount = 0;
    uint32 ResizeCount = 0;
    uint32 CollapseCount = 0;
    uint64 LastChangeFrame = 0;
};
