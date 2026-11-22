#include "Digging/ReflectionsDigGrid.h"

#include "CoreMinimal.h"
#include "Digging/ReflectionsDigTypes.h"

namespace
{
    constexpr int32 CellsPerChunk = ReflectionsDig::ChunkCells * ReflectionsDig::ChunkCells * ReflectionsDig::ChunkCells;

    /**
     * Quantise(d) = clamp(round(d / 50 * 64), -127, 127) for a signed distance d in cm.
     * The one rounding rule of the grid: round half away from zero (C's round). Clamping before
     * rounding gives the same result (the bounds are whole numbers) and keeps infinities and NaN defined.
     */
    int8 QuantiseDistanceCm(double DistanceCm)
    {
        const double Scaled = DistanceCm / ReflectionsDig::CellSizeCm * ReflectionsDig::DensityPerCell;
        const double Max = ReflectionsDig::DensityMax;
        return static_cast<int8>(FMath::RoundHalfFromZero(FMath::Clamp(Scaled, -Max, Max)));
    }

    int32 LocalCellIndex(int32 X, int32 Y, int32 Z)
    {
        return X + (Y + Z * ReflectionsDig::ChunkCells) * ReflectionsDig::ChunkCells;
    }

    /** Floor of A / B for B > 0, also for negative A. */
    int32 FloorDiv(int32 A, int32 B)
    {
        return A >= 0 ? A / B : -((-(A + 1)) / B) - 1;
    }

    /** First and last chunk (clamped to the grid) whose cell range grown by SampleBorder holds cell V. */
    void ChunksSeeingCell(int32 V, int32 NumChunks, int32& OutFirst, int32& OutLast)
    {
        // Chunk C sees cells 32C - 2 to 32C + 31 + 2.
        OutFirst = FMath::Max(0, FloorDiv(V - ReflectionsDig::SampleBorder, ReflectionsDig::ChunkCells));
        OutLast = FMath::Min(NumChunks - 1, FloorDiv(V + ReflectionsDig::SampleBorder, ReflectionsDig::ChunkCells));
    }

    /** Cells a stamp may change on one axis: centre +- (radius + 2 cells), clipped to [MinCell, MaxCell]. */
    bool StampAxisRange(double CenterCell, double RadiusCells, int32 MinCell, int32 MaxCell, int32& OutFirst, int32& OutLast)
    {
        if (MinCell > MaxCell)
        {
            return false;
        }
        const double Reach = RadiusCells + 2.0;
        const double First = FMath::Clamp(FMath::FloorToDouble(CenterCell - Reach), static_cast<double>(MinCell), static_cast<double>(MaxCell) + 1.0);
        const double Last = FMath::Clamp(FMath::CeilToDouble(CenterCell + Reach), static_cast<double>(MinCell) - 1.0, static_cast<double>(MaxCell));
        OutFirst = static_cast<int32>(First);
        OutLast = static_cast<int32>(Last);
        return OutFirst <= OutLast;
    }
}

