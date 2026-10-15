#include "OldWestDockPanel.h"
#include "OldWestTooltip.h"

#include "Brushes/SlateRoundedBoxBrush.h"
#include "InputCoreTypes.h"
#include "Rendering/DrawElements.h"
#include "Styling/CoreStyle.h"
#include "Widgets/Input/SButton.h"
#include "Widgets/Layout/SBorder.h"
#include "Widgets/Layout/SBox.h"
#include "Widgets/SBoxPanel.h"
#include "Widgets/SLeafWidget.h"
#include "Widgets/SOverlay.h"
#include "Widgets/Text/STextBlock.h"

namespace
{
const FLinearColor DockText(0.93f, 0.87f, 0.74f, 1.f);
const FLinearColor DockMuted(0.58f, 0.69f, 0.68f, 1.f);

bool SameState(const FOldWestDockPanelState& A, const FOldWestDockPanelState& B)
{
    return A.Position.Equals(B.Position, 0.001) && A.Size.Equals(B.Size, 0.001) && A.bCollapsed == B.bCollapsed;
}

class SOldWestDockEdgeHandle : public SLeafWidget
{
public:
    SLATE_BEGIN_ARGS(SOldWestDockEdgeHandle) {} SLATE_ARGUMENT(FVector2D, Direction) SLATE_END_ARGS()
    void Construct(const FArguments& Args) {
        Direction=Args._Direction;
        const auto Cursor=Direction.X&&Direction.Y
            ?(Direction.X==Direction.Y?EMouseCursor::ResizeSouthEast:EMouseCursor::ResizeSouthWest)
            :(Direction.X?EMouseCursor::ResizeLeftRight:EMouseCursor::ResizeUpDown);
        SetCursor(Cursor);
    }
    virtual FVector2D ComputeDesiredSize(float) const override {return FVector2D(12,12);}
    virtual void OnMouseEnter(const FGeometry& G,const FPointerEvent& E) override {
        SLeafWidget::OnMouseEnter(G,E);Invalidate(EInvalidateWidgetReason::Paint);
    }
    virtual void OnMouseLeave(const FPointerEvent& E) override {
        SLeafWidget::OnMouseLeave(E);Invalidate(EInvalidateWidgetReason::Paint);
    }
    virtual int32 OnPaint(const FPaintArgs&,const FGeometry& G,const FSlateRect&,FSlateWindowElementList& Out,
        int32 Layer,const FWidgetStyle&,bool) const override {
        if(!IsHovered())return Layer;
        const FVector2D Size=G.GetLocalSize(),Center=Size*.5;
        TArray<FVector2D> Points;
        if(Direction.X&&Direction.Y) {
            const FVector2D Corner(Direction.X<0?4:Size.X-4,Direction.Y<0?4:Size.Y-4);
            Points={Corner-FVector2D(Direction.X*15,0),Corner,Corner-FVector2D(0,Direction.Y*15)};
        } else {
            const FVector2D Half=Direction.X?FVector2D(0,FMath::Min(24.,Size.Y*.4)):FVector2D(FMath::Min(24.,Size.X*.4),0);
            Points={Center-Half,Center+Half};
        }
        FSlateDrawElement::MakeLines(Out,Layer+1,G.ToPaintGeometry(),Points,ESlateDrawEffect::None,
            FLinearColor(.32f,.95f,.83f,1),true,4.f);
        return Layer+1;
    }
private:
    FVector2D Direction;
};

class SOldWestDockResizeGrip : public SLeafWidget
{
public:
    SLATE_BEGIN_ARGS(SOldWestDockResizeGrip) {} SLATE_END_ARGS()
    void Construct(const FArguments&)
    {
        SetCursor(TOptional<EMouseCursor::Type>(EMouseCursor::ResizeSouthEast));
        SetToolTip(OldWestTooltip(FText::FromString(TEXT("Drag to resize this panel"))));
    }
    virtual FVector2D ComputeDesiredSize(float) const override { return FVector2D(28, 28); }
    virtual int32 OnPaint(const FPaintArgs&, const FGeometry& Geometry, const FSlateRect&,
        FSlateWindowElementList& Elements, int32 Layer, const FWidgetStyle& Style, bool) const override
    {
        const FVector2D Size = Geometry.GetLocalSize();
        for (int32 Index = 0; Index < 3; ++Index)
        {
            const float Length = 5.f + Index * 5.f;
            TArray<FVector2D> Points = {Size - FVector2D(Length + 5, 5), Size - FVector2D(5, Length + 5)};
            FSlateDrawElement::MakeLines(Elements, Layer, Geometry.ToPaintGeometry(), Points,
                ESlateDrawEffect::None, DockMuted * Style.GetColorAndOpacityTint(), true, 1.5f);
        }
        return Layer;
    }
};
}

