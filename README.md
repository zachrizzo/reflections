# Reflections

## Set up a team workspace

The owner grants teammates access to the [private GitHub repository](https://github.com/zachrizzo/reflections). On each teammate's machine, install Git and Git LFS, then clone into a separate working directory.

```powershell
git lfs install
git clone https://github.com/zachrizzo/reflections.git
cd reflections
git lfs pull
```

The project currently runs on Unreal Engine 5.9.0 Preview, changelist `60351404`. Check `Engine/Build/Build.version` in your installation. On Windows, install the Visual Studio C++ game development tools for Unreal, then open `reflections.uproject` and build the project modules when prompted. If the project’s engine association is unfamiliar to your machine, launch the matching `Engine/Binaries/Win64/UnrealEditor.exe` and open `reflections.uproject` from it, or pass the full `.uproject` path on the command line. The GUID in `EngineAssociation` is registered locally. [Epic’s engine association documentation](https://dev.epicgames.com/documentation/en-us/unreal-engine/managing-game-code-in-unreal-engine)

## Work in parallel

- Start from current `main` and work on a branch for your task. Push the branch and open a pull request when your work is ready to integrate.
- Claim the Blueprints, maps, and other binary assets you plan to edit in your team chat or task tracker. Git cannot merge simultaneous edits to an Unreal package. If your host supports Git LFS locking, you can use `git lfs lock "Content/path/to/asset.uasset"` and release it after the change lands. [Git LFS locking reference](https://github.com/git-lfs/git-lfs/blob/main/docs/man/git-lfs-lock.adoc)
- The project's levels store actors in separate packages. Teammates can edit different actors in the same level. Commit the related files in `Content/__ExternalActors__` and `Content/__ExternalObjects__` with your level changes. Coordinate edits to shared actors and level-wide settings. [One File Per Actor](https://dev.epicgames.com/documentation/en-us/unreal-engine/one-file-per-actor-in-unreal-engine)

## Edit together in Unreal

1. Everyone opens a clean checkout of the same commit using the same Unreal Engine build. Connect all machines to the same LAN or private VPN. On first launch, Unreal may write hardware defaults and generate an Android File Server token in `Config/DefaultEngine.ini`. Review `git diff -- Config/DefaultEngine.ini` and discard those generated changes before starting a session. Keep intentional project settings in your normal commits.
2. From the project root, the Windows host runs `.\Scripts\Start-MultiUserServer.ps1 -ListenAddress <host-LAN-IP>` to start **Reflections LAN** on UDP port `55059`. Substitute the host's current IPv4 address from `ipconfig`. The server's logs and session data are under `Saved/MultiUserServer`.
3. Open **Multi-User Browser** from the toolbar or **Window → Multi-User Browser**. The host creates a session on **Reflections LAN** and teammates join it. If discovery fails, add `<host-LAN-IP>:55059` in **Project Settings → Plugins → UDP Messaging → Transport → Static Endpoints**. Keep the host PC awake during the session. [Epic’s networking guide](https://dev.epicgames.com/documentation/en-us/unreal-engine/advanced-multi-user-networking-in-unreal-engine)
4. Before leaving, have one person use **Source Control → Persist Session Changes** to write the session changes to their checkout. They review, commit, and push those files. Everyone syncs to the new commit before the next session. [Epic’s Multi-User Editing guide](https://dev.epicgames.com/documentation/en-us/unreal-engine/getting-started-with-multi-user-editing-in-unreal-engine)
