#!/usr/bin/env python3
"""
Multi-GPU wrapper script for omol_optimize.py
Distributes molecular optimization tasks across multiple GPUs using screen sessions.
"""

import argparse
import subprocess
import sys
import time
from pathlib import Path
from typing import List, Dict


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
                    xyz_file = item / "conformer" / "conformer.xyz"
                    if xyz_file.exists():
                        # Check if optimization is already completed
                        if skip_completed and is_optimization_completed(item):
                            continue
                        xyz_files.append(item)
    else:
        # Process flat structure
        for item in input_dir.iterdir():
            if item.is_dir():
                xyz_file = item / "conformer" / "conformer.xyz"
                if xyz_file.exists():
                    # Check if optimization is already completed
                    if skip_completed and is_optimization_completed(item):
                        continue
                    xyz_files.append(item)
    
    return sorted(xyz_files)


def distribute_files(conformer_dirs: List[Path], num_gpus: int) -> Dict[int, List[Path]]:
    """Distribute conformer directories across GPUs."""
    gpu_groups = {i: [] for i in range(num_gpus)}
    
    for i, conformer_dir in enumerate(conformer_dirs):
        gpu_id = i % num_gpus
        gpu_groups[gpu_id].append(conformer_dir)
    
    return gpu_groups


def save_file_list(conformer_dirs: List[Path], output_file: Path):
    """Save list of conformer directories to a file."""
    with output_file.open('w') as f:
        for conformer_dir in conformer_dirs:
            f.write(f"{conformer_dir.absolute()}\n")


def create_screen_session(process_id: int, gpu_id: int, file_list_path: Path, script_path: Path, 
                         output_dir: Path = None, fmax: float = 5e-4, steps: int = 1000, 
                         verbose: bool = False) -> str:
    """Create a screen session for a specific GPU process."""
    session_name = f"omol_gpu_{gpu_id}_proc_{process_id}"
    
    # Prepare the command
    cmd_parts = [
        "python3", str(script_path),
        "--file_list", str(file_list_path),
        "--device", "cuda",
        "--fmax", str(fmax),
        "--steps", str(steps)
    ]
    
    if output_dir:
        cmd_parts.extend(["--output_dir", str(output_dir)])
    
    if verbose:
        cmd_parts.append("--verbose")
    
    cmd = " ".join(cmd_parts)
    
    # Create screen session with conda environment and GPU setup
    screen_cmd = [
        "screen", "-dmS", session_name,
        "bash", "-c", 
        f"source ~/miniconda3/etc/profile.d/conda.sh && conda activate md && export CUDA_VISIBLE_DEVICES={gpu_id} && {cmd}; echo 'GPU {gpu_id} process {process_id} finished'"
    ]
    
    return session_name, screen_cmd


def check_screen_sessions(session_names: List[str]) -> Dict[str, bool]:
    """Check which screen sessions are still running."""
    try:
        result = subprocess.run(["screen", "-ls"], capture_output=True, text=True)
        running_sessions = result.stdout
        
        status = {}
        for session_name in session_names:
            status[session_name] = session_name in running_sessions
        
        return status
    except subprocess.CalledProcessError:
        return {name: False for name in session_names}


def main():
    parser = argparse.ArgumentParser(description="Multi-GPU molecular optimization wrapper")
    parser.add_argument("input_dir", type=Path, help="Directory containing conformer subdirectories")
    parser.add_argument("--gpu_ids", type=str, default="0,1,2,3", 
                       help="Comma-separated GPU IDs or multiplication syntax (e.g., '0,1,2,3' or '1*4,2*5')")
    parser.add_argument("--output_dir", type=Path, default=None,
                       help="Output directory (default: optimize in place)")
    parser.add_argument("--fmax", type=float, default=5e-4, help="Optimization threshold (eV/Å)")
    parser.add_argument("--steps", type=int, default=10000, help="Maximum optimization steps")
    parser.add_argument("--verbose", action="store_true", help="Verbose output")
    parser.add_argument("--monitor", action="store_true", 
                       help="Monitor screen sessions until completion")
    parser.add_argument("--skip_completed", action="store_true", default=True,
                       help="Skip molecules that already have completed omol_opt calculations (default: True)")
    parser.add_argument("--force_recompute", action="store_true",
                       help="Force recomputation of all molecules, including completed ones")
    
    args = parser.parse_args()
    
    # Parse GPU IDs with multiplication support (e.g., "1*4,2*5")
    try:
        gpu_ids = []
        for part in args.gpu_ids.split(','):
            part = part.strip()
            if '*' in part:
                gpu_id, count = part.split('*')
                gpu_ids.extend([int(gpu_id.strip())] * int(count.strip()))
            else:
                gpu_ids.append(int(part))
    except ValueError:
        print(f"Error: Invalid GPU IDs format: {args.gpu_ids}")
        sys.exit(1)
    
    if not args.input_dir.exists():
        print(f"Error: Input directory {args.input_dir} not found")
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
            print("All molecules may already be optimized. Use --force_recompute to reprocess all.")
        else:
            print(f"Error: No conformer directories found in {args.input_dir}")
        sys.exit(1)
    
    print(f"Found {len(conformer_dirs)} conformer directories")
    print(f"Using {len(gpu_ids)} GPUs: {gpu_ids}")
    
    # Distribute files across GPUs
    gpu_groups = distribute_files(conformer_dirs, len(gpu_ids))
    
    # Create temporary directory for file lists
    temp_dir = Path("/tmp/omol_multi_gpu")
    temp_dir.mkdir(exist_ok=True)
    
    print("\nFile distribution:")
    session_names = []
    
    # Create file lists and screen sessions
    omol_script = Path(__file__).parent / "omol_optimize.py"
    if not omol_script.exists():
        print(f"Error: omol_optimize.py not found at {omol_script}")
        sys.exit(1)
    
    for i, gpu_id in enumerate(gpu_ids):
        conformer_group = gpu_groups[i]
        if not conformer_group:
            print(f"GPU {gpu_id} (process {i}): No files assigned")
            continue
            
        print(f"GPU {gpu_id} (process {i}): {len(conformer_group)} files")
        
        # Save file list with unique process ID to avoid conflicts
        file_list_path = temp_dir / f"process_{i:03d}_gpu_{gpu_id}_files.txt"
        save_file_list(conformer_group, file_list_path)
        
        # Create screen session with unique process and GPU identifiers
        session_name, screen_cmd = create_screen_session(
            i, gpu_id, file_list_path, omol_script,
            args.output_dir, args.fmax, args.steps, args.verbose
        )
        
        session_names.append(session_name)
        
        print(f"Starting screen session: {session_name}")
        subprocess.run(screen_cmd)
        time.sleep(1)  # Small delay between session starts
    
    print(f"\nStarted {len(session_names)} screen sessions")
    print("Use 'screen -ls' to list sessions")
    print("Use 'screen -r <session_name>' to attach to a session")
    
    if args.monitor:
        print("\nMonitoring sessions (Ctrl+C to stop monitoring)...")
        try:
            while True:
                status = check_screen_sessions(session_names)
                running = sum(status.values())
                
                if running == 0:
                    print("All sessions completed!")
                    break
                
                print(f"\rRunning sessions: {running}/{len(session_names)}", end="", flush=True)
                time.sleep(10)
                
        except KeyboardInterrupt:
            print("\nStopped monitoring. Sessions continue running in background.")
    
    print(f"\nCleanup: Remove temporary files in {temp_dir} when done")


if __name__ == "__main__":
    main()