void SOldWestDockPanel::Construct(const FArguments& Arguments)
{
    PanelId = Arguments._PanelId;
    State = Arguments._State.IsValid() ? Arguments._State : MakeShared<FOldWestDockPanelState>();
    Bounds = Arguments._Bounds;
    MinSize = Arguments._MinSize;
    MinSize.X = FMath::IsFinite(MinSize.X) ? FMath::Max(240.0, MinSize.X) : 260.0;
    MinSize.Y = FMath::IsFinite(MinSize.Y) ? FMath::Max(96.0, MinSize.Y) : 160.0;
    OnStateChanged = Arguments._OnStateChanged;
    OnActivated = Arguments._OnActivated;
    SetCanTick(true);
    SetClipping(EWidgetClipping::ClipToBounds);
    ClampState();

    FrameBrush = FSlateRoundedBoxBrush(FLinearColor(0.012f, 0.022f, 0.027f, 0.96f), 8.f,
        FLinearColor(0.20f, 0.29f, 0.29f, 1.f), 1.f);
    HeaderBrush = FSlateRoundedBoxBrush(FLinearColor(0.035f, 0.064f, 0.070f, 1.f), 6.f);
    HeaderButtonStyle = FCoreStyle::Get().GetWidgetStyle<FButtonStyle>("Button");
    HeaderButtonStyle.SetNormal(FSlateRoundedBoxBrush(FLinearColor(0.018f, 0.035f, 0.040f, 1.f), 4.f));
    HeaderButtonStyle.SetHovered(FSlateRoundedBoxBrush(FLinearColor(0.10f, 0.18f, 0.19f, 1.f), 4.f));
    HeaderButtonStyle.SetPressed(FSlateRoundedBoxBrush(FLinearColor(0.17f, 0.25f, 0.25f, 1.f), 4.f));
    HeaderButtonStyle.SetNormalPadding(FMargin(8, 2));
    HeaderButtonStyle.SetPressedPadding(FMargin(8, 2));

    TSharedRef<SWidget> TitleBar = SNew(SBox).HeightOverride(HeaderHeight - 2.f)
        [SNew(SBorder).BorderImage(&HeaderBrush).Padding(FMargin(12, 3, 7, 3))
            .ToolTip(OldWestTooltip(FText::FromString(TEXT("Drag the title to move. Drag any edge or corner to resize. Double-click the title to fold."))))
            [SNew(SHorizontalBox)
                + SHorizontalBox::Slot().FillWidth(1.f).VAlign(VAlign_Center).Padding(0, 0, 8, 0)
                [SNew(STextBlock).Text(Arguments._Title).Font(FCoreStyle::GetDefaultFontStyle("Bold", 14))
                    .ColorAndOpacity(DockText).OverflowPolicy(ETextOverflowPolicy::Ellipsis)
                    .Visibility(EVisibility::HitTestInvisible)]
                + SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Fill)
                [SNew(SBox).WidthOverride(28.f)
                    [SAssignNew(CollapseButton, SButton).ButtonStyle(&HeaderButtonStyle).ContentPadding(0).HAlign(HAlign_Center).VAlign(VAlign_Center)
                        .Cursor(EMouseCursor::Default)
                        .AccessibleText_Lambda([this]() { return FText::FromString(State->bCollapsed ? TEXT("Expand panel") : TEXT("Collapse panel")); })
                        .ToolTip(OldWestTooltip(TAttribute<FText>::CreateLambda([PanelState = State]() { return FText::FromString(PanelState->bCollapsed ? TEXT("Expand this panel") : TEXT("Collapse this panel")); })))
                        .OnClicked(this, &SOldWestDockPanel::ToggleCollapsed)
                        [SNew(STextBlock).Text_Lambda([this]() { return FText::FromString(State->bCollapsed ? TEXT("+") : TEXT("\u2212")); })
                            .Font(FCoreStyle::GetDefaultFontStyle("Bold", 14)).ColorAndOpacity(DockText)]]]]];
    Header = TitleBar;

    TSharedPtr<SOverlay> PanelOverlay;
    ChildSlot
    [SAssignNew(SizeBox, SBox)
        [SNew(SBorder).BorderImage(&FrameBrush).Padding(1.f)
            [SAssignNew(PanelOverlay,SOverlay)
                + SOverlay::Slot()
                [SNew(SVerticalBox)
                    + SVerticalBox::Slot().AutoHeight()[TitleBar]
                    + SVerticalBox::Slot().FillHeight(1.f)
                    [SAssignNew(ContentArea, SBorder).BorderImage(FCoreStyle::Get().GetBrush("NoBrush"))
                        .Padding(Arguments._ContentPadding).Clipping(EWidgetClipping::ClipToBoundsAlways)
                        .Visibility_Lambda([this]() { return State->bCollapsed ? EVisibility::Collapsed : EVisibility::Visible; })
                        [Arguments._Content.Widget]]]
                + SOverlay::Slot().HAlign(HAlign_Right).VAlign(VAlign_Bottom)
                [SAssignNew(ResizeGrip, SOldWestDockResizeGrip)
                    .Visibility_Lambda([this]() { return State->bCollapsed ? EVisibility::Collapsed : EVisibility::Visible; })]]]];
    // Dedicated overlay hit areas keep content widgets from swallowing edge hover.
    // Corners are added last so their diagonal cursor takes priority.
    for(const FVector2D Direction:{FVector2D(-1,0),FVector2D(1,0),FVector2D(0,-1),FVector2D(0,1),
        FVector2D(-1,-1),FVector2D(1,-1),FVector2D(-1,1),FVector2D(1,1)}) {
        const bool Corner=Direction.X&&Direction.Y;
        auto Handle=SNew(SOldWestDockEdgeHandle).Direction(Direction);
        auto HitArea=SNew(SBox).Visibility_Lambda([this](){return State->bCollapsed?EVisibility::Collapsed:EVisibility::Visible;})[Handle];
        if(Direction.X)HitArea->SetWidthOverride(Corner?20:12);
        if(Direction.Y)HitArea->SetHeightOverride(Corner?20:12);
        PanelOverlay->AddSlot().HAlign(Direction.X<0?HAlign_Left:Direction.X>0?HAlign_Right:HAlign_Fill)
            .VAlign(Direction.Y<0?VAlign_Top:Direction.Y>0?VAlign_Bottom:VAlign_Fill)[HitArea];
        EdgeHandles.Emplace(Direction,Handle);
    }
    RefreshSize();
}

