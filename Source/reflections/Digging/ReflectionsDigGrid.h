#pragma once

#include "CoreMinimal.h"
#include "Digging/ReflectionsDigTypes.h"

/**
 * The diggable ground: a box of cells (sample points 50 cm apart) held per chunk of 32^3 cells,
 * one byte of density (positive is solid) and one byte of material per cell.
 * Cell (x, y, z) sits at OriginCm + (x, y, z) * 50. The floor (z = 0) and the four side walls are
 * bedrock: material 255, never changed by a stamp. Outside the grid the ground keeps its initial
 * density and reads as bedrock. Game thread only; worker threads read FReflectionsDigChunkSamples copies.
 */
class REFLECTIONS_API FReflectionsDigGrid
{
public:
    FReflectionsDigGrid(FIntVector SizeInChunks, FVector OriginCm, float GroundHeightCm);

    FIntVector GetSizeInChunks() const;
    FIntVector GetSizeInCells() const;
    FVector GetOriginCm() const;
    float GetGroundHeightCm() const;

    /** World position of a cell. */
    FVector CellToWorld(FIntVector Cell) const;

    /** Density of a cell; positive is solid. Outside the grid: the initial density for that position. */
    int8 GetDensity(FIntVector Cell) const;

    /** Material of a cell. Outside the grid: bedrock. */
    uint8 GetMaterial(FIntVector Cell) const;

    /**
     * Digs (Remove) or fills (Add) a sphere. Appends, once each, every chunk with a changed cell
     * inside its cell range grown by SampleBorder cells on every side. A radius of 0 or less, a radius
     * that is not finite (infinite or NaN) or a centre that is not finite changes nothing.
     */
    void ApplyStamp(const FReflectionsDigStamp& Stamp, TArray<FIntVector>& OutDirtyChunks);

    /** Copies a chunk's cells plus a SampleBorder border, with the same answers as GetDensity and GetMaterial. */
    void CopyChunkSamples(FIntVector Chunk, FReflectionsDigChunkSamples& Out) const;

private:
    struct FChunkCells
    {
        /** ChunkCells^3 entries, indexed X + Y * 32 + Z * 32 * 32 in chunk-local cells. */
        TArray<int8> Density;
        TArray<uint8> Material;
    };

    bool IsInside(const FIntVector& Cell) const;
    bool IsBedrock(const FIntVector& Cell) const;
    int8 InitialDensity(int32 CellZ) const;
    int32 ChunkIndex(const FIntVector& Chunk) const;

    FIntVector SizeInChunks;
    FIntVector SizeInCells;
    FVector OriginCm;
    float GroundHeightCm;
    TArray<FChunkCells> Chunks;
};
