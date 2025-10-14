// TypeScript version of the ALD Test Dashboard with type safety
// This provides better IDE support, compile-time error checking, and IntelliSense

interface SupabaseClient {
  from(table: string): SupabaseQueryBuilder;
  channel(name: string): SupabaseChannel;
}

interface SupabaseQueryBuilder {
  select(columns: string): SupabaseQueryBuilder;
  eq(column: string, value: any): SupabaseQueryBuilder;
  or(filter: string): SupabaseQueryBuilder;
  order(column: string, options?: { ascending?: boolean }): SupabaseQueryBuilder;
  limit(count: number): SupabaseQueryBuilder;
  maybeSingle(): Promise<{ data: any; error: any }>;
  insert(data: any): Promise<{ error: any }>;
}

interface SupabaseChannel {
  on(event: string, config: any, callback: Function): SupabaseChannel;
  subscribe(): void;
}

interface Recipe {
  id: string;
  name: string;
  machine_id?: string;
}

interface ProcessExecution {
  id: string;
  status: string;
  updated_at: string;
  recipe_id: string;
  recipe_version: any;
}

interface StepExecution {
  id: string;
  process_id: string;
  step_name?: string;
  step_type: string;
  started_at: string;
  ended_at?: string;
}

interface ParameterCommand {
  id: string;
  parameter_name: string;
  target_value: number;
  machine_id: string;
  created_at: string;
  executed_at?: string;
  completed_at?: string;
}

interface Component {
  id: string;
  name: string;
  type: string;
}

interface TelemetryData {
  name: string;
  value: number;
  ts: string;
  type?: string;
}

// Global state interface
interface DashboardState {
  currentProcessId: string | null;
  recipeOptions: Recipe[];
  components: Component[];
}

// Configuration
const SUPABASE_URL = 'https://yceyfsqusdmcwgkwxcnt.supabase.co';
const SUPABASE_ANON_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InljZXlmc3F1c2RtY3dna3d4Y250Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3MzU5OTYzNzUsImV4cCI6MjA1MTU3MjM3NX0.tiMdbAs79ZOS3PhnEUxXq_g5JLLXG8-o_a7VAIN6cd8';
const MACHINE_ID = 'e3e6e280-0794-459f-84d5-5e468f60746e';

// Type-safe Supabase client
declare const supabase: {
  createClient: (url: string, key: string) => SupabaseClient;
};

class ALDDashboard {
  private sb: SupabaseClient;
  private state: DashboardState;
  private currentProcessId: string | null = null;

  constructor() {
    this.sb = supabase.createClient(SUPABASE_URL, SUPABASE_ANON_KEY);
    this.state = {
      currentProcessId: null,
      recipeOptions: [],
      components: []
    };
  }

  // Type-safe DOM element getter
  private $(id: string): HTMLElement {
    const element = document.getElementById(id);
    if (!element) {
      throw new Error(`Element with id '${id}' not found`);
    }
    return element;
  }

  // Type-safe logging
  private log(message: string): void {
    const logBox = this.$('log') as HTMLDivElement;
    const timestamp = new Date().toLocaleTimeString([], { hour12: false });
    const div = document.createElement('div');
    div.textContent = `${timestamp} - ${message}`;
    logBox.appendChild(div);
    
    // Keep only last 30 log entries
    while (logBox.children.length > 30) {
      logBox.removeChild(logBox.firstChild!);
    }
    logBox.scrollTop = logBox.scrollHeight;
  }

  // Type-safe toast notifications
  private toast(message: string): void {
    const toastEl = this.$('toast') as HTMLDivElement;
    toastEl.textContent = message;
    toastEl.classList.add('show');
    setTimeout(() => toastEl.classList.remove('show'), 2000);
  }