FSlateRect SOldWestDockPanel::ValidBounds() const
{
    const FSlateRect Value = Bounds.Get();
    if (!FMath::IsFinite(Value.Left) || !FMath::IsFinite(Value.Top) || !FMath::IsFinite(Value.Right)
        || !FMath::IsFinite(Value.Bottom) || Value.Right <= Value.Left || Value.Bottom <= Value.Top)
        return FSlateRect(0, 0, 1864, 1024);
    return Value;
}

FVector2D SOldWestDockPanel::GetEffectiveSize() const
{
    const FSlateRect Rect = ValidBounds();
    return FVector2D(State->Size.X, State->bCollapsed ? FMath::Min(HeaderHeight, Rect.Bottom - Rect.Top) : State->Size.Y);
}

FMargin SOldWestDockPanel::GetCanvasOffset() const
{
    const FVector2D Size = GetEffectiveSize();
    return FMargin(State->Position.X, State->Position.Y, Size.X, Size.Y);
}

bool SOldWestDockPanel::ClampState()
{
    const FOldWestDockPanelState Before = *State;
    const FSlateRect Rect = ValidBounds();
    const FVector2D Available(Rect.Right - Rect.Left, Rect.Bottom - Rect.Top);
    if (!FMath::IsFinite(State->Size.X)) State->Size.X = MinSize.X;
    if (!FMath::IsFinite(State->Size.Y)) State->Size.Y = MinSize.Y;
    if (!FMath::IsFinite(State->Position.X)) State->Position.X = Rect.Left;
    if (!FMath::IsFinite(State->Position.Y)) State->Position.Y = Rect.Top;
    State->Size.X = FMath::Clamp(State->Size.X, FMath::Min(MinSize.X, Available.X), Available.X);
    State->Size.Y = FMath::Clamp(State->Size.Y, FMath::Min(MinSize.Y, Available.Y), Available.Y);
    const FVector2D Visible = GetEffectiveSize();
    State->Position.X = FMath::Clamp(State->Position.X, double(Rect.Left), double(Rect.Right) - Visible.X);
    State->Position.Y = FMath::Clamp(State->Position.Y, double(Rect.Top), double(Rect.Bottom) - Visible.Y);
    return !SameState(Before, *State);
}

