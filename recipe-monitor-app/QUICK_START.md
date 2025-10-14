# Quick Start Guide - ALD Recipe Monitor Dashboard

**Get up and running in 5 minutes**

---

## Prerequisites

- Node.js 18+ installed
- Supabase project with ALD control system database
- Terminal access

---

## 5-Minute Setup

### Step 1: Install Dependencies (1 min)

```bash
cd recipe-monitor-app
npm install
```

### Step 2: Configure Environment (1 min)

Create `.env.local` file:

```bash
cat > .env.local << EOF
NEXT_PUBLIC_SUPABASE_URL=https://your-project-id.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=your-anon-key-here
NEXT_PUBLIC_MACHINE_ID=machine_001
EOF
```

**Get your credentials**:
1. Go to: https://app.supabase.com/project/YOUR_PROJECT/settings/api
2. Copy **Project URL** → paste as `NEXT_PUBLIC_SUPABASE_URL`
3. Copy **anon/public key** → paste as `NEXT_PUBLIC_SUPABASE_ANON_KEY`

### Step 3: Start Development Server (1 min)

```bash
npm run dev
```

Open browser to: **http://localhost:3000**

### Step 4: Verify Dashboard Loads (30 sec)

✅ You should see:
- Recipe dropdown with available recipes
- Component panels showing valve/MFC/heater states
- Status: "IDLE" (if no active process)

### Step 5: Test Real-time Updates (1.5 min)

**Open Supabase SQL Editor** and run:

```sql
-- Insert test process
INSERT INTO process_executions (recipe_id, status, current_step_index, started_at, machine_id)
VALUES (1, 'RUNNING', 0, NOW(), 'machine_001');

-- Watch dashboard auto-update!
```

✅ Dashboard should show:
- Status changes to "RUNNING"
- Progress bar appears
- No page refresh needed

---

## Common Issues & Quick Fixes

### Issue: "Failed to connect to Supabase"
```bash
# Check your .env.local file
cat .env.local

# Verify URL format: https://xxxxx.supabase.co
# Verify anon key starts with: eyJ...
```

### Issue: "No recipes found"
```sql
-- Insert test recipe in Supabase
INSERT INTO recipes (name, machine_id, total_steps, created_at)
VALUES ('Test Recipe', 'machine_001', 3, NOW());
```

### Issue: "Port 3000 already in use"
```bash
# Kill existing process
lsof -ti:3000 | xargs kill -9

# Or use different port
npm run dev -- -p 3001
```

---

## Next Steps

Once running successfully:

1. **Test Recipe Actions** → See [TESTING_CHECKLIST.md](./TESTING_CHECKLIST.md)
2. **Deploy to Production** → See [DEPLOYMENT_GUIDE.md](./DEPLOYMENT_GUIDE.md)
3. **Understand Architecture** → See [ARCHITECTURE_OVERVIEW.md](./ARCHITECTURE_OVERVIEW.md)
4. **Troubleshoot Issues** → See [TROUBLESHOOTING.md](./TROUBLESHOOTING.md)

---

## Development Workflow

```bash
# Start dev server
npm run dev

# Build for production (test before deploy)
npm run build

# Start production server locally
npm run start

# Clear cache (if weird errors)
rm -rf .next && npm run dev
```

---

## Key Files to Know

```
recipe-monitor-app/
├── .env.local              ← Your credentials (DO NOT COMMIT)
├── app/page.tsx            ← Main dashboard page
├── components/             ← UI components
│   ├── ControlPanel.tsx
│   ├── StepsPanel.tsx
│   └── ComponentsPanel.tsx
├── hooks/                  ← Data loading & subscriptions
│   ├── use-dashboard-data.ts
│   └── use-realtime-subscriptions.ts
└── lib/store/              ← State management
    └── dashboard-store.ts
```

---

## Essential Commands

```bash
# Development
npm run dev              # Start dev server
npm run build            # Build for production
npm run start            # Start production server

# Troubleshooting
rm -rf .next             # Clear Next.js cache
rm -rf node_modules      # Clear dependencies
npm install              # Reinstall dependencies

# Vercel Deployment
vercel                   # Deploy to preview
vercel --prod            # Deploy to production
```

