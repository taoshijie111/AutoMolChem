#!/usr/bin/env python3
"""
Script for performing structure optimization using the uma-s-1 model.
Takes conformer XYZ files as input and optimizes them using FAIRChem.
"""

import argparse
import logging
import sys
import time
from pathlib import Path
from typing import Tuple

import os
os.environ['OMP_NUM_THREADS'] = '1'
# import fix_dns_issus
# os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'

import numpy as np
from ase import Atoms
from ase.io import read, write
from ase.optimize import LBFGS
from ase.units import Bohr, Hartree
from fairchem.core import pretrained_mlip, FAIRChemCalculator
from fairchem.core.units.mlip_unit.api.inference import InferenceSettings


def optimize_structure(atoms: Atoms, calc, fmax: float = 5e-4, steps: int = 1000, 
                      output_dir: Path = None) -> Tuple[Atoms, bool]:
    """Optimize molecular structure using uma-s-1 model.
    
    Returns:
        Tuple[Atoms, bool]: (optimized atoms, convergence_status)
    """
    atoms.calc = calc
    
    if output_dir:
        traj_file = output_dir / "trajectory.out"
        optimizer = LBFGS(atoms, trajectory=str(traj_file), logfile=output_dir / 'opt.log')
    else:
        optimizer = LBFGS(atoms, logfile='opt.log')
    
    converged = optimizer.run(fmax, steps)
    return atoms, converged


def write_optimization_outputs(atoms: Atoms, output_dir: Path, smiles: str, energy: float, converged: bool = True):
    """Write all output files for an optimized molecule."""
    omol_opt_dir = output_dir / "omol_opt"
    omol_opt_dir.mkdir(parents=True, exist_ok=True)
    
    xyz_file = omol_opt_dir / f"optimized.xyz"
    # Create a copy of atoms without forces to avoid writing force information
    atoms_copy = atoms.copy()
    if hasattr(atoms_copy, 'arrays') and 'forces' in atoms_copy.arrays:
        del atoms_copy.arrays['forces']
    write(xyz_file, atoms_copy, comment=smiles)
    
    # energy_file = output_dir / "energy"
    energy_hartree = energy / Hartree
    # with energy_file.open("w") as f:
    #     f.write(f"$energy\n     1     {energy_hartree:.10f}     {energy_hartree:.10f}     {energy_hartree:.10f}\n$end\n")
    
    forces = atoms.get_forces(apply_constraint=True, md=False)
    gradient = -forces * Bohr / Hartree
    grad_norm = np.linalg.norm(gradient)
    
    # grad_file = output_dir / "gradient"
    # with grad_file.open("w") as f:
    #     f.write("$grad\n")
    #     f.write(f" cycle = 1   SCF energy = {energy_hartree:.10f}  |dE/dxyz| = {grad_norm:.10f}\n")
        
    #     for (x, y, z), symbol in zip(atoms.positions, atoms.get_chemical_symbols()):
    #         f.write(f"{x / Bohr:20.14f}  {y / Bohr:20.14f}  {z / Bohr:20.14f} {symbol.lower():>2}\n")
        
    #     np.savetxt(f, gradient, fmt="%20.14f")
    #     f.write("$end\n")
    
    info_file = omol_opt_dir / "info.txt"
    with info_file.open("w") as f:
        f.write(f"SMILES: {smiles}\n")
        f.write(f"Total Energy: {energy:.10f} eV\n")
        f.write(f"Total Energy: {energy_hartree:.10f} Hartree\n")
        f.write(f"Gradient Norm: {grad_norm:.10f}\n")
        f.write(f"Number of Atoms: {len(atoms)}\n")
        f.write(f"Charge: {atoms.info.get('charge', 0)}\n")
        f.write(f"Spin Multiplicity: {atoms.info.get('spin', 1)}\n")
        f.write(f"Converged: {converged}\n")


def read_conformer_info(conformer_dir: Path) -> Tuple[str, int, int]:
    """Read SMILES, charge, and spin from conformer info file."""
    info_file = conformer_dir / "rdkit_conformer" / "info.txt"
    if not info_file.exists():
        raise FileNotFoundError(f"Info file not found: {info_file}")
    
    smiles = ""
    charge = 0
    spin = 1
    
    with info_file.open("r") as f:
        for line in f:
            line = line.strip()
            if line.startswith("SMILES:"):
                smiles = line.split("SMILES:", 1)[1].strip()
            elif line.startswith("Charge:"):
                charge = int(line.split(":", 1)[1].strip())
            elif line.startswith("Spin Multiplicity:"):
                spin = int(line.split(":", 1)[1].strip())
    
    return smiles, charge, spin


