#!/usr/bin/env python3
"""
Batch XTB optimization orchestrator that submits individual SLURM jobs.
Processes molecule directories containing conformer.xyz files and submits each as a separate SLURM job.
"""

import argparse
import subprocess
import sys
import time
from pathlib import Path
from typing import List, Tuple, Optional
import os
from tqdm import tqdm
import tempfile
import json
import uuid


class XTBProcessor:
    """Process molecule directories for XTB optimization."""
    
    def __init__(self):
        pass
    
    def is_molecule_completed(self, molecule_dir: Path) -> bool:
        """
        Check if a molecule's XTB optimization is completed.
        Completion criteria: optimized.xyz exists in xtb_opt directory.
        """
        opt_file = molecule_dir / "xtb_opt" / "optimized.xyz"
        return opt_file.exists()
    
    def find_molecule_directories(self, base_dir: Path) -> List[Path]:
        """
        Find all molecule directories containing rdkit_conformer/conformer.xyz files.
        
        Args:
            base_dir: Base directory to search
            
        Returns:
            List of molecule directory paths
        """
        molecule_dirs = []
        
        # Search for directories containing rdkit_conformer/conformer.xyz
        for root, dirs, files in os.walk(base_dir):
            root_path = Path(root)
            if root_path.name == "rdkit_conformer" and "conformer.xyz" in files:
                # Add the parent directory (molecule directory)
                molecule_dirs.append(root_path.parent)
        
        return sorted(molecule_dirs)
    
    def get_molecules_to_process(self, base_dir: Path, skip_completed: bool = False) -> List[Tuple[Path, str]]:
        """
        Find molecule directories to process.
        If skip_completed is True, skip molecules that already have optimized.xyz.
        Returns list of (molecule_dir, name) tuples.
        """
        # Find all molecule directories
        all_molecule_dirs = self.find_molecule_directories(base_dir)
        
        if not all_molecule_dirs:
            print("No molecule directories with conformer/conformer.xyz files found")
            return []
        
        print(f"Found {len(all_molecule_dirs)} molecule directories")
        
        # Filter out completed if requested
        molecules_to_process = []
        skipped_count = 0
        
        for mol_dir in tqdm(all_molecule_dirs, desc="Checking molecules"):
            if skip_completed and self.is_molecule_completed(mol_dir):
                skipped_count += 1
                continue
            
            # Extract name from molecule directory
            name = mol_dir.name
            molecules_to_process.append((mol_dir, name))
        
        if skip_completed and skipped_count > 0:
            print(f"Skipped {skipped_count} completed molecules")
        
        print(f"Remaining to process: {len(molecules_to_process)} molecules")
        
        return molecules_to_process
    
    def submit_all_jobs(self, molecules: List[Tuple[Path, str]], submit_script: Path, 
                       size_per_task: int = 1, verbose: bool = False) -> int:
        """
        Submit SLURM jobs for all molecules, grouping by task size.
        Uses temporary files to avoid "Argument list too long" errors.
        Returns number of successfully submitted jobs.
        """
        # Split all molecules into tasks of specified size
        tasks = []
        for i in range(0, len(molecules), size_per_task):
            task = molecules[i:i + size_per_task]
            tasks.append(task)
        
        submitted_count = 0
        temp_files = []  # Keep track of temp files for cleanup later
        
        print(f"Submitting {len(tasks)} jobs for {len(molecules)} molecules (size_per_task={size_per_task})")
        
        for task_num, task in enumerate(tqdm(tasks, desc="Submitting jobs")):
            if verbose:
                print(f"Submitting job {task_num + 1}/{len(tasks)}: {len(task)} molecules")
            
            # Prepare task data
            task_data = []
            for molecule_dir, name in task:
                task_data.append({
                    'molecule_dir': str(molecule_dir),
                    'name': name
                })
            
            # Create job name from first molecule
            job_name = f'xtb_{task_data[0]["name"]}'
            if len(task) > 1:
                job_name += f'_+{len(task)-1}'
            
            # Write task data to temporary file in current directory (accessible to compute nodes)
            temp_filename = f"slurm_xtb_task_{uuid.uuid4().hex[:8]}_{task_num:04d}.json"
            temp_file_path = Path.cwd() / temp_filename
            temp_files.append(temp_file_path)
            
            with open(temp_file_path, 'w') as temp_file:
                json.dump(task_data, temp_file, indent=2)
            
            try:
                # Build sbatch command with temp file path
                cmd = [
                    'sbatch',
                    '--job-name', job_name,
                    str(submit_script),
                    temp_file_path
                ]
                
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
        
        print(f"Jobs submitted: {submitted_count}/{len(tasks)}")
        
        # Don't clean up temp files immediately - let SLURM jobs handle cleanup
        if temp_files:
            print(f"Created {len(temp_files)} temporary JSON files for SLURM jobs")
            print("Note: Temporary files will be cleaned up by the SLURM jobs after processing")
            if submitted_count < len(tasks):
                print("WARNING: Some jobs failed to submit. You may need to manually clean up remaining temp files:")
                failed_files = temp_files[submitted_count:]
                for f in failed_files:
                    print(f"  rm {f}")
        
        return submitted_count
    
    def submit_molecules(self, base_dir: Path, submit_script: Path, 
                        size_per_task: int = 1, skip_completed: bool = False, verbose: bool = False) -> bool:
        """
        Submit SLURM jobs for XTB optimization of all molecules in base directory.
        """
        # Find molecules to process
        molecules = self.get_molecules_to_process(base_dir, skip_completed)
        
        if not molecules:
            if skip_completed:
                print("All molecules are already optimized. No jobs to submit.")
            else:
                print("No valid molecules found")
            return True if skip_completed else False
        
        # Calculate total tasks needed
        total_tasks = (len(molecules) + size_per_task - 1) // size_per_task
        
        print(f"\nSubmitting jobs for {len(molecules)} molecules")
        print(f"Creating {total_tasks} tasks with {size_per_task} molecules per task")
        
        submitted_count = self.submit_all_jobs(molecules, submit_script, size_per_task, verbose)
        
        print(f"\nOverall submission: {submitted_count}/{total_tasks} jobs submitted successfully")
        print(f"Total molecules: {len(molecules)} ({size_per_task} molecules per task)")
        
        if submitted_count > 0:
            print("\nJobs have been submitted to SLURM. Monitor with:")
            print("  squeue -u $USER")
            print("  sacct --format=JobID,JobName,State,Start,End")
        
        return submitted_count == total_tasks


