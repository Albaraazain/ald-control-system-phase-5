# ⚡ Setpoint Responsiveness Optimization - Quick Deployment Checklist

**Version**: 1.0  
**Date**: 2025-11-01  
**Status**: ✅ Ready to Deploy

---

## 📋 Pre-Deployment Checklist

### 1. Code Verification ✅
- [x] Code changes reviewed and verified
- [x] Git diff matches documentation
- [x] All 3 files modified correctly
  - [x] `plc_data_service.py` (10s→0.5s)
  - [x] `src/parameter_control_listener.py` (10s→2s)
  - [x] `component_service.py` (10s→2s)

### 2. Documentation ✅
- [x] Main documentation complete
- [x] Deployment script ready and tested
- [x] Verification report generated
- [x] Rollback procedure documented

### 3. Environment Check
- [ ] No critical ALD processes currently running
- [ ] Maintenance window scheduled (if required)
- [ ] Operators notified of brief service restart
- [ ] Backup of current code taken (git commit)

---

## 🚀 Deployment Steps

### Step 1: Commit Changes

```bash
cd /Users/albaraa/Developer/Projects/ald-control-system-phase-5-1

git add component_service.py plc_data_service.py src/parameter_control_listener.py
git add docs/SETPOINT_RESPONSIVENESS_OPTIMIZATION.md
git add scripts/apply_responsiveness_optimization.sh
git add VERIFICATION_REPORT.md DEPLOYMENT_CHECKLIST.md

git commit -m "feat: Optimize setpoint responsiveness (10s→0.5s refresh, 10s→2s polling)

- Reduce setpoint refresh interval from 10s to 0.5s (20x faster)
- Reduce parameter command polling from 10s to 2s (5x faster)  
- Reduce component command polling from 10s to 2s (5x faster)
- Add comprehensive documentation and deployment script
- Expected: 10x faster UI updates (10-12s → 1-2s average latency)

Closes: #setpoint-responsiveness-optimization"
```

**Status**: [ ] Complete

---

### Step 2: Deploy to Raspberry Pi

```bash
# SSH to Raspberry Pi
ssh atomicoat@100.100.138.5

# Navigate to project
cd ~/ald-control-system-phase-5

# Pull latest changes
git pull origin main

# Restart terminals with optimization script
./scripts/apply_responsiveness_optimization.sh
```

**Status**: [ ] Complete

