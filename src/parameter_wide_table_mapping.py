"""
Parameter ID to Wide Table Column Mapping

This module provides the mapping between parameter UUIDs and 
their corresponding column names in the parameter_readings wide table.

Generated: 2025-10-14
Source: parameter_value_history analysis
"""

# Mapping: parameter_id (UUID) -> column_name in parameter_readings table
PARAMETER_TO_COLUMN_MAP = {
    # Float/Value parameters (10)
    '0d444e71-9767-4956-af7b-787bfa79d080': 'param_0d444e71',
    '2b2e7952-c68e-40eb-ab67-d182fc460821': 'param_2b2e7952',
    '35969620-6843-4130-8eca-d6b62dc74dbf': 'param_35969620',
    '4567ba45-1c86-45d2-bf4d-b1cf306f387a': 'param_4567ba45',
    '500c0329-946e-48c6-9b52-c08e65bd0292': 'param_500c0329',
    '62c28aac-7300-4d3d-85c7-f043c3226439': 'param_62c28aac',
    '8fe19753-ebac-47ce-8461-a713b4e42695': 'param_8fe19753',
    'b6433c16-cb13-4e6a-b5b8-1b1519f0b44b': 'param_b6433c16',
    'dcea6a6e-4349-4287-9b83-4dc72410f6b1': 'param_dcea6a6e',
    'e00b0f66-3c05-48a1-8318-f7d1da5f628e': 'param_e00b0f66',
    
    # Binary parameters (24)
    '1583a79b-079b-4b03-9c64-53b7cfa9d142': 'param_1583a79b',
    '264bfd7f-6076-4b37-be09-dce51bd250c7': 'param_264bfd7f',
    '2cadbb74-6e87-4833-96ae-719561a6c435': 'param_2cadbb74',
    '2d983731-da39-4c5f-8576-10d2189c7743': 'param_2d983731',
    '5adac7f8-816a-45bb-8f6e-ca45b8b4330f': 'param_5adac7f8',
    '5d2cfe0a-151c-4745-9865-cd78125f93d0': 'param_5d2cfe0a',
    '687cf16a-8d3d-45ce-8a94-d20ec07f6dcd': 'param_687cf16a',
    '6c08a1b0-5674-46c1-9fb5-a4c4eca1adf1': 'param_6c08a1b0',
    '6dd9ff97-2e16-4717-96bb-0794575f9425': 'param_6dd9ff97',
    '73f16b0e-6a82-4027-a1cf-66bfa16dba69': 'param_73f16b0e',
    '8195ef00-f478-48ee-9ee0-e43cc265ef42': 'param_8195ef00',
    '832228f7-6f83-490a-b59c-5e151cbe1fb1': 'param_832228f7',
    '846bc6d6-04df-4318-affb-b97cf7238793': 'param_846bc6d6',
    '84e86c3e-7109-4b2c-9064-2aea619e6f64': 'param_84e86c3e',
    '896208fd-0e1f-49a2-9ef6-46ab0d341bee': 'param_896208fd',
    '9917618c-7325-4771-a771-65b42c6d6c73': 'param_9917618c',
    '9c53f4ef-5506-4a45-9718-af8a7b233056': 'param_9c53f4ef',
    '9fc0f785-db56-4752-820a-4aade9962a99': 'param_9fc0f785',
    'b52bef6d-7656-4b9c-8ca6-0244825a7d7b': 'param_b52bef6d',
    'b6ffc326-6445-440f-9642-39e86953b399': 'param_b6ffc326',
    'c6d493fa-adf3-4784-bb80-3425dd276d49': 'param_c6d493fa',
    'ca61248a-9be5-43d2-a204-df6f15ef4fe7': 'param_ca61248a',
    'ea7ad0f0-96ce-4c88-9b9a-bd2cde56d514': 'param_ea7ad0f0',
    'fe5bd37b-742b-4383-b9c4-27693262930c': 'param_fe5bd37b',
    
    # Read-only/sensor parameters (17)
    '4d22ccb3-1e2d-48e1-8ffc-1d8653aea55a': 'param_4d22ccb3',
    '5a7c8e1e-eb2b-4b24-8ea2-a9d1aff699bf': 'param_5a7c8e1e',
    '66d984b9-3503-40c4-bdb7-05bcf1833776': 'param_66d984b9',
    '6fd0eb4a-6179-4cd1-a19a-10bf45e98b92': 'param_6fd0eb4a',
    '77207a4e-07e2-46ea-a2d6-96f144b950df': 'param_77207a4e',
    '79bb8d15-468b-497b-9810-9c1b913f17a8': 'param_79bb8d15',
    '7a657f96-40ea-4f23-804a-635b716418d6': 'param_7a657f96',
    '9562d003-4c64-4914-8e6f-48134ff30389': 'param_9562d003',
    '995f5fcd-cf30-410e-9f58-2f51e8939439': 'param_995f5fcd',
    'a9a93623-feea-4c76-8115-056357c3b516': 'param_a9a93623',
    'aea1df61-6f23-4077-9312-9244db9b3894': 'param_aea1df61',
    'aedcf5fe-ce01-4f03-97a1-025224f8fd4f': 'param_aedcf5fe',
    'af4f85cd-f0a6-46ac-b2c9-5caa1117899b': 'param_af4f85cd',
    'b906ef85-1915-40ba-898c-0595753e645e': 'param_b906ef85',
    'cea58380-2919-483e-b03f-d720b71ecf9f': 'param_cea58380',
    'e583bb2c-c135-4b0f-97e0-8e074a274a44': 'param_e583bb2c',
    'e76932c8-3ba3-4f74-849e-2b692eba6ff4': 'param_e76932c8',
}

# Reverse mapping for queries: column_name -> parameter_id
COLUMN_TO_PARAMETER_MAP = {v: k for k, v in PARAMETER_TO_COLUMN_MAP.items()}


def get_column_name(parameter_id: str) -> str:
    """
    Get the column name for a given parameter ID.
    
    Args:
        parameter_id: UUID of the parameter
        
    Returns:
        Column name in parameter_readings table
        
    Raises:
        KeyError: If parameter_id is not in the mapping
    """
    return PARAMETER_TO_COLUMN_MAP[parameter_id]


def get_parameter_id(column_name: str) -> str:
    """
    Get the parameter ID for a given column name.
    
    Args:
        column_name: Column name from parameter_readings table
        
    Returns:
        UUID of the parameter
        
    Raises:
        KeyError: If column_name is not in the mapping
    """
    return COLUMN_TO_PARAMETER_MAP[column_name]


def get_all_columns() -> list:
    """Get list of all parameter column names."""
    return list(COLUMN_TO_PARAMETER_MAP.keys())


def get_all_parameter_ids() -> list:
    """Get list of all parameter IDs."""
    return list(PARAMETER_TO_COLUMN_MAP.keys())

