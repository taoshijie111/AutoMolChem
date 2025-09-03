#!/bin/bash
#SBATCH --job-name=xtb_opt
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=4GB
#SBATCH --time=48:00:00
#SBATCH --partition=hfacexclu08

# Usage: sbatch submit_single.sh <json_file>
# <json_file> contains task data with molecule directories and names

set -e

# Check arguments
if [ $# -lt 1 ]; then
    echo "Usage: sbatch submit_single.sh <json_file>"
    echo "  json_file: JSON file containing task data"
    exit 1
fi

JSON_FILE="$1"

# Validate JSON file exists
if [ ! -f "$JSON_FILE" ]; then
    echo "ERROR: JSON file not found: $JSON_FILE"
    exit 1
fi

# Get script path
XTB_SCRIPT="xtb_single_optimization.py"

# Validate script exists
if [ ! -f "$XTB_SCRIPT" ]; then
    echo "ERROR: XTB optimization script not found: $XTB_SCRIPT"
    exit 1
fi

# Setup environment
export PYTHONUNBUFFERED=1
export OMP_NUM_THREADS=$SLURM_CPUS_PER_TASK
export MKL_NUM_THREADS=$SLURM_CPUS_PER_TASK

# Run XTB optimization with JSON input
echo "Processing JSON file: $JSON_FILE"
python3 "$XTB_SCRIPT" --json "$JSON_FILE" --verbose

# Clean up temporary JSON file after processing
if [[ "$JSON_FILE" == *"slurm_xtb_task_"*.json ]]; then
    echo "Cleaning up temporary file: $JSON_FILE"
    rm -f "$JSON_FILE"
fi