# Building the Windows guest client

There is no verified Windows package yet. This project currently has a working Linux build and a prepared Windows build path. The Linux workstation's Unreal 5.8.2 installation contains no Win64 editor, Windows batch tools or Windows SDK. The normal next step is to build the same project on a Windows x64 machine.

**Only the build machine needs Unreal Engine, Visual Studio and Python. Your friend running the finished game does not need any of them.** They will receive the complete packaged folder, with the runtime prerequisites provided by Unreal's packaging step. Neither player needs Vercel: this is a native game with a listen server running on the host player's computer.

## Build machine

Use Windows x64 with the Windows installation of **Unreal Engine 5.8.2**, including Win64 target support. Install a supported Visual Studio C++ development environment, the Windows SDK and Python 3.9 or newer. CMake is needed for the standalone reconnect tests below. Do not change the engine version to make an incompatible client build.

Epic lists Visual Studio 2022 17.14+ and Visual Studio 2026 18.0+ for UE 5.8. Its setup instructions specify the C++ workloads and Windows SDK requirements. Use an updated supported compiler; the installed engine additionally rejects particular older compiler patch versions. Turnkey and UnrealBuildTool perform the actual local toolchain checks. See [Epic's Visual Studio setup](https://dev.epicgames.com/documentation/en-us/unreal-engine/setting-up-visual-studio-development-environment-for-cplusplus-projects-in-unreal-engine) and [engine installation instructions](https://dev.epicgames.com/documentation/en-us/unreal-engine/install-unreal-engine).

The installed Linux toolchain is not a Windows compiler. Epic's documented Linux cross-compilation workflow runs **on Windows to build Linux**; it is not a Linux-to-Windows packaging procedure. See [Linux development requirements](https://dev.epicgames.com/documentation/unreal-engine/linux-development-requirements-for-unreal-engine). Locally, `MicrosoftPlatformSDK.GetInstalledSDKVersion` returns no Windows SDK on a non-Windows host (`Engine/Source/Programs/UnrealBuildTool/Platform/Windows/MicrosoftPlatformSDK.cs`).

No paid service, virtual machine or additional toolchain has been installed by this work.

## Keep host and guest on the same inputs

Use one frozen source/content export for both builds. The Windows helper fingerprints the engine version/changelist, project file, and every file under `game/OldWest/Source`, `Config` and `Content`, including the runtime card catalog. It refuses a Windows build if that fingerprint differs from the supplied Linux input snapshot, and checks it again after packaging.

The existing installed Linux review build must not automatically be paired with a new Windows build from today's edited project. Both packages need to be built from the same frozen inputs. Matching card names alone does not prove protocol or runtime compatibility.

From the repository root on Linux, after the project is frozen and before building the paired Linux host:

```bash
python3 scripts/package_oldwest_windows.py \
  --engine ~/Applications/UnrealEngine-5.8.2 \
  --snapshot-output /tmp/oldwest-paired-inputs.json
```

Retain that snapshot with the Linux build evidence. Capture another snapshot after the Linux build and verify that its `input_fingerprint` is identical. The Linux package builder remains `scripts/package_oldwest.py`; this Windows helper does not build the Linux host.

Copy the project to the Windows build machine with its directory layout intact:

- `game/OldWest/OldWest.uproject`, `Source`, `Config` and `Content`.
- `scripts`, `game/data`, `game/tests/reconnect`, `game/PLAYER_GUIDE.md`, `game/REMOTE_PLAY.md` and `game/THIRD_PARTY_NOTICES.md`.
- `art/audio/audio-manifest.json`, used by the dynamic asset inventory, and the captured `oldwest-paired-inputs.json`.

Preserve file bytes, including text line endings. A transfer that converts LF to CRLF changes the fingerprint. Omit generated Linux `Binaries`, `Intermediate`, `Saved` and `DerivedDataCache` directories. Keep build inputs and the output folder separate; use paths without shell metacharacters such as `&`, `%`, `!` or `^`.

## Run the Windows build

Open PowerShell in the copied repository. Adjust the engine and output paths. The engine folder name is arbitrary, but its `Build.version` must report 5.8.2 and match the snapshot's engine identity.

First run the read-only preflight:

```powershell
py -3 -X utf8 scripts\package_oldwest_windows.py `
  --engine "C:\Program Files\Epic Games\UE_5.8" `
  --expected-inputs "C:\OldWestInputs\oldwest-paired-inputs.json" `
  --output "D:\OldWestBuilds\windows-review-001"
```

Then use the same arguments with `--build`:

```powershell
py -3 -X utf8 scripts\package_oldwest_windows.py `
  --engine "C:\Program Files\Epic Games\UE_5.8" `
  --expected-inputs "C:\OldWestInputs\oldwest-paired-inputs.json" `
  --output "D:\OldWestBuilds\windows-review-001" `
  --build
```

The output directory must be new. The helper runs Turnkey SDK verification, builds the Win64 Development editor module, then runs BuildCookRun for the Win64 Development game with the WaterDepotV2 map, Pak/IoStore containers and prerequisites. Full tool output is retained under the output directory's `logs` folder. It neither installs missing SDKs nor launches the game. This follows Unreal's [build, cook and stage packaging workflow](https://dev.epicgames.com/documentation/unreal-engine/packaging-your-project).

The helper verifies a Windows x64 PE game executable, the generated bootstrap, required container types and an unchanged input fingerprint. It writes `oldwest-windows-package-manifest.json` with artifact hashes and `runtime_validation_pending: true`. A successful build is not a runtime or network certification. Inspection of cooked container membership and the extracted catalog is still pending; the script currently verifies the source asset inventory and presence of the resulting containers.

## Test reconnect storage on Windows

The Windows implementation uses per-user DPAPI encryption, a protected DACL granting the current account access, exclusive temporary files, a flushed write and same-directory replacement. It rejects reparse points and multiply linked credential files. The POSIX implementation retains its existing permissions and file operations.

Run these commands on the Windows build machine, with a CMake version supporting the installed Visual Studio generator:

```powershell
cmake -S game/tests/reconnect -B build/reconnect-win64 -A x64
cmake --build build/reconnect-win64 --config Release
ctest --test-dir build/reconnect-win64 -C Release --output-on-failure
```

The Windows tests exercise Unicode paths, save/read/replace, ACL hardening, encrypted contents, malformed data, temporary-file collisions and hard links. Symlink checks require Windows to permit symlink creation; the test prints `symbolic_link_checks: false` when that portion could not run. A passing result with that flag does not cover symlink rejection on that machine. A separate second-account negative check and the actual game's restart/reconnect flow remain necessary.

The game stores Windows reconnect data as `reconnect.bin` beneath its per-user `OldWest/Profiles/<profile>` settings directory. Linux continues to use its existing `reconnect.json`. Reconnect credentials are private local state and are not included in the package or input snapshot.

## Give the friend the package and connect

The script prints the actual package root beneath `archive`. Zip or copy **that entire root**, including its `Engine` and `OldWest` directories, `OldWestGame.exe`, `launch_oldwest.bat`, prerequisites and support documents. Copying only the executable will not work. On the friend's Windows computer, extract the folder and launch `OldWestGame.exe` or `launch_oldwest.bat`. If the bootstrap requests a runtime prerequisite, use the prerequisite provided with the package; Unreal Editor and Visual Studio are unnecessary for playing.

For an initial LAN test, start the matching Linux host, choose **Host A Match**, and leave it running. On Windows, choose **Join** and enter `192.0.2.16:7777` while that remains the host's actual LAN address. Host and guest must use the same paired build inputs. The Windows machine must be able to reach the host's UDP game port, normally 7777.

For different households, the private `192.168.*` address alone is insufficient. Use a reachable private-network/VPN address or an Internet endpoint with router/firewall forwarding for UDP 7777 to the host. The host must remain running throughout the match. No actual Windows-to-Linux or household-to-household connection has been verified yet. See [REMOTE_PLAY.md](REMOTE_PLAY.md) for the existing native hosting model.

## Verification still required

The Linux reconnect regression passed all 27 checks after the platform branch was added. This does **not** execute Windows code. Before calling the Windows client ready, retain evidence of:

- A successful Win64 compile/cook, cooked asset/catalog inspection and all final package hashes.
- The Windows ACL/DPAPI tests above, including the scope of any skipped link checks, and a separate account being unable to read/reuse the first account's stored credentials.
- Native Windows startup, graphics and controls on the friend's hardware. The current rendering relies on Unreal features whose Windows GPU, driver and shader-model requirements must be checked against [Epic's hardware requirements](https://dev.epicgames.com/documentation/unreal-engine/hardware-and-software-specifications-for-unreal-engine). The Windows rendering configuration has not been validated here.
- A real Windows guest versus the matching Linux host: both rulesets, hidden-hand isolation, full match, rematch and reconnect after closing/restarting the guest while the host continues running.
- A real remote Internet/private-VPN test from the friend's network, including reconnect. Tests involving two Linux processes on one workstation do not establish this.

Build inputs, game binaries and networking must be validated together. The Windows build script, Win32 persistence branch and Windows-specific tests are prepared; native Windows execution remains pending.
