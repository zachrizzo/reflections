#pragma once

#include "CoreMinimal.h"
#include "ReflectionsDigTypes.generated.h"

/** Fixed numbers of the diggable ground. */
namespace ReflectionsDig
{
    /** Distance between two neighbouring cells (sample points). */
    inline constexpr float CellSizeCm = 50.0f;
    /** Cells per chunk along each axis. */
    inline constexpr int32 ChunkCells = 32;
    /** Edge of one chunk along each axis (16 m). */
    inline constexpr float ChunkSizeCm = ChunkCells * CellSizeCm;
    /** Radius of the sphere one dig or fill of the terrain removes or adds. */
    inline constexpr float StampRadiusCm = 100.0f;
    /** Density units per cell of signed distance. */
    inline constexpr int32 DensityPerCell = 64;
    /** Largest density magnitude; density runs from -DensityMax to DensityMax. */
    inline constexpr int8 DensityMax = 127;
    /** Extra cells copied on every side of a chunk for the mesher. */
    inline constexpr int32 SampleBorder = 2;
    inline constexpr uint8 MaterialTopsoil = 0;
    inline constexpr uint8 MaterialBedrock = 255;
    /** Most vertices one chunk piece (one mesh component and its collision) may hold. */
    inline constexpr int32 MaxPieceVertices = 12000;
}

/** Whether a stamp digs ground away or fills it in. */
UENUM(BlueprintType)
enum class EReflectionsDigMode : uint8
{
    Remove,
    Add
};

/** A sphere that digs (Remove) or fills (Add) the ground grid. */
struct FReflectionsDigStamp
{
    FVector Center = FVector::ZeroVector;
    float RadiusCm = ReflectionsDig::StampRadiusCm;
    EReflectionsDigMode Mode = EReflectionsDigMode::Remove;
    /** Material given to cells an Add turns from not solid to solid. */
    uint8 Material = ReflectionsDig::MaterialTopsoil;
};

/**
 * A copy of one chunk's cells plus SampleBorder cells on every side, for the mesher's worker threads.
 * Local coordinates run from -SampleBorder to ChunkCells - 1 + SampleBorder (-2 to 33) on each axis.
 * Arrays are Side^3 long, indexed (X + 2) + (Y + 2) * Side + (Z + 2) * Side * Side: X varies fastest.
 */
struct FReflectionsDigChunkSamples
{
    static constexpr int32 Side = ReflectionsDig::ChunkCells + 2 * ReflectionsDig::SampleBorder;
    static_assert(Side == 36, "A chunk sample copy is 36 cells on a side");

    FIntVector Chunk = FIntVector::ZeroValue;
    /** Position of local cell (0, 0, 0) relative to the grid origin. */
    FVector3f LocalOriginCm = FVector3f::ZeroVector;
    TArray<int8> Density;
    TArray<uint8> Material;

    static int32 IndexOf(int32 X, int32 Y, int32 Z)
    {
        return (X + ReflectionsDig::SampleBorder)
            + (Y + ReflectionsDig::SampleBorder) * Side
            + (Z + ReflectionsDig::SampleBorder) * Side * Side;
    }

    int8 DensityAt(int32 X, int32 Y, int32 Z) const
    {
        return Density[IndexOf(X, Y, Z)];
    }

    uint8 MaterialAt(int32 X, int32 Y, int32 Z) const
    {
        return Material[IndexOf(X, Y, Z)];
    }
};
