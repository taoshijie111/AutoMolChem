#!/usr/bin/env python3
"""
Batch conformer generation orchestrator that submits individual SLURM jobs.
Processes SMI files and submits each molecule as a separate SLURM job.
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

class SMIProcessor:
    """Process SMI files and organize batch conformer generation."""
    
    def __init__(self, batch_size: int = 1000, max_molecules_per_batch: int = 1000):
        self.batch_size = batch_size
        self.max_molecules_per_batch = max_molecules_per_batch
    
    def is_molecule_completed(self, molecule_dir: Path) -> bool:
        """
        Check if a molecule's conformer generation is completed.
        Completion criteria: both conformer.xyz and info.txt exist in rdkit_conformer directory.
        """
        conformer_file = molecule_dir / "conformer.xyz"
        info_file = molecule_dir / "info.txt"
        return conformer_file.exists() and info_file.exists()
    
    def parse_smi_file_and_create_batches(self, smi_file: Path, output_dir: Path, skip_completed: bool = False) -> List[List[Tuple[str, str, Path]]]:
        """
        Parse SMI file and create batch directory structure, maintaining molecule order.
        If skip_completed is True, skip molecules that already have completed conformer generation.
        Returns list of batches, each containing (smiles, name, output_path) tuples.
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Parse SMI file first to get all molecules in order
        all_molecules = []
        with open(smi_file, 'r') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                
                parts = line.split()
                if len(parts) == 0:
                    continue
                
                smiles = parts[0]
                
                # Extract name from end of line, or use molecule_{index}
                if len(parts) > 1:
                    name = parts[-1]
                else:
                    name = f"molecule_{line_num}"
                
                all_molecules.append((smiles, name))
        
        print(f"Parsed {len(all_molecules)} molecules from {smi_file}")
        
        # Create batch structure maintaining order and checking completion
        batches = []
        current_batch = []
        batch_num = 0
        processed_count = 0
        skipped_count = 0
        
        for smiles, name in tqdm(all_molecules, desc="Processing molecules"):
            # Calculate which batch this molecule should belong to based on its position
            molecule_index = processed_count  # This maintains the original order
            target_batch_num = molecule_index // self.max_molecules_per_batch
            
            # If we need to start a new batch
            while batch_num < target_batch_num:
                if current_batch:
                    batches.append(current_batch)
                    current_batch = []
                batch_num += 1
            
            batch_dir = output_dir / f"batch_{batch_num:04d}"
            molecule_dir = batch_dir / name / 'rdkit_conformer'
            
            # Check if molecule is already completed
            if skip_completed and self.is_molecule_completed(molecule_dir):
                skipped_count += 1
                processed_count += 1
                continue
            
            current_batch.append((smiles, name, molecule_dir))
            processed_count += 1
        
        # Add the last batch if not empty
        if current_batch:
            batches.append(current_batch)
        
        print(f"Organized into {len(batches)} batches")
        if skip_completed:
            print(f"Skipped {skipped_count} completed molecules")
            print(f"Remaining to process: {processed_count - skipped_count} molecules")
        
        return batches
    
    def submit_all_jobs(self, molecules: List[Tuple[str, str, Path]], submit_script: Path, 
                       size_per_task: int = 1, verbose: bool = False) -> int:
        """
        Submit SLURM jobs for all molecules, grouping by task size across all batches.
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
            for smiles, name, output_dir in task:
                task_data.append({
                    'smiles': smiles,
                    'name': name,
                    'output_dir': str(output_dir)
                })
            
            # Create job name from first molecule
            job_name = f'conf_{task_data[0]["name"]}'
            if len(task) > 1:
                job_name += f'_+{len(task)-1}'
            
            # Write task data to temporary file in current directory (accessible to compute nodes)
            temp_filename = f"slurm_task_{uuid.uuid4().hex[:8]}_{task_num:04d}.json"
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
    
    def submit_smi_file(self, smi_file: Path, output_dir: Path, submit_script: Path, 
                       size_per_task: int = 1, skip_completed: bool = False, verbose: bool = False) -> bool:
        """
        Submit SLURM jobs for entire SMI file with batch organization.
        """
        # Parse SMI file and create batch structure with completion checking
        batches = self.parse_smi_file_and_create_batches(smi_file, output_dir, skip_completed)
        
        # Flatten all molecules from all batches for task allocation
        all_molecules = []
        for batch in batches:
            all_molecules.extend(batch)
        
        if not all_molecules:
            if skip_completed:
                print("All molecules are already completed. No jobs to submit.")
            else:
                print("No valid molecules found in SMI file")
            return True if skip_completed else False
        
        # Submit all jobs with proper task grouping
        total_tasks = (len(all_molecules) + size_per_task - 1) // size_per_task
        
        print(f"\nSubmitting jobs for {len(all_molecules)} molecules across {len(batches)} batches")
        print(f"Creating {total_tasks} tasks with {size_per_task} molecules per task")
        
        submitted_count = self.submit_all_jobs(all_molecules, submit_script, size_per_task, verbose)
        
        print(f"\nOverall submission: {submitted_count}/{total_tasks} jobs submitted successfully")
        print(f"Total molecules: {len(all_molecules)} ({size_per_task} molecules per task)")
        
        if submitted_count > 0:
            print("\nJobs have been submitted to SLURM. Monitor with:")
            print("  squeue -u $USER")
            print("  sacct --format=JobID,JobName,State,Start,End")
        
        return submitted_count == total_tasks


def main():
    parser = argparse.ArgumentParser(
        description="Submit SLURM jobs for batch conformer generation from SMI files"
    )
    parser.add_argument("smi_file", type=Path, help="Input SMI file")
    parser.add_argument("output_dir", type=Path, help="Output directory for batch structure")
    parser.add_argument("--submit-script", type=Path, default=Path(__file__).parent / "submit_single.sh",
                       help="Path to submit_single.sh script")
    parser.add_argument("--size-per-task", type=int, default=1,
                       help="Number of SMILES processed per SLURM job (default: 1)")
    parser.add_argument("--batch-size", type=int, default=1000,
                       help="Maximum molecules per batch directory (default: 1000)")
    parser.add_argument("--skip-completed", action="store_true",
                       help="Skip molecules that already have both conformer.xyz and info.txt files")
    parser.add_argument("--verbose", action="store_true", help="Verbose output")
    
    args = parser.parse_args()
    
    # Validate inputs
    if not args.smi_file.exists():
        print(f"ERROR: SMI file not found: {args.smi_file}")
        sys.exit(1)
    
    if not args.submit_script.exists():
        print(f"ERROR: Submit script not found: {args.submit_script}")
        sys.exit(1)
    
    if args.size_per_task < 1:
        print(f"ERROR: size_per_task must be >= 1, got {args.size_per_task}")
        sys.exit(1)
    
    # Validate parameter compatibility
    if args.size_per_task > args.batch_size:
        print(f"WARNING: size_per_task ({args.size_per_task}) > batch_size ({args.batch_size})")
        print("Tasks will span across batch directories, which is allowed but may be confusing.")
        print("Consider using size_per_task <= batch_size for cleaner organization.")
        print()
    
    # Check if sbatch is available
    try:
        subprocess.run(['sbatch', '--version'], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("ERROR: sbatch command not found. This script requires SLURM.")
        sys.exit(1)
    
    # Initialize processor
    processor = SMIProcessor(
        batch_size=args.batch_size,
        max_molecules_per_batch=args.batch_size
    )
    
    # Submit jobs
    print(f"Submitting jobs for {args.smi_file} -> {args.output_dir}")
    print(f"Using submit script: {args.submit_script}")
    print(f"Size per task: {args.size_per_task} molecules per job")
    print(f"Batch size: {args.batch_size} molecules per batch directory")
    if args.skip_completed:
        print("Skip completed: Enabled (molecules with both conformer.xyz and info.txt will be skipped)")
    
    success = processor.submit_smi_file(
        args.smi_file,
        args.output_dir,
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