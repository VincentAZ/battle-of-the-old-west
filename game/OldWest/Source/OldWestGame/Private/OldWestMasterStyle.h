#include "OldWestDisplayNames.h"
#pragma once
#include "CoreMinimal.h"
#include "Brushes/SlateRoundedBoxBrush.h"
#include "Styling/SlateTypes.h"
namespace OldWestMasterStyle {
inline FString Text(const std::string& S) { return OldWestDisplay::Text(FString(UTF8_TO_TCHAR(S.c_str()))); }
inline const FLinearColor Sand(.90f,.89f,.83f,1), Muted(.68f,.76f,.78f,1), Aqua(.24f,.81f,.73f,1), Pink(.96f,.36f,.38f,1);
inline const FButtonStyle& ActionButtonStyle() {
    static const FButtonStyle Style=[] {
        FButtonStyle R;
        R.SetNormal(FSlateRoundedBoxBrush(FLinearColor(.025f,.044f,.05f,1),4.f,FLinearColor(.10f,.18f,.20f,1),1.f));
        R.SetHovered(FSlateRoundedBoxBrush(FLinearColor(.06f,.12f,.13f,1),4.f,FLinearColor(.24f,.62f,.57f,1),1.f));
        R.SetPressed(FSlateRoundedBoxBrush(FLinearColor(.04f,.09f,.10f,1),4.f,FLinearColor(.24f,.81f,.73f,1),1.f));
        R.SetDisabled(FSlateRoundedBoxBrush(FLinearColor(.025f,.032f,.036f,.8f),4.f));
        return R;
    }(); return Style;
}
}
