#!/usr/bin/env python3
"""
Script for parallel structure optimization using xtb.
Optimizes molecular structures from XYZ files using xtb with ohess normal calculation.
"""

import argparse
import logging
import os
import shutil
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import List, Tuple, NamedTuple


class OptimizationResult(NamedTuple):
    molecule_path: Path
    success: bool
    message: str
    runtime: float


def find_xtb_executable() -> str:
    """Find xtb executable in PATH."""
    xtb_path = shutil.which("xtb")
    if xtb_path is None:
        raise FileNotFoundError("xtb executable not found in PATH. Please install xtb.")
    return xtb_path


def run_xtb_optimization(xyz_file: Path, work_dir: Path) -> Tuple[bool, str, float]:
    """
    Run xtb optimization with ohess normal calculation.
    
    Args:
        xyz_file: Path to input XYZ file
        work_dir: Working directory for the calculation
        
    Returns:
        Tuple of (success, message, runtime)
    """
    start_time = time.time()
    
    try:
        xtb_cmd = find_xtb_executable()
    except FileNotFoundError as e:
        return False, str(e), 0.0
    
    # Create xtb_opt subdirectory
    xtb_opt_dir = work_dir / "xtb_opt"
    xtb_opt_dir.mkdir(parents=True, exist_ok=True)
    
    # Copy conformer.xyz to xtb_opt directory for reference
    import shutil
    shutil.copy2(xyz_file, xtb_opt_dir / "conformer.xyz")
    
    # Use relative path for the xyz file when running in the working directory
    xyz_filename = "conformer.xyz"
    
    # Prepare command with relative path
    cmd = [xtb_cmd, xyz_filename, "--ohess", "normal", "-P", "1"]
    
    # Set up environment variables
    env = os.environ.copy()
    # Ensure proper environment for xtb
    env['OMP_NUM_THREADS'] = '1'
    env['MKL_NUM_THREADS'] = '1'
    
    try:
        # Run xtb optimization in the xtb_opt subdirectory
        result = subprocess.run(
            cmd,
            cwd=xtb_opt_dir,
            capture_output=True,
            text=True,
            timeout=3000,  # 5 minute timeout
            env=env
        )
        
        runtime = time.time() - start_time
        
        if result.returncode == 0:
            # Check if optimization completed successfully
            opt_xyz = xtb_opt_dir / "xtbopt.xyz"
            if opt_xyz.exists():
                # Read SMILES from info.txt to update comment line
                smiles = "Unknown"
                info_file = xtb_opt_dir / "info.txt"
                if info_file.exists():
                    with open(info_file, 'r') as f:
                        for line in f:
                            if line.startswith("SMILES:"):
                                smiles = line.split("SMILES:", 1)[1].strip()
                                break
                
                # Update comment line in optimized.xyz with SMILES
                final_opt = xtb_opt_dir / "optimized.xyz"
                if final_opt.exists():
                    final_opt.unlink()
                
                # Read original file and update comment line
                with open(opt_xyz, 'r') as f:
                    lines = f.readlines()
                
                # Update the second line (comment line) with SMILES
                if len(lines) >= 2:
                    lines[1] = f"{smiles}\n"
                
                # Write to final optimized.xyz
                with open(final_opt, 'w') as f:
                    f.writelines(lines)
                
                # Remove original xtbopt.xyz
                opt_xyz.unlink()
                
                return True, "Optimization completed successfully", runtime
            else:
                return False, "Optimization failed - no output structure found", runtime
        else:
            error_msg = f"xtb failed with return code {result.returncode}"
            if result.stderr:
                error_msg += f": {result.stderr.strip()}"
            # Also include stdout for debugging
            if result.stdout:
                error_msg += f" | stdout: {result.stdout.strip()}"
            return False, error_msg, runtime
            
    except subprocess.TimeoutExpired:
        runtime = time.time() - start_time
        return False, "Optimization timed out (>50 minutes)", runtime
    except Exception as e:
        runtime = time.time() - start_time
        return False, f"Unexpected error: {str(e)}", runtime


