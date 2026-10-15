#include "OldWestSectionBody.h"
#include "OldWestMasterStyle.h"
#include "OldWestTooltip.h"
#include "InputCoreTypes.h"
#include "Rendering/DrawElements.h"
#include "Widgets/Layout/SBox.h"
#include "Widgets/Layout/SScrollBox.h"
#include "Widgets/SBoxPanel.h"
#include "Widgets/SLeafWidget.h"

namespace {
class SSectionGrip : public SLeafWidget
{
public:
    SLATE_BEGIN_ARGS(SSectionGrip) {} SLATE_END_ARGS()
    void Construct(const FArguments&) {
        SetCursor(EMouseCursor::ResizeUpDown);
        SetToolTip(OldWestTooltip(FText::FromString(TEXT("Drag to give this section more or less room. Double-click to reset. Arrow keys resize; Esc cancels."))));
    }
    FVector2D ComputeDesiredSize(float) const override {return FVector2D(24,10);}
    int32 OnPaint(const FPaintArgs&,const FGeometry& G,const FSlateRect&,FSlateWindowElementList& Out,int32 Layer,const FWidgetStyle&,bool) const override {
        const FVector2D Size=G.GetLocalSize();
        const FLinearColor Ink=IsHovered()?OldWestMasterStyle::Aqua:FLinearColor(.17f,.26f,.28f,1);
        FSlateDrawElement::MakeLines(Out,Layer,G.ToPaintGeometry(),{FVector2D(0,5),FVector2D(Size.X,5)},ESlateDrawEffect::None,Ink,true,1.f);
        for(int I=-1;I<=1;++I)FSlateDrawElement::MakeBox(Out,Layer+1,G.ToPaintGeometry(FVector2D(3,3),FSlateLayoutTransform(FVector2D(Size.X*.5f+I*7-1.5f,3.5f))),FCoreStyle::Get().GetBrush("WhiteBrush"),ESlateDrawEffect::None,Ink);
        return Layer+1;
    }
};
}
void SOldWestSectionBody::Construct(const FArguments& A)
{
    Id=A._SectionId;State=A._State;DefaultHeight=A._DefaultHeight;MinHeight=A._MinHeight;MaxHeight=A._MaxHeight;OnHeightChanged=A._OnHeightChanged;
    SetCanTick(true);
    TSharedRef<SWidget> Content=A._Content.Widget;
    if(!A._ContentScrolls) {
        SAssignNew(Scroll,SScrollBox).ScrollBarThickness(FVector2D(5,5)).AnimateWheelScrolling(false)
            .OnUserScrolled_Lambda([Saved=State](float Offset){Saved->Scroll=Offset;})
            +SScrollBox::Slot()[Content];
        Scroll->SetScrollOffset(State->Scroll);Content=Scroll.ToSharedRef();
    }
    ChildSlot[SNew(SVerticalBox)
        +SVerticalBox::Slot().AutoHeight()[SAssignNew(Viewport,SBox).Clipping(EWidgetClipping::ClipToBoundsAlways)[Content]]
        +SVerticalBox::Slot().AutoHeight()[SAssignNew(Grip,SSectionGrip)]];
    State->Height=FMath::Max(MinHeight,FMath::IsFinite(State->Height)?State->Height:DefaultHeight);
    RefreshHeight();
}
void SOldWestSectionBody::SetHeight(float Value)
{
    const float Maximum=FMath::Max(MinHeight,MaxHeight.Get());
    State->Height=FMath::Clamp(FMath::IsFinite(Value)?Value:DefaultHeight,MinHeight,Maximum);
    RefreshHeight();
}
void SOldWestSectionBody::RefreshHeight()
{
    // Fitting a smaller dock is temporary; retain the player's chosen height
    // so enlarging the dock restores its workspace without another gesture.
    const float Height=FMath::Clamp(State->Height,MinHeight,FMath::Max(MinHeight,MaxHeight.Get()));
    if(FMath::IsNearlyEqual(Height,EffectiveHeight))return;
    EffectiveHeight=Height;
    Viewport->SetHeightOverride(EffectiveHeight);
    Invalidate(EInvalidateWidgetReason::Layout);
}
void SOldWestSectionBody::Tick(const FGeometry& G,double Time,float Delta)
{
    SCompoundWidget::Tick(G,Time,Delta);
    RefreshHeight();
}
FReply SOldWestSectionBody::OnMouseButtonDown(const FGeometry& G,const FPointerEvent& E)
{
    if(E.GetEffectingButton()!=EKeys::LeftMouseButton||!Grip->GetCachedGeometry().IsUnderLocation(E.GetScreenSpacePosition()))return FReply::Unhandled();
    Resizing=true;StartHeight=State->Height;DragStartHeight=EffectiveHeight;StartPointer=E.GetScreenSpacePosition().Y;
    PointerScale=FMath::Max(.01f,G.GetAccumulatedLayoutTransform().GetScale());
    return FReply::Handled().CaptureMouse(SharedThis(this)).SetUserFocus(SharedThis(this),EFocusCause::Mouse);
}
FReply SOldWestSectionBody::OnMouseMove(const FGeometry&,const FPointerEvent& E)
{
    if(!Resizing)return FReply::Unhandled();
    SetHeight(DragStartHeight+(E.GetScreenSpacePosition().Y-StartPointer)/PointerScale);
    return FReply::Handled();
}
void SOldWestSectionBody::Finish(bool Cancel)
{
    if(!Resizing)return;
    Resizing=false;
    if(Cancel){State->Height=StartHeight;RefreshHeight();}
    else {++ResizeCount;OnHeightChanged.ExecuteIfBound(State->Height);}
}
FReply SOldWestSectionBody::OnMouseButtonUp(const FGeometry&,const FPointerEvent& E)
{
    if(!Resizing||E.GetEffectingButton()!=EKeys::LeftMouseButton)return FReply::Unhandled();
    Finish(false);return FReply::Handled().ReleaseMouseCapture();
}
FReply SOldWestSectionBody::OnMouseButtonDoubleClick(const FGeometry&,const FPointerEvent& E)
{
    if(E.GetEffectingButton()!=EKeys::LeftMouseButton||!Grip->GetCachedGeometry().IsUnderLocation(E.GetScreenSpacePosition()))return FReply::Unhandled();
    Resizing=false;SetHeight(DefaultHeight);OnHeightChanged.ExecuteIfBound(State->Height);++ResizeCount;
    return FReply::Handled().ReleaseMouseCapture();
}
FReply SOldWestSectionBody::OnKeyDown(const FGeometry&,const FKeyEvent& E)
{
    if(E.GetKey()==EKeys::Escape&&Resizing){Finish(true);return FReply::Handled().ReleaseMouseCapture();}
    if(!Resizing&&HasKeyboardFocus()&&(E.GetKey()==EKeys::Up||E.GetKey()==EKeys::Down)) {
        SetHeight(EffectiveHeight+(E.GetKey()==EKeys::Up?-1:1)*(E.IsShiftDown()?40.f:10.f));
        ++ResizeCount;OnHeightChanged.ExecuteIfBound(State->Height);return FReply::Handled();
    }
    return FReply::Unhandled();
}
void SOldWestSectionBody::OnMouseCaptureLost(const FCaptureLostEvent& E)
{
    Finish(true);SCompoundWidget::OnMouseCaptureLost(E);
}
nlohmann::ordered_json SOldWestSectionBody::GetDebugGeometry(const FGeometry& Reference) const
{
    using J=nlohmann::ordered_json;
    auto Rect=[&](const TSharedPtr<SWidget>& W) -> J {
        if(!W.IsValid()||!GetVisibility().IsVisible())return nullptr;
        const auto& G=W->GetCachedGeometry();
        const auto Min=Reference.AbsoluteToLocal(G.LocalToAbsolute(FVector2D::ZeroVector));
        const auto Max=Reference.AbsoluteToLocal(G.LocalToAbsolute(G.GetLocalSize()));
        return {{"min",{Min.X,Min.Y}},{"max",{Max.X,Max.Y}},{"allocated_size",{G.GetLocalSize().X,G.GetLocalSize().Y}}};
    };
    J Result={{"id",std::string(TCHAR_TO_UTF8(*Id))},{"height",EffectiveHeight},{"requested_height",State->Height},{"default_height",DefaultHeight},
        {"scroll_offset",Scroll.IsValid()?Scroll->GetScrollOffset():State->Scroll},{"scroll_end",Scroll.IsValid()?Scroll->GetScrollOffsetOfEnd():0.f},
        {"resizing",Resizing},{"resize_count",ResizeCount},{"viewport",Rect(Viewport)},{"grip",Rect(Grip)}};
#if !UE_BUILD_SHIPPING
    Result["mouse_captured"]=HasMouseCapture();
#endif
    return Result;
}
