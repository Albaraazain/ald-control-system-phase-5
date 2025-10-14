# Cursor AI Prompt: Migrate Legacy Table References to Wide Table

## Context

We've migrated from a **narrow table format** to a **wide table format** for parameter data storage:

### OLD (Legacy - DO NOT USE):
- **Table**: `parameter_value_history`
- **Format**: 51 rows per timestamp (normalized)
- **Columns**: `parameter_id`, `value`, `timestamp`
- **Query Pattern**: Requires WHERE IN clause or 51 JOINs

### NEW (Current - USE THIS):
- **Table**: `parameter_readings`
- **Format**: 1 row per timestamp (denormalized/wide)
- **Columns**: `timestamp`, `param_0d444e71`, `param_2b2e7952`, ... (51 parameter columns)
- **Query Pattern**: Simple single-row access

## Your Mission

**Investigate EVERY reference to `parameter_value_history` in the codebase and migrate to use `parameter_readings` wide table format.**

Focus areas:
1. ✅ **recipe-monitor-app/** - TypeScript/React dashboard application
2. ✅ **Frontend queries** - Any Supabase queries
3. ✅ **TypeScript types** - Database type definitions
4. ✅ **API endpoints** - Any backend APIs querying parameter data
5. ✅ **Dashboard components** - Charts, graphs, real-time displays
6. ✅ **Documentation** - Update any docs referencing the old table

## Investigation Steps

### Step 1: Deep Search for Legacy Table References

Search for ALL occurrences of:
```bash
# Primary searches
grep -r "parameter_value_history" .
grep -r "parameterValueHistory" .
grep -r "parameter-value-history" .

# TypeScript type references
grep -r "ParameterValueHistory" .
grep -r "parameter_value" . --include="*.ts" --include="*.tsx"

# Supabase query references
grep -r "\.from('parameter" . --include="*.ts" --include="*.tsx"
grep -r "supabase.*parameter" . --include="*.ts" --include="*.tsx"

# SQL query references
grep -r "SELECT.*parameter.*value" . --include="*.ts" --include="*.tsx"
```

### Step 2: Analyze Each Reference

For EACH file found, determine:
1. **What is it doing?** (query, display, type definition)
2. **What data does it need?** (specific parameters or all 51)
3. **How is it structured?** (component, hook, API call)
4. **What needs to change?** (query structure, types, display logic)

### Step 3: Schema Understanding

#### Parameter ID to Column Mapping

Reference file: `src/parameter_wide_table_mapping.py`

**51 parameters mapped as**:
```typescript
// Example mappings (see full list in parameter_wide_table_mapping.py)
'0d444e71-9767-4956-af7b-787bfa79d080' → 'param_0d444e71'  // float
'2b2e7952-c68e-40eb-ab67-d182fc460821' → 'param_2b2e7952'  // float
'35969620-6843-4130-8eca-d6b62dc74dbf' → 'param_35969620'  // float
'1583a79b-079b-4b03-9c64-53b7cfa9d142' → 'param_1583a79b'  // binary
'264bfd7f-6076-4b37-be09-dce51bd250c7' → 'param_264bfd7f'  // binary
...
```

**Wide Table Structure**:
```sql
CREATE TABLE parameter_readings (
  timestamp timestamptz NOT NULL PRIMARY KEY,
  -- 51 parameter columns
  param_0d444e71 float8,
  param_2b2e7952 float8,
  param_35969620 float8,
  ... (48 more columns)
  created_at timestamptz NOT NULL DEFAULT now()
);
```

## Migration Patterns

### Pattern 1: TypeScript Type Definitions

**BEFORE (Legacy)**:
```typescript
// ❌ OLD - DO NOT USE
interface ParameterValueHistory {
  parameter_id: string;
  value: number;
  timestamp: string;
}

type ParameterData = {
  parameter_id: string;
  value: number;
  timestamp: Date;
}[];
```

**AFTER (Wide Table)**:
```typescript
// ✅ NEW - USE THIS
interface ParameterReading {
  timestamp: string;
  param_0d444e71?: number;
  param_2b2e7952?: number;
  param_35969620?: number;
  param_4567ba45?: number;
  param_500c0329?: number;
  param_62c28aac?: number;
  param_8fe19753?: number;
  param_b6433c16?: number;
  param_dcea6a6e?: number;
  param_e00b0f66?: number;
  // ... all 51 parameters as optional (some may be null)
  param_1583a79b?: number;
  param_264bfd7f?: number;
  // ... remaining parameters
  created_at: string;
}

// For time-series data
type ParameterTimeSeries = ParameterReading[];
```

### Pattern 2: Supabase Queries

**BEFORE (Legacy - Complex)**:
```typescript
// ❌ OLD - Requires 51 rows, complex filtering
const { data, error } = await supabase
  .from('parameter_value_history')
  .select('*')
  .in('parameter_id', [
    '0d444e71-9767-4956-af7b-787bfa79d080',
    '2b2e7952-c68e-40eb-ab67-d182fc460821',
    // ... 49 more IDs
  ])
  .gte('timestamp', startTime)
  .lte('timestamp', endTime)
  .order('timestamp', { ascending: true });

// Then need to pivot/transform the data:
const pivoted = data.reduce((acc, row) => {
  if (!acc[row.timestamp]) {
    acc[row.timestamp] = { timestamp: row.timestamp };
  }
  acc[row.timestamp][row.parameter_id] = row.value;
  return acc;
}, {});
```

**AFTER (Wide Table - Simple)**:
```typescript
// ✅ NEW - Single row per timestamp, no pivoting needed!
const { data, error } = await supabase
  .from('parameter_readings')
  .select('*')  // or select specific columns: 'timestamp, param_0d444e71, param_2b2e7952'
  .gte('timestamp', startTime)
  .lte('timestamp', endTime)
  .order('timestamp', { ascending: true });

// Data is already in the right format!
// data = [
//   { timestamp: '2025-10-14T10:00:00Z', param_0d444e71: 25.3, param_2b2e7952: 10.5, ... },
//   { timestamp: '2025-10-14T10:00:01Z', param_0d444e71: 25.4, param_2b2e7952: 10.6, ... },
// ]
```

### Pattern 3: Real-Time Subscriptions

**BEFORE (Legacy)**:
```typescript
// ❌ OLD
const subscription = supabase
  .channel('parameter_changes')
  .on(
    'postgres_changes',
    {
      event: 'INSERT',
      schema: 'public',
      table: 'parameter_value_history',
    },
    (payload) => {
      // Need to aggregate 51 separate inserts
      handleParameterUpdate(payload.new);
    }
  )
  .subscribe();
```

**AFTER (Wide Table)**:
```typescript
// ✅ NEW - Single insert event with all parameters!
const subscription = supabase
  .channel('parameter_readings')
  .on(
    'postgres_changes',
    {
      event: 'INSERT',
      schema: 'public',
      table: 'parameter_readings',
    },
    (payload) => {
      // All 51 parameters in one event!
      const reading = payload.new as ParameterReading;
      handleCompleteReading(reading);
    }
  )
  .subscribe();
```

### Pattern 4: Chart/Graph Data Formatting

**BEFORE (Legacy)**:
```typescript
// ❌ OLD - Complex data transformation
const formatChartData = (data: ParameterValueHistory[]) => {
  // Group by timestamp
  const byTimestamp = data.reduce((acc, row) => {
    if (!acc[row.timestamp]) {
      acc[row.timestamp] = {};
    }
    acc[row.timestamp][row.parameter_id] = row.value;
    return acc;
  }, {} as Record<string, Record<string, number>>);
  
  // Convert to chart format
  return Object.entries(byTimestamp).map(([timestamp, params]) => ({
    x: new Date(timestamp),
    temperature: params['0d444e71-9767-4956-af7b-787bfa79d080'],
    pressure: params['2b2e7952-c68e-40eb-ab67-d182fc460821'],
    // ... map all parameters
  }));
};
```

**AFTER (Wide Table)**:
```typescript
// ✅ NEW - Direct mapping, no transformation!
const formatChartData = (data: ParameterReading[]) => {
  return data.map(reading => ({
    x: new Date(reading.timestamp),
    temperature: reading.param_0d444e71,  // Direct access!
    pressure: reading.param_2b2e7952,     // No lookup needed!
    flow: reading.param_35969620,
    // ... direct field access
  }));
};
```

### Pattern 5: Dashboard Display Components

**BEFORE (Legacy)**:
```typescript
// ❌ OLD - Complex filtering and grouping
function ParameterDisplay() {
  const [parameters, setParameters] = useState<ParameterValueHistory[]>([]);
  
  useEffect(() => {
    const fetchData = async () => {
      const { data } = await supabase
        .from('parameter_value_history')
        .select('*')
        .in('parameter_id', parameterIds)
        .order('timestamp', { ascending: false })
        .limit(51); // Get latest reading (51 rows)
      
      // Group by timestamp to get latest complete reading
      const latest = data?.filter(row => 
        row.timestamp === data[0].timestamp
      );
      
      setParameters(latest || []);
    };
    
    fetchData();
  }, []);
  
  // Need to find specific parameter in array
  const temperature = parameters.find(
    p => p.parameter_id === '0d444e71-9767-4956-af7b-787bfa79d080'
  )?.value;
  
  return <div>Temperature: {temperature}°C</div>;
}
```

**AFTER (Wide Table)**:
```typescript
// ✅ NEW - Simple and direct!
function ParameterDisplay() {
  const [reading, setReading] = useState<ParameterReading | null>(null);
  
  useEffect(() => {
    const fetchData = async () => {
      const { data } = await supabase
        .from('parameter_readings')
        .select('*')
        .order('timestamp', { ascending: false })
        .limit(1); // Get latest reading (just 1 row!)
      
      setReading(data?.[0] || null);
    };
    
    fetchData();
  }, []);
  
  // Direct field access!
  return <div>Temperature: {reading?.param_0d444e71}°C</div>;
}
```

## Specific Files to Check

Based on project structure, investigate these priority files:

### High Priority - recipe-monitor-app/
```
recipe-monitor-app/lib/types/database.ts        # TypeScript types
recipe-monitor-app/lib/types/dashboard.ts       # Dashboard types
recipe-monitor-app/components/**/*.tsx          # React components
recipe-monitor-app/hooks/**/*.ts                # Custom hooks
recipe-monitor-app/lib/api/**/*.ts              # API calls
recipe-monitor-app/lib/supabase/**/*.ts         # Supabase client
```

### Medium Priority - Backend
```
src/**/*.py                                      # Python backend
tests/**/*.py                                    # Test files
docs/**/*.md                                     # Documentation
```

### Low Priority - Legacy/Archive
```
Any archived or deprecated files
```

## Migration Checklist

For EACH file with legacy table references:

### 1. TypeScript Types
- [ ] Update interface definitions
- [ ] Change from `parameter_id`/`value` to wide format
- [ ] Add all 51 parameter columns as optional fields
- [ ] Update type exports

### 2. Supabase Queries
- [ ] Change `.from('parameter_value_history')` to `.from('parameter_readings')`
- [ ] Remove `.in('parameter_id', [...])` filters
- [ ] Simplify `.select()` - no need for parameter filtering
- [ ] Update `.order()` - single row ordering is simpler
- [ ] Remove data pivoting/transformation logic

### 3. Real-Time Subscriptions
- [ ] Update table name in subscription
- [ ] Update payload handling (now gets all 51 params at once)
- [ ] Remove aggregation logic

### 4. Data Display Components
- [ ] Update state types
- [ ] Simplify data fetching (1 row vs 51 rows)
- [ ] Change from array filtering to direct field access
- [ ] Update prop types

### 5. Chart Components
- [ ] Remove data transformation logic
- [ ] Update data mapping to use direct field access
- [ ] Simplify data series generation

### 6. API Endpoints (if any)
- [ ] Update query logic
- [ ] Update response types
- [ ] Remove data pivoting

### 7. Tests
- [ ] Update test data fixtures
- [ ] Update mock data to use wide format
- [ ] Update assertions

### 8. Documentation
- [ ] Update API docs
- [ ] Update schema docs
- [ ] Update integration guides

## Testing Requirements

After migration, verify:

### 1. Functionality Tests
```bash
# Run all tests
npm test  # or yarn test in recipe-monitor-app/

