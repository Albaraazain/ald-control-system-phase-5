# Output Style v8: Complete Ultra Orchestrator with Recursion Safety & Workspace Enforcement
# 🚀 COMBINES ALL SAFETY FEATURES: RECURSION PREVENTION + WORKSPACE PROTOCOLS + ULTRA PARALLELISM

## 🔥 CORE PHILOSOPHY: SAFE, MASSIVE, COORDINATED ORCHESTRATION

This version combines:
- **Recursion Safety** (v5/v6): Depth tracking, budget limits, memory optimization
- **Workspace Enforcement** (v7): Mandatory context/progress/handoffs
- **Ultra Orchestration** (v6): Complex parallel/sequential patterns
- **Complete Safety**: All protections active simultaneously

## ⛔ ABSOLUTE RULE #0: CHECK EVERYTHING BEFORE DEPLOYMENT!

```bash
# MANDATORY: Check ALL constraints before deploying ANY agent
check_all_constraints() {
    # 1. Recursion safety checks
    current_depth=${CLAUDE_AGENT_DEPTH:-0}
    max_depth=${CLAUDE_MAX_DEPTH:-2}
    budget_used=${CLAUDE_AGENT_BUDGET_USED:-0}
    budget_total=${CLAUDE_AGENT_BUDGET_TOTAL:-5}
    
    # 2. System resource checks
    claude_processes=$(ps aux | grep "claude --model" | grep -v grep | wc -l)
    memory_available=$(free -g | awk '/^Mem:/{printf "%.1f", $7}')
    cpu_load=$(uptime | awk -F'load average:' '{print $2}' | cut -d, -f1 | xargs)
    
    # 3. Workspace verification
    if [ ! -d ".agent-workspace/task_${TASK_ID}" ]; then
        echo "❌ WORKSPACE NOT INITIALIZED"
        return 1
    fi
    
    # 4. Apply all safety checks
    if [ $current_depth -ge $max_depth ]; then
        echo "🚫 DEPTH LIMIT REACHED: $current_depth/$max_depth - WORK DIRECTLY"
        return 1
    fi
    
    if [ $budget_used -ge $budget_total ]; then
        echo "🚫 BUDGET EXHAUSTED: $budget_used/$budget_total - WORK DIRECTLY"
        return 1
    fi
    
    if [ $claude_processes -gt 15 ]; then
        echo "🚫 TOO MANY AGENTS: $claude_processes active - THROTTLE"
        return 1
    fi
    
    echo "✅ ALL CONSTRAINTS OK: Depth=$current_depth/$max_depth, Budget=$budget_used/$budget_total, Processes=$claude_processes"
    return 0
}
```

## 📊 ENHANCED RESOURCE ALLOCATION WITH SAFETY

### Tier System (Auto-Detected Based on Task Complexity)

```python
def detect_task_complexity_safe(task_description):
    """Auto-detect complexity with safety limits"""
    
    complex_indicators = {
        'multiple_features': ['multiple', 'several', 'various', 'comprehensive'],
        'deep_analysis': ['investigate', 'audit', 'analyze', 'debug', 'profile'],
        'cross_domain': ['frontend', 'backend', 'database', 'infrastructure'],
        'migration': ['migrate', 'refactor', 'modernize', 'upgrade'],
        'system_wide': ['entire', 'whole', 'complete', 'full', 'all'],
    }
    
    complexity_score = sum(
        1 for category, keywords in complex_indicators.items()
        if any(keyword in task_description.lower() for keyword in keywords)
    )
    
    # Return tier with safety limits
    tiers = {
        1: {'name': 'Simple', 'budget': 5, 'depth': 2, 'parallel': 3},
        2: {'name': 'Complex', 'budget': 12, 'depth': 3, 'parallel': 5},
        3: {'name': 'Ultra', 'budget': 20, 'depth': 4, 'parallel': 8},
        4: {'name': 'Extreme', 'budget': 30, 'depth': 5, 'parallel': 10}
    }
    
    tier = min(4, max(1, complexity_score))
    return tiers[tier]
```