def process_single_molecule(molecule_dir: Path, skip_completed: bool = True) -> OptimizationResult:
    """
    Process a single molecule directory for optimization.
    
    Args:
        molecule_dir: Path to molecule directory containing conformer/conformer.xyz
        skip_completed: Whether to skip already optimized structures
        
    Returns:
        OptimizationResult with success status and details
    """
    start_time = time.time()
    
    # Check if conformer/conformer.xyz exists
    conformer_file = molecule_dir / "conformer" / "conformer.xyz"
    if not conformer_file.exists():
        runtime = time.time() - start_time
        return OptimizationResult(
            molecule_dir, False, "No conformer/conformer.xyz file found", runtime
        )
    
    # Check if already optimized
    opt_file = molecule_dir / "xtb_opt" / "optimized.xyz"
    if skip_completed and opt_file.exists():
        runtime = time.time() - start_time
        return OptimizationResult(
            molecule_dir, True, "Already optimized (skipped)", runtime
        )
    
    # Copy info.txt to xtb_opt directory if it exists
    info_source = molecule_dir / "conformer" / "info.txt"
    if info_source.exists():
        xtb_opt_dir = molecule_dir / "xtb_opt"
        xtb_opt_dir.mkdir(parents=True, exist_ok=True)
        import shutil
        shutil.copy2(info_source, xtb_opt_dir / "info.txt")
    
    # Run optimization
    success, message, _ = run_xtb_optimization(conformer_file, molecule_dir)
    
    # Clean up failed optimization directory
    if not success:
        cleanup_failed_molecule_directory(molecule_dir)
    
    total_runtime = time.time() - start_time
    
    return OptimizationResult(molecule_dir, success, message, total_runtime)


def find_molecule_directories(base_dir: Path) -> List[Path]:
    """
    Find all molecule directories containing conformer/conformer.xyz files.
    
    Args:
        base_dir: Base directory to search
        
    Returns:
        List of molecule directory paths
    """
    molecule_dirs = []
    
    # Search for directories containing conformer/conformer.xyz
    for root, _, files in os.walk(base_dir):
        root_path = Path(root)
        if root_path.name == "conformer" and "conformer.xyz" in files:
            # Add the parent directory (molecule directory)
            molecule_dirs.append(root_path.parent)
    
    return sorted(molecule_dirs)


def cleanup_failed_molecule_directory(molecule_dir: Path):
    """Remove xtb_opt directory for failed optimization."""
    xtb_opt_dir = molecule_dir / "xtb_opt"
    if xtb_opt_dir.exists():
        try:
            shutil.rmtree(xtb_opt_dir)
        except Exception as e:
            print(f"Warning: Could not clean up directory {xtb_opt_dir}: {e}")


def cleanup_empty_batch_directories(base_dir: Path):
    """Remove any empty batch directories after processing."""
    batch_dirs = [d for d in base_dir.iterdir() if d.is_dir() and d.name.startswith('batch_')]
    removed_count = 0
    
    for batch_dir in batch_dirs:
        try:
            # Check if directory is empty or contains only empty subdirectories
            has_valid_content = False
            for item in batch_dir.rglob('*'):
                if item.is_file():
                    has_valid_content = True
                    break
            
            if not has_valid_content:
                shutil.rmtree(batch_dir)
                removed_count += 1
                print(f"Removed empty batch directory: {batch_dir.name}")
        except Exception as e:
            print(f"Warning: Could not clean up batch directory {batch_dir}: {e}")
    
    if removed_count > 0:
        print(f"Cleaned up {removed_count} empty batch directories")