# Check for TypeScript errors
npm run type-check

# Check for linting issues
npm run lint
```

### 2. Manual Testing
- [ ] Dashboard loads without errors
- [ ] Real-time updates work
- [ ] Charts display correctly
- [ ] All 51 parameters visible
- [ ] Historical data queries work
- [ ] No console errors
- [ ] Performance is improved (faster queries)

### 3. Database Queries
```sql
-- Verify wide table has data
SELECT COUNT(*), MAX(timestamp) FROM parameter_readings;

-- Check data completeness (should have 51 columns populated)
SELECT * FROM parameter_readings ORDER BY timestamp DESC LIMIT 1;

-- Verify old table is not being written to (timestamp should be old)
SELECT MAX(timestamp) FROM parameter_value_history;
```

## Expected Benefits After Migration

Once complete, you should see:

### Performance Improvements
- ✅ **51x fewer rows** to query (1 vs 51 per timestamp)
- ✅ **2-3x faster queries** (no pivoting needed)
- ✅ **Simpler code** (direct field access)
- ✅ **Better real-time** (1 event vs 51 events)

### Code Quality
- ✅ **Cleaner types** (single interface vs complex arrays)
- ✅ **Simpler logic** (no data transformation)
- ✅ **Better maintainability** (obvious field names)

### User Experience
- ✅ **Faster dashboard** (less data processing)
- ✅ **Smoother real-time** (fewer update events)
- ✅ **More reliable** (atomic updates)

## Red Flags / What NOT to Do

### ❌ DO NOT:
1. **Keep dual table support** - Choose one table (new wide table)
2. **Create abstraction layers** - Direct queries are simpler
3. **Add unnecessary complexity** - Wide table IS simpler
4. **Keep old pivoting logic** - Remove transformation code
5. **Leave commented-out code** - Clean removal

### ✅ DO:
1. **Use direct field access** - `reading.param_0d444e71`
2. **Simplify queries** - Fewer filters, no IN clauses
3. **Update types completely** - Full wide table schema
4. **Remove transformation logic** - Data is ready-to-use
5. **Test thoroughly** - Verify all features work

## Reference Files

### Parameter Mapping
See: `src/parameter_wide_table_mapping.py`
```python
PARAMETER_TO_COLUMN_MAP = {
    '0d444e71-9767-4956-af7b-787bfa79d080': 'param_0d444e71',
    '2b2e7952-c68e-40eb-ab67-d182fc460821': 'param_2b2e7952',
    # ... 49 more mappings
}
```

### Migration Documentation
- `WIDE_TABLE_MIGRATION_COMPLETE.md` - Implementation details
- `WIDE_TABLE_VERIFICATION_REPORT.md` - Test results
- `IMPLEMENTATION_SUMMARY.md` - Quick reference

### Schema
```sql
-- New table
\d parameter_readings  

-- Old table (legacy - do not use)
\d parameter_value_history
```

## Output Format

For each file you investigate, provide:

```markdown
### File: path/to/file.tsx

**Current State:**
- Uses parameter_value_history: YES
- Query pattern: [describe]
- Data transformation: [describe]

**Changes Required:**
1. Update types: [specific changes]
2. Update queries: [specific changes]
3. Update display logic: [specific changes]

**Code Diff:**
```typescript
// BEFORE
[old code]

// AFTER
[new code]
```

**Risk Level:** LOW | MEDIUM | HIGH
**Testing Required:** [specific tests]
```

## Final Deliverable

Provide:
1. **Complete file list** of all legacy references found
2. **Migration plan** for each file with code examples
3. **Risk assessment** for each change
4. **Testing checklist** for verification
5. **Updated TypeScript types** for the wide table
6. **Example queries** demonstrating the new patterns

---

**START YOUR INVESTIGATION NOW**

Begin with a comprehensive search and provide a detailed inventory of ALL files that reference the legacy `parameter_value_history` table. For each file, analyze its purpose and provide a specific migration plan with code examples.

Focus especially on the **recipe-monitor-app/** directory as this is the primary frontend application that likely has the most references to parameter data.

