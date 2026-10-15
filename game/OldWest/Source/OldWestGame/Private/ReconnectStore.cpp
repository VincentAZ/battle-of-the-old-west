#include "ReconnectStore.h"
#include "Core/json.hpp"
#include <atomic>
#include <cerrno>
#include <filesystem>
#include <vector>

#if defined(_WIN32)
#if __has_include("Windows/WindowsHWrapper.h")
#include "Windows/WindowsHWrapper.h"
#include "Windows/AllowWindowsPlatformTypes.h"
#define OLDWEST_HIDE_WINDOWS_TYPES 1
#else
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>
#endif
#include <aclapi.h>
#include <wincrypt.h>
#include <dpapi.h>
#if defined(OLDWEST_HIDE_WINDOWS_TYPES)
#include "Windows/HideWindowsPlatformTypes.h"
#undef OLDWEST_HIDE_WINDOWS_TYPES
#endif
#endif

#if defined(__unix__) || defined(__APPLE__)
#include <fcntl.h>
#include <sys/stat.h>
#include <unistd.h>
#endif

namespace oldwest {
namespace {
bool HexIdentifier(const std::string& value)
{
    if (value.size() != 32) return false;
    for (const unsigned char c : value)
        if (!((c >= '0' && c <= '9') || (c >= 'a' && c <= 'f') || (c >= 'A' && c <= 'F'))) return false;
    return true;
}
bool Valid(const ReconnectCredentials& value)
{
    if (value.endpoint.empty() || value.endpoint.size() > 253 || value.endpoint.find(':') == std::string::npos
        || !HexIdentifier(value.serverSession) || !HexIdentifier(value.token)) return false;
    for (const unsigned char c : value.endpoint)
        if (!((c >= '0' && c <= '9') || (c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z')
            || c == '.' || c == '-' || c == ':' || c == '[' || c == ']')) return false;
    return true;
}
#if defined(_WIN32)
struct WinHandle {
    HANDLE value = INVALID_HANDLE_VALUE;
    explicit WinHandle(HANDLE handle) : value(handle) {}
    ~WinHandle() { if (value && value != INVALID_HANDLE_VALUE) CloseHandle(value); }
    WinHandle(const WinHandle&) = delete;
    WinHandle& operator=(const WinHandle&) = delete;
};
struct WinMemory {
    void* value = nullptr;
    ~WinMemory() { if (value) LocalFree(value); }
};

// Use the process account, never a broad Users/Everyone ACE. The descriptor is
// protected against inherited permissions and is also used for creation, so a
// credential file is never briefly created with a permissive default ACL.
struct PrivateWinSecurity {
    std::vector<unsigned char> user;
    std::vector<unsigned char> acl;
    SECURITY_DESCRIPTOR descriptor {};
    SECURITY_ATTRIBUTES attributes {};
    bool Initialize(bool directory)
    {
        HANDLE rawToken = nullptr;
        if (!OpenProcessToken(GetCurrentProcess(), TOKEN_QUERY, &rawToken)) return false;
        WinHandle token(rawToken);
        DWORD bytes = 0;
        GetTokenInformation(token.value, TokenUser, nullptr, 0, &bytes);
        if (!bytes) return false;
        std::vector<unsigned char> info(bytes);
        if (!GetTokenInformation(token.value, TokenUser, info.data(), bytes, &bytes)) return false;
        PSID sid = reinterpret_cast<TOKEN_USER*>(info.data())->User.Sid;
        if (!IsValidSid(sid)) return false;
        user.resize(GetLengthSid(sid));
        if (!CopySid(static_cast<DWORD>(user.size()), user.data(), sid)) return false;
        acl.resize(sizeof(ACL) + sizeof(ACCESS_ALLOWED_ACE) - sizeof(DWORD) + user.size());
        PACL list = reinterpret_cast<PACL>(acl.data());
        if (!InitializeAcl(list, static_cast<DWORD>(acl.size()), ACL_REVISION)
            || !AddAccessAllowedAceEx(list, ACL_REVISION, directory ? OBJECT_INHERIT_ACE | CONTAINER_INHERIT_ACE : 0,
                FILE_ALL_ACCESS, user.data())
            || !InitializeSecurityDescriptor(&descriptor, SECURITY_DESCRIPTOR_REVISION)
            || !SetSecurityDescriptorOwner(&descriptor, user.data(), 0)
            || !SetSecurityDescriptorDacl(&descriptor, 1, list, 0)
            || !SetSecurityDescriptorControl(&descriptor, SE_DACL_PROTECTED, SE_DACL_PROTECTED)) return false;
        attributes.nLength = sizeof(attributes);
        attributes.lpSecurityDescriptor = &descriptor;
        attributes.bInheritHandle = 0;
        return true;
    }
};

std::wstring WideDirectory(const std::string& directory)
{
    if (directory.empty() || directory.size() > 32760 || directory.find('\0') != std::string::npos) return {};
    const int size = MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, directory.data(), static_cast<int>(directory.size()), nullptr, 0);
    if (!size) return {};
    std::wstring result(static_cast<std::size_t>(size), L'\0');
    if (MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, directory.data(), static_cast<int>(directory.size()), result.data(), size) != size) return {};
    return result;
}

bool WinOwner(HANDLE handle, PSID expected, bool requirePrivate)
{
    PSID owner = nullptr;
    PACL acl = nullptr;
    PSECURITY_DESCRIPTOR raw = nullptr;
    if (GetSecurityInfo(handle, SE_FILE_OBJECT, OWNER_SECURITY_INFORMATION | DACL_SECURITY_INFORMATION,
        &owner, nullptr, &acl, nullptr, &raw) != ERROR_SUCCESS) return false;
    WinMemory memory; memory.value = raw;
    if (!owner || !IsValidSid(owner) || !EqualSid(owner, expected)) return false;
    if (!requirePrivate) return true;
    SECURITY_DESCRIPTOR_CONTROL control = 0;
    DWORD revision = 0;
    if (!GetSecurityDescriptorControl(raw, &control, &revision) || !(control & SE_DACL_PROTECTED)
        || !acl || !IsValidAcl(acl) || acl->AceCount != 1) return false;
    void* entry = nullptr;
    if (!GetAce(acl, 0, &entry)) return false;
    const auto* ace = static_cast<const ACCESS_ALLOWED_ACE*>(entry);
    return ace->Header.AceType == ACCESS_ALLOWED_ACE_TYPE && !(ace->Header.AceFlags & INHERIT_ONLY_ACE)
        && ace->Header.AceSize >= sizeof(ACCESS_ALLOWED_ACE)
        && IsValidSid(const_cast<DWORD*>(&ace->SidStart))
        && EqualSid(const_cast<DWORD*>(&ace->SidStart), expected)
        && (ace->Mask & FILE_ALL_ACCESS) == FILE_ALL_ACCESS;
}

bool WinFileKind(HANDLE handle, bool directory, BY_HANDLE_FILE_INFORMATION& info)
{
    return handle != INVALID_HANDLE_VALUE && GetFileType(handle) == FILE_TYPE_DISK
        && GetFileInformationByHandle(handle, &info)
        && !(info.dwFileAttributes & FILE_ATTRIBUTE_REPARSE_POINT)
        && bool(info.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) == directory
        && (directory || info.nNumberOfLinks == 1);
}

ReconnectReadResult ReadWinProfile(const std::string& directory)
{
    const std::wstring wide = WideDirectory(directory);
    PrivateWinSecurity security;
    if (wide.empty() || !security.Initialize(true)) return {ReconnectReadStatus::Unavailable, {}};
    WinHandle parent(CreateFileW(wide.c_str(), FILE_READ_ATTRIBUTES | READ_CONTROL, FILE_SHARE_READ | FILE_SHARE_WRITE,
        nullptr, OPEN_EXISTING, FILE_FLAG_BACKUP_SEMANTICS | FILE_FLAG_OPEN_REPARSE_POINT, nullptr));
    if (parent.value == INVALID_HANDLE_VALUE)
    {
        const DWORD error = GetLastError();
        return {error == ERROR_FILE_NOT_FOUND || error == ERROR_PATH_NOT_FOUND ? ReconnectReadStatus::Missing : ReconnectReadStatus::Unavailable, {}};
    }
    BY_HANDLE_FILE_INFORMATION info {};
    if (!WinFileKind(parent.value, true, info) || !WinOwner(parent.value, security.user.data(), true)) return {ReconnectReadStatus::Invalid, {}};
    const std::wstring filename = (std::filesystem::path(wide) / L"reconnect.bin").wstring();
    WinHandle file(CreateFileW(filename.c_str(), GENERIC_READ | READ_CONTROL, FILE_SHARE_READ | FILE_SHARE_DELETE,
        nullptr, OPEN_EXISTING, FILE_FLAG_OPEN_REPARSE_POINT | FILE_FLAG_SEQUENTIAL_SCAN, nullptr));
    if (file.value == INVALID_HANDLE_VALUE)
        return {GetLastError() == ERROR_FILE_NOT_FOUND ? ReconnectReadStatus::Missing : ReconnectReadStatus::Unavailable, {}};
    if (!WinFileKind(file.value, false, info) || !WinOwner(file.value, security.user.data(), true)
        || info.nFileSizeHigh || !info.nFileSizeLow || info.nFileSizeLow > 16384) return {ReconnectReadStatus::Invalid, {}};
    std::vector<unsigned char> encrypted(info.nFileSizeLow);
    DWORD count = 0;
    if (!ReadFile(file.value, encrypted.data(), static_cast<DWORD>(encrypted.size()), &count, nullptr) || count != encrypted.size())
        return {ReconnectReadStatus::Invalid, {}};
    DATA_BLOB input {count, encrypted.data()}, output {};
    if (!CryptUnprotectData(&input, nullptr, nullptr, nullptr, nullptr, CRYPTPROTECT_UI_FORBIDDEN, &output))
        return {ReconnectReadStatus::Invalid, {}};
    WinMemory decrypted; decrypted.value = output.pbData;
    if (!output.cbData || output.cbData > 4096) return {ReconnectReadStatus::Invalid, {}};
    try
    {
        const auto record = nlohmann::ordered_json::parse(output.pbData, output.pbData + output.cbData);
        SecureZeroMemory(output.pbData, output.cbData);
        if (record.at("version").get<int>() != 1) return {ReconnectReadStatus::Invalid, {}};
        ReconnectCredentials credentials {record.at("endpoint").get<std::string>(),
            record.at("server_session").get<std::string>(), record.at("token").get<std::string>()};
        if (!Valid(credentials)) return {ReconnectReadStatus::Invalid, {}};
        return {ReconnectReadStatus::Loaded, std::move(credentials)};
    }
    catch (const std::exception&) { SecureZeroMemory(output.pbData, output.cbData); return {ReconnectReadStatus::Invalid, {}}; }
}

bool WriteWinProfile(const std::string& directory, const ReconnectCredentials& credentials)
{
    const std::wstring wide = WideDirectory(directory);
    PrivateWinSecurity security, fileSecurity;
    if (wide.empty() || !security.Initialize(true) || !fileSecurity.Initialize(false)) return false;
    // The parent profile directory contains no credential bytes while being
    // created/hardened. Only its verified owner may have its ACL replaced.
    std::error_code error;
    std::filesystem::create_directories(std::filesystem::path(wide).parent_path(), error);
    if (error) return false;
    if (!CreateDirectoryW(wide.c_str(), &security.attributes) && GetLastError() != ERROR_ALREADY_EXISTS) return false;
    WinHandle parent(CreateFileW(wide.c_str(), FILE_READ_ATTRIBUTES | READ_CONTROL | WRITE_DAC, FILE_SHARE_READ | FILE_SHARE_WRITE,
        nullptr, OPEN_EXISTING, FILE_FLAG_BACKUP_SEMANTICS | FILE_FLAG_OPEN_REPARSE_POINT, nullptr));
    BY_HANDLE_FILE_INFORMATION info {};
    if (!WinFileKind(parent.value, true, info) || !WinOwner(parent.value, security.user.data(), false)) return false;
    if (SetSecurityInfo(parent.value, SE_FILE_OBJECT, DACL_SECURITY_INFORMATION | PROTECTED_DACL_SECURITY_INFORMATION,
        nullptr, nullptr, reinterpret_cast<PACL>(security.acl.data()), nullptr) != ERROR_SUCCESS
        || !WinOwner(parent.value, security.user.data(), true)) return false;
    std::string plain = nlohmann::ordered_json({{"version", 1}, {"endpoint", credentials.endpoint},
        {"server_session", credentials.serverSession}, {"token", credentials.token}}).dump();
    DATA_BLOB input {static_cast<DWORD>(plain.size()), reinterpret_cast<unsigned char*>(plain.data())}, output {};
    const bool protectedBytes = CryptProtectData(&input, L"Battle of the Old West reconnect profile", nullptr, nullptr, nullptr,
        CRYPTPROTECT_UI_FORBIDDEN, &output) != 0;
    SecureZeroMemory(plain.data(), plain.size());
    if (!protectedBytes) return false;
    WinMemory encrypted; encrypted.value = output.pbData;
    static std::atomic<unsigned long> serial {0};
    std::wstring temporary;
    HANDLE raw = INVALID_HANDLE_VALUE;
    for (int attempt = 0; attempt < 32; ++attempt)
    {
        temporary = (std::filesystem::path(wide) / (L".reconnect." + std::to_wstring(GetCurrentProcessId()) + L"." + std::to_wstring(++serial) + L".tmp")).wstring();
        raw = CreateFileW(temporary.c_str(), GENERIC_WRITE | READ_CONTROL, 0, &fileSecurity.attributes,
            CREATE_NEW, FILE_ATTRIBUTE_TEMPORARY | FILE_FLAG_OPEN_REPARSE_POINT, nullptr);
        if (raw != INVALID_HANDLE_VALUE || GetLastError() != ERROR_FILE_EXISTS) break;
    }
    if (raw == INVALID_HANDLE_VALUE) return false;
    bool written = false;
    {
        WinHandle file(raw);
        DWORD count = 0;
        written = WinFileKind(file.value, false, info) && WinOwner(file.value, security.user.data(), true)
            && WriteFile(file.value, output.pbData, output.cbData, &count, nullptr) && count == output.cbData
            && FlushFileBuffers(file.value);
    }
    const std::wstring destination = (std::filesystem::path(wide) / L"reconnect.bin").wstring();
    if (written) written = MoveFileExW(temporary.c_str(), destination.c_str(), MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH) != 0;
    if (!written) DeleteFileW(temporary.c_str());
    return written;
}
#endif
#if defined(__unix__) || defined(__APPLE__)
struct FileDescriptor {
    int value = -1;
    explicit FileDescriptor(int descriptor) : value(descriptor) {}
    ~FileDescriptor() { if (value >= 0) close(value); }
    FileDescriptor(const FileDescriptor&) = delete;
    FileDescriptor& operator=(const FileDescriptor&) = delete;
};
bool PrivateDirectory(int descriptor)
{
    struct stat state {};
    return descriptor >= 0 && fstat(descriptor, &state) == 0 && S_ISDIR(state.st_mode)
        && state.st_uid == geteuid() && (state.st_mode & 0077) == 0;
}
#endif
}