  // Type-safe status updates
  private setStatus(status: string): void {
    const statusText = this.$('status-text') as HTMLSpanElement;
    const statusDot = this.$('status-dot') as HTMLSpanElement;
    
    let text = '⚪ IDLE';
    let dotClass = 'dot-idle';
    
    switch (status.toLowerCase()) {
      case 'running':
        text = '🔵 RUNNING';
        dotClass = 'dot-run';
        break;
      case 'paused':
        text = '⏸ PAUSED';
        dotClass = 'dot-paused';
        break;
      case 'completed':
        text = '✅ DONE';
        dotClass = 'dot-done';
        break;
      case 'failed':
        text = '❌ FAILED';
        dotClass = 'dot-fail';
        break;
    }
    
    statusText.textContent = text;
    statusDot.className = `dot ${dotClass}`;
    
    const pauseBtn = this.$('btn-pause') as HTMLButtonElement;
    const stopBtn = this.$('btn-stop') as HTMLButtonElement;
    pauseBtn.disabled = status !== 'running';
    stopBtn.disabled = status !== 'running';
  }

  // Type-safe process ID management
  private setPid(pid: string | null): void {
    this.currentProcessId = pid;
    const pidShort = this.$('pid-short') as HTMLSpanElement;
    pidShort.textContent = pid ? String(pid).slice(0, 8) : '—';
  }

  // Type-safe recipe loading
  private async loadRecipes(): Promise<Recipe[]> {
    try {
      const { data, error } = await this.sb
        .from('recipes')
        .select('id,name,machine_id')
        .eq('is_public', true)
        .order('name');
        
      if (error) {
        this.log(`recipes error: ${error.message}`);
        return [];
      }
      return data || [];
    } catch (e) {
      this.log(`recipes error: ${(e as Error).message}`);
      return [];
    }
  }

  // Type-safe active process detection
  private async detectActiveProcess(): Promise<{ id: string; status: string } | null> {
    try {
      const machines = await this.sb
        .from('machines')
        .select('current_process_id,status')
        .eq('id', MACHINE_ID)
        .maybeSingle();
        
      if (machines.data && machines.data.current_process_id) {
        return { id: machines.data.current_process_id, status: machines.data.status };
      }
    } catch (e) {
      // Ignore errors
    }
    
    const processExecutions = await this.sb
      .from('process_executions')
      .select('id,status')
      .eq('machine_id', MACHINE_ID)
      .eq('status', 'running')
      .order('updated_at', { ascending: false })
      .limit(1)
      .maybeSingle();
      
    if (processExecutions.error) {
      this.log(`process detect error: ${processExecutions.error.message}`);
      return null;
    }
    
    return processExecutions.data || null;
  }

  // Type-safe process state loading
  private async loadProcessState(pid: string): Promise<void> {
    const out: Array<{ k: string; v: string }> = [];
    
    try {
      const pe = await this.sb
        .from('process_executions')
        .select('id,status,updated_at,recipe_id,recipe_version')
        .eq('id', pid)
        .maybeSingle();
        
      if (pe.data) {
        out.push({ k: 'Status', v: pe.data.status });
        this.setStatus(pe.data.status);
      }
      
      const st = await this.sb
        .from('process_execution_state')
        .select('current_step_name,current_step_type,current_step_index,progress')
        .eq('execution_id', pid)
        .maybeSingle();
        
      if (st.data) {
        const prog = st.data.progress || {};
        const total = prog.total_steps || 0;
        const done = prog.completed_steps || 0;
        
        const stepNow = this.$('step-now') as HTMLSpanElement;
        const stepTotal = this.$('step-total') as HTMLSpanElement;
        stepNow.textContent = String(done);
        stepTotal.textContent = String(total);
        
        out.push({
          k: 'Current Step',
          v: `${st.data.current_step_name || st.data.current_step_type || '-'} (#${(st.data.current_step_index ?? -1) + 1})`
        });
      }
      
      // Render state
      const box = this.$('t2-state') as HTMLDivElement;
      box.innerHTML = '';
      for (const item of out) {
        const div = document.createElement('div');
        div.className = 'kv';
        div.innerHTML = `<div>${item.k}</div><div class="small mono">${item.v ?? '—'}</div>`;
        box.appendChild(div);
      }
    } catch (e) {
      this.log(`process state error: ${(e as Error).message}`);
    }
  }