FReflectionsDigGrid::FReflectionsDigGrid(FIntVector InSizeInChunks, FVector InOriginCm, float InGroundHeightCm)
    : SizeInChunks(InSizeInChunks.ComponentMax(FIntVector::ZeroValue))
    , SizeInCells(SizeInChunks * ReflectionsDig::ChunkCells)
    , OriginCm(InOriginCm)
    , GroundHeightCm(InGroundHeightCm)
{
    Chunks.SetNum(SizeInChunks.X * SizeInChunks.Y * SizeInChunks.Z);
    for (int32 ChunkZ = 0; ChunkZ < SizeInChunks.Z; ++ChunkZ)
    {
        for (int32 ChunkY = 0; ChunkY < SizeInChunks.Y; ++ChunkY)
        {
            for (int32 ChunkX = 0; ChunkX < SizeInChunks.X; ++ChunkX)
            {
                const FIntVector Chunk(ChunkX, ChunkY, ChunkZ);
                const FIntVector Base = Chunk * ReflectionsDig::ChunkCells;
                FChunkCells& Cells = Chunks[ChunkIndex(Chunk)];
                Cells.Density.SetNumUninitialized(CellsPerChunk);
                Cells.Material.SetNumUninitialized(CellsPerChunk);
                for (int32 Z = 0; Z < ReflectionsDig::ChunkCells; ++Z)
                {
                    const int8 Density = InitialDensity(Base.Z + Z);
                    for (int32 Y = 0; Y < ReflectionsDig::ChunkCells; ++Y)
                    {
                        for (int32 X = 0; X < ReflectionsDig::ChunkCells; ++X)
                        {
                            const int32 Index = LocalCellIndex(X, Y, Z);
                            Cells.Density[Index] = Density;
                            Cells.Material[Index] = IsBedrock(Base + FIntVector(X, Y, Z)) ? ReflectionsDig::MaterialBedrock : ReflectionsDig::MaterialTopsoil;
                        }
                    }
                }
            }
        }
    }
}

FIntVector FReflectionsDigGrid::GetSizeInChunks() const
{
    return SizeInChunks;
}

FIntVector FReflectionsDigGrid::GetSizeInCells() const
{
    return SizeInCells;
}

FVector FReflectionsDigGrid::GetOriginCm() const
{
    return OriginCm;
}

float FReflectionsDigGrid::GetGroundHeightCm() const
{
    return GroundHeightCm;
}

FVector FReflectionsDigGrid::CellToWorld(FIntVector Cell) const
{
    return OriginCm + FVector(Cell) * ReflectionsDig::CellSizeCm;
}

int8 FReflectionsDigGrid::GetDensity(FIntVector Cell) const
{
    if (!IsInside(Cell))
    {
        return InitialDensity(Cell.Z);
    }
    const FIntVector Chunk(Cell.X / ReflectionsDig::ChunkCells, Cell.Y / ReflectionsDig::ChunkCells, Cell.Z / ReflectionsDig::ChunkCells);
    return Chunks[ChunkIndex(Chunk)].Density[LocalCellIndex(Cell.X % ReflectionsDig::ChunkCells, Cell.Y % ReflectionsDig::ChunkCells, Cell.Z % ReflectionsDig::ChunkCells)];
}

uint8 FReflectionsDigGrid::GetMaterial(FIntVector Cell) const
{
    if (!IsInside(Cell))
    {
        return ReflectionsDig::MaterialBedrock;
    }
    const FIntVector Chunk(Cell.X / ReflectionsDig::ChunkCells, Cell.Y / ReflectionsDig::ChunkCells, Cell.Z / ReflectionsDig::ChunkCells);
    return Chunks[ChunkIndex(Chunk)].Material[LocalCellIndex(Cell.X % ReflectionsDig::ChunkCells, Cell.Y % ReflectionsDig::ChunkCells, Cell.Z % ReflectionsDig::ChunkCells)];
}

