#!/usr/bin/env python3

import os
import sys
import subprocess
import argparse
import tempfile
import shutil
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor

def is_orca_calculation_complete(output_file_path):
    """Check if ORCA calculation completed successfully by examining the output file."""
    try:
        with open(output_file_path, 'r') as f:
            lines = f.readlines()
            if len(lines) >= 2:
                # Check second-to-last line
                second_last_line = lines[-2].strip()
                return 'ORCA TERMINATED NORMALLY' in second_last_line
        return False
    except (IOError, OSError):
        return False

def run_orca_task(inp_file_path, cores_per_task=1, force_not_skip=False):
    """Run ORCA calculation for a single input file in a temporary directory."""
    inp_file = Path(inp_file_path)
    original_dir = inp_file.parent
    
    # Check if output file already exists and calculation completed successfully
    if not force_not_skip:
        output_file = original_dir / f"{inp_file.stem}.output"
        if output_file.exists() and is_orca_calculation_complete(output_file):
            print(f"Skipping: {inp_file} (calculation already completed successfully)")
            return True, str(inp_file)
    
    # Set environment variable for ORCA parallelism
    env = os.environ.copy()
    env['OMP_NUM_THREADS'] = str(cores_per_task)
    
    # Create temporary directory for calculation
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        try:
            print(f"Processing: {inp_file}")
            
            # Copy input file and any xyz file to temporary directory
            temp_inp = temp_path / inp_file.name
            shutil.copy2(inp_file, temp_inp)
            
            # Copy .xyz file if it exists
            for xyz_file in Path(inp_file_path).parent.glob('*.xyz'):
                temp_xyz = temp_path / xyz_file.name
                shutil.copy2(xyz_file, temp_xyz)

            # Run ORCA calculation in temporary directory
            temp_output = temp_path / f"{inp_file.stem}.output"
            with open(temp_output, 'w') as f:
                subprocess.run(
                    ['/home/user/applications/orca-6.1.0-f.0_linux_x86-64/bin/orca', temp_inp.name],
                    cwd=temp_path,
                    stdout=f,
                    stderr=subprocess.STDOUT,
                    env=env,
                    check=True
                )
            
            # Copy output files back to original directory
            output_file = original_dir / f"{inp_file.stem}.output"
            shutil.copy2(temp_output, output_file)
            
            # Copy .hess file if it exists
            temp_hess = temp_path / f"{inp_file.stem}.hess"
            if temp_hess.exists():
                hess_file = original_dir / f"{inp_file.stem}.hess"
                shutil.copy2(temp_hess, hess_file)
            
            # Copy all .xyz files from temp directory
            for xyz_file in temp_path.glob('*.xyz'):
                output_xyz = original_dir / xyz_file.name
                shutil.copy2(xyz_file, output_xyz)
            
            print(f"Completed: {inp_file}")
            return True, str(inp_file)
            
        except subprocess.CalledProcessError as e:
            print(f"Failed: {inp_file} (exit code: {e.returncode})", file=sys.stderr)
            # Still try to copy output file if it exists for debugging
            temp_output = temp_path / f"{inp_file.stem}.output"
            if temp_output.exists():
                output_file = original_dir / f"{inp_file.stem}.output"
                shutil.copy2(temp_output, output_file)
            return False, str(inp_file)
        except Exception as e:
            print(f"Error processing {inp_file}: {e}", file=sys.stderr)
            return False, str(inp_file)

