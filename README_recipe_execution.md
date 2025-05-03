# Recipe Execution Guide

This document explains how to create and execute a simple recipe in the system.

## Simple Valve Recipe

The included SQL script `simple_valve_recipe.sql` creates a basic recipe that opens a valve for 5 seconds. This can be used for testing valve functionality without complex setup.

### Recipe Structure

The recipe consists of:
1. A record in the `recipes` table
2. A single step in the `recipe_steps` table
3. A command in the `recipe_commands` table to trigger execution

### How to Execute the Recipe

#### 1. Add the Recipe to the Database

Run the SQL script to add the recipe to your database:

```bash
psql -U your_username -d your_database -f simple_valve_recipe.sql
```

Or use your database management tool to run the SQL script.

#### 2. Execute the Recipe

There are two ways to execute the recipe:

**Option A: Automatic Execution**
- Start the application with `python main.py`
- The application will automatically detect and process pending recipe commands
- The recipe will execute and open valve 1 for 5 seconds

**Option B: Programmatic Execution**
- Create a simple script to start the recipe:

```python
import asyncio
from recipe_flow.starter import start_recipe

async def run_recipe():
    # Define the parameters
    recipe_id = "3f9e55ec-95f6-4d6a-a214-a6de7e8df6c3"  # ID from SQL script
    parameters = {
        "recipe_id": recipe_id,
        "operator_id": "4365609c-394e-4197-8c38-6dc3b846c60e"  # ID from SQL script
    }
    
    # Start the recipe (command_id is arbitrary as we're calling directly)
    await start_recipe(999, parameters)
    
    # Wait for recipe to finish (adjust time as needed)
    print("Recipe started, waiting for completion...")
    await asyncio.sleep(10)
    print("Recipe execution should be complete")

# Run the async function
asyncio.run(run_recipe())
```

### Modifying the Recipe

To modify the recipe:

1. Change the valve number by editing the `parameters` field in the SQL for `recipe_steps`
2. Adjust the duration by changing `duration_ms` in the parameters
3. Add more steps by adding more rows to the `recipe_steps` table with increasing `sequence_number` values

### Recipe Step Types

The system supports several types of recipe steps:

1. **valve** - Opens a valve for a specified duration
   ```json
   {"valve_number": 1, "duration_ms": 5000}
   ```

2. **purge** - Executes a purge operation for a specified duration
   ```json
   {"duration_ms": 10000}
   ```

3. **set parameter** - Sets a component parameter to a specific value
   ```json
   {"parameter_id": "108b3663-ac43-4d4b-af14-41f13a7b500f", "value": 250}
   ```

4. **loop** - Repeats a sequence of steps
   ```json
   {"repeat_count": 5, "child_steps": [1, 2, 3]}
   ```

### Troubleshooting

If the recipe doesn't execute:

1. Check that the machine status is 'idle' in the database
2. Verify the operator_id exists and is valid
3. Ensure the valve_number specified in the recipe exists in your database
4. Check the application logs for error messages

## Viewing Recipe Execution

To see the status of recipe execution:

1. Check the `process_executions` table for current execution details
2. Look at the `machine_state` table to see the current machine state
3. Monitor the application logs for step-by-step execution updates