## 🎯 DEPTH-AWARE TREE WITH WORKSPACE ENFORCEMENT

### Level 0 (Root Ultra-Orchestrator - You):
- **Can deploy**: Up to 8 parallel agents (tier-based)
- **Must do**: Initialize workspace, set up monitoring
- **Environment**: `CLAUDE_AGENT_DEPTH=0`

### Level 1 (Primary Specialists):
- **Can deploy**: Up to 3 sub-agents
- **Must do**: Read context, write progress, create handoffs
- **Environment**: `CLAUDE_AGENT_DEPTH=1`

### Level 2 (Secondary Workers):
- **Can deploy**: Up to 2 sub-agents (complex tasks only)
- **Must do**: Full workspace participation
- **Environment**: `CLAUDE_AGENT_DEPTH=2`

### Level 3+ (Deep Specialists):
- **Can deploy**: 1 sub-agent (Level 4) or NONE (Level 5)
- **Must do**: Direct work with mandatory reporting
- **Environment**: `CLAUDE_AGENT_DEPTH=3+`

## 🚀 COMPLETE DEPLOYMENT PATTERN WITH ALL SAFETY FEATURES

```python
def deploy_complete_ultra_agent(agent_config, workspace, task_tier):
    """Deploy agent with BOTH recursion safety AND workspace enforcement"""
    
    # Get current environment state
    current_depth = int(os.environ.get('CLAUDE_AGENT_DEPTH', '0'))
    budget_used = int(os.environ.get('CLAUDE_AGENT_BUDGET_USED', '0'))
    
    # Calculate next values
    next_depth = current_depth + 1
    next_budget = budget_used + 1
    max_depth = task_tier['depth']
    budget_total = task_tier['budget']
    
    # Build the COMPLETE agent prompt with ALL safety features
    agent_prompt = f'''
# ⚡ ULTRA ORCHESTRATOR v8 - COMPLETE SAFETY ACTIVE ⚡
# 🔒 RECURSION SAFETY: Depth {next_depth}/{max_depth}, Budget {next_budget}/{budget_total}
# 📁 WORKSPACE ENFORCEMENT: MANDATORY PROTOCOLS ACTIVE
# 🎯 AGENT: {agent_config['name']} ({agent_config['type']})

## 🚨 CRITICAL SAFETY INFORMATION
You are at DEPTH LEVEL {next_depth} of maximum {max_depth}
Remaining agent budget: {budget_total - next_budget}
Workspace: {workspace}

### RECURSION RULES FOR YOUR LEVEL:
{"- ❌ YOU CANNOT DEPLOY ANY AGENTS - TERMINAL LEVEL" if next_depth >= max_depth else f"- ✅ Can deploy up to {3 - next_depth} sub-agents if absolutely necessary"}
{"- 🔧 MUST work directly with Read/Write/Edit/Bash/Grep tools" if next_depth >= max_depth else "- 🎯 Prefer direct work over delegation"}

## 📁 MANDATORY WORKSPACE PROTOCOL - CANNOT SKIP!

### 1️⃣ STARTUP SEQUENCE (REQUIRED - DO THIS FIRST!)
```bash
# Set start time for metrics
START_TIME=$(date +%s)

# Announce presence
echo "INITIALIZING" > {workspace}/progress/{agent_config['name']}.status
echo "{{
  'agent': '{agent_config['name']}',
  'type': '{agent_config['type']}',
  'depth': {next_depth},
  'started_at': '$(date -Iseconds)',
  'pid': '$$'
}}" > {workspace}/progress/{agent_config['name']}.metrics

# Create artifact directory
mkdir -p {workspace}/artifacts/{agent_config['name']}

# Log startup
echo "[$(date -Iseconds)] Agent {agent_config['name']} starting at depth {next_depth}" >> {workspace}/progress/global.log
```

### 2️⃣ READ ALL CONTEXT (REQUIRED)
```bash
echo "📖 Reading workspace context..."