**Alternative** (if script doesn't work):
```bash
# Manual restart
pkill -f terminal1_launcher
pkill -f terminal2_launcher  
pkill -f terminal3_launcher
sleep 3

python terminal1_launcher.py &
python terminal2_launcher.py &
python terminal3_launcher.py &
```

---

### Step 3: Verify Deployment

#### 3a. Check Services Running
```bash
pgrep -fl terminal.*_launcher
```
**Expected**: 3 processes listed  
**Status**: [ ] Complete

#### 3b. Verify Configuration
```bash
# Check setpoint interval
tail -50 /tmp/terminal1_plc_data_service.log | grep "Setpoint refresh"
```
**Expected**: Shows `0.5s`  
**Status**: [ ] Complete

```bash
# Check polling interval
tail -50 /tmp/terminal3_parameter_control.log | grep "polling (interval:"
```
**Expected**: Shows `2s`  
**Status**: [ ] Complete

#### 3c. Check for Errors
```bash
# Check for startup errors
tail -100 /tmp/terminal1_plc_data_service.log | grep -i error
tail -100 /tmp/terminal2_recipe_service.log | grep -i error
tail -100 /tmp/terminal3_parameter_control.log | grep -i error
```
**Expected**: No critical errors  
**Status**: [ ] Complete

---

### Step 4: Functional Testing

#### 4a. Test Setpoint Update
1. Open Flutter app on mobile/web
2. Navigate to machine dashboard
3. Adjust a setpoint (temperature, pressure, or flow rate)
4. **Measure time** from slider adjustment to "Current" value update

**Expected Result**: 1-2 seconds (was 10-12 seconds before)  
**Actual Time**: _______ seconds  
**Status**: [ ] Pass / [ ] Fail

#### 4b. Test Component Toggle
1. Toggle a valve or component on/off
2. Observe UI feedback

**Expected Result**: 1-2 seconds response  
**Status**: [ ] Pass / [ ] Fail

#### 4c. Test Multiple Rapid Changes
1. Change 3-5 setpoints in quick succession
2. Verify all updates propagate correctly

**Expected Result**: All changes reflected within 3 seconds  
**Status**: [ ] Pass / [ ] Fail

---

### Step 5: Monitor System Health (First 30 minutes)

#### 5a. Check PLC Connection Stability
```bash
tail -f /tmp/terminal1_plc_data_service.log | grep -i "plc"
```
**Watch for**: No unexpected disconnects  
**Status**: [ ] Stable

#### 5b. Check CPU Usage
```bash
top -p $(pgrep -f terminal1_launcher)
```
**Expected**: CPU < 20% (slight increase is normal)  
**Actual**: _______%  
**Status**: [ ] Normal

#### 5c. Check Error Rate
```bash
tail -f /tmp/*.log | grep -i error
```
**Expected**: No increase in error frequency  
**Status**: [ ] Normal

#### 5d. Check Log File Growth
```bash
ls -lh /tmp/terminal*.log
```
**Expected**: Steady growth, not explosive  
**Status**: [ ] Normal

---

## ✅ Success Criteria Summary

| Criterion | Target | Status |
|-----------|--------|--------|
| All terminals running | 3 processes | [ ] |
| Setpoint interval | 0.5s | [ ] |
| Polling interval | 2s | [ ] |
| UI update latency | <2s average | [ ] |
| No startup errors | 0 critical errors | [ ] |
| PLC connection stable | No disconnects | [ ] |
| CPU usage reasonable | <30% | [ ] |

**Overall Deployment Status**: [ ] SUCCESS / [ ] ISSUES FOUND

---

## 🔄 Rollback Procedure (If Needed)

### Quick Rollback (Environment Variable)

```bash
ssh atomicoat@100.100.138.5
cd ~/ald-control-system-phase-5

# Set old interval
export SETPOINT_REFRESH_INTERVAL=10.0

# Restart Terminal 1
pkill -f terminal1_launcher
python terminal1_launcher.py &

# Verify
tail -f /tmp/terminal1_plc_data_service.log | grep "Setpoint refresh"
# Should show: 10.0s
```

**Recovery Time**: ~30 seconds

---

### Full Rollback (Git Revert)

```bash
ssh atomicoat@100.100.138.5
cd ~/ald-control-system-phase-5

# Revert commit
git revert HEAD
git push origin main

# Restart all terminals
pkill -f terminal1_launcher
pkill -f terminal2_launcher
pkill -f terminal3_launcher
sleep 3

python terminal1_launcher.py &
python terminal2_launcher.py &
python terminal3_launcher.py &
```

**Recovery Time**: ~2 minutes

---

## 📊 Post-Deployment Monitoring

### First Hour Checklist

- [ ] Monitor logs for errors every 10 minutes
- [ ] Test 5-10 setpoint changes from UI
- [ ] Verify PLC connection remains stable
- [ ] Check with operators for feedback

### First 24 Hours Checklist

- [ ] Review error logs for any new patterns
- [ ] Check log file sizes (should be manageable)
- [ ] Collect operator feedback on responsiveness
- [ ] Verify no performance degradation

### First Week Checklist

- [ ] Analyze performance metrics
- [ ] Document any issues encountered
- [ ] Fine-tune intervals if needed
- [ ] Update documentation with lessons learned

---

## 📝 Notes Section

**Deployment Date**: _______________  
**Deployed By**: _______________  
**Deployment Time**: _______________

**Issues Encountered**:
```
(Note any issues here)
```

**Resolution Steps**:
```
(Note how issues were resolved)
```

**Operator Feedback**:
```
(Note feedback from operators)
```

**Additional Notes**:
```
(Any other observations)
```

---

## 📞 Support Contacts

**If Issues Arise**:
1. Check logs first (see commands above)
2. Attempt rollback if critical (see procedures above)
3. Document issue for further investigation

**Key Files**:
- Deployment script: `scripts/apply_responsiveness_optimization.sh`
- Full documentation: `docs/SETPOINT_RESPONSIVENESS_OPTIMIZATION.md`
- Verification report: `VERIFICATION_REPORT.md`

---

## 🎯 Final Sign-Off

**Pre-Deployment Verification**: [ ] Complete  
**Deployment Executed**: [ ] Complete  
**Post-Deployment Testing**: [ ] Complete  
**System Stable**: [ ] Yes / [ ] No  

**Sign-Off By**: _______________  
**Date**: _______________  

**Overall Status**: [ ] SUCCESS ✅ / [ ] ISSUES FOUND ⚠️

---

**Next Review**: _______________  
**Follow-up Actions**: 
- [ ] Update documentation with actual performance metrics
- [ ] Share results with team
- [ ] Consider future enhancements

---

*End of Deployment Checklist*

