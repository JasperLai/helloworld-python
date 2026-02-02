# HelloWorld Python

A Python project containing a hello world example and a forex cashflow conversion tool.

## Usage

To run the basic program:

```bash
python main.py
```

To run the forex cashflow conversion tool:

```bash
python forex_cashflow_tool/cashflow_converter.py --input <交易明细CSV文件> [其他选项]
```

## Forex Cashflow Conversion Tool

The forex cashflow conversion tool processes foreign exchange transaction details and generates cashflow reports. It supports various FX transaction types (Spot/FX Swap/Outright Forward) and calculates P&L based on forward points.

### Features
- Processes Spot, FX Swap, and Outright Forward transactions
- Supports multiple currencies with proper decimal handling
- Generates aggregated cashflow reports in CSV and HTML formats
- Includes forward points interpolation functionality
- Provides filtering capabilities by portfolio/folder

### Command Line Options
- `--input`: Path to the transaction detail CSV file (required)
- `--template`: HTML template file path
- `--out_csv`: Output CSV filename for aggregated cashflows
- `--out_html`: Output HTML filename for cashflow report
- `--points_csv`: Path to forward points CSV file
- `--ignore_folders`: Comma-separated list of folders to ignore
- `--filter_config`: Path to JSON filter configuration file
- `--out_dir`: Output directory (default: generatedFile)

## Original Features

- Prints "Hello, World!" to the console
- Greets a specified person by name
