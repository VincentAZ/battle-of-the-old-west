#pragma once

// Generated from exact original Prospector outsole/tread mesh vertices.
// Each selected vertex has weight1 on the named Foot bone. Six per foot,
// including the lowest tread point; this is not a whole-surface support proof.
namespace OldWestScientistSoles {
struct FPoint { const TCHAR* Side; const TCHAR* Object; int32 Vertex; const TCHAR* Bone; double X,Y,Z; };
static const FPoint Points[] = {
    {TEXT("Left"),TEXT("Left_Tread"),0,TEXT("LeftFoot"),4.91794683039,-23.3299344778,3.61888967454},
    {TEXT("Left"),TEXT("Survivor_Left_Outsole"),11,TEXT("LeftFoot"),-0.0334090436809,-0.30213710852,-11.5210674703},
    {TEXT("Left"),TEXT("Survivor_Left_Outsole"),0,TEXT("LeftFoot"),-6.58656135201,-13.1960257888,-3.45447584987},
    {TEXT("Left"),TEXT("Survivor_Left_Outsole"),23,TEXT("LeftFoot"),7.55057558417,-11.1591927707,-3.38883586228},
    {TEXT("Left"),TEXT("Survivor_Left_Outsole"),42,TEXT("LeftFoot"),-4.80331815779,-22.2270011902,2.84719076008},
    {TEXT("Left"),TEXT("Left_Tread.006"),25,TEXT("LeftFoot"),5.77251687646,-4.83783222735,-8.46009775996},
    {TEXT("Right"),TEXT("Right_Tread"),0,TEXT("RightFoot"),4.45704348385,-23.4500706196,3.03369909525},
    {TEXT("Right"),TEXT("Survivor_Right_Outsole"),11,TEXT("RightFoot"),-1.82330422103,-0.303667737171,-11.4167198539},
    {TEXT("Right"),TEXT("Survivor_Right_Outsole"),0,TEXT("RightFoot"),-7.55497962236,-12.779070437,-2.15508434922},
    {TEXT("Right"),TEXT("Survivor_Right_Outsole"),23,TEXT("RightFoot"),6.47305250168,-11.484144628,-4.51070144773},
    {TEXT("Right"),TEXT("Survivor_Right_Outsole"),42,TEXT("RightFoot"),-5.18631711602,-21.8456611037,3.89766544104},
    {TEXT("Right"),TEXT("Right_Tread.006"),25,TEXT("RightFoot"),4.18164134026,-5.1148597151,-9.30866077542},
};
}