ReconnectReadResult ReadReconnectProfile(const std::string& directory)
{
#if defined(_WIN32)
    return ReadWinProfile(directory);
#elif defined(__unix__) || defined(__APPLE__)
    FileDescriptor parent(open(directory.c_str(), O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC));
    if (parent.value < 0) return {errno == ENOENT ? ReconnectReadStatus::Missing : ReconnectReadStatus::Unavailable, {}};
    if (!PrivateDirectory(parent.value)) return {ReconnectReadStatus::Invalid, {}};
    FileDescriptor file(openat(parent.value, "reconnect.json", O_RDONLY | O_NONBLOCK | O_NOFOLLOW | O_CLOEXEC));
    if (file.value < 0) return {errno == ENOENT ? ReconnectReadStatus::Missing : ReconnectReadStatus::Unavailable, {}};
    struct stat state {};
    if (fstat(file.value, &state) != 0 || !S_ISREG(state.st_mode) || state.st_uid != geteuid()
        || (state.st_mode & 0077) != 0 || state.st_nlink != 1 || state.st_size <= 0 || state.st_size > 4096)
        return {ReconnectReadStatus::Invalid, {}};
    std::string bytes(static_cast<std::size_t>(state.st_size), '\0');
    std::size_t offset = 0;
    while (offset < bytes.size())
    {
        const ssize_t count = read(file.value, bytes.data() + offset, bytes.size() - offset);
        if (count < 0 && errno == EINTR) continue;
        if (count <= 0) return {ReconnectReadStatus::Invalid, {}};
        offset += static_cast<std::size_t>(count);
    }
    try
    {
        const auto record = nlohmann::ordered_json::parse(bytes);
        if (record.at("version").get<int>() != 1) return {ReconnectReadStatus::Invalid, {}};
        ReconnectCredentials credentials {record.at("endpoint").get<std::string>(),
            record.at("server_session").get<std::string>(), record.at("token").get<std::string>()};
        if (!Valid(credentials)) return {ReconnectReadStatus::Invalid, {}};
        return {ReconnectReadStatus::Loaded, std::move(credentials)};
    }
    catch (const std::exception&) { return {ReconnectReadStatus::Invalid, {}}; }
#else
    (void)directory;
    return {ReconnectReadStatus::Unavailable, {}};
#endif
}

