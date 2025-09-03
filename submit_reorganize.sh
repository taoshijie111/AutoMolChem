#!/bin/bash
#SBATCH --job-name=reorganize_conformers
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=10
#SBATCH --mem=32GB
#SBATCH --time=12:00:00
#SBATCH --partition=hfacexclu08

# Usage: sbatch submit_reorganize.sh <conformer_output_directory>
# Reorganizes conformer files with 10 parallel processes

set -e

# Check arguments
if [ $# -ne 1 ]; then
    echo "Usage: sbatch submit_reorganize.sh <conformer_output_directory>"
    echo "  conformer_output_directory: Directory containing batch_* subdirectories"
    exit 1
fi

CONFORMER_OUTPUT_DIR="$1"

# Validate directory exists
if [ ! -d "$CONFORMER_OUTPUT_DIR" ]; then
    echo "ERROR: Directory not found: $CONFORMER_OUTPUT_DIR"
    exit 1
fi

# Get script path (assuming it's in the same directory)
REORGANIZE_SCRIPT="reorganize_conformer_files.sh"

# Validate script exists
if [ ! -f "$REORGANIZE_SCRIPT" ]; then
    echo "ERROR: Reorganization script not found: $REORGANIZE_SCRIPT"
    exit 1
fi

# Make sure script is executable
chmod +x "$REORGANIZE_SCRIPT"

# Setup environment
export PYTHONUNBUFFERED=1
export OMP_NUM_THREADS=$SLURM_CPUS_PER_TASK

# Show job information
echo "=== Slurm Job Information ==="
echo "Job ID: $SLURM_JOB_ID"
echo "Job Name: $SLURM_JOB_NAME"
echo "Node: $SLURMD_NODENAME"
echo "CPUs per task: $SLURM_CPUS_PER_TASK"
echo "Memory: 32GB"
echo "==========================="
echo ""

# Run reorganization with 10 parallel processes
echo "Starting reorganization of: $CONFORMER_OUTPUT_DIR"
echo "Using $SLURM_CPUS_PER_TASK parallel processes"
echo ""

start_time=$(date +%s)

# Execute the reorganization script
./"$REORGANIZE_SCRIPT" "$CONFORMER_OUTPUT_DIR" "$SLURM_CPUS_PER_TASK"

end_time=$(date +%s)
duration=$((end_time - start_time))

echo ""
echo "=== Job Completion ==="
echo "Total execution time: ${duration} seconds"
echo "Job completed successfully at: $(date)"
echo "======================"