#pragma once
#include "CoreMinimal.h"
#include "Widgets/SLeafWidget.h"
#include "Rendering/DrawElements.h"

// Native line art stays crisp as the HUD scales. Labels always accompany icons.
enum class EOldWestHUDIcon : uint8 { Cards, Deploy, Shield, Attack, Water, Event, Turn, Repair };
class SOldWestHUDIcon : public SLeafWidget
{
public:
    SLATE_BEGIN_ARGS(SOldWestHUDIcon) : _Kind(EOldWestHUDIcon::Cards), _Color(FLinearColor(.24f,.81f,.73f,1)), _Size(28.f) {}
        SLATE_ARGUMENT(EOldWestHUDIcon, Kind)
        SLATE_ARGUMENT(FLinearColor, Color)
        SLATE_ARGUMENT(float, Size)
    SLATE_END_ARGS()
    void Construct(const FArguments& A) { Kind=A._Kind; Color=A._Color; Size=A._Size; SetVisibility(EVisibility::HitTestInvisible); }
    FVector2D ComputeDesiredSize(float) const override { return FVector2D(Size,Size); }
    int32 OnPaint(const FPaintArgs&,const FGeometry& G,const FSlateRect&,FSlateWindowElementList& Out,int32 L,const FWidgetStyle& Style,bool Enabled) const override
    {
        const FVector2D Scale=G.GetLocalSize()/24.f;
        auto Line=[&](std::initializer_list<FVector2D> P) {
            TArray<FVector2D> Points; for(const auto& V:P)Points.Add(V*Scale);
            FSlateDrawElement::MakeLines(Out,L,G.ToPaintGeometry(),Points,ESlateDrawEffect::None,Color*Style.GetColorAndOpacityTint(),true,1.8f);
        };
        switch(Kind) {
        case EOldWestHUDIcon::Cards:
            Line({{5,18},{2,18},{2,2},{15,2},{15,5}});Line({{7,6},{21,6},{21,22},{7,22},{7,6}});Line({{10,11},{18,11}});Line({{10,15},{16,15}});break;
        case EOldWestHUDIcon::Deploy:
            Line({{3,14},{3,21},{21,21},{21,14}});Line({{12,2},{12,16}});Line({{6,10},{12,16},{18,10}});break;
        case EOldWestHUDIcon::Shield:
            Line({{12,2},{21,6},{19,16},{12,22},{5,16},{3,6},{12,2}});Line({{8,11},{11,14},{17,8}});break;
        case EOldWestHUDIcon::Attack:
            Line({{4,20},{20,4},{15,4},{20,4},{20,9}});Line({{3,14},{10,21}});Line({{4,4},{9,9}});Line({{16,16},{21,21}});break;
        case EOldWestHUDIcon::Water:
            // Whiskey bottle (the canonical 'water' resource, Western presentation).
            Line({{10,2},{14,2},{14,7},{17,10},{17,22},{7,22},{7,10},{10,7},{10,2}});Line({{7,13},{17,13}});Line({{7,18},{17,18}});break;
        case EOldWestHUDIcon::Event:
            Line({{12,2},{19,5},{22,12},{19,19},{12,22},{5,19},{2,12},{5,5},{12,2}});Line({{12,6},{12,12},{17,15}});break;
        case EOldWestHUDIcon::Turn:
            Line({{3,12},{21,12},{14,5}});Line({{21,12},{14,19}});break;
        case EOldWestHUDIcon::Repair:
            Line({{9,2},{15,2},{15,9},{22,9},{22,15},{15,15},{15,22},{9,22},{9,15},{2,15},{2,9},{9,9},{9,2}});break;
        }
        return L;
    }
private:
    EOldWestHUDIcon Kind;
    FLinearColor Color;
    float Size;
};
