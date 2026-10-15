#pragma once
#include "CoreMinimal.h"
#include "Core/json.hpp"
#include "Widgets/SCompoundWidget.h"

class SBox;
class SScrollBox;

struct FOldWestSectionState
{
    float Height=160.f;
    float Scroll=0.f;
};
DECLARE_DELEGATE_OneParam(FOnOldWestSectionChanged, float);

// An accordion's independent viewport. Resizing changes available room, never
// the size of cards or text inside it. The state survives ordinary HUD rebuilds.
class SOldWestSectionBody : public SCompoundWidget
{
public:
    SLATE_BEGIN_ARGS(SOldWestSectionBody) : _DefaultHeight(160.f), _MinHeight(48.f), _MaxHeight(900.f), _ContentScrolls(false) {}
        SLATE_ARGUMENT(FString, SectionId)
        SLATE_ARGUMENT(TSharedPtr<FOldWestSectionState>, State)
        SLATE_ARGUMENT(float, DefaultHeight)
        SLATE_ARGUMENT(float, MinHeight)
        SLATE_ATTRIBUTE(float, MaxHeight)
        SLATE_ARGUMENT(bool, ContentScrolls)
        SLATE_EVENT(FOnOldWestSectionChanged, OnHeightChanged)
        SLATE_DEFAULT_SLOT(FArguments, Content)
    SLATE_END_ARGS()
    void Construct(const FArguments& Args);
    bool IsResizing() const {return Resizing;}
    nlohmann::ordered_json GetDebugGeometry(const FGeometry& Reference) const;
    virtual bool SupportsKeyboardFocus() const override {return true;}
    virtual void Tick(const FGeometry&,double,float) override;
    virtual FReply OnMouseButtonDown(const FGeometry&,const FPointerEvent&) override;
    virtual FReply OnMouseButtonUp(const FGeometry&,const FPointerEvent&) override;
    virtual FReply OnMouseButtonDoubleClick(const FGeometry&,const FPointerEvent&) override;
    virtual FReply OnMouseMove(const FGeometry&,const FPointerEvent&) override;
    virtual FReply OnKeyDown(const FGeometry&,const FKeyEvent&) override;
    virtual void OnMouseCaptureLost(const FCaptureLostEvent&) override;
private:
    void SetHeight(float Height);
    void RefreshHeight();
    void Finish(bool Cancel);
    FString Id;
    TSharedPtr<FOldWestSectionState> State;
    TSharedPtr<SBox> Viewport;
    TSharedPtr<SScrollBox> Scroll;
    TSharedPtr<SWidget> Grip;
    FOnOldWestSectionChanged OnHeightChanged;
    TAttribute<float> MaxHeight;
    float DefaultHeight=160.f,MinHeight=48.f,StartHeight=160.f;
    float StartPointer=0.f,PointerScale=1.f;
    float EffectiveHeight=0.f,DragStartHeight=0.f;
    bool Resizing=false;
    uint32 ResizeCount=0;
};
