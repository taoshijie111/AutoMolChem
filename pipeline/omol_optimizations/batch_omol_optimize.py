#!/usr/bin/env python3
"""
Batch OMOL optimization orchestrator that submits individual SLURM jobs.
Distributes molecular optimization tasks across multiple GPU jobs using SLURM.
"""

import argparse
import subprocess
import sys
import time
from pathlib import Path
from typing import List, Dict, Tuple
import uuid
from tqdm import tqdm
import os


def is_optimization_completed(conformer_dir: Path) -> bool:
    """Check if optimization is already completed for a conformer directory."""
    omol_opt_dir = conformer_dir / "omol_opt"
    if not omol_opt_dir.exists():
        return False
    
    # Check for essential output files that indicate successful completion
    optimized_file = omol_opt_dir / "optimized.xyz"
    info_file = omol_opt_dir / "info.txt"
    
    return optimized_file.exists() and info_file.exists()


def find_xyz_files(input_dir: Path, skip_completed: bool = True) -> List[Path]:
    """Find all conformer XYZ files to be processed, optionally filtering out completed calculations."""
    xyz_files = []
    
    # Check if input_dir contains batch subdirectories
    batch_dirs = [item for item in input_dir.iterdir() if item.is_dir() and item.name.startswith('batch_')]
    
    if batch_dirs:
        # Process batch structure
        for batch_dir in batch_dirs:
            for item in batch_dir.iterdir():
                if item.is_dir():
                    xyz_file = item / "rdkit_conformer" / "conformer.xyz"
                    if xyz_file.exists():
                        # Check if optimization is already completed
                        if skip_completed and is_optimization_completed(item):
                            continue
                        xyz_files.append(item)
    else:
        # Process flat structure
        for item in input_dir.iterdir():
            if item.is_dir():
                xyz_file = item / "rdkit_conformer" / "conformer.xyz"
                if xyz_file.exists():
                    # Check if optimization is already completed
                    if skip_completed and is_optimization_completed(item):
                        continue
                    xyz_files.append(item)
    
    return sorted(xyz_files)


def distribute_files(conformer_dirs: List[Path], gpu_num: int) -> List[List[Path]]:
    """Distribute conformer directories across tasks for individual SLURM jobs."""
    task_groups = [[] for _ in range(gpu_num)]
    
    for i, conformer_dir in enumerate(conformer_dirs):
        task_id = i % gpu_num
        task_groups[task_id].append(conformer_dir)
    
    # Filter out empty groups
    return [group for group in task_groups if group]


def submit_optimization_jobs(task_groups: List[List[Path]], submit_script: Path, 
                           output_dir: Path = None, fmax: float = 5e-4, 
                           steps: int = 1000, verbose: bool = False) -> int:
    """
    Submit SLURM jobs for all task groups.
    Uses temporary file lists to pass conformer directories to avoid argument length limits.
    Returns number of successfully submitted jobs.
    """
    submitted_count = 0
    temp_files = []
    
    print(f"Submitting {len(task_groups)} GPU jobs for molecular optimization")
    
    for task_num, conformer_group in enumerate(tqdm(task_groups, desc="Submitting jobs")):
        if verbose:
            print(f"Submitting job {task_num + 1}/{len(task_groups)}: {len(conformer_group)} molecules")
        
        # Create job name from first molecule directory
        first_mol_name = conformer_group[0].name
        job_name = f'omol_{first_mol_name}'
        if len(conformer_group) > 1:
            job_name += f'_+{len(conformer_group)-1}'
        
        # Write conformer directories to temporary file list in current directory
        temp_filename = f"omol_filelist_{uuid.uuid4().hex[:8]}_{task_num:04d}.txt"
        temp_file_path = Path.cwd() / temp_filename
        temp_files.append(temp_file_path)
        
        with open(temp_file_path, 'w') as temp_file:
            for conformer_dir in conformer_group:
                temp_file.write(f"{conformer_dir.absolute()}\n")
        
        try:
            # Build sbatch command with file list and parameters
            cmd = [
                'sbatch',
                '--job-name', job_name,
                str(submit_script),
                str(temp_file_path),
                str(fmax),
                str(steps)
            ]
            
            if output_dir:
                cmd.append(str(output_dir.absolute()))
            
            if verbose:
                cmd.append("--verbose")
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                submitted_count += 1
                job_id = result.stdout.strip().split()[-1] if result.stdout else "unknown"
                if verbose:
                    print(f"  Job submitted: {job_id}")
            else:
                print(f"  ERROR: Failed to submit job for task {task_num + 1}")
                if result.stderr:
                    print(f"  Error: {result.stderr.strip()}")
                    
        except subprocess.TimeoutExpired:
            print(f"  ERROR: Job submission timed out for task {task_num + 1}")
        except Exception as e:
            print(f"  ERROR: Job submission failed for task {task_num + 1}: {e}")
        
        # Small delay to avoid overwhelming the scheduler
        time.sleep(0.1)
    
    print(f"Jobs submitted: {submitted_count}/{len(task_groups)}")
    
    # Don't clean up temp files immediately - let SLURM jobs handle cleanup
    if temp_files:
        print(f"Created {len(temp_files)} temporary file lists for SLURM jobs")
        print("Note: Temporary files will be cleaned up by the SLURM jobs after processing")
        if submitted_count < len(task_groups):
            print("WARNING: Some jobs failed to submit. You may need to manually clean up remaining temp files:")
            failed_files = temp_files[submitted_count:]
            for f in failed_files:
                print(f"  rm {f}")
    
    return submitted_count


