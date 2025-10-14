# Deployment Guide - ALD Recipe Monitor Dashboard

**Version**: 1.0.0
**Last Updated**: 2025-10-14

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Environment Setup](#environment-setup)
3. [Database Schema Verification](#database-schema-verification)
4. [Local Development](#local-development)
5. [Production Build](#production-build)
6. [Deployment to Vercel](#deployment-to-vercel)
7. [Post-Deployment Verification](#post-deployment-verification)
8. [Rollback Procedures](#rollback-procedures)

---

## Prerequisites

### Required Software
- **Node.js**: 18.x or higher (20.x recommended)
- **npm**: 9.x or higher (included with Node.js)
- **Git**: For version control
- **Supabase Account**: Active project with database access

### Required Access
- Supabase project URL and anon key
- Deployment platform credentials (Vercel account)
- Database admin access for schema verification

---

## Environment Setup

### Step 1: Clone and Navigate

```bash
cd /path/to/ald-control-system-phase-5-1/recipe-monitor-app
```

### Step 2: Install Dependencies

```bash
npm install
```

**Expected output**: All dependencies installed without errors. Check for:
- `@supabase/supabase-js` v2.75.0+
- `next` v15.5.5
- `react` v19.1.0
- `zustand` v5.0.8

### Step 3: Configure Environment Variables

Create `.env.local` file in the project root:

```bash
touch .env.local
```

Add the following configuration:

```env
# Supabase Configuration
NEXT_PUBLIC_SUPABASE_URL=https://your-project-id.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=your-anon-key-here

# Machine Configuration
NEXT_PUBLIC_MACHINE_ID=machine_001

# Optional: Enable debug logging
NEXT_PUBLIC_DEBUG_MODE=false
```

### Step 4: Obtain Supabase Credentials

**From Supabase Dashboard**:

1. Navigate to: https://app.supabase.com/project/YOUR_PROJECT_ID/settings/api
2. Copy **Project URL** → paste as `NEXT_PUBLIC_SUPABASE_URL`
3. Copy **anon/public key** → paste as `NEXT_PUBLIC_SUPABASE_ANON_KEY`

**Security Note**:
- NEVER commit `.env.local` to version control
- Verify `.env.local` is in `.gitignore`
- Use different keys for development and production

### Step 5: Verify Configuration

```bash
npm run dev
```

Check console output for:
- ✅ No environment variable errors
- ✅ Supabase client initialization success
- ✅ Server running on http://localhost:3000

---

## Database Schema Verification

Before deploying, verify all required tables and columns exist in your Supabase database.

### Required Tables Checklist

Run these queries in Supabase SQL Editor to verify schema:

#### 1. Recipes Table

```sql
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_name = 'recipes'
ORDER BY ordinal_position;
```

**Required columns**:
- ✅ `id` (bigint, primary key)
- ✅ `name` (text)
- ✅ `machine_id` (text)
- ✅ `total_steps` (integer)
- ✅ `created_at` (timestamp with time zone)

#### 2. Process Executions Table

```sql
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_name = 'process_executions'
ORDER BY ordinal_position;
```

**Required columns**:
- ✅ `id` (bigint, primary key)
- ✅ `recipe_id` (bigint, foreign key → recipes.id)
- ✅ `status` (text: 'IDLE', 'RUNNING', 'PAUSED', 'COMPLETED', 'FAILED')
- ✅ `current_step_index` (integer)
- ✅ `started_at` (timestamp with time zone)
- ✅ `completed_at` (timestamp with time zone, nullable)
- ✅ `machine_id` (text)

#### 3. Recipe Steps Table

```sql
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_name = 'recipe_steps'
ORDER BY ordinal_position;
```

**Required columns**:
- ✅ `id` (bigint, primary key)
- ✅ `recipe_id` (bigint, foreign key → recipes.id)
- ✅ `step_order` (integer)
- ✅ `action` (text)
- ✅ `duration` (numeric)
- ✅ `step_type` (text)

#### 4. Recipe Step Executions Table

```sql
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_name = 'recipe_step_executions'
ORDER BY ordinal_position;
```

**Required columns**:
- ✅ `process_execution_id` (bigint, foreign key → process_executions.id)
- ✅ `step_order` (integer)
- ✅ `status` (text: 'PENDING', 'RUNNING', 'COMPLETED', 'FAILED')
- ✅ `started_at` (timestamp with time zone, nullable)
- ✅ `completed_at` (timestamp with time zone, nullable)

#### 5. Component Parameters Table

```sql
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_name = 'component_parameters'
ORDER BY ordinal_position;
```

**Required columns**:
- ✅ `id` (bigint, primary key)
- ✅ `machine_id` (text)
- ✅ `component_id` (bigint, foreign key → machine_components.id)
- ✅ `current_value` (numeric)
- ✅ `target_value` (numeric, nullable)
- ✅ `updated_at` (timestamp with time zone)

#### 6. Machine Components Table

```sql
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_name = 'machine_components'
ORDER BY ordinal_position;
```

**Required columns**:
- ✅ `id` (bigint, primary key)
- ✅ `name` (text)
- ✅ `type` (text: 'VALVE', 'MFC', 'CHAMBER_HEATER')

### Realtime Configuration Verification

Enable Realtime on required tables:

1. Navigate to: https://app.supabase.com/project/YOUR_PROJECT_ID/database/replication
2. Verify Realtime is enabled for:
   - ✅ `process_executions`
   - ✅ `component_parameters`
   - ✅ `recipe_step_executions`

**Test Realtime**:
```sql
-- Insert test record
INSERT INTO process_executions (recipe_id, status, current_step_index, started_at, machine_id)
VALUES (1, 'RUNNING', 0, NOW(), 'machine_001');

-- Dashboard should auto-update if realtime working
```

### Row Level Security (RLS) Policies

Verify RLS policies allow anonymous read access:

```sql
-- Check existing policies
SELECT * FROM pg_policies
WHERE tablename IN ('recipes', 'process_executions', 'recipe_steps',
                    'recipe_step_executions', 'component_parameters', 'machine_components');
```

**Minimum required policies**:
- Read access (SELECT) for anon role on all tables
- Write access for recipe_commands table (if implementing actions)

---

## Local Development

### Step 1: Start Development Server

```bash
npm run dev
```

**Expected output**:
```
▲ Next.js 15.5.5
- Local:        http://localhost:3000
- Ready in 1.2s
```

### Step 2: Access Dashboard

Open browser to: http://localhost:3000

### Step 3: Verify Initial Load

**Loading sequence checklist**:
1. ✅ Loading spinner displays
2. ✅ "Loading dashboard..." message shows
3. ✅ Recipes load in dropdown selector
4. ✅ Current process displays (if active)
5. ✅ Component parameters load
6. ✅ No console errors

**Console logs to verify**:
```
[Dashboard] Initializing data load
[Dashboard] Loaded X recipes
[Dashboard] Loaded active process: <process_id>
[Dashboard] Loaded X recipe steps
[Dashboard] Loaded X component parameters
[Dashboard] Realtime subscriptions established
```

### Step 4: Development Workflow

**Hot reload enabled**: Changes auto-refresh without restart

**File watching**:
- Components: `components/*.tsx`
- Hooks: `hooks/*.ts`
- Store: `lib/store/*.ts`
- Styles: `app/globals.css`

**TypeScript checking**:
```bash
# Run type check
npm run build
```

**Common development commands**:
```bash
# Clear cache and restart
rm -rf .next && npm run dev

# Check for type errors
npx tsc --noEmit

# Format code (if prettier configured)
npx prettier --write .
```

---

## Production Build

### Step 1: Build for Production

```bash
npm run build
```

**Expected output**:
```
▲ Next.js 15.5.5

Creating an optimized production build ...
✓ Compiled successfully
✓ Linting and checking validity of types
✓ Collecting page data
✓ Generating static pages (X/X)
✓ Finalizing page optimization

Route (app)                              Size     First Load JS
┌ ○ /                                    5.2 kB         120 kB
└ ○ /_not-found                          871 B          116 kB

○  (Static)  prerendered as static content
```

### Step 2: Test Production Build Locally

```bash
npm run start
```

Open http://localhost:3000 and verify:
- ✅ Dashboard loads correctly
- ✅ All components render
- ✅ Realtime subscriptions work
- ✅ No console errors
- ✅ Performance acceptable (< 2s initial load)

### Step 3: Build Optimization Checklist

- ✅ Bundle size < 200 KB First Load JS
- ✅ No unused dependencies in package.json
- ✅ Tree-shaking working (check build output)
- ✅ Static generation for / route
- ✅ No build warnings

**If bundle too large**:
```bash
# Analyze bundle
npm install -g @next/bundle-analyzer
ANALYZE=true npm run build
```

---

## Deployment to Vercel

### Option 1: Vercel CLI (Recommended)

#### Step 1: Install Vercel CLI

```bash
npm install -g vercel
```

#### Step 2: Login to Vercel

```bash
vercel login
```

#### Step 3: Deploy

```bash
# From project root
cd recipe-monitor-app

# Deploy to preview
vercel

# Deploy to production
vercel --prod
```

#### Step 4: Configure Environment Variables

```bash
# Add environment variables via CLI
vercel env add NEXT_PUBLIC_SUPABASE_URL
# Paste value when prompted

vercel env add NEXT_PUBLIC_SUPABASE_ANON_KEY
# Paste value when prompted

vercel env add NEXT_PUBLIC_MACHINE_ID
# Enter: machine_001
```

### Option 2: Vercel Dashboard (Git Integration)

#### Step 1: Push to Git Repository

```bash
git add .
git commit -m "Prepare recipe monitor dashboard for deployment"
git push origin main
```

#### Step 2: Import to Vercel

1. Navigate to: https://vercel.com/new
2. Select Git provider (GitHub/GitLab/Bitbucket)
3. Import repository: `ald-control-system-phase-5-1`
4. Configure project:
   - **Root Directory**: `recipe-monitor-app`
   - **Framework Preset**: Next.js
   - **Build Command**: `npm run build`
   - **Output Directory**: `.next`

#### Step 3: Configure Environment Variables

In Vercel dashboard:
1. Go to: Project Settings → Environment Variables
2. Add each variable:
   - `NEXT_PUBLIC_SUPABASE_URL` = `https://your-project.supabase.co`
   - `NEXT_PUBLIC_SUPABASE_ANON_KEY` = `your-anon-key`
   - `NEXT_PUBLIC_MACHINE_ID` = `machine_001`
3. Apply to: Production, Preview, Development

#### Step 4: Deploy

Click **Deploy** button

**Deployment process**:
```
⏳ Building...
✓ Build completed
⏳ Deploying...
✓ Deployed to: https://your-app.vercel.app
```

### Post-Deployment Configuration

#### Custom Domain (Optional)

1. Go to: Project Settings → Domains
2. Add custom domain: `monitor.your-domain.com`
3. Configure DNS:
   - Type: `CNAME`
   - Name: `monitor`
   - Value: `cname.vercel-dns.com`

#### Environment-Specific Variables

**Production**:
- Use production Supabase URL
- Use production anon key
- Set `NEXT_PUBLIC_DEBUG_MODE=false`

**Preview/Staging**:
- Use staging Supabase URL (if available)
- Use staging anon key
- Set `NEXT_PUBLIC_DEBUG_MODE=true`

---

## Post-Deployment Verification

### Step 1: Health Check

Access deployment URL and verify:

**Visual checks**:
- ✅ Dashboard loads without errors
- ✅ Recipe dropdown populated
- ✅ All panels visible (Control, Steps, Components, Log)
- ✅ Styling correct (dark theme, gradients)
- ✅ Responsive layout works on mobile

**Functional checks**:
- ✅ Recipes load from database
- ✅ Active process displays (if any)
- ✅ Realtime subscriptions connect
- ✅ Component parameters display
- ✅ Toast notifications work

**Performance checks**:
- ✅ Initial load < 3 seconds
- ✅ Time to Interactive < 5 seconds
- ✅ No layout shift (CLS < 0.1)
- ✅ No memory leaks (check DevTools)

### Step 2: Browser Console Verification

Open DevTools console and verify:
- ✅ No error messages
- ✅ Supabase client initialized
- ✅ Realtime channels subscribed
- ✅ No 404 or network errors

**Expected logs**:
```
[Dashboard] Initializing data load
[Dashboard] Loaded 5 recipes
[Dashboard] Realtime subscriptions established
```

### Step 3: Network Tab Verification

Check Network tab:
- ✅ Supabase API calls successful (200 status)
- ✅ WebSocket connection established (ws://)
- ✅ No failed requests
- ✅ Response times < 500ms

### Step 4: Mobile Responsiveness

Test on:
- ✅ Desktop (≥1024px)
- ✅ Tablet (768px - 1023px)
- ✅ Mobile (320px - 767px)

Verify:
- ✅ Layout stacks vertically on mobile
- ✅ Buttons remain clickable
- ✅ Text readable without zooming
- ✅ No horizontal scroll

### Step 5: Cross-Browser Testing

Test on:
- ✅ Chrome/Edge (latest)
- ✅ Firefox (latest)
- ✅ Safari (latest)
- ✅ Mobile Safari (iOS)
- ✅ Chrome Mobile (Android)

---

## Rollback Procedures

### Vercel Rollback

#### Via Vercel Dashboard

1. Go to: Project → Deployments
2. Find previous working deployment
3. Click **•••** menu → **Promote to Production**
4. Confirm promotion

**Rollback time**: ~30 seconds

#### Via Vercel CLI

```bash
# List deployments
vercel ls

# Rollback to specific deployment
vercel rollback <deployment-url>
```

### Git Rollback

If deployment broken due to code changes:

```bash
# Find last working commit
git log --oneline

# Rollback to specific commit
git revert <commit-hash>
git push origin main

# Vercel auto-deploys new commit
```

### Emergency Procedures

**If dashboard completely broken**:

1. **Immediate**: Set maintenance page
   ```bash
   # Create app/page.tsx with simple message
   echo 'export default function Page() { return <div>Maintenance in progress</div> }' > app/page.tsx
   git commit -am "Emergency maintenance mode"
   git push
   ```

2. **Investigate**: Check Vercel logs
   ```bash
   vercel logs <deployment-url>
   ```

3. **Fix**: Address issue in local environment
4. **Test**: Verify fix with `npm run build && npm run start`
5. **Deploy**: Push fix and monitor

### Common Rollback Scenarios

**Scenario 1: Environment variable mismatch**
- Fix: Update environment variables in Vercel dashboard
- Redeploy: Vercel → Deployments → Redeploy

**Scenario 2: Breaking dependency update**
- Fix: Revert package.json and package-lock.json
- Commit and push

**Scenario 3: Database schema mismatch**
- Fix: Restore previous database migration
- Or: Deploy code compatible with current schema

---

## Deployment Checklist

Before deploying to production, verify:

### Pre-Deployment
- ✅ All tests passing locally
- ✅ Build completes without errors
- ✅ Environment variables configured
- ✅ Database schema verified
- ✅ Realtime subscriptions enabled
- ✅ RLS policies configured
- ✅ .env.local not committed to Git

### During Deployment
- ✅ Deployment completes successfully
- ✅ No build errors in Vercel logs
- ✅ All environment variables set correctly

### Post-Deployment
- ✅ Dashboard loads without errors
- ✅ All components render correctly
- ✅ Realtime subscriptions working
- ✅ Cross-browser testing passed
- ✅ Mobile responsive testing passed
- ✅ Performance metrics acceptable

---

## Support and Troubleshooting

**For common issues, see**: [TROUBLESHOOTING.md](./TROUBLESHOOTING.md)

**For testing procedures, see**: [TESTING_CHECKLIST.md](./TESTING_CHECKLIST.md)

**For architecture details, see**: [ARCHITECTURE_OVERVIEW.md](./ARCHITECTURE_OVERVIEW.md)

---

**Document Version**: 1.0.0
**Last Updated**: 2025-10-14
**Next Review**: 2025-11-14