def main():
    parser = argparse.ArgumentParser(description="Optimize molecular structures using xtb")
    parser.add_argument("input_dir", type=Path, help="Input directory containing molecule subdirectories")
    parser.add_argument("--workers", type=int, default=4, help="Number of parallel workers")
    parser.add_argument("--verbose", action="store_true", help="Verbose output")
    parser.add_argument("--force", action="store_true", help="Force re-optimization of already optimized structures")
    parser.add_argument("--cleanup", action="store_true", default=True, help="Clean up empty directories after processing (default: True)")
    parser.add_argument("--no_cleanup", action="store_true", help="Disable cleanup of empty directories")
    parser.add_argument("--skip_completed", action="store_true", default=True, help="Skip already optimized structures (default: True)")
    
    args = parser.parse_args()
    
    # Set up logging
    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    # Validate input directory
    if not args.input_dir.exists():
        print(f"Error: Input directory {args.input_dir} not found")
        sys.exit(1)
    
    # Check for xtb executable
    try:
        xtb_path = find_xtb_executable()
        print(f"Found xtb executable at: {xtb_path}")
    except FileNotFoundError as e:
        print(f"Error: {e}")
        sys.exit(1)
    
    # Find molecule directories
    print(f"Searching for molecule directories in {args.input_dir}...")
    molecule_dirs = find_molecule_directories(args.input_dir)
    
    if not molecule_dirs:
        print("No molecule directories with conformer.xyz files found")
        sys.exit(1)
    
    print(f"Found {len(molecule_dirs)} molecule directories to process")
    
    # Filter out already optimized if not forcing and skip_completed is enabled
    skip_completed = args.skip_completed and not args.force
    if not skip_completed:
        print("Note: Will process ALL molecules (including already completed ones)")
        
    if not args.force:
        unoptimized_dirs = []
        for mol_dir in molecule_dirs:
            if not skip_completed or not (mol_dir / "xtb_opt" / "optimized.xyz").exists():
                unoptimized_dirs.append(mol_dir)
        
        already_optimized = len(molecule_dirs) - len(unoptimized_dirs)
        if already_optimized > 0:
            print(f"Skipping {already_optimized} already optimized structures (use --force to re-optimize)")
        
        molecule_dirs = unoptimized_dirs
    
    if not molecule_dirs:
        print("All structures are already optimized")
        return
    
    print(f"Starting optimization of {len(molecule_dirs)} structures with {args.workers} workers...")
    
    # Track results
    successful = 0
    failed = 0
    skipped = 0
    total_runtime = 0
    
    start_time = time.time()
    
    # Process molecules in parallel
    with ProcessPoolExecutor(max_workers=args.workers) as executor:
        # Submit all jobs
        future_to_dir = {
            executor.submit(process_single_molecule, mol_dir, skip_completed): mol_dir 
            for mol_dir in molecule_dirs
        }
        
        # Process completed jobs
        for future in as_completed(future_to_dir):
            mol_dir = future_to_dir[future]
            
            try:
                result = future.result()
                total_runtime += result.runtime
                
                if result.success:
                    if "skipped" in result.message.lower():
                        skipped += 1
                        if args.verbose:
                            print(f"⊖ {result.molecule_path.name}: {result.message}")
                    else:
                        successful += 1
                        if args.verbose:
                            print(f"✓ {result.molecule_path.name}: {result.message} ({result.runtime:.1f}s)")
                else:
                    failed += 1
                    print(f"✗ {result.molecule_path.name}: {result.message}")
                    
            except Exception as e:
                failed += 1
                print(f"✗ {mol_dir.name}: Unexpected error: {str(e)}")
    
    wall_time = time.time() - start_time
    
    # Clean up empty batch directories if enabled
    if args.cleanup and not args.no_cleanup:
        print(f"\nCleaning up empty directories...")
        cleanup_empty_batch_directories(args.input_dir)
    
    # Print summary
    print(f"\nOptimization complete:")
    print(f"  Successful: {successful}")
    print(f"  Failed: {failed}")
    if skipped > 0:
        print(f"  Skipped: {skipped}")
    print(f"  Wall time: {wall_time:.2f} seconds")
    print(f"  Total CPU time: {total_runtime:.2f} seconds")
    if successful > 0:
        print(f"  Average time per optimization: {total_runtime/successful:.2f} seconds")


if __name__ == "__main__":
    main()