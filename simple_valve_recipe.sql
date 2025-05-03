-- Simple Valve Recipe SQL Script
-- This script creates a recipe that opens a valve for a few seconds

-- Generate UUIDs for our entities
-- In a real database you would use the UUID generation function
-- Here we're just hardcoding some UUIDs for simplicity
-- Recipe UUID: 3f9e55ec-95f6-4d6a-a214-a6de7e8df6c3
-- Recipe Step UUID: a2b59862-3e58-4d78-b567-a8c145a2bcce

-- First, create the recipe
INSERT INTO recipes (
  id, 
  name, 
  description, 
  version, 
  created_at, 
  updated_at, 
  created_by, 
  chamber_temperature_set_point, 
  pressure_set_point, 
  status
) VALUES (
  '3f9e55ec-95f6-4d6a-a214-a6de7e8df6c3', -- id
  'Simple Valve Test Recipe', -- name
  'A simple recipe that opens valve 1 for 5 seconds', -- description
  '1.0', -- version
  NOW(), -- created_at
  NOW(), -- updated_at
  NULL, -- created_by (optional)
  NULL, -- chamber_temperature_set_point (optional)
  NULL, -- pressure_set_point (optional)
  'active' -- status
);

-- Now create the recipe step that opens a valve
INSERT INTO recipe_steps (
  id, 
  recipe_id, 
  name, 
  type, 
  parameters, 
  sequence_number, 
  created_at, 
  updated_at
) VALUES (
  'a2b59862-3e58-4d78-b567-a8c145a2bcce', -- id
  '3f9e55ec-95f6-4d6a-a214-a6de7e8df6c3', -- recipe_id (must match the recipe ID above)
  'Open Valve 1', -- name
  'valve', -- type
  '{"valve_number": 1, "duration_ms": 5000}', -- parameters as JSON
  1, -- sequence_number (first step)
  NOW(), -- created_at
  NOW() -- updated_at
);

-- Create a sample recipe command to start the recipe
-- This is optional - you can also trigger this programmatically
INSERT INTO recipe_commands (
  id, 
  type, 
  parameters, 
  status, 
  created_at, 
  updated_at, 
  executed_at, 
  error_message, 
  machine_id
) VALUES (
  '2', -- id (assuming 1 is already used based on the existing file)
  'start_recipe', -- type
  '{"recipe_id": "3f9e55ec-95f6-4d6a-a214-a6de7e8df6c3", "operator_id": "4365609c-394e-4197-8c38-6dc3b846c60e"}', -- parameters
  'pending', -- status
  NOW(), -- created_at
  NOW(), -- updated_at
  NULL, -- executed_at
  NULL, -- error_message
  'e3e6e280-0794-459f-84d5-5e468f60746e' -- machine_id (using the same as in the example)
);

-- To execute the recipe, you would:
-- 1. Run this SQL script to add the recipe to the database
-- 2. Either:
--    a. Run the application which will pick up and process the pending recipe_command
--    b. Manually trigger the recipe execution from your application