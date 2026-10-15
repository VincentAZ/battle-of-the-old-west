#include "ReconnectStore.h"
#define NOMINMAX
#include <windows.h>
#include <aclapi.h>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <vector>

namespace fs = std::filesystem;
using namespace oldwest;
namespace {
std::string Utf8(const fs::path& path)
{
    const std::wstring value = path.wstring();
    const int count = WideCharToMultiByte(CP_UTF8, WC_ERR_INVALID_CHARS, value.data(), static_cast<int>(value.size()), nullptr, 0, nullptr, nullptr);
    if (count <= 0) throw std::runtime_error("UTF8 conversion failed");
    std::string result(static_cast<std::size_t>(count), '\0');
    WideCharToMultiByte(CP_UTF8, WC_ERR_INVALID_CHARS, value.data(), static_cast<int>(value.size()), result.data(), count, nullptr, nullptr);
    return result;
}
std::string Bytes(const fs::path& path)
{
    std::ifstream file(path, std::ios::binary);
    return std::string(std::istreambuf_iterator<char>(file), {});
}
bool ProtectedSingleAce(const fs::path& path)
{
    PSECURITY_DESCRIPTOR sd = nullptr;
    PACL acl = nullptr;
    const DWORD result = GetNamedSecurityInfoW(const_cast<wchar_t*>(path.c_str()), SE_FILE_OBJECT,
        DACL_SECURITY_INFORMATION, nullptr, nullptr, &acl, nullptr, &sd);
    SECURITY_DESCRIPTOR_CONTROL control = 0; DWORD revision = 0;
    const bool valid = result == ERROR_SUCCESS && acl && acl->AceCount == 1
        && GetSecurityDescriptorControl(sd, &control, &revision) && (control & SE_DACL_PROTECTED);
    if (sd) LocalFree(sd);
    return valid;
}
bool AddWorldRead(const fs::path& path)
{
    PSECURITY_DESCRIPTOR sd = nullptr; PACL oldAcl = nullptr, newAcl = nullptr;
    if (GetNamedSecurityInfoW(const_cast<wchar_t*>(path.c_str()), SE_FILE_OBJECT, DACL_SECURITY_INFORMATION,
        nullptr, nullptr, &oldAcl, nullptr, &sd) != ERROR_SUCCESS) return false;
    unsigned char world[SECURITY_MAX_SID_SIZE] {}; DWORD size = sizeof(world);
    bool ok = CreateWellKnownSid(WinWorldSid, nullptr, world, &size) != 0;
    EXPLICIT_ACCESSW access {};
    access.grfAccessPermissions = FILE_GENERIC_READ;
    access.grfAccessMode = GRANT_ACCESS;
    access.grfInheritance = NO_INHERITANCE;
    access.Trustee.TrusteeForm = TRUSTEE_IS_SID;
    access.Trustee.TrusteeType = TRUSTEE_IS_WELL_KNOWN_GROUP;
    access.Trustee.ptstrName = reinterpret_cast<LPWSTR>(world);
    if (ok) ok = SetEntriesInAclW(1, &access, oldAcl, &newAcl) == ERROR_SUCCESS;
    if (ok) ok = SetNamedSecurityInfoW(const_cast<wchar_t*>(path.c_str()), SE_FILE_OBJECT,
        DACL_SECURITY_INFORMATION | PROTECTED_DACL_SECURITY_INFORMATION, nullptr, nullptr, newAcl, nullptr) == ERROR_SUCCESS;
    if (newAcl) LocalFree(newAcl);
    LocalFree(sd); return ok;
}
}
int main()
{
    wchar_t temporary[MAX_PATH] {};
    if (!GetTempPathW(MAX_PATH, temporary)) return 1;
    const fs::path root = fs::path(temporary) / (L"oldwest-reconnect-" + std::to_wstring(GetCurrentProcessId()) + L"-" + std::to_wstring(GetTickCount64()));
    const fs::path profile = root / L"profile-\u00e9-\u4e2d";
    const fs::path file = profile / L"reconnect.bin";
    int checks = 0;
    bool symlinkChecks = false;
    auto require = [&](bool ok) { ++checks; if (!ok) throw std::runtime_error("Windows reconnect regression failed"); };
    const ReconnectCredentials first {"192.0.2.16:7777", "0123456789abcdef0123456789abcdef", "abcdef0123456789abcdef0123456789"};
    const ReconnectCredentials second {"host.example:7777", "11111111111111111111111111111111", "22222222222222222222222222222222"};
    try
    {
        require(ReadReconnectProfile(Utf8(profile)).status == ReconnectReadStatus::Missing);
        fs::create_directories(profile);
        const fs::path collision = profile / (L".reconnect." + std::to_wstring(GetCurrentProcessId()) + L".1.tmp");
        { std::ofstream out(collision); out << "interrupted"; }
        require(WriteReconnectProfile(Utf8(profile), first));
        require(fs::exists(collision));
        auto read = ReadReconnectProfile(Utf8(profile));
        require(read.status == ReconnectReadStatus::Loaded && read.credentials.endpoint == first.endpoint
            && read.credentials.serverSession == first.serverSession && read.credentials.token == first.token);
        require(ProtectedSingleAce(profile)); require(ProtectedSingleAce(file));
        const std::string encrypted = Bytes(file);
        require(encrypted.find(first.token) == std::string::npos && encrypted.find(first.endpoint) == std::string::npos);
        require(WriteReconnectProfile(Utf8(profile), second));
        require(ReadReconnectProfile(Utf8(profile)).credentials.token == second.token);
        auto invalid = first; invalid.endpoint += "?SeatToken=injected";
        require(!WriteReconnectProfile(Utf8(profile), invalid));
        require(ReadReconnectProfile(Utf8(profile)).credentials.token == second.token);
        require(AddWorldRead(file));
        require(ReadReconnectProfile(Utf8(profile)).status == ReconnectReadStatus::Invalid);
        require(WriteReconnectProfile(Utf8(profile), first));
        require(ProtectedSingleAce(file));
        require(AddWorldRead(profile));
        require(ReadReconnectProfile(Utf8(profile)).status == ReconnectReadStatus::Invalid);
        require(WriteReconnectProfile(Utf8(profile), first));
        require(ProtectedSingleAce(profile));
        { auto bytes = Bytes(file); bytes[bytes.size()/2] ^= 0x40; std::ofstream out(file, std::ios::binary|std::ios::trunc); out.write(bytes.data(), bytes.size()); }
        require(ReadReconnectProfile(Utf8(profile)).status == ReconnectReadStatus::Invalid);
        { std::ofstream out(file, std::ios::binary|std::ios::trunc); out << std::string(16385, 'x'); }
        require(ReadReconnectProfile(Utf8(profile)).status == ReconnectReadStatus::Invalid);
        require(WriteReconnectProfile(Utf8(profile), first));
        const fs::path alias = profile / L"hardlink.bin";
        require(CreateHardLinkW(alias.c_str(), file.c_str(), nullptr) != 0);
        require(ReadReconnectProfile(Utf8(profile)).status == ReconnectReadStatus::Invalid);
        require(WriteReconnectProfile(Utf8(profile), second));
        require(ReadReconnectProfile(Utf8(profile)).credentials.token == second.token);
        // Only exercise privileged symlink creation if Windows permits it. A
        // printed false flag keeps this limitation visible to the reviewer.
        const fs::path linkedDirectory = root / L"linked-profile";
        if (CreateSymbolicLinkW(linkedDirectory.c_str(), profile.c_str(), SYMBOLIC_LINK_FLAG_DIRECTORY | 0x2))
        {
            symlinkChecks = true;
            require(!WriteReconnectProfile(Utf8(linkedDirectory), first));
            require(ReadReconnectProfile(Utf8(linkedDirectory)).status != ReconnectReadStatus::Loaded);
            fs::remove(linkedDirectory);
            fs::remove(file);
            require(CreateSymbolicLinkW(file.c_str(), alias.c_str(), 0x2) != 0);
            require(ReadReconnectProfile(Utf8(profile)).status != ReconnectReadStatus::Loaded);
            require(WriteReconnectProfile(Utf8(profile), second));
            require(!fs::is_symlink(file));
        }
        { std::ofstream orphan(profile/L".reconnect.interrupted.tmp"); orphan << "partial"; }
        require(ReadReconnectProfile(Utf8(profile)).credentials.token == second.token);
        fs::remove_all(root);
        std::cout << "{\"ok\":true,\"checks\":" << checks << ",\"symbolic_link_checks\":" << (symlinkChecks ? "true" : "false") << "}\n";
        return 0;
    }
    catch (const std::exception& error)
    {
        std::error_code ignored; fs::remove_all(root, ignored);
        std::cerr << error.what() << " (check " << checks << ")\n"; return 1;
    }
}
