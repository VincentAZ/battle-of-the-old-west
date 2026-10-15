#pragma once
#include <array>
#include <string>
#include <string_view>
#include <vector>

// Western presentation vocabulary (scripts/western_terms.py). Display only:
// commands, saves, catalogs, AI inputs and network payloads never pass here.
// One left-to-right pass, longest phrase first, whole words only, so a
// translated name is never translated again and bare IDs stay canonical.
namespace OldWestWesternTerms
{
struct FTerm
{
    const char* From;
    const char* To;
    bool ProseOnly;
};
inline constexpr FTerm Terms[] = {
#include "OldWestWesternTerms.inl"
};
inline bool IsWord(unsigned char C)
{
    return (C >= 'a' && C <= 'z') || (C >= 'A' && C <= 'Z') || (C >= '0' && C <= '9') || C == '_';
}
inline const std::array<std::vector<int>, 256>& Index()
{
    // Terms are already sorted longest-first; bucket them by first byte.
    static const auto Built = [] {
        std::array<std::vector<int>, 256> Buckets;
        for (int I = 0; I < int(std::size(Terms)); ++I)
            Buckets[static_cast<unsigned char>(Terms[I].From[0])].push_back(I);
        return Buckets;
    }();
    return Built;
}
inline std::string Translate(std::string_view Text)
{
    if (Text.empty() || Text.front() == '{' || Text.front() == '[') return std::string(Text);
    const bool Prose = Text.find(' ') != std::string_view::npos;
    const auto& Buckets = Index();
    std::string Out;
    Out.reserve(Text.size() + 16);
    for (std::size_t I = 0; I < Text.size();)
    {
        const unsigned char C = static_cast<unsigned char>(Text[I]);
        if (I == 0 || !IsWord(static_cast<unsigned char>(Text[I - 1])))
        {
            bool Matched = false;
            for (const int T : Buckets[C])
            {
                const FTerm& Term = Terms[T];
                if (Term.ProseOnly && !Prose) continue;
                const std::string_view From(Term.From);
                if (Text.compare(I, From.size(), From) != 0) continue;
                const std::size_t End = I + From.size();
                if (End < Text.size() && IsWord(static_cast<unsigned char>(Text[End]))) continue;
                Out += Term.To;
                I = End;
                Matched = true;
                break;
            }
            if (Matched) continue;
        }
        Out += Text[I++];
    }
    return Out;
}
}