void FReflectionsDigGrid::ApplyStamp(const FReflectionsDigStamp& Stamp, TArray<FIntVector>& OutDirtyChunks)
{
    const double RadiusCm = Stamp.RadiusCm;
    if (!(RadiusCm > 0.0) || !FMath::IsFinite(RadiusCm) || !FMath::IsFinite(Stamp.Center.X) || !FMath::IsFinite(Stamp.Center.Y) || !FMath::IsFinite(Stamp.Center.Z))
    {
        return;
    }

    // Only non-bedrock cells can change: x and y from 1 to max - 1, z from 1 up.
    const FVector CenterCells = (Stamp.Center - OriginCm) / ReflectionsDig::CellSizeCm;
    const double RadiusCells = RadiusCm / ReflectionsDig::CellSizeCm;
    int32 FirstX, LastX, FirstY, LastY, FirstZ, LastZ;
    if (!StampAxisRange(CenterCells.X, RadiusCells, 1, SizeInCells.X - 2, FirstX, LastX)
        || !StampAxisRange(CenterCells.Y, RadiusCells, 1, SizeInCells.Y - 2, FirstY, LastY)
        || !StampAxisRange(CenterCells.Z, RadiusCells, 1, SizeInCells.Z - 1, FirstZ, LastZ))
    {
        return;
    }

    const bool bRemove = Stamp.Mode == EReflectionsDigMode::Remove;
    TArray<bool> ChunkDirty;
    bool bAnyChanged = false;

    for (int32 Z = FirstZ; Z <= LastZ; ++Z)
    {
        for (int32 Y = FirstY; Y <= LastY; ++Y)
        {
            for (int32 X = FirstX; X <= LastX; ++X)
            {
                const FIntVector Cell(X, Y, Z);
                const double DistanceCm = FVector::Dist(CellToWorld(Cell), Stamp.Center);
                const FIntVector Chunk(X / ReflectionsDig::ChunkCells, Y / ReflectionsDig::ChunkCells, Z / ReflectionsDig::ChunkCells);
                FChunkCells& Cells = Chunks[ChunkIndex(Chunk)];
                const int32 Index = LocalCellIndex(X % ReflectionsDig::ChunkCells, Y % ReflectionsDig::ChunkCells, Z % ReflectionsDig::ChunkCells);
                const int8 Old = Cells.Density[Index];

                if (bRemove)
                {
                    const int8 New = QuantiseDistanceCm(DistanceCm - RadiusCm);
                    if (New >= Old)
                    {
                        continue;
                    }
                    Cells.Density[Index] = New;
                }
                else
                {
                    const int8 New = QuantiseDistanceCm(RadiusCm - DistanceCm);
                    if (New <= Old)
                    {
                        continue;
                    }
                    Cells.Density[Index] = New;
                    if (Old <= 0 && New > 0)
                    {
                        Cells.Material[Index] = Stamp.Material;
                    }
                }

                if (!bAnyChanged)
                {
                    bAnyChanged = true;
                    ChunkDirty.SetNumZeroed(Chunks.Num());
                }
                int32 FirstChunkX, LastChunkX, FirstChunkY, LastChunkY, FirstChunkZ, LastChunkZ;
                ChunksSeeingCell(X, SizeInChunks.X, FirstChunkX, LastChunkX);
                ChunksSeeingCell(Y, SizeInChunks.Y, FirstChunkY, LastChunkY);
                ChunksSeeingCell(Z, SizeInChunks.Z, FirstChunkZ, LastChunkZ);
                for (int32 ChunkZ = FirstChunkZ; ChunkZ <= LastChunkZ; ++ChunkZ)
                {
                    for (int32 ChunkY = FirstChunkY; ChunkY <= LastChunkY; ++ChunkY)
                    {
                        for (int32 ChunkX = FirstChunkX; ChunkX <= LastChunkX; ++ChunkX)
                        {
                            ChunkDirty[ChunkIndex(FIntVector(ChunkX, ChunkY, ChunkZ))] = true;
                        }
                    }
                }
            }
        }
    }

    if (!bAnyChanged)
    {
        return;
    }
    for (int32 ChunkZ = 0; ChunkZ < SizeInChunks.Z; ++ChunkZ)
    {
        for (int32 ChunkY = 0; ChunkY < SizeInChunks.Y; ++ChunkY)
        {
            for (int32 ChunkX = 0; ChunkX < SizeInChunks.X; ++ChunkX)
            {
                const FIntVector Chunk(ChunkX, ChunkY, ChunkZ);
                if (ChunkDirty[ChunkIndex(Chunk)])
                {
                    OutDirtyChunks.AddUnique(Chunk);
                }
            }
        }
    }
}