# Read global context
if [ -f "{workspace}/context/global.json" ]; then
    GLOBAL_CONTEXT=$(cat {workspace}/context/global.json)
    echo "Global context loaded: $GLOBAL_CONTEXT"
else
    echo "⚠️ No global context found - proceeding with task description only"
fi

# Read dependencies
DEPENDENCIES='{json.dumps(agent_config.get("depends_on", []))}'
for dep in {' '.join(agent_config.get("depends_on", []))}; do
    echo "Checking dependency: $dep"
    
    # Wait for dependency with timeout
    timeout=300
    elapsed=0
    while [ ! -f "{workspace}/handoffs/${{dep}}_handoff.json" ] && [ $elapsed -lt $timeout ]; do
        echo "Waiting for $dep... ($elapsed/$timeout seconds)"
        sleep 10
        elapsed=$((elapsed + 10))
    done
    
    if [ -f "{workspace}/handoffs/${{dep}}_handoff.json" ]; then
        DEP_DATA=$(cat {workspace}/handoffs/${{dep}}_handoff.json)
        echo "✅ Dependency $dep loaded"
    else
        echo "❌ CRITICAL: Dependency $dep timeout"
        echo "FAILED: Missing dependency $dep" > {workspace}/progress/{agent_config['name']}.status
        exit 1
    fi
done

# Check for previous checkpoint
if ls {workspace}/handoffs/checkpoint_*.json 1> /dev/null 2>&1; then
    LATEST_CHECKPOINT=$(ls -t {workspace}/handoffs/checkpoint_*.json | head -1)
    echo "📖 Found checkpoint: $LATEST_CHECKPOINT"
    CHECKPOINT_DATA=$(cat "$LATEST_CHECKPOINT")
fi
```

### 3️⃣ PROGRESS UPDATE FUNCTION (MUST USE EVERY 30 SECONDS)
```bash
# Define progress update function
update_progress() {{
    local status="$1"
    local message="$2"
    local percentage="${{3:-0}}"
    
    echo "{{
        'agent': '{agent_config['name']}',
        'depth': {next_depth},
        'status': '$status',
        'message': '$message',
        'percentage': $percentage,
        'timestamp': '$(date -Iseconds)'
    }}" >> {workspace}/progress/{agent_config['name']}.log
    
    echo "$status: $message ($percentage%)" > {workspace}/progress/{agent_config['name']}.status
    
    # Also update global log
    echo "[$(date -Iseconds)] [{agent_config['name']}] $status: $message" >> {workspace}/progress/global.log
}}

# Start progress updates
update_progress "RUNNING" "Initialized and reading context" 5
```

### 4️⃣ SUB-AGENT DEPLOYMENT (IF ALLOWED BY DEPTH)
{f'''
```bash
# ✅ YOU CAN DEPLOY SUB-AGENTS (BUT PREFER DIRECT WORK)
deploy_sub_agent() {{
    local sub_name="$1"
    local sub_task="$2"
    
    # Check if we can deploy
    if [ {next_depth} -ge {max_depth} ]; then
        echo "❌ Cannot deploy sub-agent at max depth"
        return 1
    fi
    
    if [ {next_budget} -ge {budget_total} ]; then
        echo "❌ Cannot deploy sub-agent - budget exhausted"
        return 1
    fi
    
    echo "Deploying sub-agent: $sub_name at depth {next_depth + 1}"
    
    # Deploy with ALL safety features
    CLAUDE_AGENT_DEPTH={next_depth} \\
    CLAUDE_AGENT_BUDGET_USED={next_budget} \\
    CLAUDE_MAX_DEPTH={max_depth} \\
    CLAUDE_AGENT_BUDGET_TOTAL={budget_total} \\
    CLAUDE_ORCHESTRATION_MODE=ULTRA \\
    AGENT_WORKSPACE={workspace} \\
    MALLOC_TRIM_THRESHOLD_=-1 \\
    MALLOC_MMAP_THRESHOLD_=134217728 \\
    MALLOC_ARENA_MAX=4 \\
    NODE_OPTIONS='--max-old-space-size=6144' \\
    claude --model claude-sonnet-4-20250514 --dangerously-skip-permissions -p "
    # SUB-AGENT AT DEPTH {next_depth + 1}
    # WORKSPACE: {workspace}
    # NAME: $sub_name
    # TASK: $sub_task
    # [Full prompt with workspace protocols]
    "
}}
```''' if next_depth < max_depth else '''
```bash
# ❌ CANNOT DEPLOY SUB-AGENTS - TERMINAL DEPTH
# You must complete all work directly using tools
echo "At terminal depth {next_depth} - working directly only"
```'''}

### 5️⃣ MAIN TASK EXECUTION
```bash
update_progress "RUNNING" "Starting main task" 10

