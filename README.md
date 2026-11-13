# Reflections

## Set up a team workspace

Use a private Git remote with Git LFS enabled. To publish the initial commit to an empty repository, the project owner runs the following from this folder. Replace `<repository-url>` with the actual clone URL and grant teammates write access through the host.

```powershell
git remote add origin <repository-url>
git push -u origin main
```

On each teammate's machine, install Git and Git LFS, then clone into a separate working directory.

```powershell
git lfs install
git clone <repository-url>
cd reflections
git lfs pull
```

The project currently runs on Unreal Engine 5.9.0, changelist `60351404`. Check `Engine/Build/Build.version` in your installation. On Windows, install the Visual Studio C++ game development tools for Unreal, then open `reflections.uproject` and build the project modules when prompted. If the project’s engine association is unfamiliar to your machine, launch the matching `Engine/Binaries/Win64/UnrealEditor.exe` and open `reflections.uproject` from it, or pass the full `.uproject` path on the command line. The GUID in `EngineAssociation` is registered locally. See [Epic’s engine association documentation](https://dev.epicgames.com/documentation/en-us/unreal-engine/managing-game-code-in-unreal-engine).

## Work in parallel

- Start from current `main` and work on a branch for your task. Push the branch and open a pull request when your work is ready to integrate.
- Claim the Blueprints, maps, and other binary assets you plan to edit in your team chat or task tracker. Git cannot merge simultaneous edits to an Unreal package. If your host supports Git LFS locking, you can use `git lfs lock "Content/path/to/asset.uasset"` and release it after the change lands. [Git LFS locking reference](https://github.com/git-lfs/git-lfs/blob/main/docs/man/git-lfs-lock.adoc)
- The project's levels store actors in separate packages. Teammates can edit different actors in the same level. Commit the related files in `Content/__ExternalActors__` and `Content/__ExternalObjects__` with your level changes. Coordinate edits to shared actors and level-wide settings. [One File Per Actor](https://dev.epicgames.com/documentation/en-us/unreal-engine/one-file-per-actor-in-unreal-engine)

## Edit together in Unreal

1. Everyone opens a clean checkout of the same commit using the same Unreal Engine build. Connect all machines to the same LAN or private VPN.
2. The host opens **Multi-User Browser** from the toolbar or **Window → Multi-User Browser**, launches the server, and creates a session. Teammates open the browser and join that session. If discovery fails, configure a static endpoint using the server's private address and port. [Epic’s networking guide](https://dev.epicgames.com/documentation/en-us/unreal-engine/advanced-multi-user-networking-in-unreal-engine)
3. Before leaving, have one person use **Source Control → Persist Session Changes** to write the session changes to their checkout. They review, commit, and push those files. Everyone syncs to the new commit before the next session. [Epic’s Multi-User Editing guide](https://dev.epicgames.com/documentation/en-us/unreal-engine/getting-started-with-multi-user-editing-in-unreal-engine)
