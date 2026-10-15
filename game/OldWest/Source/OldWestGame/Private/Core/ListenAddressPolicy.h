#pragma once
#include <algorithm>
#include <cctype>
#include <cstdint>
#include <string>
#include <vector>

namespace oldwest::network {
// Invite suggestions only. These classifications must never gate a manually
// entered endpoint, socket binding, firewall rule or routing decision.
struct InviteAddress {
    std::string Host, Interface;
    bool MetadataKnown = false, Up = true, Loopback = false, PointToPoint = false, Physical = false;
};

inline bool NumberedInterface(const std::string& Name, const char* Prefix) {
    const std::string P(Prefix);
    return Name.compare(0, P.size(), P) == 0 && Name.size() > P.size() &&
        std::all_of(Name.begin() + P.size(), Name.end(), [](unsigned char C) { return std::isdigit(C); });
}

inline bool KnownNonLanInterface(std::string Name) {
    std::transform(Name.begin(), Name.end(), Name.begin(), [](unsigned char C) { return std::tolower(C); });
    for (const char* Prefix : {"docker", "virbr", "vnet", "lxcbr", "cni", "tun", "tap", "wg", "tailscale", "utun"})
        if (NumberedInterface(Name, Prefix)) return true;
    for (const char* Prefix : {"veth", "flannel.", "cali"})
        if (Name.compare(0, std::string(Prefix).size(), Prefix) == 0) return true;
    // Docker's default user-defined bridges, not arbitrary br0/br-lan bridges.
    return Name.size() == 15 && Name.compare(0, 3, "br-") == 0 &&
        std::all_of(Name.begin() + 3, Name.end(), [](unsigned char C) { return std::isxdigit(C); });
}

inline bool UsableInviteIPv4(const std::string& Host, std::uint32_t& Number) {
    Number = 0;
    std::size_t At = 0;
    for (int Part = 0; Part < 4; ++Part) {
        unsigned Value = 0, Digits = 0;
        while (At < Host.size() && Host[At] >= '0' && Host[At] <= '9') {
            Value = Value * 10 + (Host[At++] - '0');
            if (++Digits > 3 || Value > 255) return false;
        }
        if (Digits == 0) return false;
        Number = (Number << 8) | Value;
        if (Part < 3 && (At == Host.size() || Host[At++] != '.')) return false;
    }
    if (At != Host.size()) return false;
    const unsigned A = Number >> 24, B = (Number >> 16) & 255;
    return A != 0 && A != 127 && A < 224 && !(A == 169 && B == 254);
}

inline std::vector<std::string> PreferredInviteHosts(const std::vector<InviteAddress>& Candidates) {
    struct Ranked { std::string Host; bool Physical; std::uint32_t Number; };
    std::vector<Ranked> Accepted;
    for (const InviteAddress& A : Candidates) {
        std::uint32_t Number;
        if (!UsableInviteIPv4(A.Host, Number)) continue;
        if (A.MetadataKnown && (!A.Up || A.Loopback || A.PointToPoint || KnownNonLanInterface(A.Interface))) continue;
        Accepted.push_back({A.Host, A.MetadataKnown && A.Physical, Number});
    }
    std::sort(Accepted.begin(), Accepted.end(), [](const Ranked& A, const Ranked& B) {
        if (A.Physical != B.Physical) return A.Physical > B.Physical;
        if (A.Number != B.Number) return A.Number < B.Number;
        return A.Host < B.Host;
    });
    std::vector<std::string> Result;
    for (const Ranked& A : Accepted)
        if (std::find(Result.begin(), Result.end(), A.Host) == Result.end()) Result.push_back(A.Host);
    return Result;
}
}