  // Type-safe step history loading
  private async loadRecentSteps(pid: string): Promise<void> {
    let rows: Array<{ label: string; when: string; extra: string }> = [];
    
    try {
      const res = await this.sb
        .from('step_execution_history')
        .select('*')
        .eq('process_id', pid)
        .order('started_at', { ascending: false })
        .limit(10);
        
      if (!res.error && res.data && res.data.length) {
        rows = res.data.map((r: StepExecution) => ({
          label: r.step_name || r.step_type || 'step',
          when: r.started_at,
          extra: r.ended_at ? 'completed' : 'running'
        }));
      }
    } catch (e) {
      this.log(`step history error: ${(e as Error).message}`);
    }
    
    const box = this.$('t2-steps') as HTMLDivElement;
    box.innerHTML = '';
    for (const r of rows) {
      const div = document.createElement('div');
      div.className = 'kv';
      div.innerHTML = `<div>${r.label}</div><div class="small mono">${new Date(r.when).toLocaleTimeString([], { hour12: false })} · ${String(r.extra).toUpperCase()}</div>`;
      box.appendChild(div);
    }
  }

  // Type-safe telemetry loading
  private async loadTelemetry(): Promise<void> {
    const box = this.$('t1-telemetry') as HTMLDivElement;
    box.innerHTML = '';
    let usedHistory = false;
    let rows: TelemetryData[] = [];
    
    try {
      const res = await this.sb
        .from('parameter_value_history')
        .select('*')
        .order('timestamp', { ascending: false })
        .limit(10);
        
      if (!res.error && res.data && res.data.length) {
        usedHistory = true;
        rows = res.data.map((r: any) => ({
          name: r.parameter_id || r.name,
          value: r.value,
          ts: r.timestamp
        }));
      }
    } catch (e) {
      this.log(`parameter history error: ${(e as Error).message}`);
    }
    
    if (!usedHistory) {
      try {
        const snap = await this.sb
          .from('component_parameters')
          .select('id,current_value,target_value,updated_at,machine_components(name,type)')
          .eq('machine_id', MACHINE_ID);
          
        if (!snap.error && snap.data) {
          rows = snap.data.map((r: any) => ({
            name: r.machine_components?.name || r.id,
            value: r.current_value,
            ts: r.updated_at,
            type: r.machine_components?.type
          }));
        }
      } catch (e) {
        this.log(`component parameters error: ${(e as Error).message}`);
      }
    }
    
    if (rows.length === 0) {
      box.innerHTML = '<div class="small mono">No telemetry data available</div>';
      return;
    }
    
    for (const r of rows.slice(0, 10)) {
      const div = document.createElement('div');
      div.className = 'kv';
      const glyph = r.type === 'valve' ? (Number(r.value) >= 0.999 ? '🟢' : '🔴') : '🧪';
      div.innerHTML = `<div>${glyph} ${r.name}</div><div class="small mono">${(r.value ?? '—')}</div>`;
      box.appendChild(div);
    }
  }

  // Type-safe component loading
  private async loadComponents(): Promise<Component[]> {
    try {
      const { data, error } = await this.sb
        .from('machine_components')
        .select('id,name,type')
        .eq('machine_id', MACHINE_ID)
        .order('name');
        
      if (error) {
        this.log(`components error: ${error.message}`);
        return [];
      }
      return data || [];
    } catch (e) {
      this.log(`components error: ${(e as Error).message}`);
      return [];
    }
  }

  // Type-safe parameter commands loading
  private async loadParamCommands(): Promise<void> {
    try {
      const { data, error } = await this.sb
        .from('parameter_control_commands')
        .select('*')
        .or(`machine_id.eq.${MACHINE_ID},machine_id.is.null`)
        .order('created_at', { ascending: false })
        .limit(10);
        
      if (error) {
        this.log(`parameter commands error: ${error.message}`);
      }
      
      const box = this.$('t3-commands') as HTMLDivElement;
      box.innerHTML = '';
      
      for (const r of (data || [])) {
        const status = r.completed_at ? 'completed' : (r.executed_at ? 'executing' : 'pending');
        const div = document.createElement('div');
        div.className = 'kv';
        div.innerHTML = `<div>${r.parameter_name} → ${r.target_value}</div><div class="small mono"><span class="pill">${status}</span></div>`;
        box.appendChild(div);
      }
    } catch (e) {
      this.log(`parameter commands error: ${(e as Error).message}`);
      const box = this.$('t3-commands') as HTMLDivElement;
      box.innerHTML = '<div class="small mono">No parameter commands found</div>';
    }
  }