void FReflectionsDigGrid::CopyChunkSamples(FIntVector Chunk, FReflectionsDigChunkSamples& Out) const
{
    constexpr int32 Side = FReflectionsDigChunkSamples::Side;
    constexpr int32 Border = ReflectionsDig::SampleBorder;
    constexpr int32 Cells = ReflectionsDig::ChunkCells;
    const FIntVector Base = Chunk * Cells;
    Out.Chunk = Chunk;
    Out.LocalOriginCm = FVector3f(Base) * ReflectionsDig::CellSizeCm;
    Out.Density.SetNumUninitialized(Side * Side * Side);
    Out.Material.SetNumUninitialized(Side * Side * Side);
    int8* const OutDensity = Out.Density.GetData();
    uint8* const OutMaterial = Out.Material.GetData();

    // Row by row along X: runs inside the grid are copied from each chunk's storage (rows are contiguous in X
    // there too); cells outside the grid get what GetDensity and GetMaterial give them (initial density, bedrock).
    for (int32 Z = -Border; Z < Cells + Border; ++Z)
    {
        const int32 CellZ = Base.Z + Z;
        const int8 OutsideDensity = InitialDensity(CellZ);
        for (int32 Y = -Border; Y < Cells + Border; ++Y)
        {
            const int32 CellY = Base.Y + Y;
            const int32 RowStart = FReflectionsDigChunkSamples::IndexOf(-Border, Y, Z);
            const bool bRowInGrid = CellY >= 0 && CellY < SizeInCells.Y && CellZ >= 0 && CellZ < SizeInCells.Z;
            if (!bRowInGrid)
            {
                FMemory::Memset(OutDensity + RowStart, static_cast<uint8>(OutsideDensity), Side);
                FMemory::Memset(OutMaterial + RowStart, ReflectionsDig::MaterialBedrock, Side);
                continue;
            }
            for (int32 X = -Border; X < Cells + Border;)
            {
                const int32 CellX = Base.X + X;
                const int32 OutIndex = RowStart + X + Border;
                if (CellX < 0 || CellX >= SizeInCells.X)
                {
                    OutDensity[OutIndex] = OutsideDensity;
                    OutMaterial[OutIndex] = ReflectionsDig::MaterialBedrock;
                    ++X;
                    continue;
                }
                const int32 LocalX = CellX % Cells;
                const int32 Run = FMath::Min3(Cells - LocalX, Cells + Border - X, SizeInCells.X - CellX);
                const FChunkCells& Source = Chunks[ChunkIndex(FIntVector(CellX / Cells, CellY / Cells, CellZ / Cells))];
                const int32 SourceIndex = LocalCellIndex(LocalX, CellY % Cells, CellZ % Cells);
                FMemory::Memcpy(OutDensity + OutIndex, Source.Density.GetData() + SourceIndex, Run);
                FMemory::Memcpy(OutMaterial + OutIndex, Source.Material.GetData() + SourceIndex, Run);
                X += Run;
            }
        }
    }
}

bool FReflectionsDigGrid::IsInside(const FIntVector& Cell) const
{
    return Cell.X >= 0 && Cell.Y >= 0 && Cell.Z >= 0
        && Cell.X < SizeInCells.X && Cell.Y < SizeInCells.Y && Cell.Z < SizeInCells.Z;
}

bool FReflectionsDigGrid::IsBedrock(const FIntVector& Cell) const
{
    return Cell.Z == 0 || Cell.X == 0 || Cell.Y == 0 || Cell.X == SizeInCells.X - 1 || Cell.Y == SizeInCells.Y - 1;
}

int8 FReflectionsDigGrid::InitialDensity(int32 CellZ) const
{
    const double CellWorldZ = OriginCm.Z + static_cast<double>(CellZ) * ReflectionsDig::CellSizeCm;
    return QuantiseDistanceCm(static_cast<double>(GroundHeightCm) - CellWorldZ);
}

int32 FReflectionsDigGrid::ChunkIndex(const FIntVector& Chunk) const
{
    return Chunk.X + (Chunk.Y + Chunk.Z * SizeInChunks.Y) * SizeInChunks.X;
}
