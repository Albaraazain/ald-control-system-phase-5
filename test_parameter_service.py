#!/usr/bin/env python3
"""
Test/Demo utility for Terminal 3: Parameter Service

This script demonstrates the parameter service functionality including:
- Parameter validation
- Terminal 1 coordination
- Database communication
- Health monitoring

Usage:
    python test_parameter_service.py --create-test-commands
    python test_parameter_service.py --health-check
    python test_parameter_service.py --coordination-status
"""
import asyncio
import argparse
import os
import sys
from datetime import datetime
from typing import List, Dict, Any

# Add project root to path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

from src.log_setup import get_service_logger, set_log_level
from src.config import MACHINE_ID
from src.db import get_supabase
from src.terminal_coordination.parameter_coordinator import parameter_coordinator

logger = get_service_logger('parameter_control')


async def create_test_parameter_commands(count: int = 3) -> List[str]:
    """Create test parameter control commands for testing Terminal 3"""
    try:
        supabase = get_supabase()

        # Get some actual parameters from the database
        logger.info("Fetching available parameters for test commands...")
        params_result = supabase.table('component_parameters').select('id, name, parameter_name, data_type, min_value, max_value').limit(10).execute()

        if not params_result.data:
            logger.warning("No parameters found in database, creating fallback test commands")
            test_commands = [
                {
                    "parameter_name": "test_pump_1",
                    "target_value": 1,
                    "machine_id": MACHINE_ID,
                    "data_type": "binary"
                },
                {
                    "parameter_name": "test_mfc_flow_rate",
                    "target_value": 150.0,
                    "machine_id": MACHINE_ID,
                    "data_type": "float"
                },
                {
                    "parameter_name": "test_temperature_setpoint",
                    "target_value": 250.0,
                    "machine_id": MACHINE_ID,
                    "data_type": "float"
                }
            ]
        else:
            # Create commands using real parameters
            test_commands = []
            for i, param in enumerate(params_result.data[:count]):
                # Generate appropriate test value based on parameter constraints
                param_name = param.get('parameter_name') or param['name']
                data_type = param.get('data_type', 'float')
                min_val = param.get('min_value')
                max_val = param.get('max_value')

                if data_type == 'binary':
                    target_value = 1
                elif data_type == 'integer':
                    if min_val is not None and max_val is not None:
                        target_value = int((min_val + max_val) / 2)
                    else:
                        target_value = 100
                else:  # float
                    if min_val is not None and max_val is not None:
                        target_value = (min_val + max_val) / 2
                    else:
                        target_value = 123.45

                test_commands.append({
                    "parameter_name": param_name,
                    "component_parameter_id": param['id'],
                    "target_value": target_value,
                    "machine_id": MACHINE_ID,
                    "data_type": data_type,
                    "timeout_ms": 15000
                })

        logger.info(f"Creating {len(test_commands)} test parameter commands...")

        result = (
            supabase.table("parameter_control_commands")
            .insert(test_commands)
            .execute()
        )

        if result.data:
            command_ids = [cmd['id'] for cmd in result.data]
            logger.info(f"Successfully created {len(result.data)} test parameter commands:")
            for cmd in result.data:
                param_id = cmd.get('component_parameter_id', 'N/A')
                param_name = cmd['parameter_name']
                target_val = cmd['target_value']
                logger.info(f"  Command {cmd['id']}: {param_name} = {target_val} (ID: {param_id})")
            return command_ids
        else:
            logger.error("Failed to create test parameter commands")
            return []

    except Exception as e:
        logger.error(f"Error creating test parameter commands: {str(e)}", exc_info=True)
        return []


async def check_coordination_status() -> Dict[str, Any]:
    """Check the status of Terminal 3 coordination with Terminal 1"""
    try:
        logger.info("Checking Terminal 3 coordination status...")

        # Get coordination health
        health = await parameter_coordinator.get_coordination_health()
        logger.info(f"Coordination Health: {health}")

        # Get pending requests
        pending = await parameter_coordinator.get_pending_requests()
        logger.info(f"Pending Requests: {len(pending)}")

        if pending:
            logger.info("Pending coordination requests:")
            for req in pending:
                logger.info(f"  Request {req['id']}: {req['parameter_name']} = {req['target_value']} (Status: {req['status']})")

        return {
            "health": health,
            "pending_requests": len(pending),
            "pending_details": pending
        }

    except Exception as e:
        logger.error(f"Error checking coordination status: {str(e)}", exc_info=True)
        return {"error": str(e)}


