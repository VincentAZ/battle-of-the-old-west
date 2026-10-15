#include "OldWestHUD.h"
#include "OldWestSession.h"
#include "OldWestBattlefield.h"
#include "OldWestPunkShelter.h"
#include "OldWestStaging.h"
#include "OldWestDockPanel.h"
#include "EngineUtils.h"
#include "Rendering/DrawElements.h"
#include "Framework/Application/SlateApplication.h"
#include "Fonts/FontMeasure.h"
#include "Styling/CoreStyle.h"
using J=nlohmann::ordered_json;

J SOldWestHUD::BattlefieldLabels() const
{
    J Labels=J::array();
    if(!Owner.IsValid()||!SceneControlsVisible()||OverviewOpen||SettingsOpen||HelpOpen||DraggedCard!=INDEX_NONE)return Labels;
    const float U=OverlayUnit();
    const auto Bounds=BattlefieldRect();
    const auto Font=FCoreStyle::GetDefaultFontStyle("Regular",FMath::Max(1,FMath::RoundToInt(12*U)));
    const auto Measure=FSlateApplication::Get().GetRenderer()->GetFontMeasureService();
    TArray<AOldWestUnit*> Units;
    for(TActorIterator<AOldWestUnit> It(Owner->GetWorld());It;++It)
        if(!It->IsHidden()&&!It->IsPreviewOnly()&&(!It->IsVisuallyDead()||It->Camp))Units.Add(*It);
    Units.Sort([](const AOldWestUnit& A,const AOldWestUnit& B){return A.EntityId<B.EntityId;});
    TArray<FSlateRect> Occupied;
    // Headings share the same measured, screen-space collision layout as card names.
    if(BattlefieldTextVisible&&Staging.IsValid()) {
        int32 LabelId=-10000;
        for(const auto& Heading:Staging->GetFieldLabels()) {
            --LabelId;
            FVector2D At;if(!ProjectToHUD(Heading.Position,At))continue;
            const FVector2D Size=Measure->Measure(Heading.Text,Font)+FVector2D(12*U,6*U);
            if(Size.X>Bounds.Right-Bounds.Left-8*U)continue;
            const float X=FMath::Clamp(float(At.X-Size.X*.5),Bounds.Left+4*U,Bounds.Right-float(Size.X)-4*U);
            const float BaseY=FMath::Clamp(float(At.Y-Size.Y*.5),Bounds.Top+4*U,FMath::Max(Bounds.Top+4*U,Bounds.Bottom-float(Size.Y)-4*U));
            FSlateRect Rect;bool Fits=false;
            for(int32 Step=0;Step<24;++Step) {
                const float Y=BaseY+(Step%2?1:-1)*((Step+1)/2)*(Size.Y+4*U);
                Rect=FSlateRect(X,Y,X+Size.X,Y+Size.Y);
                if(Rect.Top<Bounds.Top+4*U||Rect.Bottom>Bounds.Bottom-4*U)continue;
                bool Free=true;
                for(const auto& Other:Occupied)if(Rect.ExtendBy(2*U).IntersectionWith(Other).GetArea()>0){Free=false;break;}
                if(Free){Fits=true;break;}
            }
            if(!Fits)continue;
            Occupied.Add(Rect);
            Labels.push_back({{"id",LabelId},{"screen",{(Rect.Left+Rect.Right)*.5f,(Rect.Top+Rect.Bottom)*.5f}},
                {"anchor",{At.X,At.Y}},{"rect",{Rect.Left,Rect.Top,Rect.Right,Rect.Bottom}},
                {"label",std::string(TCHAR_TO_UTF8(*Heading.Text))},{"decorative",true},{"damaged",false},{"side",Heading.Side},{"readiness","none"}});
        }
    }
    for(const auto* Unit:Units) {
        const bool DiscardChoice=DiscardChoiceCards.Contains(Unit->EntityId);
        if(!BattlefieldTextVisible&&!DiscardChoice)continue;
        const FBox Visual=Unit->GetVisualBounds();if(!Visual.IsValid)continue;
        FVector2D Anchor;
        if(!ProjectToHUD(FVector(Visual.GetCenter().X,Visual.GetCenter().Y,Visual.GetCenter().Z),Anchor))continue;
        FString Text=Unit->GetUnitName();
        if(DiscardChoice)Text+=TEXT(" · DISCARD CHOICE");
        const bool Hurt=Unit->GetVisualDamage()==1&&!Unit->IsVisuallyDead();
        if(Unit->IsVisuallyDead())Text+=TEXT(" · burned out");
        else if(Hurt)Text+=Unit->Camp?TEXT(" · damaged"):TEXT(" · wounded");
        const FString Readiness=BattlefieldReadiness.FindRef(Unit->EntityId);
        const bool HasReadiness=!Unit->IsVisuallyDead()&&!Unit->IsEventToken()&&!Readiness.IsEmpty()&&Readiness!=TEXT("none");
        const FVector2D Extent=Measure->Measure(Text,Font)+FVector2D((HasReadiness?28:12)*U,6*U);
        FSlateRect Rect;bool Fits=false;
        // Keep names beside their figure, using both sides when a large hand
        // needs more space. The connector below identifies displaced labels.
        for(int32 Ring=0;Ring<3&&!Fits;++Ring)for(int32 Step=0;Step<12&&!Fits;++Step)for(int32 Side=0;Side<2;++Side) {
            const float DesiredX=Side==0?Anchor.X+26*U+Ring*(Extent.X+8*U):Anchor.X-26*U-Extent.X-Ring*(Extent.X+8*U);
            const float X=FMath::Clamp(DesiredX,Bounds.Left+4*U,FMath::Max(Bounds.Left+4*U,Bounds.Right-float(Extent.X)-4*U));
            const float Y=Anchor.Y-Extent.Y+(Step%2?1:-1)*((Step+1)/2)*(Extent.Y+3*U);
            Rect=FSlateRect(X,Y,X+Extent.X,Y+Extent.Y);
            if(Rect.Top<Bounds.Top+4*U||Rect.Bottom>Bounds.Bottom-4*U)continue;
            bool Free=true;
            for(const auto& Other:Occupied)if(Rect.IntersectionWith(Other).GetArea()>0){Free=false;break;}
            if(Free){Fits=true;break;}
        }
        if(!Fits)continue;
        Occupied.Add(Rect);
        Labels.push_back({{"id",Unit->EntityId},{"screen",{(Rect.Left+Rect.Right)*.5f,(Rect.Top+Rect.Bottom)*.5f}},
            {"anchor",{Anchor.X,Anchor.Y}},{"rect",{Rect.Left,Rect.Top,Rect.Right,Rect.Bottom}},
            {"label",std::string(TCHAR_TO_UTF8(*Text))},{"damaged",Hurt},{"side",Unit->Side},{"discard_choice",DiscardChoice},
            {"readiness",HasReadiness?std::string(TCHAR_TO_UTF8(*Readiness)):"none"}});
    }
    if(BattlefieldTextVisible&&PunkShelter.IsValid()) {
        for(const auto& Dock:DockPanels)if(Dock.IsValid()&&Dock->GetVisibility().IsVisible()) {
            const auto& G=Dock->GetCachedGeometry();
            const FVector2D A=GetCachedGeometry().AbsoluteToLocal(G.LocalToAbsolute(FVector2D::ZeroVector));
            const FVector2D B=GetCachedGeometry().AbsoluteToLocal(G.LocalToAbsolute(G.GetLocalSize()));
            Occupied.Add(FSlateRect(A.X,A.Y,B.X,B.Y));
        }
        auto Points=PunkShelter->ReadyPositions();
        float RecruitTop=Bounds.Bottom;
        for(const auto& Point:Points){FVector2D At;if(ProjectToHUD(Point.Value,At))RecruitTop=FMath::Min(RecruitTop,float(At.Y));}
        // The staging heading identifies the yard; only recruit prompts belong here.
        for(const auto& Point:Points) {
            FVector2D At;if(!ProjectToHUD(Point.Value,At))continue;
            const FString Caption=Point.Key==-2000?TEXT("DRIFTER YARD"):TEXT("DRAG DRIFTER");
            const FVector2D Size=Measure->Measure(Caption,Font)+FVector2D(12*U,6*U);
            FSlateRect Rect;bool Fits=false;
            // Longer Drifter prompts need lateral alternatives around the yard
            // signs and camp names, rather than a single crowded vertical stack.
            for(int32 Step=0;Step<16&&!Fits;++Step)for(int32 Offset:{0,-1,-2,-3,1,2,3}) {
                const float X=FMath::Clamp(float(At.X-Size.X*.5+Offset*(Size.X+8*U)),Bounds.Left+4*U,FMath::Max(Bounds.Left+4*U,Bounds.Right-float(Size.X)-4*U));
                const float Y=(Point.Key==-2000?At.Y:RecruitTop)-Size.Y-Step*(Size.Y+3*U);
                Rect=FSlateRect(X,Y,X+Size.X,Y+Size.Y);
                if(Rect.Top<Bounds.Top+4*U||Rect.Bottom>Bounds.Bottom-4*U)continue;
                bool Free=true;for(const auto& Other:Occupied)if(Rect.IntersectionWith(Other).GetArea()>0){Free=false;break;}
                if(Free){Fits=true;break;}
            }
            if(!Fits)continue;Occupied.Add(Rect);
            Labels.push_back({{"id",Point.Key},{"screen",{(Rect.Left+Rect.Right)*.5,(Rect.Top+Rect.Bottom)*.5}},{"anchor",{At.X,At.Y}},
                {"rect",{Rect.Left,Rect.Top,Rect.Right,Rect.Bottom}},
                {"label",std::string(TCHAR_TO_UTF8(*Caption))},{"damaged",false},{"side",0},{"readiness","none"}});
        }
    }
    return Labels;
}
J SOldWestHUD::DamageMarkers() const
{
    J Markers=J::array();
    for(auto Label:BattlefieldLabels())if(Label["damaged"].get<bool>()) {
        Label["label"]="! DAMAGED";Markers.push_back(Label);
    }
    return Markers;
}
int32 SOldWestHUD::PaintDamageMarkers(const FGeometry& Geometry,FSlateWindowElementList& Elements,int32 Layer) const
{
    const float U=OverlayUnit();
    for(const auto& M:BattlefieldLabels()) {
        const auto& R=M["rect"];
        const FVector2D Start(R[0].get<double>(),R[1].get<double>()),Size(R[2].get<double>()-Start.X,R[3].get<double>()-Start.Y);
        const bool Hurt=M["damaged"];
        const bool DiscardChoice=M.value("discard_choice",false);
        const std::string Readiness=M.value("readiness",std::string("none"));
        const bool HasReadiness=Readiness!="none";
        const FLinearColor Color=DiscardChoice?FLinearColor(1.f,.82f,.22f,1):Hurt?FLinearColor(1.f,.52f,.19f,1):M["side"]==0?FLinearColor(.64f,.88f,.85f,1):FLinearColor(.95f,.78f,.65f,1);
        const auto& Anchor=M["anchor"];
        const FVector2D At(Anchor[0].get<double>(),Anchor[1].get<double>());
        const FVector2D Edge(FMath::Clamp(At.X,Start.X,Start.X+Size.X),FMath::Clamp(At.Y,Start.Y,Start.Y+Size.Y));
        if(FVector2D::Distance(At,Edge)>35*U)
            FSlateDrawElement::MakeLines(Elements,Layer,Geometry.ToPaintGeometry(),{At,Edge},ESlateDrawEffect::None,FLinearColor(.70f,.78f,.73f,.65f),true,U);
        FSlateDrawElement::MakeBox(Elements,Layer,Geometry.ToPaintGeometry(Size,FSlateLayoutTransform(Start)),FCoreStyle::Get().GetBrush("WhiteBrush"),ESlateDrawEffect::None,FLinearColor(.012f,.02f,.023f,.88f));
        if(DiscardChoice) {
            const FVector2D End=Start+Size;
            FSlateDrawElement::MakeLines(Elements,Layer+1,Geometry.ToPaintGeometry(),
                {Start,FVector2D(End.X,Start.Y),End,FVector2D(Start.X,End.Y),Start},
                ESlateDrawEffect::None,Color,true,2.f*U);
        }
        if(AOldWestPunkShelter::IsToken(M["id"].get<int32>())) {
            const auto& A=M["anchor"];TArray<FVector2D> Line;
            Line.Add(Start+FVector2D(Size.X*.5,Size.Y));Line.Add(FVector2D(A[0].get<double>(),A[1].get<double>()));
            FSlateDrawElement::MakeLines(Elements,Layer,Geometry.ToPaintGeometry(),Line,ESlateDrawEffect::None,FLinearColor(.45f,.85f,.75f,.65f),true,U);
        }
        if(Hurt)FSlateDrawElement::MakeBox(Elements,Layer+1,Geometry.ToPaintGeometry(FVector2D(3*U,Size.Y),FSlateLayoutTransform(Start)),FCoreStyle::Get().GetBrush("WhiteBrush"),ESlateDrawEffect::None,Color);
        if(HasReadiness) {
            const FVector2D Origin=Start+FVector2D(6*U,(Size.Y-10*U)*.5f);
            const FLinearColor Ink=Readiness=="ready"?FLinearColor(.28f,.94f,.50f,1):Readiness=="recovering"?FLinearColor(1.f,.78f,.34f,1):FLinearColor(1.f,.35f,.58f,1);
            auto Stroke=[&](std::initializer_list<FVector2D> Points) {
                TArray<FVector2D> P;for(const auto& Point:Points)P.Add(Origin+Point*U);
                FSlateDrawElement::MakeLines(Elements,Layer+2,Geometry.ToPaintGeometry(),P,ESlateDrawEffect::None,Ink,true,1.7f*U);
            };
            // Vector strokes stay sharp without relying on a symbol font.
            if(Readiness=="ready")Stroke({{0,5},{3,8},{10,1}});
            else if(Readiness=="recovering") {
                Stroke({{1,0},{9,0},{9,2},{1,8},{1,10},{9,10},{9,8},{1,2},{1,0}});
            } else Stroke({{1,5},{9,5}});
        }
        const FString Text(UTF8_TO_TCHAR(M["label"].get_ref<const std::string&>().c_str()));
        FSlateDrawElement::MakeText(Elements,Layer+2,Geometry.ToPaintGeometry(Size,FSlateLayoutTransform(Start+FVector2D(HasReadiness?22:6,3)*U)),Text,FCoreStyle::GetDefaultFontStyle("Regular",FMath::Max(1,FMath::RoundToInt(12*U))),ESlateDrawEffect::None,Color);
    }
    return Layer+3;
}