void SOldWestDockPanel::RefreshSize()
{
    if (SizeBox.IsValid())
    {
        const FVector2D Size = GetEffectiveSize();
        SizeBox->SetWidthOverride(float(Size.X));
        SizeBox->SetHeightOverride(float(Size.Y));
    }
    Invalidate(EInvalidateWidgetReason::Layout | EInvalidateWidgetReason::Paint);
}

void SOldWestDockPanel::NotifyChanged(bool bFinished)
{
    LastChangeFrame = GFrameCounter;
    RefreshSize();
    OnStateChanged.ExecuteIfBound(*State, bFinished);
}

void SOldWestDockPanel::SetState(const FOldWestDockPanelState& NewState, bool bNotify)
{
    // Callers must defer HUD rebuilds and external layout restores during capture.
    if (IsInteracting()) return;
    const FOldWestDockPanelState Before = *State;
    *State = NewState;
    ClampState();
    if (bNotify && !SameState(Before, *State)) NotifyChanged(true);
    else RefreshSize();
}

void SOldWestDockPanel::SetBounds(TAttribute<FSlateRect> NewBounds)
{
    Bounds = MoveTemp(NewBounds);
    if (ClampState()) NotifyChanged(!IsInteracting());
    else RefreshSize();
}

void SOldWestDockPanel::SetCollapsed(bool bCollapsed)
{
    if (IsInteracting() || State->bCollapsed == bCollapsed) return;
    State->bCollapsed = bCollapsed;
    ClampState();
    ++CollapseCount;
    NotifyChanged(true);
}

FReply SOldWestDockPanel::ToggleCollapsed()
{
    OnActivated.ExecuteIfBound();
    SetCollapsed(!State->bCollapsed);
    return FReply::Handled();
}

void SOldWestDockPanel::Tick(const FGeometry& Geometry, double CurrentTime, float DeltaTime)
{
    SCompoundWidget::Tick(Geometry, CurrentTime, DeltaTime);
    if (ClampState()) NotifyChanged(!IsInteracting());
}

bool SOldWestDockPanel::Over(const TSharedPtr<SWidget>& Widget, const FPointerEvent& Event) const
{
    return Widget.IsValid() && Widget->GetVisibility().IsVisible()
        && Widget->GetCachedGeometry().IsUnderLocation(Event.GetScreenSpacePosition());
}

FVector2D SOldWestDockPanel::ResizeDirection(const FGeometry& Geometry, const FPointerEvent& Event) const
{
    if (State->bCollapsed) return FVector2D::ZeroVector;
    const FVector2D P = Geometry.AbsoluteToLocal(Event.GetScreenSpacePosition());
    const FVector2D S = Geometry.GetLocalSize();
    if (P.X < 0 || P.Y < 0 || P.X > S.X || P.Y > S.Y) return FVector2D::ZeroVector;
    for(int32 I=EdgeHandles.Num()-1;I>=0;--I)
        if(Over(EdgeHandles[I].Value,Event))return EdgeHandles[I].Key;
    // Reserve a real hit area at every border; corners resize both axes.
    if (Over(ResizeGrip, Event)) return FVector2D(1, 1);
    const float Border = 12.f;
    return FVector2D(P.X < Border ? -1 : P.X > S.X - Border ? 1 : 0,
        P.Y < Border ? -1 : P.Y > S.Y - Border ? 1 : 0);
}

