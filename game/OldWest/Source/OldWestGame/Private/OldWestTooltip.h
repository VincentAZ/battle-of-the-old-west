#pragma once
#include "CoreMinimal.h"
#include "Brushes/SlateRoundedBoxBrush.h"
#include "Styling/CoreStyle.h"
#include "Widgets/SToolTip.h"
#include "Widgets/Text/STextBlock.h"

// Tooltips live in their own Slate popup, outside the logical HUD scale box.
// Use a readable popup font and the same high-contrast palette as the panels.
inline TSharedPtr<IToolTip> OldWestTooltip(TAttribute<FText> Text)
{
    if (!Text.IsBound() && (!Text.IsSet() || Text.Get().IsEmpty())) return nullptr;
    static const FSlateRoundedBoxBrush Background(FLinearColor(.012f,.022f,.027f,1.f), 5.f,
        FLinearColor(.20f,.29f,.29f,1.f), 1.f);
    return SNew(SToolTip).BorderImage(&Background).TextMargin(FMargin(8.f,6.f))
        [SNew(STextBlock).Text(Text).Font(FCoreStyle::GetDefaultFontStyle("Regular",12))
            .ColorAndOpacity(FLinearColor(.93f,.91f,.85f,1.f)).WrapTextAt(320.f)];
}
