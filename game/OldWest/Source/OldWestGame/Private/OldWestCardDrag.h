#pragma once
#include "CoreMinimal.h"
#include "Input/DragAndDrop.h"
#include "Widgets/SCompoundWidget.h"

// A local Slate gesture. The HUD retains the exact legal command, revision,
// and match identity; this object never grants authority to move a card.
class FOldWestCardDrag : public FDragDropOperation
{
public:
    DRAG_DROP_OPERATOR_TYPE(FOldWestCardDrag, FDragDropOperation)
    int32 Card = 0;
    TFunction<void()> Finished;
    TSharedPtr<SWidget> Preview;
    FVector2D Pointer = FVector2D::ZeroVector;
    TFunction<bool()> Active;
    TFunction<FVector2D(FVector2D)> Constrain;
    virtual TSharedPtr<SWidget> GetDefaultDecorator() const override { return Active && Active() ? Preview : nullptr; }
    virtual FVector2D GetDecoratorPosition() const override { return Constrain ? Constrain(Pointer + FVector2D(20, 20)) : Pointer + FVector2D(20, 20); }
    virtual void OnDragged(const FDragDropEvent& Event) override
    {
        Pointer = Event.GetScreenSpacePosition();
        FDragDropOperation::OnDragged(Event);
    }
    static TSharedRef<FOldWestCardDrag> New(int32 Id, TFunction<void()> OnFinished, TSharedPtr<SWidget> CardPreview, TFunction<bool()> IsActive, TFunction<FVector2D(FVector2D)> ConstrainPosition)
    {
        TSharedRef<FOldWestCardDrag> Drag = MakeShared<FOldWestCardDrag>();
        Drag->Card = Id; Drag->Finished = MoveTemp(OnFinished);
        Drag->Preview = MoveTemp(CardPreview);
        Drag->Active = MoveTemp(IsActive); Drag->Constrain = MoveTemp(ConstrainPosition);
        Drag->bCreateNewWindow = false;
        Drag->Construct();
        return Drag;
    }
    virtual void OnDrop(bool Handled, const FPointerEvent& Event) override
    {
        FDragDropOperation::OnDrop(Handled, Event);
        if (Finished) Finished();
    }
};

class SOldWestDragCard : public SCompoundWidget
{
public:
    SLATE_BEGIN_ARGS(SOldWestDragCard) {}
        SLATE_DEFAULT_SLOT(FArguments, Content)
        SLATE_ARGUMENT(TFunction<void()>, Clicked)
        SLATE_ARGUMENT(TFunction<void(FVector2D)>, Context)
        SLATE_ARGUMENT(TFunction<TSharedPtr<FDragDropOperation>()>, BeginDrag)
    SLATE_END_ARGS()
    void Construct(const FArguments& Args)
    {
        Context = Args._Context; Clicked = Args._Clicked; BeginDrag = Args._BeginDrag;
        ChildSlot[Args._Content.Widget];
    }
    virtual FReply OnMouseButtonDown(const FGeometry&, const FPointerEvent& Event) override
    {
        if (Event.GetEffectingButton()==EKeys::RightMouseButton && Context) { Context(Event.GetScreenSpacePosition()); return FReply::Handled(); }
        if (Event.GetEffectingButton() != EKeys::LeftMouseButton) return FReply::Unhandled();
        return FReply::Handled().CaptureMouse(SharedThis(this)).DetectDrag(SharedThis(this), EKeys::LeftMouseButton);
    }
    virtual FReply OnMouseButtonUp(const FGeometry& Geometry, const FPointerEvent& Event) override
    {
        if (Event.GetEffectingButton() != EKeys::LeftMouseButton || !HasMouseCapture()) return FReply::Unhandled();
        if (Geometry.IsUnderLocation(Event.GetScreenSpacePosition()) && Clicked) Clicked();
        return FReply::Handled().ReleaseMouseCapture();
    }
    virtual FReply OnDragDetected(const FGeometry&, const FPointerEvent&) override
    {
        if (BeginDrag) if (TSharedPtr<FDragDropOperation> Operation = BeginDrag())
            return FReply::Handled().ReleaseMouseCapture().BeginDragDrop(Operation.ToSharedRef());
        return FReply::Handled().ReleaseMouseCapture();
    }
private:
    TFunction<void(FVector2D)> Context;
    TFunction<void()> Clicked;
    TFunction<TSharedPtr<FDragDropOperation>()> BeginDrag;
};