async def test_parameter_validation():
    """Test parameter validation functionality"""
    try:
        logger.info("Testing parameter validation...")

        # Import validation function
        from parameter_service import validate_parameter_request

        # Test valid parameter
        valid_command = {
            "parameter_name": "test_parameter",
            "target_value": 100.0,
            "component_parameter_id": None
        }

        result = await validate_parameter_request(valid_command)
        logger.info(f"Validation test result: {result}")

        return result

    except Exception as e:
        logger.error(f"Error testing parameter validation: {str(e)}", exc_info=True)
        return {"valid": False, "error": str(e)}


async def monitor_command_processing(command_ids: List[str], timeout: int = 60):
    """Monitor the processing of parameter commands"""
    try:
        logger.info(f"Monitoring {len(command_ids)} parameter commands for {timeout} seconds...")

        supabase = get_supabase()
        start_time = asyncio.get_event_loop().time()

        while asyncio.get_event_loop().time() - start_time < timeout:
            # Check command status
            result = (
                supabase.table("parameter_control_commands")
                .select("id, parameter_name, target_value, executed_at, completed_at, error_message")
                .in_("id", command_ids)
                .execute()
            )

            if result.data:
                completed = []
                pending = []

                for cmd in result.data:
                    if cmd.get('completed_at'):
                        completed.append(cmd)
                    else:
                        pending.append(cmd)

                logger.info(f"Status: {len(completed)} completed, {len(pending)} pending")

                if len(completed) == len(command_ids):
                    logger.info("All commands completed!")
                    for cmd in completed:
                        status = "SUCCESS" if not cmd.get('error_message') else f"FAILED: {cmd['error_message']}"
                        logger.info(f"  {cmd['parameter_name']} = {cmd['target_value']}: {status}")
                    break

            await asyncio.sleep(2)

        if asyncio.get_event_loop().time() - start_time >= timeout:
            logger.warning(f"Monitoring timeout after {timeout} seconds")

    except Exception as e:
        logger.error(f"Error monitoring command processing: {str(e)}", exc_info=True)


async def cleanup_test_data():
    """Clean up old test data"""
    try:
        logger.info("Cleaning up old test data...")

        # Cleanup old coordination requests
        await parameter_coordinator.cleanup_old_requests(max_age_hours=1)

        # Cleanup old test commands (older than 1 hour)
        supabase = get_supabase()
        result = (
            supabase.table("parameter_control_commands")
            .delete()
            .eq("machine_id", MACHINE_ID)
            .like("parameter_name", "test_%")
            .lt("created_at", datetime.utcnow().isoformat())
            .execute()
        )

        if result.data:
            logger.info(f"Cleaned up {len(result.data)} old test commands")
        else:
            logger.info("No old test commands to clean up")

    except Exception as e:
        logger.error(f"Error cleaning up test data: {str(e)}", exc_info=True)


async def main():
    """Main function for test utility"""
    parser = argparse.ArgumentParser(description="Terminal 3 Parameter Service Test Utility")
    parser.add_argument("--create-test-commands", action="store_true", help="Create test parameter commands")
    parser.add_argument("--count", type=int, default=3, help="Number of test commands to create")
    parser.add_argument("--health-check", action="store_true", help="Check coordination health")
    parser.add_argument("--coordination-status", action="store_true", help="Check coordination status")
    parser.add_argument("--test-validation", action="store_true", help="Test parameter validation")
    parser.add_argument("--monitor", action="store_true", help="Monitor command processing")
    parser.add_argument("--cleanup", action="store_true", help="Clean up old test data")
    parser.add_argument("--log-level", choices=["DEBUG", "INFO", "WARNING", "ERROR"], default="INFO", help="Log level")

    args = parser.parse_args()

    # Set log level
    set_log_level(args.log_level)

    logger.info("Starting Terminal 3 Parameter Service Test Utility")
    logger.info(f"Machine ID: {MACHINE_ID}")

    try:
        if args.create_test_commands:
            command_ids = await create_test_parameter_commands(args.count)
            if command_ids and args.monitor:
                await monitor_command_processing(command_ids)

        if args.health_check or args.coordination_status:
            status = await check_coordination_status()
            print(f"\nCoordination Status Summary:")
            print(f"  Health: {status.get('health', {}).get('coordination_healthy', 'Unknown')}")
            print(f"  Success Rate: {status.get('health', {}).get('success_rate_percent', 0)}%")
            print(f"  Pending Requests: {status.get('pending_requests', 0)}")

        if args.test_validation:
            validation_result = await test_parameter_validation()
            print(f"\nValidation Test Result: {validation_result}")

        if args.cleanup:
            await cleanup_test_data()

        logger.info("Test utility completed successfully")

    except Exception as e:
        logger.error(f"Error in test utility: {str(e)}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())