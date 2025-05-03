import pandas as pd

# Read the Excel file
xlsx_file = "Atomicoat ModbusAddress03.05.2025.xlsx"
output_csv = "Atomicoat_ModbusAddress03.05.2025.csv"

# Read Excel file
df = pd.read_excel(xlsx_file)

# Save to CSV
df.to_csv(output_csv, index=False)
print(f"Successfully converted {xlsx_file} to {output_csv}")