  // Type-safe component commands loading (disabled due to RLS)
  private async loadComponentCommands(): Promise<void> {
    const box = this.$('t4-commands') as HTMLDivElement;
    box.innerHTML = '<div class="small mono">Component commands require authentication</div>';
    this.log('Component commands require user authentication due to RLS policies');
  }

  // Type-safe recipe actions
  private async startRecipe(): Promise<void> {
    const recipeSelect = this.$('recipe-select') as HTMLSelectElement;
    const rid = recipeSelect.value;
    
    if (!rid) {
      this.toast('Select a recipe');
      return;
    }
    
    try {
      const { error } = await this.sb
        .from('recipe_commands')
        .insert({ recipe_id: rid, machine_id: MACHINE_ID, command_type: 'start', status: 'pending' });
        
      if (error) {
        this.toast(`⚠️ ${error.message}`);
        return;
      }
      
      this.toast('✅ start sent');
      this.log(`start recipe ${rid}`);
    } catch (e) {
      this.toast(`⚠️ ${(e as Error).message}`);
    }
  }

  private async pauseRecipe(): Promise<void> {
    if (!this.currentProcessId) return;
    
    try {
      const { error } = await this.sb
        .from('recipe_commands')
        .insert({ recipe_id: null, machine_id: MACHINE_ID, command_type: 'pause', status: 'pending' });
        
      if (error) {
        this.toast(`⚠️ ${error.message}`);
      } else {
        this.toast('⏸ pause sent');
        this.log('pause');
      }
    } catch (e) {
      this.toast(`⚠️ ${(e as Error).message}`);
    }
  }

  private async stopRecipe(): Promise<void> {
    if (!this.currentProcessId) return;
    
    try {
      const { error } = await this.sb
        .from('recipe_commands')
        .insert({ recipe_id: null, machine_id: MACHINE_ID, command_type: 'stop', status: 'pending' });
        
      if (error) {
        this.toast(`⚠️ ${error.message}`);
      } else {
        this.toast('🛑 stop sent');
        this.log('stop');
      }
    } catch (e) {
      this.toast(`⚠️ ${(e as Error).message}`);
    }
  }

  // Type-safe parameter sending
  private async sendParameter(): Promise<void> {
    const nameInput = this.$('t3-param-name') as HTMLInputElement;
    const valueInput = this.$('t3-param-value') as HTMLInputElement;
    
    const name = nameInput.value.trim();
    const valRaw = valueInput.value;
    
    if (!name) {
      this.toast('Enter parameter_name');
      return;
    }
    
    const target = valRaw === '' ? null : Number(valRaw);
    
    try {
      const { error } = await this.sb
        .from('parameter_control_commands')
        .insert({ machine_id: MACHINE_ID, parameter_name: name, target_value: target, status: null });
        
      if (error) {
        this.toast(`⚠️ ${error.message}`);
      } else {
        this.toast('✅ parameter command sent');
        this.log(`param ${name} -> ${target}`);
      }
    } catch (e) {
      this.toast(`⚠️ ${(e as Error).message}`);
    }
  }

  // Type-safe component sending (disabled)
  private async sendComponent(): Promise<void> {
    this.toast('⚠️ Component commands require authentication');
    this.log('Component commands require user authentication due to RLS policies');
  }