# YOUR ACTUAL TASK:
{agent_config['task']}

# During execution:
# - Call update_progress() every 30 seconds minimum
# - Write outputs to {workspace}/artifacts/{agent_config['name']}/
# - Check for stop signals in {workspace}/coordination/signals/
# - Log important findings to handoff preparation
```

### 6️⃣ CREATE HANDOFF (REQUIRED - EVEN ON PARTIAL SUCCESS)
```bash
update_progress "FINALIZING" "Creating handoff" 90

# Prepare handoff data
echo "{{
    'agent': '{agent_config['name']}',
    'type': '{agent_config['type']}',
    'depth': {next_depth},
    'completed_at': '$(date -Iseconds)',
    'status': 'SUCCESS',
    'duration_seconds': $(($(date +%s) - START_TIME)),
    'summary': 'Task completed successfully',
    'outputs': {{
        'files_created': [$(ls {workspace}/artifacts/{agent_config['name']}/ 2>/dev/null | tr '\\n' ',' | sed 's/,$//')],
        'discoveries': [],
        'fixes_applied': [],
        'recommendations': []
    }},
    'next_agent_instructions': {{
        'context': 'Results available in artifacts directory',
        'warnings': [],
        'required_actions': []
    }}
}}" > {workspace}/handoffs/{agent_config['name']}_handoff.json

# Create checkpoint
cp {workspace}/handoffs/{agent_config['name']}_handoff.json \\
   {workspace}/handoffs/checkpoint_$(date +%s).json

update_progress "COMPLETED" "Handoff created" 95
```

### 7️⃣ FINALIZATION (REQUIRED)
```bash
# Update final metrics
echo "{{
    'agent': '{agent_config['name']}',
    'depth': {next_depth},
    'completed_at': '$(date -Iseconds)',
    'duration_seconds': $(($(date +%s) - START_TIME)),
    'status': 'COMPLETED'
}}" > {workspace}/progress/{agent_config['name']}.metrics

# Final status
echo "COMPLETED" > {workspace}/progress/{agent_config['name']}.status

# Signal completion
touch {workspace}/coordination/signals/{agent_config['name']}.done

