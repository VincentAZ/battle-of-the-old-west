#pragma once
#include "CoreMinimal.h"

class UWorld;

namespace OldWestNetworkAddresses
{
// Suggested IPv4 endpoints for a listen host. On Linux, physical interfaces
// rank first and known container/tunnel interfaces are omitted. On other
// platforms, use the socket subsystem's existing adapter selection. This does not
// contact an external service, discover a public NAT address, or promise that
// another network can reach the returned addresses.
TArray<FString> GetLocalListenAddresses(UWorld* World);
}
