#include "OldWestNetworkAddresses.h"
#include "Core/ListenAddressPolicy.h"
#include "Engine/World.h"
#include "HAL/FileManager.h"
#include "IPAddress.h"
#include "SocketSubsystem.h"
#if PLATFORM_LINUX
#include <arpa/inet.h>
#include <ifaddrs.h>
#include <net/if.h>
#endif

namespace {
std::vector<oldwest::network::InviteAddress> LocalInterfaceMetadata()
{
    std::vector<oldwest::network::InviteAddress> Result;
#if PLATFORM_LINUX
    // UE's Unix address enumeration intentionally returns every UP interface
    // and drops its name. Recover local metadata for invite ranking only.
    ifaddrs* Interfaces = nullptr;
    if (getifaddrs(&Interfaces) != 0) return Result;
    for (const ifaddrs* Interface = Interfaces; Interface; Interface = Interface->ifa_next)
    {
        if (!Interface->ifa_addr || !Interface->ifa_name || Interface->ifa_addr->sa_family != AF_INET) continue;
        char Host[INET_ADDRSTRLEN] = {};
        const auto* Address = reinterpret_cast<const sockaddr_in*>(Interface->ifa_addr);
        if (!inet_ntop(AF_INET, &Address->sin_addr, Host, sizeof(Host))) continue;
        const FString Device = FString::Printf(TEXT("/sys/class/net/%s/device"), UTF8_TO_TCHAR(Interface->ifa_name));
        Result.push_back({Host, Interface->ifa_name, true,
            (Interface->ifa_flags & IFF_UP) != 0 && (Interface->ifa_flags & IFF_RUNNING) != 0,
            (Interface->ifa_flags & IFF_LOOPBACK) != 0, (Interface->ifa_flags & IFF_POINTOPOINT) != 0,
            IFileManager::Get().DirectoryExists(*Device)});
    }
    freeifaddrs(Interfaces);
#endif
    return Result;
}
}

TArray<FString> OldWestNetworkAddresses::GetLocalListenAddresses(UWorld* World)
{
    TArray<FString> Result;
    if (!World || World->GetNetMode() != NM_ListenServer) return Result;
    ISocketSubsystem* Sockets = ISocketSubsystem::Get(PLATFORM_SOCKETSUBSYSTEM);
    if (!Sockets) return Result;
    TArray<TSharedPtr<FInternetAddr>> Addresses;
    if (!Sockets->GetLocalAdapterAddresses(Addresses)) return Result;
    const auto Metadata = LocalInterfaceMetadata();
    std::vector<oldwest::network::InviteAddress> Candidates;
    for (const auto& Address : Addresses)
    {
        // Keep the existing automatic IPv4 contract. Manual DNS/IPv4/IPv6
        // joining remains separate, including bracketed IPv6 host:port syntax.
        if (!Address.IsValid() || !Address->IsValid() || Address->GetProtocolType() != FNetworkProtocolTypes::IPv4) continue;
        const std::string Host(TCHAR_TO_UTF8(*Address->ToString(false)));
        bool Found = false;
        for (const auto& Interface : Metadata)
            if (Interface.Host == Host) { Candidates.push_back(Interface); Found = true; }
        // Missing metadata never implies that an address is a Docker network.
        // Windows retains UE's UP Ethernet/Wi-Fi enumeration in this patch.
        if (!Found) Candidates.push_back({Host, ""});
    }
    for (const auto& Host : oldwest::network::PreferredInviteHosts(Candidates))
        Result.Add(FString::Printf(TEXT("%s:%d"), UTF8_TO_TCHAR(Host.c_str()), World->URL.Port));
    return Result;
}
