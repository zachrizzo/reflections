# Gray London

Open `reflections.uproject` with the Unreal Engine 5.9.0 build described in the root README, then open **Content/GrayLondon/Maps/GrayLondon_Geodata** in the editor and press Play. This level is an optional addition: the project's existing startup level, game mode and character are unchanged. Install Git LFS and run `git lfs pull` after checkout to obtain the Unreal content.

Gray London is a geographic gameplay prototype of central London, clipped to roughly a 3.5-mile radius. It includes the Thames, Buckingham Palace, the Tower of London and an outer park and water boundary. Much of the street geometry, building massing, facades and period detail is approximate. Shops generally have no interiors; the world is not a comprehensive historical reconstruction. The source project received local play and streaming tests, but routes, collision, visual details and performance have not been exhaustively tested in this project.

The map uses Unreal's Procedural Content Generation Framework (PCG), enabled by default in the matching engine build. Its World Partition actor and object packages are required alongside the map. Procedural awnings use an original, simplified substitute mesh and existing project-made canvas materials; their locations are illustrative.

For the sources, attribution and known limitations see [GRAY_LONDON_DATA_SOURCES.md](GRAY_LONDON_DATA_SOURCES.md) and [GRAY_LONDON_PERIOD_AUDIT.md](GRAY_LONDON_PERIOD_AUDIT.md). Third-party license texts are included in this directory. Note the documented Albert Memorial source-provenance caveat in the source notes.
