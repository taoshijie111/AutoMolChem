#!/usr/bin/env python3
"""
Script for XTB optimization of single molecules from XYZ files.
Optimizes molecular structures from conformer.xyz files using XTB with ohess normal calculation.
Memory-optimized version for supercomputer environments.
"""

import argparse
import json
import logging
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Tuple

try:
    from rdkit import Chem
except ImportError:
    Chem = None


def infer_charge_and_spin(smiles: str) -> Tuple[int, int]:
    """
    Infer charge and spin multiplicity from SMILES string.
    For organic molecules, this handles the most common cases.
    """
    if Chem is None:
        # Default to neutral singlet for organic molecules
        return 0, 1
    
    try:
        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            return 0, 1
        
        charge = sum(atom.GetFormalCharge() for atom in mol.GetAtoms())
        
        num_radicals = 0
        for atom in mol.GetAtoms():
            num_radicals += atom.GetNumRadicalElectrons()
        
        spin = num_radicals + 1
        
        return int(charge), int(spin)
    except:
        # Default to neutral singlet for organic molecules
        return 0, 1


def find_xtb_executable() -> str:
    """Find xtb executable in PATH."""
    xtb_path = shutil.which("xtb")
    if xtb_path is None:
        raise FileNotFoundError("xtb executable not found in PATH. Please install xtb.")
    return xtb_path