bool WriteReconnectProfile(const std::string& directory, const ReconnectCredentials& credentials)
{
    if (!Valid(credentials)) return false;
#if defined(_WIN32)
    return WriteWinProfile(directory, credentials);
#elif defined(__unix__) || defined(__APPLE__)
    std::error_code error;
    std::filesystem::create_directories(directory, error);
    if (error) return false;
    FileDescriptor parent(open(directory.c_str(), O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC));
    struct stat state {};
    if (parent.value < 0 || fstat(parent.value, &state) != 0 || state.st_uid != geteuid()
        || !S_ISDIR(state.st_mode) || fchmod(parent.value, 0700) != 0 || !PrivateDirectory(parent.value)) return false;
    const std::string bytes = nlohmann::ordered_json({{"version", 1}, {"endpoint", credentials.endpoint},
        {"server_session", credentials.serverSession}, {"token", credentials.token}}).dump();
    static std::atomic<unsigned long> serial {0};
    std::string temporary;
    int descriptor = -1;
    for (int attempt = 0; attempt < 32; ++attempt)
    {
        temporary = ".reconnect." + std::to_string(getpid()) + "." + std::to_string(++serial) + ".tmp";
        descriptor = openat(parent.value, temporary.c_str(), O_WRONLY | O_CREAT | O_EXCL | O_NOFOLLOW | O_CLOEXEC, 0600);
        if (descriptor >= 0 || errno != EEXIST) break;
    }
    FileDescriptor file(descriptor);
    if (file.value < 0) return false;
    bool written = true;
    std::size_t offset = 0;
    while (offset < bytes.size())
    {
        const ssize_t count = write(file.value, bytes.data() + offset, bytes.size() - offset);
        if (count < 0 && errno == EINTR) continue;
        if (count <= 0) { written = false; break; }
        offset += static_cast<std::size_t>(count);
    }
    written = written && fsync(file.value) == 0;
    if (written) written = renameat(parent.value, temporary.c_str(), parent.value, "reconnect.json") == 0;
    if (!written) unlinkat(parent.value, temporary.c_str(), 0);
    return written && fsync(parent.value) == 0;
#else
    (void)directory;
    return false;
#endif
}
}