def is_optimization_completed(conformer_dir: Path) -> bool:
    """Check if optimization is already completed for a conformer directory."""
    omol_opt_dir = conformer_dir / "omol_opt"
    if not omol_opt_dir.exists():
        return False
    
    # Check for essential output files that indicate successful completion
    optimized_file = omol_opt_dir / "optimized.xyz"
    info_file = omol_opt_dir / "info.txt"
    
    return optimized_file.exists() and info_file.exists()


def optimize_conformer_directory(conformer_dir: Path, calc, fmax: float, steps: int, 
                               output_dir: Path = None) -> Tuple[bool, str]:
    """Optimize a single conformer directory."""
    try:
        xyz_file = conformer_dir / "rdkit_conformer" / "conformer.xyz"
        if not xyz_file.exists():
            return False, f"Conformer XYZ file not found: {xyz_file}"
        
        # Copy conformer.xyz to omol_opt directory for reference
        if output_dir is None:
            output_dir = conformer_dir
        omol_opt_dir = output_dir / "omol_opt"
        omol_opt_dir.mkdir(parents=True, exist_ok=True)
        import shutil
        shutil.copy2(xyz_file, omol_opt_dir / "conformer.xyz")
        
        smiles, charge, spin = read_conformer_info(conformer_dir)
        
        atoms = read(xyz_file)
        atoms.info["charge"] = charge
        atoms.info["spin"] = spin
        
        start_time = time.time()
        atoms, converged = optimize_structure(atoms, calc, fmax=fmax, steps=steps, output_dir=omol_opt_dir)
        runtime = time.time() - start_time
        energy = atoms.get_potential_energy()
        
        # Only save results for converged calculations
        if converged:
            write_optimization_outputs(atoms, conformer_dir if output_dir is None else output_dir, smiles, energy, converged=True)
            return True, f"Converged - Energy: {energy:.6f} eV, Charge: {charge}, Spin: {spin}, RunTime: {runtime:.2f} seconds"
        else:
            # Remove the omol_opt directory since optimization did not converge
            if omol_opt_dir.exists():
                shutil.rmtree(omol_opt_dir)
            return False, f"Did not converge - Energy: {energy:.6f} eV, Charge: {charge}, Spin: {spin}, Max steps ({steps}) reached"
        
    except Exception as e:
        error_msg = f"Error optimizing {conformer_dir}: {str(e)}"
        logging.error(error_msg)
        return False, error_msg


def find_conformer_directories(base_dir: Path, skip_completed: bool = True) -> list[Path]:
    """Find all directories containing rdkit_conformer/conformer.xyz files, including in batch subdirectories."""
    conformer_dirs = []
    
    # Check if base_dir contains batch subdirectories
    batch_dirs = [item for item in base_dir.iterdir() if item.is_dir() and item.name.startswith('batch_')]
    
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
                        conformer_dirs.append(item)
    else:
        # Process flat structure
        for item in base_dir.iterdir():
            if item.is_dir():
                xyz_file = item / "rdkit_conformer" / "conformer.xyz"
                if xyz_file.exists():
                    # Check if optimization is already completed
                    if skip_completed and is_optimization_completed(item):
                        continue
                    conformer_dirs.append(item)
    
    return sorted(conformer_dirs)


def get_batch_output_dir(conformer_dir: Path, base_output_dir: Path, preserve_batch_structure: bool = True) -> Path:
    """Determine output directory, preserving batch structure if present."""
    if not preserve_batch_structure:
        return base_output_dir / conformer_dir.name
    
    # Check if conformer_dir is in a batch structure
    if conformer_dir.parent.name.startswith('batch_'):
        batch_name = conformer_dir.parent.name
        return base_output_dir / batch_name / conformer_dir.name
    else:
        return base_output_dir / conformer_dir.name