def run_xtb_optimization(xyz_file: Path, work_dir: Path, charge: int = 0, uhf: int = 0) -> Tuple[bool, str, float]:
    """
    Run xtb optimization with ohess normal calculation.
    
    Args:
        xyz_file: Path to input XYZ file
        work_dir: Working directory for the calculation
        charge: Molecular charge
        uhf: Number of unpaired electrons
        
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
    shutil.copy2(xyz_file, xtb_opt_dir / "conformer.xyz")
    
    # Use relative path for the xyz file when running in the working directory
    xyz_filename = "conformer.xyz"
    
    # Prepare command with relative path
    cmd = [xtb_cmd, xyz_filename, "--ohess", "normal", "-P", "1"]
    
    # Add charge and UHF parameters if non-default
    if charge != 0:
        cmd.extend(["--chrg", str(charge)])
    if uhf != 0:
        cmd.extend(["--uhf", str(uhf)])
    
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
            timeout=3000,  # 50 minute timeout
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


def process_single_molecule(molecule_dir: Path, skip_completed: bool = True, charge: int = None, uhf: int = None) -> Tuple[bool, str, float]:
    """
    Process a single molecule directory for XTB optimization.
    
    Args:
        molecule_dir: Path to molecule directory containing conformer/conformer.xyz
        skip_completed: Whether to skip already optimized structures
        charge: Molecular charge (if None, inferred from SMILES)
        uhf: Number of unpaired electrons (if None, inferred from SMILES)
        
    Returns:
        Tuple of (success, message, runtime)
    """
    start_time = time.time()
    
    # Check if rdkit_conformer/conformer.xyz exists
    conformer_file = molecule_dir / "rdkit_conformer" / "conformer.xyz"
    if not conformer_file.exists():
        runtime = time.time() - start_time
        return False, "No conformer/conformer.xyz file found", runtime
    
    # Check if already optimized
    opt_file = molecule_dir / "xtb_opt" / "optimized.xyz"
    if skip_completed and opt_file.exists():
        runtime = time.time() - start_time
        return True, "Already optimized (skipped)", runtime
    
    # Copy info.txt to xtb_opt directory if it exists
    info_source = molecule_dir / "rdkit_conformer" / "info.txt"
    if info_source.exists():
        xtb_opt_dir = molecule_dir / "xtb_opt"
        xtb_opt_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(info_source, xtb_opt_dir / "info.txt")
    
    # Infer charge and spin from SMILES if not provided
    if charge is None or uhf is None:
        smiles = "Unknown"
        if info_source.exists():
            with open(info_source, 'r') as f:
                for line in f:
                    if line.startswith("SMILES:"):
                        smiles = line.split("SMILES:", 1)[1].strip()
                        break
        
        if smiles != "Unknown":
            inferred_charge, inferred_spin = infer_charge_and_spin(smiles)
            if charge is None:
                charge = inferred_charge
            if uhf is None:
                uhf = inferred_spin - 1  # Convert spin multiplicity to unpaired electrons
        else:
            # Default values for organic molecules
            if charge is None:
                charge = 0
            if uhf is None:
                uhf = 0
    
    # Run optimization
    success, message, _ = run_xtb_optimization(conformer_file, molecule_dir, charge, uhf)
    
    # Clean up failed optimization directory
    if not success:
        cleanup_failed_molecule_directory(molecule_dir)
    
    total_runtime = time.time() - start_time
    
    return success, message, total_runtime


def cleanup_failed_molecule_directory(molecule_dir: Path):
    """Remove xtb_opt directory for failed optimization."""
    xtb_opt_dir = molecule_dir / "xtb_opt"
    if xtb_opt_dir.exists():
        try:
            shutil.rmtree(xtb_opt_dir)
        except Exception as e:
            print(f"Warning: Could not clean up directory {xtb_opt_dir}: {e}")


def process_json_task(json_file: Path, verbose: bool = False) -> int:
    """
    Process a JSON task file containing molecule directories to optimize.
    
    Args:
        json_file: Path to JSON file with molecule directory data
        verbose: Enable verbose output
        
    Returns:
        Number of successfully processed molecules
    """
    if not json_file.exists():
        print(f"ERROR: JSON file not found: {json_file}")
        return 0
    
    # Load task data
    try:
        with open(json_file, 'r') as f:
            task_data = json.load(f)
    except Exception as e:
        print(f"ERROR: Failed to read JSON file: {e}")
        return 0
    
    if not isinstance(task_data, list):
        print("ERROR: JSON file must contain a list of molecule data")
        return 0
    
    successful = 0
    
    for i, mol_data in enumerate(task_data):
        if not isinstance(mol_data, dict):
            print(f"ERROR: Invalid molecule data at index {i}")
            continue
        
        if 'molecule_dir' not in mol_data:
            print(f"ERROR: Missing 'molecule_dir' in data at index {i}")
            continue
        
        molecule_dir = Path(mol_data['molecule_dir'])
        name = mol_data.get('name', molecule_dir.name)
        
        if verbose:
            print(f"Processing {name} ({molecule_dir})")
        
        # Process the molecule
        success, message, runtime = process_single_molecule(molecule_dir, skip_completed=True)
        
        if success:
            successful += 1
            if verbose:
                if "skipped" in message.lower():
                    print(f"⊖ {name}: {message}")
                else:
                    print(f"✓ {name}: {message} ({runtime:.1f}s)")
        else:
            print(f"✗ {name}: {message}")
    
    return successful


def process_single_molecule_args(molecule_dir: Path, name: str, verbose: bool = False, charge: int = None, uhf: int = None) -> int:
    """
    Process a single molecule from command line arguments.
    
    Args:
        molecule_dir: Path to molecule directory
        name: Name for the molecule
        verbose: Enable verbose output
        charge: Molecular charge (if None, inferred from SMILES)
        uhf: Number of unpaired electrons (if None, inferred from SMILES)
        
    Returns:
        1 if successful, 0 if failed
    """
    if verbose:
        print(f"Processing {name} ({molecule_dir})")
    
    # Process the molecule
    success, message, runtime = process_single_molecule(molecule_dir, skip_completed=True, charge=charge, uhf=uhf)
    
    if success:
        if verbose:
            if "skipped" in message.lower():
                print(f"⊖ {name}: {message}")
            else:
                print(f"✓ {name}: {message} ({runtime:.1f}s)")
        return 1
    else:
        print(f"✗ {name}: {message}")
        return 0


def main():
    parser = argparse.ArgumentParser(description="XTB optimization for single molecules")
    
    # JSON input mode (for SLURM batch processing)
    parser.add_argument("--json", type=Path, help="JSON file containing molecule directory data")
    
    # Direct argument mode  
    parser.add_argument("--molecule-dir", type=Path, help="Molecule directory containing conformer/conformer.xyz")
    parser.add_argument("--name", type=str, help="Name for the molecule (used in output)")
    
    parser.add_argument("--verbose", action="store_true", help="Verbose output")
    parser.add_argument("--chrg", type=int, default=None, help="Molecular charge (inferred from SMILES if not provided)")
    parser.add_argument("--uhf", type=int, default=None, help="Number of unpaired electrons (inferred from SMILES if not provided)")
    
    args = parser.parse_args()
    
    # Set up logging
    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    # Check for xtb executable
    try:
        xtb_path = find_xtb_executable()
        if args.verbose:
            print(f"Found xtb executable at: {xtb_path}")
    except FileNotFoundError as e:
        print(f"Error: {e}")
        sys.exit(1)
    
    successful = 0
    
    if args.json:
        # Process JSON task file
        successful = process_json_task(args.json, args.verbose)
        
    elif args.molecule_dir:
        # Process single molecule directory
        if not args.molecule_dir.exists():
            print(f"Error: Molecule directory {args.molecule_dir} not found")
            sys.exit(1)
        
        name = args.name or args.molecule_dir.name
        successful = process_single_molecule_args(args.molecule_dir, name, args.verbose, args.chrg, args.uhf)
        
    else:
        print("Error: Must specify either --json or --molecule-dir")
        parser.print_help()
        sys.exit(1)
    
    if args.verbose:
        print(f"\nProcessing complete: {successful} molecules optimized successfully")
    
    # Exit with appropriate code
    sys.exit(0 if successful > 0 else 1)


if __name__ == "__main__":
    main()