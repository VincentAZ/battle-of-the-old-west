#include "ReconnectStore.h"
#include <filesystem>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <sys/stat.h>
#include <unistd.h>

namespace fs = std::filesystem;
using namespace oldwest;
int main()
{
    char pattern[] = "/tmp/oldwest-reconnect-unit-XXXXXX";
    const fs::path root = mkdtemp(pattern);
    int checks = 0;
    auto require = [&](bool value) { ++checks; if (!value) throw std::runtime_error("Reconnect-store regression failed"); };
    const fs::path profile = root / "a";
    const fs::path path = profile / "reconnect.json";
    const ReconnectCredentials first {"127.0.0.1:7777", "0123456789abcdef0123456789abcdef", "abcdef0123456789abcdef0123456789"};
    const ReconnectCredentials second {"[::1]:7778", "11111111111111111111111111111111", "22222222222222222222222222222222"};
    try
    {
        require(ReadReconnectProfile(profile.string()).status == ReconnectReadStatus::Missing);
        fs::create_directories(profile);
        const fs::path collision = profile / (".reconnect." + std::to_string(getpid()) + ".1.tmp");
        { std::ofstream orphan(collision); orphan << "{interrupted previous process"; }
        require(WriteReconnectProfile(profile.string(), first));
        require(fs::exists(collision));
        const auto saved = ReadReconnectProfile(profile.string());
        require(saved.status == ReconnectReadStatus::Loaded && saved.credentials.endpoint == first.endpoint
            && saved.credentials.serverSession == first.serverSession && saved.credentials.token == first.token);
        struct stat metadata {};
        require(stat(profile.c_str(), &metadata) == 0 && (metadata.st_mode & 0777) == 0700);
        require(stat(path.c_str(), &metadata) == 0 && (metadata.st_mode & 0777) == 0600);
        require(WriteReconnectProfile(profile.string(), second));
        require(ReadReconnectProfile(profile.string()).credentials.endpoint == second.endpoint);
        require(ReadReconnectProfile((root / "b").string()).status == ReconnectReadStatus::Missing);
        ReconnectCredentials invalid = first;
        invalid.endpoint += "?SeatToken=injected";
        require(!WriteReconnectProfile(profile.string(), invalid));
        require(ReadReconnectProfile(profile.string()).credentials.endpoint == second.endpoint);
        chmod(path.c_str(), 0644);
        require(ReadReconnectProfile(profile.string()).status == ReconnectReadStatus::Invalid);
        require(WriteReconnectProfile(profile.string(), first));
        require(stat(path.c_str(), &metadata) == 0 && (metadata.st_mode & 0777) == 0600);
        { std::ofstream file(path); file << "{truncated"; }
        require(ReadReconnectProfile(profile.string()).status == ReconnectReadStatus::Invalid);
        { std::ofstream file(path); file << std::string(4097, 'x'); }
        require(ReadReconnectProfile(profile.string()).status == ReconnectReadStatus::Invalid);
        require(WriteReconnectProfile(profile.string(), first));
        fs::rename(path, profile / "original.json");
        fs::create_symlink(profile / "original.json", path);
        require(ReadReconnectProfile(profile.string()).status != ReconnectReadStatus::Loaded);
        require(WriteReconnectProfile(profile.string(), second));
        require(!fs::is_symlink(path));
        require(ReadReconnectProfile(profile.string()).credentials.token == second.token);
        fs::remove(path);
        require(mkfifo(path.c_str(), 0600) == 0);
        require(ReadReconnectProfile(profile.string()).status == ReconnectReadStatus::Invalid);
        fs::remove(path);
        fs::create_symlink(profile, root / "aliased-profile");
        require(!WriteReconnectProfile((root / "aliased-profile").string(), first));
        require(ReadReconnectProfile((root / "aliased-profile").string()).status != ReconnectReadStatus::Loaded);
        require(WriteReconnectProfile(profile.string(), first));
        // Interrupted temporary writes do not replace the complete record.
        { std::ofstream orphan(profile / ".reconnect.interrupted.tmp"); orphan << "{partial"; }
        require(ReadReconnectProfile(profile.string()).credentials.token == first.token);
        fs::remove_all(root);
        std::cout << "Reconnect store: " << checks << " checks passed\n";
        return 0;
    }
    catch (const std::exception& error)
    {
        fs::remove_all(root);
        std::cerr << error.what() << " (check " << checks << ")\n";
        return 1;
    }
}