def main():
    parser = argparse.ArgumentParser(description="Optimize molecular structures using uma-s-1 model")
    parser.add_argument("input_dir", type=Path, nargs='?', help="Directory containing batch and conformer subdirectories")
    parser.add_argument("--file_list", type=Path, default=None,
                       help="File containing list of conformer directories to process")
    parser.add_argument("--output_dir", type=Path, default=None, 
                       help="Output directory (default: optimize in place)")
    parser.add_argument("--fmax", type=float, default=5e-4, help="Optimization threshold (eV/Å)")
    parser.add_argument("--steps", type=int, default=10000, help="Maximum optimization steps")
    parser.add_argument("--verbose", action="store_true", help="Verbose output")
    parser.add_argument("--device", default='cuda')
    parser.add_argument("--preserve_batch_structure", action="store_true", default=True,
                       help="Preserve batch directory structure in output")
    parser.add_argument("--model", choices=['uma-m-1p1', 'uma-s-1'], default='uma-m-1p1')
    parser.add_argument("--skip_completed", action="store_true", default=True,
                       help="Skip molecules that already have completed omol_opt calculations (default: True)")
    parser.add_argument("--force_recompute", action="store_true",
                       help="Force recomputation of all molecules, including completed ones")
    
    args = parser.parse_args()
    
    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    # Determine conformer directories to process
    skip_completed = args.skip_completed and not args.force_recompute
    if not skip_completed:
        print("Note: Will process ALL molecules (including already completed ones)")
        
    if args.file_list:
        # Read conformer directories from file list
        if not args.file_list.exists():
            print(f"Error: File list {args.file_list} not found")
            sys.exit(1)
        
        conformer_dirs = []
        with args.file_list.open('r') as f:
            for line in f:
                conformer_dir = Path(line.strip())
                if conformer_dir.exists():
                    # Check if optimization is already completed
                    if skip_completed and is_optimization_completed(conformer_dir):
                        continue
                    conformer_dirs.append(conformer_dir)
                else:
                    print(f"Warning: Directory not found: {conformer_dir}")
        
        if not conformer_dirs:
            if skip_completed:
                print(f"No unprocessed conformer directories found in {args.file_list}")
                print("All molecules may already be optimized. Use --force_recompute to reprocess all.")
            else:
                print(f"Error: No valid conformer directories found in {args.file_list}")
            sys.exit(1)
            
    else:
        # Use input_dir to find conformer directories
        if not args.input_dir:
            print("Error: Either input_dir or --file_list must be provided")
            sys.exit(1)
            
        if not args.input_dir.exists():
            print(f"Error: Input directory {args.input_dir} not found")
            sys.exit(1)
        
        conformer_dirs = find_conformer_directories(args.input_dir, skip_completed=skip_completed)
        if not conformer_dirs:
            if skip_completed:
                print(f"No unprocessed conformer directories found in {args.input_dir}")
                print("All molecules may already be optimized. Use --force_recompute to reprocess all.")
            else:
                print(f"Error: No conformer directories found in {args.input_dir}")
            sys.exit(1)
    
    print(f"Found {len(conformer_dirs)} conformer directories to optimize")
    
    # Count batches if batch structure is detected
    batch_counts = {}
    for conf_dir in conformer_dirs:
        if conf_dir.parent.name.startswith('batch_'):
            batch_name = conf_dir.parent.name
            batch_counts[batch_name] = batch_counts.get(batch_name, 0) + 1
    
    if batch_counts:
        print(f"Detected batch structure with {len(batch_counts)} batches:")
        for batch_name in sorted(batch_counts.keys()):
            print(f"  {batch_name}: {batch_counts[batch_name]} molecules")
    
    if args.output_dir:
        args.output_dir.mkdir(parents=True, exist_ok=True)
    
    successful = 0
    failed = 0
    converged = 0
    not_converged = 0
    
    print("Starting structure optimization...")
    
    # Load calculator once
    model_name = args.model
    print(f"Loading {model_name} model...")
    predictor = pretrained_mlip.get_predict_unit(model_name, device=args.device, inference_settings=InferenceSettings(tf32=False, 
                                                                                                            activation_checkpointing=True, 
                                                                                                            merge_mole=False, 
                                                                                                            compile=False, 
                                                                                                            wigner_cuda=False, 
                                                                                                            external_graph_gen=False, 
                                                                                                            internal_graph_gen_version=2,))
    calc = FAIRChemCalculator(predictor, task_name="omol")
    
    print(f"Sucessed Loaded {model_name} model!")
    for conformer_dir in conformer_dirs:
        if args.output_dir:
            output_subdir = get_batch_output_dir(conformer_dir, args.output_dir, args.preserve_batch_structure)
            output_subdir.mkdir(parents=True, exist_ok=True)
        else:
            output_subdir = conformer_dir
        
        success, message = optimize_conformer_directory(
            conformer_dir, calc, args.fmax, args.steps, output_subdir
        )
        
        if success:
            successful += 1
            converged += 1
            if args.verbose:
                batch_info = f" ({conformer_dir.parent.name})" if conformer_dir.parent.name.startswith('batch_') else ""
                print(f"✓ {conformer_dir.name}{batch_info}: {message}")
        else:
            failed += 1
            if "Did not converge" in message:
                not_converged += 1
            batch_info = f" ({conformer_dir.parent.name})" if conformer_dir.parent.name.startswith('batch_') else ""
            print(f"✗ {conformer_dir.name}{batch_info}: {message}")
    
    print(f"\nStructure optimization complete:")
    print(f"  Converged (saved): {converged}")
    print(f"  Did not converge: {not_converged}")
    print(f"  Failed (errors): {failed - not_converged}")
    print(f"  Total processed: {len(conformer_dirs)}")
    
    if args.output_dir:
        print(f"  Output directory: {args.output_dir}")
        if batch_counts:
            print(f"  Batch structure preserved: {args.preserve_batch_structure}")
    else:
        print(f"  Optimized in place: {args.input_dir}")


if __name__ == "__main__":
    main()
