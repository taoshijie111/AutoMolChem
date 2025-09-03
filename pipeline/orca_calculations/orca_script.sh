#!/bin/sh

#SBATCH --job-name=orca              # Job name
#SBATCH --nodes=1                    # Number of nodes
#SBATCH --ntasks-per-node=1         # Number of cores (or tasks) per node
#SBATCH --cpus-per-task=4  
#SBATCH --time=24:00:00              # Time limit in HH:MM:SS
#SBATCH --partition=hfacexclu08   

source ~/anaconda3/etc/profile.d/conda.sh
conda activate uma

export OMPI_MCA_hwloc_base_binding_policy=none
export OMPI_MCA_rmaps_base_oversubscribe=1
export OMP_NUM_THREADS=1
export LD_LIBRARY_PATH=~/anaconda3/envs/uma/lib:$LD_LIBRARY_PATH

echo "Working directory is $SLURM_SUBMIT_DIR"
cd $SLURM_SUBMIT_DIR
echo "Running on host $(hostname)"
echo "Time is $(date)"
echo "Directory is $(pwd)"
echo "This jobs runs on the following processors:"
echo $SLURM_JOB_NODELIST
NPROCS=$SLURM_NTASKS
echo "This job has allocated $NPROCS cores"

# Run ORCA for all *.inp files from a temporary directory
ORCA_SCRATCH=$(mktemp -d /tmp/orca__XXXXXX)

function finish {
  rm -rf "$ORCA_SCRATCH"
}
trap finish EXIT

echo "Running ORCA from $ORCA_SCRATCH"

# Find the single .inp file
input_file=$(ls *.inp 2>/dev/null | head -1)

if [ -f "$input_file" ]; then
  echo "Processing $input_file"
  cp "$input_file" $ORCA_SCRATCH
  cp *.xyz $ORCA_SCRATCH 2>/dev/null || true  # Copy xyz files if any exist
  cd $ORCA_SCRATCH
  /public/home/huangm/source/orca_6_0_0_shared_openmpi416/orca "$input_file" > "${input_file%.inp}.output"
  # Copy back all relevant ORCA files
  cp "$input_file" $SLURM_SUBMIT_DIR
  cp "${input_file%.inp}.output" $SLURM_SUBMIT_DIR
  cd $SLURM_SUBMIT_DIR
else
  echo "No input file found."
fi

echo "All ORCA jobs completed."