def main():
    parser = argparse.ArgumentParser(
        description="Submit SLURM jobs for batch XTB optimization of molecule directories"
    )
    parser.add_argument("input_dir", type=Path, help="Input directory containing molecule subdirectories with conformer/")
    parser.add_argument("--submit-script", type=Path, default=Path(__file__).parent / "submit_single.sh",
                       help="Path to submit_single.sh script")
    parser.add_argument("--size-per-task", type=int, default=1,
                       help="Number of molecules processed per SLURM job (default: 1)")
    parser.add_argument("--skip-completed", action="store_true",
                       help="Skip molecules that already have xtb_opt/optimized.xyz files")
    parser.add_argument("--verbose", action="store_true", help="Verbose output")
    
    args = parser.parse_args()
    
    # Validate inputs
    if not args.input_dir.exists():
        print(f"ERROR: Input directory not found: {args.input_dir}")
        sys.exit(1)
    
    if not args.submit_script.exists():
        print(f"ERROR: Submit script not found: {args.submit_script}")
        sys.exit(1)
    
    if args.size_per_task < 1:
        print(f"ERROR: size_per_task must be >= 1, got {args.size_per_task}")
        sys.exit(1)
    
    # Check if sbatch is available
    try:
        subprocess.run(['sbatch', '--version'], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("ERROR: sbatch command not found. This script requires SLURM.")
        sys.exit(1)
    
    # Initialize processor
    processor = XTBProcessor()
    
    # Submit jobs
    print(f"Submitting XTB optimization jobs for {args.input_dir}")
    print(f"Using submit script: {args.submit_script}")
    print(f"Size per task: {args.size_per_task} molecules per job")
    if args.skip_completed:
        print("Skip completed: Enabled (molecules with xtb_opt/optimized.xyz will be skipped)")
    
    success = processor.submit_molecules(
        args.input_dir,
        args.submit_script,
        args.size_per_task,
        args.skip_completed,
        args.verbose
    )
    
    if success:
        print("\nAll jobs submitted successfully!")
        sys.exit(0)
    else:
        print("\nSome job submissions failed. Check output above for details.")
        sys.exit(1)


if __name__ == "__main__":
    main()