FCursorReply SOldWestDockPanel::OnCursorQuery(const FGeometry& Geometry, const FPointerEvent& Event) const
{
    const FVector2D Axes = IsInteracting() ? ResizeAxes : ResizeDirection(Geometry, Event);
    if (Axes.X && Axes.Y) return FCursorReply::Cursor(Axes.X == Axes.Y ? EMouseCursor::ResizeSouthEast : EMouseCursor::ResizeSouthWest);
    if (Axes.X) return FCursorReply::Cursor(EMouseCursor::ResizeLeftRight);
    if (Axes.Y) return FCursorReply::Cursor(EMouseCursor::ResizeUpDown);
    if (Over(Header, Event) && !Over(CollapseButton, Event)) return FCursorReply::Cursor(EMouseCursor::CardinalCross);
    return SCompoundWidget::OnCursorQuery(Geometry, Event);
}

FReply SOldWestDockPanel::OnPreviewMouseButtonDown(const FGeometry& Geometry, const FPointerEvent& Event)
{
    OnActivated.ExecuteIfBound();
    if (Event.GetEffectingButton() == EKeys::LeftMouseButton && !IsInteracting())
    {
        ResizeAxes = ResizeDirection(Geometry, Event);
        if (!ResizeAxes.IsZero()) return BeginInteraction(EInteraction::Resize, Geometry, Event);
    }
    return FReply::Unhandled(); // Child buttons and scroll bars retain their input.
}

FReply SOldWestDockPanel::BeginInteraction(EInteraction Mode, const FGeometry& Geometry, const FPointerEvent& Event)
{
    Interaction = Mode;
    StartState = *State;
    StartGeometry = Geometry;
    StartPointer = Geometry.AbsoluteToLocal(Event.GetScreenSpacePosition());
    bInteractionChanged = false;
    return FReply::Handled().CaptureMouse(SharedThis(this)).SetUserFocus(SharedThis(this), EFocusCause::Mouse);
}

FReply SOldWestDockPanel::OnMouseButtonDown(const FGeometry& Geometry, const FPointerEvent& Event)
{
    if (Event.GetEffectingButton() == EKeys::LeftMouseButton && !IsInteracting())
    {
        ResizeAxes = ResizeDirection(Geometry, Event);
        if (!ResizeAxes.IsZero()) return BeginInteraction(EInteraction::Resize, Geometry, Event);
        if (Over(Header, Event) && !Over(CollapseButton, Event)) return BeginInteraction(EInteraction::Move, Geometry, Event);
    }
    return FReply::Handled(); // Empty panel space must never pick/rotate the world.
}

FReply SOldWestDockPanel::OnMouseMove(const FGeometry&, const FPointerEvent& Event)
{
    if (!IsInteracting() || !HasMouseCapture()) return FReply::Unhandled();
    const FVector2D Delta = StartGeometry.AbsoluteToLocal(Event.GetScreenSpacePosition()) - StartPointer;
    const FOldWestDockPanelState Before = *State;
    if (Interaction == EInteraction::Move) State->Position = StartState.Position + Delta;
    else
    {
        const FSlateRect Rect = ValidBounds();
        for (int32 Axis = 0; Axis < 2; ++Axis)
        {
            if (!ResizeAxes[Axis]) continue;
            const double Low = Axis ? Rect.Top : Rect.Left, High = Axis ? Rect.Bottom : Rect.Right;
            const double Anchor = StartState.Position[Axis] + (ResizeAxes[Axis] < 0 ? StartState.Size[Axis] : 0);
            const double Room = ResizeAxes[Axis] < 0 ? Anchor - Low : High - Anchor;
            State->Size[Axis] = FMath::Clamp(StartState.Size[Axis] + Delta[Axis] * ResizeAxes[Axis], FMath::Min(MinSize[Axis], Room), Room);
            State->Position[Axis] = ResizeAxes[Axis] < 0 ? Anchor - State->Size[Axis] : Anchor;
        }
    }
    ClampState();
    if (!SameState(Before, *State))
    {
        bInteractionChanged = true;
        NotifyChanged(false);
    }
    return FReply::Handled();
}

void SOldWestDockPanel::FinishInteraction(bool bCancel)
{
    if (!IsInteracting()) return;
    const EInteraction Finished = Interaction;
    Interaction = EInteraction::None;
    if (bCancel) { *State = StartState; ClampState(); }
    else if (bInteractionChanged)
    {
        if (Finished == EInteraction::Move) ++MoveCount;
        else ++ResizeCount;
    }
    bInteractionChanged = false;
    NotifyChanged(true);
}

