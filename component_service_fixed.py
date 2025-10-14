async def process_component_command(command: Dict[str, Any]):
    """
    Process a component control command (turn_on/turn_off operations).

    Args:
        command: Command data from component_control_commands table
                Required fields: id, component_id, action
    """
    start_time = time.time()

    # Extract component command fields (NOT parameter fields)
    command_id = command['id']
    component_id = command['component_id']
    action = command['action']  # 'turn_on' or 'turn_off'
    reason = command.get('reason', 'manual')
    machine_id = command.get('machine_id', 'global')

    logger.info(f"⚙️ [COMPONENT START] Command ID: {command_id} | Component ID: {component_id} | Action: {action} | Reason: {reason} | Machine: {machine_id}")
    logger.debug(f"🔍 [COMPONENT DETAILS] Full command data: {command}")

    supabase = get_supabase()

    try:
        # Ensure PLC is connected, attempt reconnection if needed
        if not await ensure_plc_connection():
            # Track retry count
            retry_count = state.failed_commands.get(command_id, 0) + 1
            state.failed_commands[command_id] = retry_count

            # Calculate backoff delay
            backoff_delay = state.retry_delay_base * (2 ** (retry_count - 1))

            error_msg = f"PLC is not connected (retry {retry_count}/{state.max_retries})"
            logger.warning(f"{error_msg}. Will retry in {backoff_delay} seconds")

            # Record the error but keep as uncompleted for retry
            if retry_count < state.max_retries:
                supabase.table("component_control_commands").update({
                    "error_message": error_msg
                }).eq("id", command_id).execute()

                # Remove from processed to allow retry
                state.processed_commands.discard(command_id)

                # Wait before allowing retry
                await asyncio.sleep(backoff_delay)
                return
            else:
                raise RuntimeError(f"PLC connection failed after {state.max_retries} attempts")

        # Load component metadata from machine_components table
        logger.debug(f"🔍 [COMPONENT LOOKUP] Fetching component metadata for ID: {component_id}")
        component_response = supabase.table('machine_components').select('*').eq('id', component_id).execute()

        if not component_response.data or len(component_response.data) == 0:
            raise ValueError(f"Component {component_id} not found in machine_components table")

        component_data = component_response.data[0]
        component_type = component_data.get('type') or component_data.get('component_type')
        component_name = component_data.get('name')
        modbus_address = component_data.get('modbus_address') or component_data.get('write_modbus_address')

        logger.info(f"📦 [COMPONENT] Type: {component_type}, Name: {component_name}, Address: {modbus_address}")

        # Validate action
        if action not in ['turn_on', 'turn_off']:
            raise ValueError(f"Invalid action: {action}. Must be 'turn_on' or 'turn_off'")

        # Convert action to boolean for PLC write
        target_state = (action == 'turn_on')  # True for on, False for off
        logger.debug(f"🔢 [ACTION CONVERSION] Action '{action}' -> Boolean: {target_state}")

        success = False

        if modbus_address is not None:
            # Write component state to PLC coil
            logger.debug(f"✏️ [PLC WRITE START] Writing {action} (boolean={target_state}) to coil address {modbus_address}...")

            # Handle both RealPLC (with communicator) and SimulationPLC (direct methods)
            if hasattr(plc_manager.plc, 'communicator'):
                # RealPLC with communicator
                if hasattr(plc_manager.plc.communicator, 'write_coil'):
                    logger.debug(f"✏️ [PLC WRITE] Writing boolean {target_state} to coil {modbus_address}")
                    success = plc_manager.plc.communicator.write_coil(modbus_address, target_state)
                    if success:
                        logger.info(f"✅ [PLC WRITE SUCCESS] Component {component_name} set to {action} at coil {modbus_address}")
                    else:
                        logger.error(f"❌ [PLC WRITE FAILED] Failed to write {action} to component {component_name} at coil {modbus_address}")
                else:
                    logger.error(f"❌ [PLC INTERFACE] PLC communicator doesn't support write_coil")
                    success = False
            else:
                # SimulationPLC with direct methods
                if hasattr(plc_manager.plc, 'write_coil'):
                    logger.debug(f"✏️ [PLC WRITE] Writing boolean {target_state} to coil {modbus_address}")
                    success = await plc_manager.plc.write_coil(modbus_address, target_state)
                    if success:
                        logger.info(f"✅ [PLC WRITE SUCCESS] Component {component_name} set to {action} at coil {modbus_address}")
                    else:
                        logger.error(f"❌ [PLC WRITE FAILED] Failed to write {action} to component {component_name} at coil {modbus_address}")
                else:
                    logger.error(f"❌ [PLC INTERFACE] PLC doesn't support write_coil")
                    success = False
        else:
            raise ValueError(f"Component {component_name} (ID: {component_id}) has no modbus address configured in machine_components table")

        # Update command status based on result
        if success:
            processing_time_ms = int((time.time() - start_time) * 1000)
            logger.info(f"✅ [COMMAND SUCCESS] Component command completed successfully")
            logger.info(f"📊 [PERFORMANCE] Command ID: {command_id} | Component: {component_name} | Action: {action} | Duration: {processing_time_ms}ms")
            await finalize_component_command(command_id, success=True)

            # Update component.is_activated in machine_components table
            supabase.table('machine_components').update({
                'is_activated': target_state
            }).eq('id', component_id).execute()

            logger.info(f"✅ [COMPONENT UPDATE] Component {component_name} is_activated set to {target_state}")
        else:
            processing_time_ms = int((time.time() - start_time) * 1000)
            logger.error(f"❌ [COMMAND FAILED] Component command failed")
            logger.error(f"📊 [PERFORMANCE] Command ID: {command_id} | Component: {component_name} | Action: {action} | Duration: {processing_time_ms}ms")
            await finalize_component_command(command_id, success=False, error_message="PLC write operation failed")

    except Exception as e:
        error_msg = str(e)
        logger.error(f"❌ [COMPONENT ERROR] {error_msg}")

        # Track retry count
        retry_count = state.failed_commands.get(command_id, 0) + 1
        state.failed_commands[command_id] = retry_count

        if retry_count < state.max_retries:
            error_msg_with_retry = f"{error_msg} (retry {retry_count}/{state.max_retries})"

            # Record the error and allow retry after backoff
            supabase.table("component_control_commands").update({
                "error_message": error_msg_with_retry
            }).eq("id", command_id).execute()

            # Remove from processed to allow retry
            state.processed_commands.discard(command_id)

            # Wait with exponential backoff
            backoff_delay = state.retry_delay_base * (2 ** (retry_count - 1))
            await asyncio.sleep(backoff_delay)
        else:
            # Non-PLC errors or exceeded retries
            processing_time_ms = int((time.time() - start_time) * 1000)
            logger.error(f"❌ COMPONENT COMMAND FAILED - ID: {command_id} | Component: {component_name} | Action: {action} | Status: ERROR | Duration: {processing_time_ms}ms")
            await finalize_component_command(command_id, success=False, error_message=f"{error_msg} (after {retry_count} attempts)")