def main():
    parser = argparse.ArgumentParser(
        description='Submit ORCA calculations in parallel using temporary directories',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Example usage:
    python submit_orca_batch.py part_2_1863 8
    python submit_orca_batch.py part_2_1863 16 --cores-per-task 2
    python submit_orca_batch.py part_2_1863 8 --inp-name opt
    python submit_orca_batch.py part_2_1863 8 --force-not-skip
    
This will find all .inp files in part_2_1863 and submit them optimally.
With 8 total cores and 1 core per task: 8 parallel tasks
With 16 total cores and 2 cores per task: 8 parallel tasks
Use --inp-name to filter files (e.g., "opt" matches *opt*.inp files)
Use --force-not-skip to process all files even if they already completed successfully
Each task runs in a temporary directory with only .output and .hess files copied back.
        '''
    )
    
    parser.add_argument('main_directory', 
                       help='Main directory path containing subdirectories with ORCA input files')
    parser.add_argument('total_cores', type=int,
                       help='Total number of CPU cores available')
    parser.add_argument('--cores-per-task', type=int, default=1,
                       help='Number of CPU cores per ORCA task (default: 1)')
    parser.add_argument('--inp-name', type=str,
                       help='Specific pattern or name to search for inp files (e.g., "opt" will match opt.inp)')
    parser.add_argument('--force-not-skip', action='store_true',
                       help='Force processing of all files, even if output files already exist with successful completion')
    
    args = parser.parse_args()
    
    # Validate inputs
    main_dir = Path(args.main_directory)
    if not main_dir.is_dir():
        print(f"Error: Directory '{main_dir}' does not exist.", file=sys.stderr)
        sys.exit(1)
    
    if args.total_cores <= 0:
        print("Error: Total number of cores must be a positive integer.", file=sys.stderr)
        sys.exit(1)
    
    if args.cores_per_task <= 0:
        print("Error: Cores per task must be a positive integer.", file=sys.stderr)
        sys.exit(1)
    
    if args.cores_per_task > args.total_cores:
        print("Error: Cores per task cannot exceed total cores.", file=sys.stderr)
        sys.exit(1)
    
    # Calculate optimal parallelism
    max_parallel_tasks = args.total_cores // args.cores_per_task
    
    print(f"Configuration:")
    print(f"  Total cores: {args.total_cores}")
    print(f"  Cores per task: {args.cores_per_task}")
    print(f"  Max parallel tasks: {max_parallel_tasks}")
    
    # Find all .inp files in subdirectories
    print(f"Searching for ORCA input files in {main_dir}...")
    if args.inp_name:
        # Use specific pattern when inp_name is provided
        search_pattern = f'**/{args.inp_name}.inp'
        print(f"Using search pattern: {search_pattern}")
        inp_files = sorted(main_dir.glob(search_pattern))
    else:
        # Use default exact match mode
        inp_files = sorted(main_dir.glob('**/*.inp'))
    
    if not inp_files:
        print(f"Error: No .inp files found in {main_dir}", file=sys.stderr)
        sys.exit(1)
    
    print(f"Found {len(inp_files)} ORCA input files")
    
    # Check how many already have completed calculations (unless forcing)
    existing_outputs = 0
    if not args.force_not_skip:
        for inp_file in inp_files:
            output_file = inp_file.parent / f"{inp_file.stem}.output"
            if output_file.exists() and is_orca_calculation_complete(output_file):
                existing_outputs += 1
        
        files_to_process = len(inp_files) - existing_outputs
        print(f"Files with successful completions: {existing_outputs}")
        print(f"Files to process: {files_to_process}")
        
        if files_to_process == 0:
            print("All calculations already completed successfully!")
            return
    else:
        print("Force mode enabled - will process all files regardless of existing outputs")
        files_to_process = len(inp_files)
    
    # Submit jobs using ProcessPoolExecutor
    successful = 0
    failed = 0
    
    with ProcessPoolExecutor(max_workers=max_parallel_tasks) as executor:
        # Submit all tasks
        futures = [executor.submit(run_orca_task, str(inp_file), args.cores_per_task, args.force_not_skip) for inp_file in inp_files]
        
        # Collect results
        for future in futures:
            success, _ = future.result()
            if success:
                successful += 1
            else:
                failed += 1
    
    print(f"\nAll ORCA calculations completed.")
    print(f"Successful (including skipped): {successful}")
    if not args.force_not_skip:
        print(f"Skipped (already completed): {existing_outputs}")
    print(f"Failed: {failed}")
    
    if failed > 0:
        sys.exit(1)

if __name__ == '__main__':
    main()