---

## Quick Reference: Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `NEXT_PUBLIC_SUPABASE_URL` | Supabase project URL | `https://abc123.supabase.co` |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Supabase anonymous key | `eyJhbGc...` |
| `NEXT_PUBLIC_MACHINE_ID` | Machine identifier | `machine_001` |

**Important**: All variables must start with `NEXT_PUBLIC_` to be accessible in browser.

---

## Quick Reference: Database Tables

| Table | Purpose |
|-------|---------|
| `recipes` | Recipe definitions |
| `recipe_steps` | Steps for each recipe |
| `process_executions` | Running recipe processes |
| `recipe_step_executions` | Individual step execution history |
| `machine_components` | Hardware component definitions |
| `component_parameters` | Current component values |

---

## Quick Test Queries

### View Available Recipes
```sql
SELECT id, name, total_steps FROM recipes WHERE machine_id = 'machine_001';
```

### Check Active Process
```sql
SELECT * FROM process_executions WHERE status = 'RUNNING' AND machine_id = 'machine_001';
```

### View Component States
```sql
SELECT mc.name, mc.type, cp.current_value
FROM component_parameters cp
JOIN machine_components mc ON cp.component_id = mc.id
WHERE cp.machine_id = 'machine_001'
ORDER BY mc.type, mc.name;
```

### Start Test Process (Manual)
```sql
INSERT INTO process_executions (recipe_id, status, current_step_index, started_at, machine_id)
VALUES (1, 'RUNNING', 0, NOW(), 'machine_001')
RETURNING id;
```

---

## Quick Browser DevTools Check

Open DevTools (F12) and verify:

### Console Tab
```
✅ No red errors
✅ See logs: "[Dashboard] Initializing data load"
✅ See logs: "[Dashboard] Realtime subscriptions established"
```

### Network Tab
```
✅ Supabase API calls successful (200 status)
✅ WebSocket connection active (WS tab)
✅ Filter by "Fetch/XHR" to see data requests
```

### Application Tab
```
✅ Local Storage contains Supabase session (if auth enabled)
```

---

## Quick Performance Check

After dashboard loads, check:

```bash
# In browser console
console.log(performance.timing.loadEventEnd - performance.timing.navigationStart)
# Should be < 3000ms (3 seconds)
```

Or use DevTools Lighthouse:
1. Open DevTools
2. Lighthouse tab
3. Generate report
4. Target: Performance > 90

---

## Getting Help

**Documentation**:
- Full setup: [DEPLOYMENT_GUIDE.md](./DEPLOYMENT_GUIDE.md)
- Testing: [TESTING_CHECKLIST.md](./TESTING_CHECKLIST.md)
- Troubleshooting: [TROUBLESHOOTING.md](./TROUBLESHOOTING.md)
- Architecture: [ARCHITECTURE_OVERVIEW.md](./ARCHITECTURE_OVERVIEW.md)

**Check First**:
1. Browser console for errors
2. `.env.local` file has correct values
3. Dev server is running (`npm run dev`)
4. Supabase project is active

**Debug Commands**:
```bash
# Check Node version
node --version  # Should be 18+

# Check npm version
npm --version   # Should be 9+

# Test Supabase connection
curl https://your-project-id.supabase.co/rest/v1/

# Check port availability
lsof -i :3000
```

---

## Quick Win Checklist

After 5 minutes, you should have:

- [ ] Dependencies installed
- [ ] `.env.local` configured
- [ ] Dev server running
- [ ] Dashboard loads at http://localhost:3000
- [ ] Recipes visible in dropdown
- [ ] Components display current states
- [ ] No console errors
- [ ] Realtime updates working (tested with SQL insert)

**If all checked ✅ → You're ready to develop!**

---

**Happy Coding!** 🚀

For detailed information, see [DEPLOYMENT_GUIDE.md](./DEPLOYMENT_GUIDE.md)