def main():
    parser = argparse.ArgumentParser(description="Submit SLURM jobs for batch OMOL optimization")
    parser.add_argument("input_dir", type=Path, help="Directory containing conformer subdirectories")
    parser.add_argument("--gpu_num", type=int, default=4,
                       help="Number of tasks/jobs to submit (default: 4)")
    parser.add_argument("--submit-script", type=Path, default=Path(__file__).parent / "submit_omol_single.sh",
                       help="Path to submit_omol_single.sh script")
    parser.add_argument("--output_dir", type=Path, default=None,
                       help="Output directory (default: optimize in place)")
    parser.add_argument("--fmax", type=float, default=5e-4, help="Optimization threshold (eV/Å)")
    parser.add_argument("--steps", type=int, default=10000, help="Maximum optimization steps")
    parser.add_argument("--verbose", action="store_true", help="Verbose output")
    parser.add_argument("--skip-completed", action="store_true", default=True,
                       help="Skip molecules that already have completed omol_opt calculations (default: True)")
    parser.add_argument("--force-recompute", action="store_true",
                       help="Force recomputation of all molecules, including completed ones")
    
    args = parser.parse_args()
    
    # Validate inputs
    if not args.input_dir.exists():
        print(f"ERROR: Input directory {args.input_dir} not found")
        sys.exit(1)
    
    if not args.submit_script.exists():
        print(f"ERROR: Submit script not found: {args.submit_script}")
        sys.exit(1)
    
    if args.gpu_num < 1:
        print(f"ERROR: gpu_num must be >= 1, got {args.gpu_num}")
        sys.exit(1)
    
    # Check if sbatch is available
    try:
        subprocess.run(['sbatch', '--version'], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("ERROR: sbatch command not found. This script requires SLURM.")
        sys.exit(1)
    
    # Find all conformer directories
    print("Scanning for conformer directories...")
    skip_completed = args.skip_completed and not args.force_recompute
    if not skip_completed:
        print("Note: Will process ALL molecules (including already completed ones)")
    
    conformer_dirs = find_xyz_files(args.input_dir, skip_completed=skip_completed)
    
    if not conformer_dirs:
        if skip_completed:
            print(f"No unprocessed conformer directories found in {args.input_dir}")
            print("All molecules may already be optimized. Use --force-recompute to reprocess all.")
        else:
            print(f"ERROR: No conformer directories found in {args.input_dir}")
        sys.exit(1)
    
    print(f"Found {len(conformer_dirs)} conformer directories to process")
    
    # Distribute files across tasks
    task_groups = distribute_files(conformer_dirs, args.gpu_num)
    total_jobs = len(task_groups)
    
    print(f"\nJob distribution:")
    print(f"Total molecules: {len(conformer_dirs)}")
    print(f"Number of tasks: {args.gpu_num}")
    print(f"Total jobs: {total_jobs}")
    
    # Show distribution details
    for i, group in enumerate(task_groups):
        print(f"Task {i+1}: {len(group)} molecules")
    
    if args.output_dir:
        print(f"Output directory: {args.output_dir}")
    else:
        print("Output: Optimize in place")
    
    print(f"Using submit script: {args.submit_script}")
    
    # Submit all jobs
    submitted_count = submit_optimization_jobs(
        task_groups, args.submit_script, args.output_dir, 
        args.fmax, args.steps, args.verbose
    )
    
    print(f"\nOverall submission: {submitted_count}/{total_jobs} jobs submitted successfully")
    
    if submitted_count > 0:
        print("\nJobs have been submitted to SLURM. Monitor with:")
        print("  squeue -u $USER")
        print("  sacct --format=JobID,JobName,State,Start,End")
    
    if submitted_count == total_jobs:
        print("\nAll jobs submitted successfully!")
        sys.exit(0)
    else:
        print("\nSome job submissions failed. Check output above for details.")
        sys.exit(1)


if __name__ == "__main__":
    main()