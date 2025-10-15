# PLC Bulk Read Optimization Plan

## Current Performance Analysis

### Issues Identified
1. **Sequential Individual Reads**: 51 parameters read one-by-one with 51 separate Modbus TCP requests
2. **Network Overhead**: Each request has ~5-10ms network round-trip time
3. **Total Time**: 250-570ms per collection cycle (target: <100ms)
4. **Timing Violations**: Cannot complete within 1-second target window

### Observed Times (from logs)
```
- 0.247s (247ms) - 51 parameters
- 0.257s (257ms) - 51 parameters  
- 0.301s (301ms) - 51 parameters
- 0.514s (514ms) - 51 parameters
- 0.571s (571ms) - 51 parameters
```

**Average: ~390ms per cycle (51 individual reads)**

## Optimization Strategy

### Phase 1: Implement Bulk Reads (Estimated 5-10x Speedup)

Instead of 51 individual reads, group parameters by address proximity:

**Before:**
```
51 individual reads = 51 × (5-10ms network + 2-5ms PLC processing) = 357-765ms
```

**After (estimated):**
```
3-5 bulk reads = 5 × (5-10ms network + 10-20ms PLC bulk processing) = 75-150ms
```

**Expected speedup: 390ms → 50-100ms (4-8x faster)**

### Implementation Steps

1. **Add bulk read support to RealPLC.read_all_parameters()**
   - Group parameters by Modbus register type (coils vs holding registers)
   - Group parameters by address proximity (within 10 addresses)
   - Use existing `optimize_address_ranges()` method

2. **Optimization parameters:**
   ```python
   max_gap = 10           # Group parameters within 10 addresses
   max_range_size = 50    # Up to 50 registers per bulk read
   ```

3. **Example grouping for typical ALD system:**
   - Coils (binary): Addresses 0-37 → 1-2 bulk reads (~20-40 coils)
   - Holding Registers (floats): Addresses scattered → 2-4 bulk reads

### Phase 2: Cache Optimization Metadata (One-time Setup)

Pre-compute bulk read ranges during initialization:
```python
# During initialize(), after loading parameter metadata:
self._bulk_read_ranges = self._optimize_bulk_reads()
```

This eliminates per-cycle optimization overhead.

### Phase 3: Parallel Reads (Advanced - Optional)

If further speedup needed, read coils and registers in parallel:
```python
# Concurrent execution
coils_task = asyncio.create_task(self._bulk_read_coils(coil_ranges))
regs_task = asyncio.create_task(self._bulk_read_registers(register_ranges))

coil_results, reg_results = await asyncio.gather(coils_task, regs_task)
```

**Additional speedup: 20-30% reduction**

## Expected Performance Gains

| Optimization Level | Read Time | Speedup | Timing Violations |
|-------------------|-----------|---------|-------------------|
| Current (individual) | 250-570ms | 1x | Frequent |
| Phase 1 (bulk reads) | 50-100ms | 4-8x | Rare |
| Phase 2 (cached optimization) | 40-80ms | 6-10x | None |
| Phase 3 (parallel) | 30-60ms | 8-13x | None |

## Risk Assessment

**Low Risk Changes:**
- Phase 1 & 2 use existing, tested bulk read methods
- Fallback to individual reads if bulk fails
- No changes to PLC or Modbus configuration needed

**Testing Plan:**
1. Test bulk reads in simulation mode
2. Verify data accuracy (compare bulk vs individual)
3. Test with real PLC hardware
4. Monitor timing and error rates
5. Add performance metrics logging

## Implementation Priority

**HIGH PRIORITY - Phase 1:**
- Immediate 4-8x speedup
- Eliminates timing violations
- Uses existing proven methods

**MEDIUM PRIORITY - Phase 2:**  
- Additional 20-30% speedup
- Cleaner code
- Reduces per-cycle overhead

**LOW PRIORITY - Phase 3:**
- Incremental gains
- Added complexity
- May not be needed after Phase 1-2

## Code Changes Required

**Primary File:** `src/plc/real_plc.py`
- Method: `read_all_parameters()` - ~50 lines
- Method: `read_all_setpoints()` - ~30 lines
- New method: `_optimize_bulk_reads()` - ~80 lines
- New method: `_execute_bulk_reads()` - ~100 lines

**Total estimated LOC:** ~260 lines

**Estimated dev time:** 2-3 hours
**Testing time:** 1-2 hours
**Total:** Half day effort for 4-8x performance improvement

## Success Metrics

1. **Read time < 100ms** for 51 parameters (currently 250-570ms)
2. **Zero timing violations** in 1-hour continuous operation
3. **100% data accuracy** compared to individual reads
4. **Reduced log noise** - fewer individual parameter logs

## Next Steps

1. Review and approve this plan
2. Implement Phase 1 bulk reads
3. Test in simulation mode
4. Test with real hardware
5. Monitor performance for 24 hours
6. If successful, implement Phase 2






