#!/bin/bash
#SBATCH --job-name=omol_opt
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --gres=gpu:1
#SBATCH --time=unlimited
#SBATCH --partition=a800

# Usage: sbatch submit_omol_single.sh <file_list> <fmax> <steps> [output_dir] [--verbose]
# <file_list> contains list of conformer directories to optimize

set -e

# Check arguments
if [ $# -lt 3 ]; then
    echo "Usage: sbatch submit_omol_single.sh <file_list> <fmax> <steps> [output_dir] [--verbose]"
    echo "  file_list: Text file containing list of conformer directories"
    echo "  fmax: Optimization threshold (e.g., 5e-4)"
    echo "  steps: Maximum optimization steps (e.g., 10000)"
    echo "  output_dir: Optional output directory"
    echo "  --verbose: Optional verbose flag"
    exit 1
fi

FILE_LIST="$1"
FMAX="$2"
STEPS="$3"
OUTPUT_DIR="$4"
VERBOSE="$5"

# Validate file list exists
if [ ! -f "$FILE_LIST" ]; then
    echo "ERROR: File list not found: $FILE_LIST"
    exit 1
fi

# Get script path
OMOL_SCRIPT="omol_optimize.py"

# Validate script exists
if [ ! -f "$OMOL_SCRIPT" ]; then
    echo "ERROR: OMOL optimization script not found: $OMOL_SCRIPT"
    exit 1
fi

# Setup environment
export PYTHONUNBUFFERED=1
export OMP_NUM_THREADS=$SLURM_CPUS_PER_TASK
export MKL_NUM_THREADS=$SLURM_CPUS_PER_TASK

# Activate conda environment
source activate uma

# Print GPU allocation information
echo "=== GPU Allocation Info ==="
echo "CUDA_VISIBLE_DEVICES: $CUDA_VISIBLE_DEVICES"
echo "SLURM_GPUS_ON_NODE: $SLURM_GPUS_ON_NODE"
export https_proxy=10.11.1.10:46813

# Build command
CMD_ARGS=(
    --file_list "$FILE_LIST"
    --device "cuda"
    --fmax "$FMAX"
    --steps "$STEPS"
)

if [ -n "$OUTPUT_DIR" ] && [ "$OUTPUT_DIR" != "--verbose" ]; then
    CMD_ARGS+=(--output_dir "$OUTPUT_DIR")
fi

if [ "$VERBOSE" = "--verbose" ] || [ "$OUTPUT_DIR" = "--verbose" ]; then
    CMD_ARGS+=(--verbose)
fi

# Run OMOL optimization
echo "Processing file list: $FILE_LIST"
echo "Command: python3 $OMOL_SCRIPT ${CMD_ARGS[@]}"
python3 "$OMOL_SCRIPT" "${CMD_ARGS[@]}"

# Clean up temporary file list after processing
if [[ "$FILE_LIST" == *"omol_filelist_"*.txt ]]; then
    echo "Cleaning up temporary file: $FILE_LIST"
    rm -f "$FILE_LIST"
fi
