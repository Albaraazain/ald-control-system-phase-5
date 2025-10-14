# Troubleshooting Guide - ALD Recipe Monitor Dashboard

**Version**: 1.0.0
**Last Updated**: 2025-10-14

## Table of Contents

1. [Quick Diagnostics](#quick-diagnostics)
2. [Connection Issues](#connection-issues)
3. [Build and Compilation Errors](#build-and-compilation-errors)
4. [Runtime Errors](#runtime-errors)
5. [Realtime Subscription Issues](#realtime-subscription-issues)
6. [Data Loading Problems](#data-loading-problems)
7. [Type Errors](#type-errors)
8. [Environment Variable Issues](#environment-variable-issues)
9. [Performance Issues](#performance-issues)
10. [Deployment Issues](#deployment-issues)

---

## Quick Diagnostics

### First Steps for Any Issue

1. **Check Browser Console**
   ```
   F12 → Console tab
   Look for red error messages
   ```

2. **Check Network Tab**
   ```
   F12 → Network tab
   Filter by "Fetch/XHR" or "WS"
   Look for failed requests (red)
   ```

3. **Verify Environment Variables**
   ```bash
   cat .env.local
   # Ensure all required variables present
   ```

4. **Check Dev Server**
   ```bash
   # Is server running?
   lsof -i :3000

   # Restart if needed
   npm run dev
   ```

5. **Clear Cache**
   ```bash
   # Clear Next.js cache
   rm -rf .next
   rm -rf node_modules/.cache
   npm run dev
   ```

---

## Connection Issues

### Issue: "Failed to connect to Supabase"

**Symptoms**:
- Error message on page load
- Console error: `Failed to initialize Supabase client`
- Dashboard shows error state

**Possible Causes**:

#### 1. Invalid Supabase URL

**Diagnosis**:
```bash
# Check .env.local
cat .env.local | grep NEXT_PUBLIC_SUPABASE_URL

# Should be: https://xxxxx.supabase.co
```

**Solution**:
```bash
# Fix URL in .env.local
NEXT_PUBLIC_SUPABASE_URL=https://your-project-id.supabase.co

# Restart dev server
npm run dev
```

#### 2. Invalid Anon Key

**Diagnosis**:
```bash
# Check anon key
cat .env.local | grep NEXT_PUBLIC_SUPABASE_ANON_KEY

# Should be long JWT string (eyJ...)
```

**Solution**:
1. Go to Supabase Dashboard: https://app.supabase.com/project/YOUR_PROJECT/settings/api
2. Copy **anon/public** key
3. Update `.env.local`:
   ```bash
   NEXT_PUBLIC_SUPABASE_ANON_KEY=eyJhbGc...
   ```
4. Restart dev server

#### 3. Network/Firewall Blocking

**Diagnosis**:
```bash
# Test connectivity
curl https://your-project-id.supabase.co/rest/v1/

# Should return: {"message":"The resource you requested could not be found."}
```

**Solution**:
- Check corporate firewall settings
- Disable VPN temporarily
- Check browser extensions (ad blockers)
- Try different network

#### 4. Supabase Service Down

**Diagnosis**:
- Check Supabase Status: https://status.supabase.com
- Check project dashboard for alerts

**Solution**:
- Wait for service restoration
- Check Supabase status page for updates

---

### Issue: "CORS Error"

**Symptoms**:
- Console error: `Access to fetch at 'https://...' from origin 'http://localhost:3000' has been blocked by CORS policy`

**Cause**: Supabase RLS policies or API configuration

**Solution**:
1. Verify anon key is correct (not service_role key)
2. Check Supabase API settings allow localhost
3. In production, add your domain to Supabase allowed origins:
   - Supabase Dashboard → Settings → API → Site URL
   - Add: `https://your-domain.com`

---

### Issue: "WebSocket Connection Failed"

**Symptoms**:
- Console error: `WebSocket connection to 'wss://...' failed`
- Realtime updates not working
- Manual refresh required to see changes

**Diagnosis**:
```javascript
// Check in console
console.log(window.WebSocket)
// Should exist

// Check network tab → WS filter
// Should see connection attempts
```

**Solutions**:

#### 1. Browser Extension Interference
```
Disable extensions:
- Ad blockers
- Privacy tools
- VPN extensions

Test in incognito mode
```

#### 2. Corporate Proxy Blocking
```
Check proxy settings:
- System Preferences → Network → Advanced → Proxies
- Try direct connection

Workaround: Use polling fallback (if implemented)
```

#### 3. Supabase Realtime Not Enabled
```
Fix:
1. Supabase Dashboard → Database → Replication
2. Enable Realtime for tables:
   - process_executions
   - component_parameters
   - recipe_step_executions
```

---

## Build and Compilation Errors

### Issue: "Module not found: Can't resolve '@/...'

**Symptoms**:
```
Error: Module not found: Can't resolve '@/components/ControlPanel'
```

**Cause**: TypeScript path alias misconfiguration

**Solution**:

1. **Check tsconfig.json**:
   ```json
   {
     "compilerOptions": {
       "paths": {
         "@/*": ["./*"]
       }
     }
   }
   ```

2. **Verify file exists**:
   ```bash
   ls -la components/ControlPanel.tsx
   ```

3. **Restart TypeScript server** (VSCode):
   ```
   Cmd/Ctrl + Shift + P → "TypeScript: Restart TS Server"
   ```

4. **Clear cache and rebuild**:
   ```bash
   rm -rf .next node_modules/.cache
   npm run dev
   ```

---

### Issue: "Cannot find module 'next' or its corresponding type declarations"

**Symptoms**:
```
Cannot find module 'next' or its corresponding type declarations.ts(2760)
```

**Cause**: Dependencies not installed or corrupted

**Solution**:
```bash
# Remove and reinstall dependencies
rm -rf node_modules package-lock.json
npm install

# Verify Next.js installed
npm list next
# Should show: next@15.5.5

# Restart dev server
npm run dev
```

---

### Issue: "Error: Minified React error"

**Symptoms**:
- Build succeeds but runtime error
- Error code: `Minified React error #...`

**Cause**: React version mismatch or duplicate React instances

**Solution**:

1. **Check for duplicate React**:
   ```bash
   npm ls react
   # Should show single version tree
   ```

2. **Fix duplicates**:
   ```bash
   npm dedupe
   npm install
   ```

3. **Verify React version**:
   ```json
   // package.json
   {
     "dependencies": {
       "react": "19.1.0",
       "react-dom": "19.1.0"
     }
   }
   ```

4. **Clear cache**:
   ```bash
   rm -rf .next
   npm run dev
   ```

---

## Runtime Errors

### Issue: "Hydration failed because the initial UI does not match"

**Symptoms**:
```
Error: Hydration failed because the initial UI does not match what was rendered on the server.
```

**Cause**: Server-rendered HTML differs from client-rendered HTML

**Common Causes**:

#### 1. Using Browser-Only APIs in Server Components
```typescript
// ❌ Wrong - causes hydration error
export default function Component() {
  const time = new Date().toLocaleTimeString() // Different on server/client
  return <div>{time}</div>
}

// ✅ Correct - use client component
'use client'
export default function Component() {
  const [time, setTime] = useState('')
  useEffect(() => {
    setTime(new Date().toLocaleTimeString())
  }, [])
  return <div>{time}</div>
}
```

#### 2. Incorrect Nesting
```typescript
// ❌ Wrong - <p> cannot contain <div>
<p>
  <div>Content</div>
</p>

// ✅ Correct
<div>
  <p>Content</p>
</div>
```

**Solution**:
1. Add `'use client'` directive to components using hooks
2. Check HTML nesting rules
3. Use `suppressHydrationWarning` attribute (temporary):
   ```typescript
   <div suppressHydrationWarning>{dynamicContent}</div>
   ```

---

### Issue: "Cannot read properties of undefined"

**Symptoms**:
```
Uncaught TypeError: Cannot read properties of undefined (reading 'name')
```

**Cause**: Accessing nested properties before data loads

**Diagnosis**:
```typescript
// Example error location
<div>{currentProcess.recipe.name}</div>
// currentProcess is null initially
```

**Solution**:

1. **Add null checks**:
   ```typescript
   // ✅ Correct
   <div>{currentProcess?.recipe?.name || 'No recipe'}</div>
   ```

2. **Use loading state**:
   ```typescript
   if (!currentProcess) {
     return <div>Loading...</div>
   }
   return <div>{currentProcess.recipe.name}</div>
   ```

3. **Provide default values in store**:
   ```typescript
   const currentProcess = useDashboardStore(
     state => state.currentProcess || null
   )
   ```

---

### Issue: "Maximum update depth exceeded"

**Symptoms**:
```
Error: Maximum update depth exceeded. This can happen when a component repeatedly calls setState inside componentWillUpdate or componentDidUpdate.
```

**Cause**: Infinite render loop

**Common Causes**:

1. **setState in render function**:
   ```typescript
   // ❌ Wrong - causes infinite loop
   function Component() {
     const [count, setCount] = useState(0)
     setCount(count + 1) // Called every render!
     return <div>{count}</div>
   }
   ```

2. **useEffect with missing dependencies**:
   ```typescript
   // ❌ Wrong - runs every render
   useEffect(() => {
     setData(fetchData())
   }) // Missing dependency array

   // ✅ Correct
   useEffect(() => {
     setData(fetchData())
   }, []) // Empty array = run once
   ```

**Solution**:
- Move state updates to event handlers or useEffect
- Add proper dependency arrays to useEffect
- Check Zustand store for circular updates

---

## Realtime Subscription Issues

### Issue: "Realtime updates not working"

**Symptoms**:
- Database changes don't appear in dashboard
- Manual refresh required to see updates
- Console shows no realtime messages

**Diagnosis Checklist**:

1. **Check Realtime enabled on table**:
   ```sql
   -- Run in Supabase SQL Editor
   SELECT schemaname, tablename
   FROM pg_publication_tables
   WHERE pubname = 'supabase_realtime';

   -- Should include: process_executions, component_parameters, etc.
   ```

2. **Check WebSocket connection**:
   ```
   DevTools → Network → WS tab
   Should see: wss://your-project.supabase.co/realtime/v1/websocket
   Status: 101 Switching Protocols (green)
   ```

3. **Check console for subscription errors**:
   ```
   Look for: [Realtime] subscription error
   ```

**Solutions**:

#### 1. Enable Realtime on Tables
```
Supabase Dashboard:
1. Database → Replication
2. Click "supabase_realtime" publication
3. Enable tables:
   ✅ process_executions
   ✅ component_parameters
   ✅ recipe_step_executions
4. Save changes
5. Refresh dashboard
```

#### 2. Fix Subscription Filters
```typescript
// Check hook: hooks/use-realtime-subscriptions.ts

// ✅ Correct - filter by machine_id
.channel('process-updates')
.on('postgres_changes', {
  event: '*',
  schema: 'public',
  table: 'process_executions',
  filter: `machine_id=eq.${MACHINE_ID}`
}, handleUpdate)
.subscribe()
```

#### 3. Check RLS Policies
```sql
-- Verify SELECT policy exists
SELECT * FROM pg_policies
WHERE tablename = 'process_executions';

-- Create if missing
CREATE POLICY "Allow anonymous read" ON process_executions
  FOR SELECT USING (true);
```

---

### Issue: "Subscription established but no updates received"

**Diagnosis**:
```typescript
// Add logging to subscription handler
.on('postgres_changes', {...}, (payload) => {
  console.log('[Realtime] Update received:', payload)
  // If this logs, handler is working
  // If not, subscription filter may be wrong
})
```

**Common Issues**:

1. **Filter mismatch**:
   ```typescript
   // ❌ Wrong - machine_id doesn't match
   filter: `machine_id=eq.machine_002`
   // But NEXT_PUBLIC_MACHINE_ID=machine_001

   // ✅ Correct - use env variable
   filter: `machine_id=eq.${process.env.NEXT_PUBLIC_MACHINE_ID}`
   ```

2. **Wrong event type**:
   ```typescript
   // ❌ Only listens to INSERT
   event: 'INSERT'

   // ✅ Listen to all changes
   event: '*'
   ```

3. **Store update not triggered**:
   ```typescript
   // Verify store action called
   .on('postgres_changes', {...}, (payload) => {
     console.log('Updating store with:', payload.new)
     useDashboardStore.getState().setCurrentProcess(payload.new)
   })
   ```

---

## Data Loading Problems

### Issue: "Dashboard stuck on loading screen"

**Symptoms**:
- Loading spinner never disappears
- "Loading dashboard..." message persists
- No error message shown

**Diagnosis**:
```javascript
// Check in browser console
console.log(useDashboardStore.getState())
// Check if data populated
```

**Common Causes**:

#### 1. Empty Database Tables
```sql
-- Check data exists
SELECT COUNT(*) FROM recipes WHERE machine_id = 'machine_001';
SELECT COUNT(*) FROM machine_components;

-- If 0, need to insert test data
```

**Solution**: Insert test data (see [TESTING_CHECKLIST.md](./TESTING_CHECKLIST.md))

#### 2. Hook Never Resolves
```typescript
// Check hook: hooks/use-dashboard-data.ts
// Ensure setLoading(false) called in all paths

try {
  // ... data loading
  setLoading(false) // ✅ Must be called
} catch (error) {
  setError(error.message)
  setLoading(false) // ✅ Must be called here too
}
```

#### 3. Async Race Condition
```typescript
// Verify useEffect cleanup
useEffect(() => {
  let cancelled = false

  async function loadData() {
    const data = await fetchData()
    if (!cancelled) {
      setData(data)
      setLoading(false)
    }
  }

  loadData()

  return () => {
    cancelled = true // Prevent state update after unmount
  }
}, [])
```

---

### Issue: "No recipes found in dropdown"

**Symptoms**:
- Recipe dropdown empty
- Message: "No recipes available"

**Diagnosis**:
```sql
-- Check recipes table
SELECT * FROM recipes WHERE machine_id = 'machine_001';

-- If empty, need to insert recipes
```

**Solution**:
```sql
-- Insert test recipe
INSERT INTO recipes (name, machine_id, total_steps, created_at)
VALUES ('Test Recipe', 'machine_001', 5, NOW())
RETURNING id;
```

**Check RLS policy**:
```sql
-- Verify anonymous can read
SELECT * FROM pg_policies WHERE tablename = 'recipes';

-- Create policy if missing
CREATE POLICY "Allow anonymous read recipes" ON recipes
  FOR SELECT USING (true);
```

---

## Type Errors

### Issue: "Property 'X' does not exist on type 'Y'"

**Symptoms**:
```typescript
Property 'recipe' does not exist on type 'ProcessExecution'
```

**Cause**: Type definition mismatch with database

**Solution**:

1. **Regenerate types from Supabase**:
   ```bash
   npx supabase gen types typescript --project-id YOUR_PROJECT_ID > lib/types/database.ts
   ```

2. **Update custom types** (lib/types/dashboard.ts):
   ```typescript
   // Ensure types match database schema
   export interface ProcessExecutionWithRecipe {
     id: number
     recipe_id: number
     recipe: Recipe // Add if missing
     status: string
     // ... other fields
   }
   ```

3. **Add type assertion if needed**:
   ```typescript
   const process = data as ProcessExecutionWithRecipe
   ```

---

### Issue: "Type 'null' is not assignable to type 'X'"

**Symptoms**:
```typescript
Type 'null' is not assignable to type 'ProcessExecution'
```

**Cause**: Strict null checks

**Solution**:

1. **Use optional chaining**:
   ```typescript
   const recipeName = process?.recipe?.name
   ```

2. **Update type to allow null**:
   ```typescript
   const [process, setProcess] = useState<ProcessExecution | null>(null)
   ```

3. **Provide type guard**:
   ```typescript
   if (process !== null) {
     // TypeScript knows process is not null here
     console.log(process.recipe.name)
   }
   ```

---

### Issue: "Argument of type 'X' is not assignable to parameter of type 'Y'"

**Symptoms**:
```typescript
Argument of type 'string' is not assignable to parameter of type 'Status'
```

**Cause**: Enum or union type mismatch

**Solution**:

1. **Use proper type**:
   ```typescript
   // Define union type
   type Status = 'IDLE' | 'RUNNING' | 'PAUSED' | 'COMPLETED' | 'FAILED'

   // Use type assertion
   const status: Status = 'RUNNING'
   setStatus(status)
   ```

2. **Add type to database types**:
   ```typescript
   // lib/types/database.ts
   export type ProcessStatus =
     | 'IDLE'
     | 'RUNNING'
     | 'PAUSED'
     | 'COMPLETED'
     | 'FAILED'
   ```

---

## Environment Variable Issues

### Issue: "Environment variable undefined"

**Symptoms**:
```javascript
console.log(process.env.NEXT_PUBLIC_SUPABASE_URL)
// Output: undefined
```

**Solutions**:

#### 1. Variable Not Prefixed with NEXT_PUBLIC_
```bash
# ❌ Wrong - not accessible in browser
SUPABASE_URL=https://...

# ✅ Correct - accessible in browser
NEXT_PUBLIC_SUPABASE_URL=https://...
```

#### 2. .env.local Not Loaded
```bash
# Verify file exists
ls -la .env.local

# Verify contents
cat .env.local

# Restart dev server (required after .env changes)
npm run dev
```

#### 3. Using in Server Component
```typescript
// ❌ Won't work in server components
'use server'
console.log(process.env.NEXT_PUBLIC_SUPABASE_URL)

// ✅ Works in client components
'use client'
console.log(process.env.NEXT_PUBLIC_SUPABASE_URL)
```

#### 4. Vercel Deployment Missing Variables
```bash
# Add via CLI
vercel env add NEXT_PUBLIC_SUPABASE_URL

# Or via dashboard:
# Vercel Project → Settings → Environment Variables
```

---

### Issue: "Environment variable contains wrong value"

**Diagnosis**:
```bash
# Check .env.local
cat .env.local

# Check actual value in app
console.log(process.env.NEXT_PUBLIC_SUPABASE_URL)
```

**Common Issues**:

1. **Spaces in value**:
   ```bash
   # ❌ Wrong
   NEXT_PUBLIC_SUPABASE_URL= https://project.supabase.co

   # ✅ Correct (no space after =)
   NEXT_PUBLIC_SUPABASE_URL=https://project.supabase.co
   ```

2. **Quotes when not needed**:
   ```bash
   # Usually correct without quotes
   NEXT_PUBLIC_SUPABASE_URL=https://project.supabase.co

   # Only quote if value contains spaces
   NEXT_PUBLIC_MACHINE_ID="machine 001"
   ```

3. **Cached old value**:
   ```bash
   # Clear Next.js cache
   rm -rf .next
   npm run dev
   ```

---

## Performance Issues

### Issue: "Dashboard slow to load"

**Diagnosis**:
1. Open DevTools → Performance
2. Record page load
3. Check metrics:
   - LCP (Largest Contentful Paint) > 4s = slow
   - TBT (Total Blocking Time) > 500ms = slow

**Solutions**:

#### 1. Optimize Initial Data Query
```typescript
// ❌ Multiple sequential queries
const recipes = await supabase.from('recipes').select()
const components = await supabase.from('components').select()
const process = await supabase.from('process').select()

// ✅ Parallel queries
const [recipes, components, process] = await Promise.all([
  supabase.from('recipes').select(),
  supabase.from('components').select(),
  supabase.from('process').select()
])
```

#### 2. Add Indices to Database
```sql
-- Speed up common queries
CREATE INDEX idx_process_executions_machine_id
  ON process_executions(machine_id);

CREATE INDEX idx_component_parameters_machine_id
  ON component_parameters(machine_id);

CREATE INDEX idx_recipes_machine_id
  ON recipes(machine_id);
```

#### 3. Reduce Bundle Size
```bash
# Analyze bundle
npm run build

# Check output for large dependencies
# Consider code splitting or lighter alternatives
```

---

### Issue: "UI freezes during updates"

**Cause**: Too many re-renders or expensive computations

**Solutions**:

1. **Use React.memo for expensive components**:
   ```typescript
   export const ExpensiveComponent = React.memo(({ data }) => {
     // Component code
   })
   ```

2. **Use useMemo for expensive calculations**:
   ```typescript
   const sortedSteps = useMemo(() => {
     return steps.sort((a, b) => a.order - b.order)
   }, [steps])
   ```

3. **Optimize Zustand selectors**:
   ```typescript
   // ❌ Triggers re-render on any store change
   const store = useDashboardStore()

   // ✅ Only re-renders when steps change
   const steps = useDashboardStore(state => state.steps)
   ```

---

## Deployment Issues

### Issue: "Build fails in Vercel"

**Symptoms**:
- Local build succeeds: `npm run build` ✅
- Vercel build fails ❌

**Check Vercel Logs**:
```
Vercel Dashboard → Deployments → Failed Deployment → View Logs
```

**Common Causes**:

#### 1. Missing Environment Variables
```
Error: Missing NEXT_PUBLIC_SUPABASE_URL
```

**Solution**:
```bash
# Add via CLI
vercel env add NEXT_PUBLIC_SUPABASE_URL production

# Or via dashboard
Vercel → Settings → Environment Variables
```

#### 2. Type Errors (Strict Mode)
```
Error: Type error: Property 'X' does not exist on type 'Y'
```

**Solution**:
```bash
# Fix type errors locally first
npx tsc --noEmit

# Fix errors, then deploy again
```

#### 3. Build Timeout
```
Error: Build exceeded maximum duration of 45 seconds
```

**Solution**:
- Optimize dependencies
- Consider Pro plan for longer timeouts
- Split large components

---

### Issue: "Deployed app shows blank page"

**Diagnosis**:
1. Check Vercel deployment URL
2. Open browser console
3. Look for errors

**Common Causes**:

#### 1. Environment Variables Missing
```javascript
// Console shows:
Uncaught Error: Supabase URL is undefined
```

**Solution**: Add environment variables in Vercel, redeploy

#### 2. Build Output Incorrect
```
Vercel Dashboard → Deployment → Build Settings
Framework Preset: Next.js
Build Command: npm run build
Output Directory: .next ← Must be correct
Root Directory: recipe-monitor-app ← Must be correct if in subdirectory
```

#### 3. Runtime Error on Server
```
Check Vercel Function Logs:
Vercel → Deployment → Functions → View Logs
```

---

## Getting Help

### Information to Provide

When reporting issues, include:

1. **Error message** (full text from console)
2. **Browser** (Chrome 120, Safari 17, etc.)
3. **Environment** (local dev, staging, production)
4. **Steps to reproduce**
5. **Expected vs actual behavior**
6. **Screenshots** (if UI issue)
7. **Console logs**
8. **Network tab** (if connection issue)

### Useful Debug Commands

```bash
# Check versions
node --version
npm --version
npx next --version

# Check environment
cat .env.local

# Check dependencies
npm list

# Check for outdated packages
npm outdated

# Check build output
npm run build

# Check type errors
npx tsc --noEmit

# Test Supabase connection
curl https://your-project.supabase.co/rest/v1/

# Check disk space
df -h
```

### Log Collection

```bash
# Capture build logs
npm run build 2>&1 | tee build.log

# Capture runtime logs
# (Open DevTools → Console → Right-click → Save as...)

# Capture network logs
# (Open DevTools → Network → Right-click → Save all as HAR)
```

---

## Related Documentation

- **Deployment Guide**: [DEPLOYMENT_GUIDE.md](./DEPLOYMENT_GUIDE.md)
- **Testing Checklist**: [TESTING_CHECKLIST.md](./TESTING_CHECKLIST.md)
- **Architecture Overview**: [ARCHITECTURE_OVERVIEW.md](./ARCHITECTURE_OVERVIEW.md)

---

**Document Version**: 1.0.0
**Last Updated**: 2025-10-14
**Next Review**: 2025-11-14