  // Type-safe realtime subscriptions
  private subscribeRealtime(): void {
    // Process table (status / lifecycle)
    this.sb.channel('proc').on('postgres_changes', {
      event: '*',
      schema: 'public',
      table: 'process_executions',
      filter: `machine_id=eq.${MACHINE_ID}`
    }, async (payload: any) => {
      const row = payload.new || payload.old;
      if (!row) return;
      
      if (this.currentProcessId && row.id !== this.currentProcessId && row.status !== 'running') return;
      
      const ap = await this.detectActiveProcess();
      this.setPid(ap?.id || null);
      
      if (this.currentProcessId) {
        await this.loadProcessState(this.currentProcessId);
        await this.loadRecentSteps(this.currentProcessId);
      }
    }).subscribe();

    // Machines (current_process_id changes)
    this.sb.channel('machines').on('postgres_changes', {
      event: 'UPDATE',
      schema: 'public',
      table: 'machines',
      filter: `id=eq.${MACHINE_ID}`
    }, async (p: any) => {
      const pid = p.new?.current_process_id || null;
      this.setPid(pid);
      
      if (pid) {
        await this.loadProcessState(pid);
        await this.loadRecentSteps(pid);
      } else {
        this.setStatus('idle');
        const t2State = this.$('t2-state') as HTMLDivElement;
        const t2Steps = this.$('t2-steps') as HTMLDivElement;
        const stepNow = this.$('step-now') as HTMLSpanElement;
        const stepTotal = this.$('step-total') as HTMLSpanElement;
        
        t2State.innerHTML = '';
        t2Steps.innerHTML = '';
        stepNow.textContent = '0';
        stepTotal.textContent = '0';
      }
    }).subscribe();

    // Step history
    this.sb.channel('steps-hist').on('postgres_changes', {
      event: '*',
      schema: 'public',
      table: 'step_execution_history'
    }, (p: any) => {
      if (!this.currentProcessId || p.new?.process_id !== this.currentProcessId) return;
      this.loadRecentSteps(this.currentProcessId);
    }).subscribe();

    // Parameter commands
    this.sb.channel('param-cmd').on('postgres_changes', {
      event: '*',
      schema: 'public',
      table: 'parameter_control_commands'
    }, () => this.loadParamCommands()).subscribe();

    // Component parameter updates (for T1 snapshot freshness)
    this.sb.channel('comp-params').on('postgres_changes', {
      event: 'UPDATE',
      schema: 'public',
      table: 'component_parameters',
      filter: `machine_id=eq.${MACHINE_ID}`
    }, () => this.loadTelemetry()).subscribe();
  }

  // Type-safe initialization
  public async init(): Promise<void> {
    try {
      // Load recipes
      this.state.recipeOptions = await this.loadRecipes();
      const recipeSelect = this.$('recipe-select') as HTMLSelectElement;
      recipeSelect.innerHTML = '';
      
      this.state.recipeOptions.forEach(r => {
        const option = document.createElement('option');
        option.value = r.id;
        option.textContent = r.name || r.id;
        recipeSelect.appendChild(option);
      });

      // Load components for Terminal 4
      this.state.components = await this.loadComponents();
      const componentSelect = this.$('t4-component') as HTMLSelectElement;
      componentSelect.innerHTML = '';
      
      this.state.components.forEach(c => {
        if (['valve', 'mfc', 'relay', 'pump', 'heater', 'chamber_heater'].includes((c.type || '').toLowerCase())) {
          const option = document.createElement('option');
          option.value = c.id;
          option.textContent = `${c.name} (${c.type})`;
          componentSelect.appendChild(option);
        }
      });

      // Detect active process
      const ap = await this.detectActiveProcess();
      this.setPid(ap?.id || null);
      this.setStatus(ap?.status || 'idle');
      
      if (this.currentProcessId) {
        await this.loadProcessState(this.currentProcessId);
        await this.loadRecentSteps(this.currentProcessId);
      }

      // Load snapshots
      await this.loadTelemetry();
      await this.loadParamCommands();
      await this.loadComponentCommands();

      // Bind event listeners
      const startBtn = this.$('btn-start') as HTMLButtonElement;
      const pauseBtn = this.$('btn-pause') as HTMLButtonElement;
      const stopBtn = this.$('btn-stop') as HTMLButtonElement;
      const paramSendBtn = this.$('t3-send') as HTMLButtonElement;
      const compSendBtn = this.$('t4-send') as HTMLButtonElement;

      startBtn.addEventListener('click', () => this.startRecipe());
      pauseBtn.addEventListener('click', () => this.pauseRecipe());
      stopBtn.addEventListener('click', () => this.stopRecipe());
      paramSendBtn.addEventListener('click', () => this.sendParameter());
      compSendBtn.addEventListener('click', () => this.sendComponent());

      // Subscribe to realtime updates
      this.subscribeRealtime();
      
      this.log('Dashboard initialized successfully');
    } catch (e) {
      this.log(`Initialization error: ${(e as Error).message}`);
    }
  }
}

// Initialize dashboard when page loads
window.addEventListener('load', () => {
  const dashboard = new ALDDashboard();
  dashboard.init();
});


