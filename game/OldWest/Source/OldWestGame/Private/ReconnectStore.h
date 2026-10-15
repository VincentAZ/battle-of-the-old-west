#pragma once
#include <string>

namespace oldwest {
struct ReconnectCredentials {
    std::string endpoint;
    std::string serverSession;
    std::string token;
};
enum class ReconnectReadStatus { Loaded, Missing, Invalid, Unavailable };
struct ReconnectReadResult {
    ReconnectReadStatus status = ReconnectReadStatus::Missing;
    ReconnectCredentials credentials;
};

// The supplied directory belongs to one local profile. Neither function logs
// credentials. On Unix, directories/files are restricted to the current user;
// symlinks, foreign ownership, unsafe modes and oversized records are rejected.
ReconnectReadResult ReadReconnectProfile(const std::string& directory);
bool WriteReconnectProfile(const std::string& directory, const ReconnectCredentials& credentials);
}