FReply SOldWestDockPanel::OnMouseButtonUp(const FGeometry&, const FPointerEvent& Event)
{
    if (IsInteracting() && Event.GetEffectingButton() == EKeys::LeftMouseButton)
    {
        FinishInteraction(false);
        return FReply::Handled().ReleaseMouseCapture();
    }
    return FReply::Handled();
}

FReply SOldWestDockPanel::OnMouseButtonDoubleClick(const FGeometry&, const FPointerEvent& Event)
{
    if (Event.GetEffectingButton() == EKeys::LeftMouseButton && Over(Header, Event) && !Over(CollapseButton, Event))
        return ToggleCollapsed();
    return FReply::Handled();
}

FReply SOldWestDockPanel::OnMouseWheel(const FGeometry&, const FPointerEvent&)
{
    return FReply::Handled(); // An inner SScrollBox handles scrolling before this.
}

FReply SOldWestDockPanel::OnKeyDown(const FGeometry& Geometry, const FKeyEvent& Event)
{
    if (IsInteracting() && Event.GetKey() == EKeys::Escape)
    {
        FinishInteraction(true);
        return FReply::Handled().ReleaseMouseCapture();
    }
    return SCompoundWidget::OnKeyDown(Geometry, Event);
}

void SOldWestDockPanel::OnMouseCaptureLost(const FCaptureLostEvent& Event)
{
    FinishInteraction(true);
    SCompoundWidget::OnMouseCaptureLost(Event);
}

nlohmann::ordered_json SOldWestDockPanel::GetDebugGeometry(const FGeometry& Reference) const
{
    using J = nlohmann::ordered_json;
    auto RectOf = [&Reference](const FGeometry& Geometry)
    {
        const FVector2D Min = Reference.AbsoluteToLocal(Geometry.LocalToAbsolute(FVector2D::ZeroVector));
        const FVector2D Max = Reference.AbsoluteToLocal(Geometry.LocalToAbsolute(Geometry.GetLocalSize()));
        const FVector2D Size = Geometry.GetLocalSize();
        return J{{"min", {Min.X, Min.Y}}, {"max", {Max.X, Max.Y}}, {"allocated_size", {Size.X, Size.Y}}};
    };
    auto WidgetRect = [&RectOf](const TSharedPtr<SWidget>& Widget) -> J
    {
        return Widget.IsValid() && Widget->GetVisibility().IsVisible() ? RectOf(Widget->GetCachedGeometry()) : J(nullptr);
    };
    const FSlateRect Rect = ValidBounds();
    const FVector2D VisibleSize = GetEffectiveSize();
    J Handles=J::array();
    for(const auto& Handle:EdgeHandles)Handles.push_back({{"direction",{Handle.Key.X,Handle.Key.Y}},
        {"hovered",Handle.Value->IsHovered()},{"rect",WidgetRect(Handle.Value)}});
    return J{{"id", std::string(TCHAR_TO_UTF8(*PanelId))},
        {"position", {State->Position.X, State->Position.Y}}, {"expanded_size", {State->Size.X, State->Size.Y}},
        {"effective_size", {VisibleSize.X, VisibleSize.Y}}, {"min_size", {MinSize.X, MinSize.Y}},
        {"bounds", {{"min", {Rect.Left, Rect.Top}}, {"max", {Rect.Right, Rect.Bottom}}}},
        {"collapsed", State->bCollapsed}, {"visible", GetVisibility().IsVisible()}, {"enabled", IsEnabled()},
        {"header_height", HeaderHeight}, {"content_clipped", true},
        {"interacting", IsInteracting()}, {"mouse_captured", HasMouseCapture()},
        {"operation", Interaction == EInteraction::Move ? "move" : Interaction == EInteraction::Resize ? "resize" : "none"},
        {"move_count", MoveCount}, {"resize_count", ResizeCount}, {"collapse_count", CollapseCount},
        {"last_change_frame", LastChangeFrame}, {"panel", RectOf(GetCachedGeometry())},
        {"header", WidgetRect(Header)}, {"collapse_button", WidgetRect(CollapseButton)},
        {"content", State->bCollapsed ? J(nullptr) : WidgetRect(ContentArea)},
        {"resize_grip", State->bCollapsed ? J(nullptr) : WidgetRect(ResizeGrip)}, {"resize_handles",Handles}};
}