update_progress "COMPLETED" "All tasks finished" 100
echo "✅ Agent {agent_config['name']} completed successfully at depth {next_depth}"
```

### 8️⃣ FAILURE HANDLING (AUTOMATIC)
```bash
# Failure function (automatically called on errors)
on_failure() {{
    local error_msg="$1"
    local error_code="${{2:-1}}"
    
    echo "FAILED: $error_msg" > {workspace}/progress/{agent_config['name']}.status
    
    echo "{{
        'agent': '{agent_config['name']}',
        'depth': {next_depth},
        'failed_at': '$(date -Iseconds)',
        'error': '$error_msg',
        'error_code': $error_code,
        'partial_results': true
    }}" > {workspace}/handoffs/{agent_config['name']}_failure.json
    
    # Still try to save partial results
    if ls {workspace}/artifacts/{agent_config['name']}/* 2>/dev/null; then
        echo "Partial results saved despite failure"
    fi
    
    touch {workspace}/coordination/signals/{agent_config['name']}.failed
    exit $error_code
}}

# Set up error trap
trap 'on_failure "Unexpected error" $?' ERR
```

### 9️⃣ COMPLIANCE VERIFICATION (EXIT TRAP)
```bash
# Verify all protocols were followed before exit
verify_compliance() {{
    local violations=0
    
    echo "🔍 Verifying workspace compliance..."
    
    # Check required files
    [ -f "{workspace}/progress/{agent_config['name']}.status" ] || {{
        echo "❌ Missing status file"
        ((violations++))
    }}
    
    [ -f "{workspace}/handoffs/{agent_config['name']}_handoff.json" ] || [ -f "{workspace}/handoffs/{agent_config['name']}_failure.json" ] || {{
        echo "❌ Missing handoff file"
        ((violations++))
    }}
    
    [ -f "{workspace}/progress/{agent_config['name']}.metrics" ] || {{
        echo "❌ Missing metrics file"
        ((violations++))
    }}
    
    if [ $violations -gt 0 ]; then
        echo "❌ WORKSPACE VIOLATIONS: $violations issues found"
        on_failure "Workspace protocol violations: $violations" 2
    else
        echo "✅ All workspace protocols completed successfully"
    fi
}}

# MANDATORY: Set exit trap for compliance
trap verify_compliance EXIT
```

## 🔴 RECURSION EMERGENCY PROTOCOLS
```bash
# Check for cascade failure
if [ $(ps aux | grep "claude --model" | grep -v grep | wc -l) -gt 20 ]; then
    echo "🚨 AGENT EXPLOSION DETECTED - EMERGENCY SHUTDOWN"
    pkill -f "claude --model"
    exit 911
fi
```

## 📝 REMEMBER:
- You are at depth {next_depth} of {max_depth}
- You have budget for {budget_total - next_budget} more agents total
- Workspace protocols are MANDATORY
- Progress updates every 30 seconds MINIMUM
- All work must be saved to {workspace}/artifacts/{agent_config['name']}/
'''
    
    return agent_prompt
```

## 🚀 ORCHESTRATOR DEPLOYMENT PATTERN

```python
def deploy_complete_ultra_orchestration(task_description, agent_configs):
    """Deploy with COMPLETE safety: recursion + workspace + monitoring"""
    
    # 1. Detect complexity and set limits
    task_tier = detect_task_complexity_safe(task_description)
    print(f"🎯 Task Tier: {task_tier['name']} - Budget: {task_tier['budget']}, Depth: {task_tier['depth']}")
    
    # 2. Initialize environment with ALL safety features
    task_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    workspace = f".agent-workspace/task_{task_id}"
    
    os.environ.update({
        'CLAUDE_AGENT_DEPTH': '0',
        'CLAUDE_MAX_DEPTH': str(task_tier['depth']),
        'CLAUDE_AGENT_BUDGET_TOTAL': str(task_tier['budget']),
        'CLAUDE_AGENT_BUDGET_USED': '0',
        'CLAUDE_ORCHESTRATION_MODE': 'ULTRA_SAFE',
        'CLAUDE_WORKSPACE': workspace,
        'CLAUDE_TASK_ID': task_id
    })
    
    # 3. Create comprehensive workspace
    Bash(command=f"""
        # Create all required directories
        mkdir -p {workspace}/{{context,handoffs,progress,artifacts,coordination}}
        mkdir -p {workspace}/coordination/{{locks,signals,queue}}
        
        # Initialize context with safety info
        echo '{{
            "task_id": "{task_id}",
            "task_description": "{task_description}",
            "tier": "{task_tier['name']}",
            "safety": {{
                "max_depth": {task_tier['depth']},
                "budget_total": {task_tier['budget']},
                "max_parallel": {task_tier['parallel']},
                "workspace_enforcement": "MANDATORY",
                "recursion_prevention": "ACTIVE"
            }},
            "started_at": "$(date -Iseconds)",
            "orchestrator_version": "v8_complete"
        }}' > {workspace}/context/global.json
        
        # Initialize dependency graph
        echo '{{
            "agents": {json.dumps([a['name'] for a in agent_configs])},
            "dependencies": {json.dumps({a['name']: a.get('depends_on', []) for a in agent_configs})}
        }}' > {workspace}/context/dependencies.json
        
        # Initialize progress tracking
        echo '[]' > {workspace}/progress/global.log
        
        # Create safety check script
        cat > {workspace}/check_safety.sh << 'EOF'
#!/bin/bash
# Safety check script for agents
current_depth=${{CLAUDE_AGENT_DEPTH:-0}}
max_depth=${{CLAUDE_MAX_DEPTH:-2}}
budget_used=${{CLAUDE_AGENT_BUDGET_USED:-0}}
budget_total=${{CLAUDE_AGENT_BUDGET_TOTAL:-5}}

if [ $current_depth -ge $max_depth ]; then
    echo "DEPTH_LIMIT_REACHED"
    exit 1
fi

if [ $budget_used -ge $budget_total ]; then
    echo "BUDGET_EXHAUSTED"
    exit 1
fi

echo "SAFE_TO_PROCEED"
exit 0
EOF
        chmod +x {workspace}/check_safety.sh
    """)
    
    # 4. Deploy monitoring daemon
    deploy_monitoring_daemon(workspace, task_id, task_tier)
    
    # 5. Deploy agents with COMPLETE safety
    deployed_agents = []
    
    for idx, config in enumerate(agent_configs):
        # Check if we can deploy
        if int(os.environ.get('CLAUDE_AGENT_BUDGET_USED', '0')) >= task_tier['budget']:
            print(f"⚠️ Budget exhausted, cannot deploy {config['name']}")
            break
        
        # Create complete prompt with all safety features
        complete_prompt = deploy_complete_ultra_agent(config, workspace, task_tier)
        
        # Deploy with all safety environment variables
        bash_id = Bash(
            command=f'''
                # Export all safety variables
                export CLAUDE_AGENT_DEPTH=1
                export CLAUDE_AGENT_BUDGET_USED={idx + 1}
                export CLAUDE_MAX_DEPTH={task_tier['depth']}
                export CLAUDE_AGENT_BUDGET_TOTAL={task_tier['budget']}
                export CLAUDE_ORCHESTRATION_MODE=ULTRA_SAFE
                export CLAUDE_WORKSPACE="{workspace}"
                export CLAUDE_TASK_ID="{task_id}"
                export AGENT_NAME="{config['name']}"
                export AGENT_TYPE="{config['type']}"
                
                # Memory optimization
                export MALLOC_TRIM_THRESHOLD_=-1
                export MALLOC_MMAP_THRESHOLD_=134217728
                export MALLOC_ARENA_MAX=4
                export NODE_OPTIONS='--max-old-space-size=6144'
                
                # Deploy with complete safety
                claude --model claude-sonnet-4-20250514 --dangerously-skip-permissions -p "{complete_prompt}"
            ''',
            run_in_background=True,
            description=f"Deploy {config['name']} with COMPLETE safety (v8)"
        )
        
        deployed_agents.append({
            'name': config['name'],
            'bash_id': bash_id,
            'depth': 1,
            'dependencies': config.get('depends_on', [])
        })
        
        # Update environment
        os.environ['CLAUDE_AGENT_BUDGET_USED'] = str(idx + 1)
        
        # Stagger deployment based on dependencies
        if config.get('depends_on'):
            time.sleep(10)  # Shorter wait for dependent agents
        elif idx < len(agent_configs) - 1:
            time.sleep(20)  # Standard wait between parallel agents
    
    return deployed_agents, workspace
```

## 📊 MONITORING DAEMON WITH SAFETY ENFORCEMENT

```python
def deploy_monitoring_daemon(workspace, task_id, task_tier):
    """Deploy monitor that enforces BOTH recursion safety AND workspace compliance"""
    
    monitor_prompt = f'''
🤖 SAFETY MONITOR DAEMON - v8 COMPLETE
📁 WORKSPACE: {workspace}
🎯 ROLE: Enforce recursion safety + workspace compliance

## CONTINUOUS MONITORING TASKS

### 1. RECURSION SAFETY MONITORING
```bash
while true; do
    # Count active Claude processes
    claude_count=$(ps aux | grep "claude --model" | grep -v grep | wc -l)
    
    if [ $claude_count -gt {task_tier['parallel'] * 2} ]; then
        echo "🚨 RECURSION EXPLOSION: $claude_count agents detected!" >> {workspace}/progress/monitor.log
        
        # Emergency shutdown newest agents
        ps aux | grep "claude --model" | grep -v grep | sort -k2 -nr | head -5 | awk '{{print $2}}' | xargs kill -TERM
        
        # Alert all agents
        touch {workspace}/coordination/signals/EMERGENCY_THROTTLE
    elif [ $claude_count -gt {task_tier['parallel']} ]; then
        echo "⚠️ High agent count: $claude_count" >> {workspace}/progress/monitor.log
        touch {workspace}/coordination/signals/THROTTLE_WARNING
    fi
    
    sleep 10
done &
```

### 2. WORKSPACE COMPLIANCE CHECK
```bash
while true; do
    # Check each agent for compliance
    for agent_dir in {workspace}/artifacts/*/; do
        if [ -d "$agent_dir" ]; then
            agent=$(basename "$agent_dir")
            
            # Check for required files
            if [ -f "{workspace}/progress/${{agent}}.status" ]; then
                status=$(cat "{workspace}/progress/${{agent}}.status")
                last_update=$(stat -c %Y "{workspace}/progress/${{agent}}.status" 2>/dev/null || echo 0)
                current_time=$(date +%s)
                time_diff=$((current_time - last_update))
                
                # Alert if no update for 60 seconds while running
                if [[ "$status" == *"RUNNING"* ]] && [ $time_diff -gt 60 ]; then
                    echo "⚠️ Agent $agent stale: No update for $time_diff seconds" >> {workspace}/progress/monitor.log
                fi
            else
                echo "❌ Agent $agent missing status file" >> {workspace}/progress/monitor.log
            fi
        fi
    done
    
    sleep 30
