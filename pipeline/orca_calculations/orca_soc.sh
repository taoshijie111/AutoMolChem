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

# Create ORCA scratch directory
ORCA_SCRATCH=$(mktemp -d /tmp/orca__XXXXXX)
function finish {
  rm -rf "$ORCA_SCRATCH"
}
trap finish EXIT
echo "Running ORCA from $ORCA_SCRATCH"

# Step 1: Run s0_opt.inp first
if [ -f "s0_opt.inp" ]; then
    echo "Step 1: Processing s0_opt.inp"
    cp "s0_opt.inp" $ORCA_SCRATCH
    cp *.xyz $ORCA_SCRATCH 2>/dev/null || true  # Copy existing xyz files if any, ignore if none exist
    cd $ORCA_SCRATCH
    /public/home/huangm/source/orca_6_0_0_shared_openmpi416/orca "s0_opt.inp" > "s0_opt.output"
    
    # Copy back s0_opt results including the generated xyz file
    cp "s0_opt.inp" $SLURM_SUBMIT_DIR
    cp "s0_opt.output" $SLURM_SUBMIT_DIR
    cp "s0_opt.hess" $SLURM_SUBMIT_DIR
    cp "s0_opt.xyz" $SLURM_SUBMIT_DIR 2>/dev/null || echo "Warning: s0_opt.xyz not found"
    
    cd $SLURM_SUBMIT_DIR
    echo "Step 1: s0_opt.inp completed"
else
    echo "Error: s0_opt.inp not found!"
    exit 1
fi

# Step 2: Run soc_cal.inp using the generated s0_opt.xyz
if [ -f "soc_cal.inp" ]; then
    echo "Step 2: Processing soc_cal.inp"
    cp "soc_cal.inp" $ORCA_SCRATCH
    cp "s0_opt.xyz" $ORCA_SCRATCH  # Copy the freshly generated xyz file
    cp *.xyz $ORCA_SCRATCH 2>/dev/null || true  # Copy any other xyz files
    cd $ORCA_SCRATCH
    /public/home/huangm/source/orca_6_0_0_shared_openmpi416/orca "soc_cal.inp" > "soc_cal.output"
    
    # Copy back soc_cal results
    cp "soc_cal.inp" $SLURM_SUBMIT_DIR
    cp "soc_cal.output" $SLURM_SUBMIT_DIR
    
    cd $SLURM_SUBMIT_DIR
    echo "Step 2: soc_cal.inp completed"
else
    echo "Error: soc_cal.inp not found!"
    exit 1
fi

echo "All ORCA jobs completed."