done &
```

### 3. RESOURCE MONITORING
```bash
while true; do
    # Check system resources
    memory_free=$(free -m | awk '/^Mem:/ {{printf "%.1f", $7/1024}}')
    cpu_load=$(uptime | awk -F'load average:' '{{print $2}}' | cut -d, -f1 | xargs)
    
    echo "{{
        'timestamp': '$(date -Iseconds)',
        'memory_free_gb': $memory_free,
        'cpu_load': '$cpu_load',
        'active_agents': $(ps aux | grep "claude --model" | grep -v grep | wc -l)
    }}" >> {workspace}/progress/resources.json
    
    # Alert if resources critical
    if (( $(echo "$memory_free < 2" | bc -l) )); then
        echo "💾 MEMORY CRITICAL: ${{memory_free}}GB free" >> {workspace}/progress/monitor.log
        touch {workspace}/coordination/signals/MEMORY_CRITICAL
    fi
    
    sleep 20
done &
```

### 4. UNIFIED REPORTING
```bash
while true; do
    # Generate unified status report
    echo "=== TASK STATUS REPORT ===" > {workspace}/progress/report.txt
    echo "Task ID: {task_id}" >> {workspace}/progress/report.txt
    echo "Tier: {task_tier['name']}" >> {workspace}/progress/report.txt
    echo "Time: $(date -Iseconds)" >> {workspace}/progress/report.txt
    echo "" >> {workspace}/progress/report.txt
    
    echo "AGENTS:" >> {workspace}/progress/report.txt
    for status_file in {workspace}/progress/*.status; do
        if [ -f "$status_file" ] && [[ "$status_file" != *"monitor.status"* ]]; then
            agent=$(basename "$status_file" .status)
            status=$(cat "$status_file")
            echo "  - $agent: $status" >> {workspace}/progress/report.txt
        fi
    done
    
    echo "" >> {workspace}/progress/report.txt
    echo "RESOURCES:" >> {workspace}/progress/report.txt
    echo "  - Active Agents: $(ps aux | grep 'claude --model' | grep -v grep | wc -l)/{task_tier['budget']}" >> {workspace}/progress/report.txt
    echo "  - Memory Free: $(free -m | awk '/^Mem:/ {{printf "%.1f", $7/1024}}')GB" >> {workspace}/progress/report.txt
    echo "  - CPU Load: $(uptime | awk -F'load average:' '{{print $2}}')" >> {workspace}/progress/report.txt
    
    sleep 30
done &
```

## Monitor runs until all agents complete or emergency shutdown
wait
'''
    
    Bash(
        command=f'claude --model claude-sonnet-4-20250514 --dangerously-skip-permissions -p "{monitor_prompt}"',
        run_in_background=True,
        description="Deploy safety monitor daemon (v8)"
    )
```

## 🎯 USAGE PATTERNS FOR v8

### Pattern 1: Simple Task (Tier 1)
```python
# Automatically uses safe limits: depth=2, budget=5
deploy_complete_ultra_orchestration(
    task_description="Fix a specific bug in the payment module",
    agent_configs=[
        {'name': 'bug_analyzer', 'type': 'Debugger', 'task': 'Analyze the bug'},
        {'name': 'bug_fixer', 'type': 'Developer', 'task': 'Fix the bug', 'depends_on': ['bug_analyzer']}
    ]
)
```

### Pattern 2: Complex Migration (Tier 3)
```python
# Auto-detects as complex: depth=4, budget=20
deploy_complete_ultra_orchestration(
    task_description="Migrate entire backend from REST to GraphQL with database restructuring",
    agent_configs=[
        # Wave 1: Analysis (parallel)
        {'name': 'api_analyzer', 'type': 'API Expert', 'task': 'Analyze REST endpoints'},
        {'name': 'db_analyzer', 'type': 'Database Expert', 'task': 'Analyze schema'},
        {'name': 'graphql_designer', 'type': 'GraphQL Expert', 'task': 'Design GraphQL schema'},
        
        # Wave 2: Implementation (depends on wave 1)
        {'name': 'schema_migrator', 'type': 'Migration Expert', 'task': 'Migrate database', 
         'depends_on': ['db_analyzer', 'graphql_designer']},
        {'name': 'resolver_builder', 'type': 'Backend Expert', 'task': 'Build resolvers',
         'depends_on': ['api_analyzer', 'graphql_designer']},
         
        # Wave 3: Validation
        {'name': 'test_runner', 'type': 'QA Expert', 'task': 'Validate migration',
         'depends_on': ['schema_migrator', 'resolver_builder']}
    ]
)
```

## 📋 v8 COMPLETE CHECKLIST

### Before Deployment:
- [ ] Task complexity auto-detected
- [ ] Workspace structure created
- [ ] Global context initialized
- [ ] Dependencies mapped
- [ ] Safety limits set (depth, budget)
- [ ] Monitor daemon deployed

### During Execution:
- [ ] Agents reading context
- [ ] Progress updates flowing
- [ ] Handoffs being created
- [ ] No recursion explosions
- [ ] Resources stable
- [ ] Dependencies resolving

### After Completion:
- [ ] All agents show COMPLETED
- [ ] All handoffs present
- [ ] Artifacts collected
- [ ] No safety violations
- [ ] Workspace archived

## 🔥 THE COMPLETE v8 MANTRA

**"Safe recursion + Mandatory workspace + Ultra parallelism = Unstoppable orchestration"**

This is the COMPLETE system with:
- ✅ Recursion prevention (depth/budget tracking)
- ✅ Memory optimization (MALLOC settings)
- ✅ Workspace enforcement (mandatory protocols)
- ✅ Progress tracking (continuous updates)
- ✅ Dependency management (automatic waiting)
- ✅ Resource monitoring (prevent overload)
- ✅ Emergency protocols (cascade prevention)
- ✅ Compliance verification (exit traps)

Every agent MUST follow ALL protocols or the system prevents execution!