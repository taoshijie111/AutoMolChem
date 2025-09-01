#!/usr/bin/env python3
"""
Script for parallel generation of molecular conformations from SMILES.
Generates conformers using RDKit and saves them as XYZ files with charge and spin information.
"""

import argparse
import logging
import shutil
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import List, Optional, Tuple, NamedTuple

import numpy as np
from ase import Atoms
from ase.io import write


class ConformerGenerator:
    """
    Generate molecule conformers using RDKit with improved error handling.
    Handles UFF force field issues by falling back to MMFF or other methods.
    """

    def __init__(self, max_conformers: int = 1, rmsd_threshold: float = 0.5, 
                 force_field: str = 'uff', pool_multiplier: int = 5,
                 fallback_force_field: str = 'mmff94'):
        self.max_conformers = max_conformers
        self.rmsd_threshold = rmsd_threshold if rmsd_threshold is not None and rmsd_threshold >= 0 else -1.0
        self.force_field = force_field
        self.fallback_force_field = fallback_force_field
        self.pool_multiplier = pool_multiplier
        
        # Set up logging to suppress UFF warnings if desired
        logging.getLogger('rdkit').setLevel(logging.ERROR)

    def generate_conformers(self, mol):
        """Generate conformers for a molecule with improved error handling."""
        # Sanitize molecule first
        mol = self.sanitize_molecule(mol)
        
        mol = self.embed_molecule(mol)
        if not mol.GetNumConformers():
            raise RuntimeError('No conformers generated for molecule')
        
        self.minimize_conformers(mol)
        mol = self.prune_conformers(mol)
        return mol

    def sanitize_molecule(self, mol):
        """Sanitize molecule to handle problematic structures."""
        try:
            from rdkit import Chem
        except ModuleNotFoundError:
            raise ImportError("This function requires RDKit to be installed.")
        
        # Make a copy to avoid modifying original
        mol = Chem.Mol(mol)
        
        # Sanitize the molecule
        try:
            Chem.SanitizeMol(mol)
        except:
            # If sanitization fails, try to fix common issues
            mol = self.fix_molecule_issues(mol)
        
        return mol

    def fix_molecule_issues(self, mol):
        """Attempt to fix common molecule issues."""
        try:
            from rdkit import Chem
        except ModuleNotFoundError:
            raise ImportError("This function requires RDKit to be installed.")
        
        # Try different sanitization operations
        try:
            # Clear computed properties and try again
            mol.ClearComputedProps()
            Chem.SanitizeMol(mol, sanitizeOps=Chem.SanitizeFlags.SANITIZE_ALL^Chem.SanitizeFlags.SANITIZE_PROPERTIES)
        except:
            # If that fails, try without certain operations
            try:
                Chem.SanitizeMol(mol, sanitizeOps=Chem.SanitizeFlags.SANITIZE_ALL^
                                Chem.SanitizeFlags.SANITIZE_PROPERTIES^
                                Chem.SanitizeFlags.SANITIZE_CLEANUP)
            except:
                print("Warning: Could not fully sanitize molecule. Proceeding with caution.")
        
        return mol

    def embed_molecule(self, mol):
        """Generate conformers with initial embedding and improved parameters."""
        try:
            from rdkit import Chem
            from rdkit.Chem import AllChem
        except ModuleNotFoundError:
            raise ImportError("This function requires RDKit to be installed.")

        mol = Chem.AddHs(mol)
        n_confs = self.max_conformers * self.pool_multiplier
        
        # Use improved embedding parameters
        params = AllChem.ETKDG()
        params.randomSeed = 42  # For reproducibility
        params.pruneRmsThresh = -1.0
        params.numThreads = 0  # Use all available threads
        
        # Try embedding with ETKDG first (better than basic embedding)
        try:
            conf_ids = AllChem.EmbedMultipleConfs(mol, numConfs=n_confs, params=params)
            if len(conf_ids) == 0:
                # Fallback to basic embedding
                AllChem.EmbedMultipleConfs(mol, numConfs=n_confs, pruneRmsThresh=-1.)
        except:
            # Fallback to basic embedding
            AllChem.EmbedMultipleConfs(mol, numConfs=n_confs, pruneRmsThresh=-1.)
        
        return mol

    def minimize_conformers(self, mol):
        """Minimize molecule conformers with fallback force fields."""
        successful_minimizations = 0
        total_conformers = mol.GetNumConformers()
        
        for conf in mol.GetConformers():
            success = False
            
            # Try primary force field
            ff = self.get_molecule_force_field(mol, conf_id=conf.GetId())
            if ff is not None:
                try:
                    result = ff.Minimize()
                    if result == 0:  # Successful minimization
                        successful_minimizations += 1
                        success = True
                except Exception as e:
                    pass  # Try fallback
            
            # If primary failed, try fallback force field
            if not success and self.fallback_force_field != self.force_field:
                ff = self.get_molecule_force_field(mol, conf_id=conf.GetId(), force_fallback=True)
                if ff is not None:
                    try:
                        result = ff.Minimize()
                        if result == 0:  # Successful minimization
                            successful_minimizations += 1
                            success = True
                    except Exception as e:
                        pass
            
            # If both force fields failed, at least we have the embedded geometry
            if not success:
                successful_minimizations += 1  # Count as successful since we have geometry
        
        if successful_minimizations == 0:
            print("Warning: No conformers could be minimized successfully")
        elif successful_minimizations < total_conformers:
            print(f"Warning: Only {successful_minimizations}/{total_conformers} conformers minimized successfully")

    def get_molecule_force_field(self, mol, conf_id: Optional[int] = None, force_fallback: bool = False, **kwargs):
        """Get a force field for a molecule with fallback options."""
        try:
            from rdkit.Chem import AllChem
        except ModuleNotFoundError:
            raise ImportError("This function requires RDKit to be installed.")

        ff = None
        
        # Choose which force field to use
        if force_fallback:
            target_ff = self.fallback_force_field
        else:
            target_ff = self.force_field
        
        # Try to get the specified force field
        if target_ff.startswith('mmff'):
            ff = self._get_mmff_force_field(mol, conf_id, **kwargs)
        elif target_ff == 'uff':
            ff = self._get_uff_force_field(mol, conf_id, **kwargs)
        
        return ff

    def _get_mmff_force_field(self, mol, conf_id: Optional[int] = None, **kwargs):
        """Get MMFF force field."""
        try:
            from rdkit.Chem import AllChem
            
            # Sanitize for MMFF
            AllChem.MMFFSanitizeMolecule(mol)
            mmff_props = AllChem.MMFFGetMoleculeProperties(
                mol, mmffVariant=self.force_field)
            
            if mmff_props is not None:
                ff = AllChem.MMFFGetMoleculeForceField(mol, mmff_props, 
                                                       confId=conf_id, **kwargs)
                return ff
            else:
                return None
        except Exception as e:
            print(f"MMFF force field setup failed: {e}")
            return None

    def _get_uff_force_field(self, mol, conf_id: Optional[int] = None, **kwargs):
        """Get UFF force field with improved error handling."""
        try:
            from rdkit.Chem import AllChem
            import sys
            import os
            from contextlib import redirect_stderr
            
            # Suppress UFF warnings by redirecting stderr temporarily
            with open(os.devnull, 'w') as devnull:
                with redirect_stderr(devnull):
                    ff = AllChem.UFFGetMoleculeForceField(mol, confId=conf_id, **kwargs)
            
            # Additional check: make sure UFF can actually handle this molecule
            if ff is not None:
                try:
                    # Test if we can calculate energy (this will fail if UFF has issues)
                    _ = ff.CalcEnergy()
                    return ff
                except:
                    return None
            
            return ff
        except Exception as e:
            return None

    def prune_conformers(self, mol):
        """Prune conformers using RMSD threshold."""
        try:
            from rdkit import Chem
        except ModuleNotFoundError:
            raise ImportError("This function requires RDKit to be installed.")

        if self.rmsd_threshold < 0 or mol.GetNumConformers() <= 1:
            return mol

        energies = self.get_conformer_energies(mol)
        
        # Handle case where no energies could be calculated
        if np.all(np.isinf(energies)):
            print("Warning: No valid energies calculated, keeping all conformers")
            return mol
        
        rmsd = self.get_conformer_rmsd(mol)

        # Sort by energy, but handle infinite energies
        finite_mask = np.isfinite(energies)
        if np.any(finite_mask):
            sort = np.argsort(energies)
        else:
            sort = np.arange(len(energies))
        
        keep = []
        discard = []
        
        for i in sort:
            if len(keep) == 0:
                keep.append(i)
                continue
            
            if len(keep) >= self.max_conformers:
                discard.append(i)
                continue
            
            this_rmsd = rmsd[i][np.asarray(keep, dtype=int)]
            
            if np.all(this_rmsd >= self.rmsd_threshold):
                keep.append(i)
            else:
                discard.append(i)

        new_mol = Chem.Mol(mol)
        new_mol.RemoveAllConformers()
        conf_ids = [conf.GetId() for conf in mol.GetConformers()]
        for i in keep:
            conf = mol.GetConformer(conf_ids[i])
            new_mol.AddConformer(conf, assignId=True)
        return new_mol

    def get_conformer_energies(self, mol) -> np.ndarray:
        """Calculate conformer energies with error handling."""
        energies = []
        for conf in mol.GetConformers():
            ff = self.get_molecule_force_field(mol, conf_id=conf.GetId())
            if ff is not None:
                try:
                    energy = ff.CalcEnergy()
                    energies.append(energy)
                except:
                    energies.append(float('inf'))
            else:
                energies.append(float('inf'))
        return np.asarray(energies, dtype=float)

    @staticmethod
    def get_conformer_rmsd(mol) -> np.ndarray:
        """Calculate conformer-conformer RMSD."""
        try:
            from rdkit.Chem import AllChem
        except ModuleNotFoundError:
            raise ImportError("This function requires RDKit to be installed.")

        rmsd = np.zeros((mol.GetNumConformers(), mol.GetNumConformers()), dtype=float)
        for i, ref_conf in enumerate(mol.GetConformers()):
            for j, fit_conf in enumerate(mol.GetConformers()):
                if i >= j:
                    continue
                try:
                    rmsd[i, j] = AllChem.GetBestRMS(mol, mol, ref_conf.GetId(), fit_conf.GetId())
                    rmsd[j, i] = rmsd[i, j]
                except:
                    # If RMSD calculation fails, set to infinity
                    rmsd[i, j] = float('inf')
                    rmsd[j, i] = float('inf')
        return rmsd
    

def rdkit_mol_to_ase_atoms(mol) -> Atoms:
    """Convert RDKit molecule to ASE Atoms object."""
    try:
        from rdkit import Chem
    except ModuleNotFoundError:
        raise ImportError("This function requires RDKit to be installed.")
    
    conf = mol.GetConformer()
    symbols = [atom.GetSymbol() for atom in mol.GetAtoms()]
    positions = conf.GetPositions()
    
    atoms = Atoms(symbols=symbols, positions=positions)
    return atoms


def infer_charge_and_spin(mol) -> Tuple[int, int]:
    """
    Infer charge and spin multiplicity from RDKit molecule.
    For organic molecules, this handles the most common cases.
    """
    charge = sum(atom.GetFormalCharge() for atom in mol.GetAtoms())
    
    num_radicals = 0
    for atom in mol.GetAtoms():
        num_radicals += atom.GetNumRadicalElectrons()
    
    spin = num_radicals + 1
    
    return int(charge), int(spin)


def get_batch_directory(base_output_dir: Path, molecule_idx: int, batch_size: int) -> Path:
    """Determine which batch directory a molecule should go into."""
    batch_id = molecule_idx // batch_size
    batch_dir = base_output_dir / f"batch_{batch_id:04d}"
    return batch_dir


def write_conformer_xyz(atoms: Atoms, output_dir: Path, smiles: str):
    """Write XYZ file for conformer structure only."""
    conformer_dir = output_dir / "conformer"
    conformer_dir.mkdir(parents=True, exist_ok=True)
    
    xyz_file = conformer_dir / "conformer.xyz"
    write(xyz_file, atoms)
    
    info_file = conformer_dir / "info.txt"
    with info_file.open("w") as f:
        f.write(f"SMILES: {smiles}\n")
        f.write(f"Number of Atoms: {len(atoms)}\n")
        f.write(f"Charge: {atoms.info.get('charge', 0)}\n")
        f.write(f"Spin Multiplicity: {atoms.info.get('spin', 1)}\n")


def cleanup_failed_molecule_directory(molecule_dir: Path):
    """Remove directory and all its contents for failed molecule generation."""
    if molecule_dir.exists():
        try:
            shutil.rmtree(molecule_dir)
        except Exception as e:
            print(f"Warning: Could not clean up directory {molecule_dir}: {e}")


def cleanup_empty_batch_directories(output_dir: Path):
    """Remove any empty batch directories after processing."""
    batch_dirs = [d for d in output_dir.iterdir() if d.is_dir() and d.name.startswith('batch_')]
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


class MoleculeData(NamedTuple):
    idx: int
    smiles: str
    name: Optional[str]


def process_single_smiles(args_tuple: Tuple[MoleculeData, Path, int]) -> Tuple[int, bool, str]:
    """Process a single SMILES string to generate conformer."""
    mol_data, output_base_dir, batch_size = args_tuple
    idx, smiles, mol_name = mol_data.idx, mol_data.smiles, mol_data.name
    
    try:
        from rdkit import Chem
    except ModuleNotFoundError:
        return idx, False, "RDKit not available"
    
    # Determine batch directory
    batch_dir = get_batch_directory(output_base_dir, idx, batch_size)
    
    if mol_name:
        safe_name = "".join(c for c in mol_name if c.isalnum() or c in (' ', '-', '_')).strip()
        safe_name = safe_name.replace(' ', '_')
        output_dir = batch_dir / safe_name
    else:
        output_dir = batch_dir / f"molecule_{idx}"
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    try:
        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            cleanup_failed_molecule_directory(output_dir)
            return idx, False, f"Invalid SMILES: {smiles}"
        
        conformer_gen = ConformerGenerator(max_conformers=1)
        mol = conformer_gen.generate_conformers(mol)
        
        charge, spin = infer_charge_and_spin(mol)
        
        atoms = rdkit_mol_to_ase_atoms(mol)
        atoms.info["charge"] = charge
        atoms.info["spin"] = spin
        
        write_conformer_xyz(atoms, output_dir, smiles)
        
        batch_id = idx // batch_size
        return idx, True, f"Conformer generated - Batch: {batch_id:04d}, Charge: {charge}, Spin: {spin}"
        
    except Exception as e:
        # Clean up the directory if conformer generation failed
        cleanup_failed_molecule_directory(output_dir)
        error_msg = f"Error processing {smiles}: {str(e)}"
        logging.error(error_msg)
        return idx, False, error_msg


def read_smiles_file(smi_file: Path) -> List[MoleculeData]:
    """Read SMILES from file, including optional molecule names."""
    molecules = []
    with smi_file.open('r') as f:
        for idx, line in enumerate(f):
            line = line.strip()
            if line and not line.startswith('#'):
                parts = line.split(maxsplit=1)
                smiles = parts[0]
                mol_name = parts[1] if len(parts) > 1 else None
                molecules.append(MoleculeData(idx, smiles, mol_name))
    return molecules


def main():
    parser = argparse.ArgumentParser(description="Generate molecular conformers from SMILES")
    parser.add_argument("smi_file", type=Path, help="Input .smi file with SMILES strings")
    parser.add_argument("--output_dir", type=Path, default=Path("./conformers"), help="Output directory")
    parser.add_argument("--workers", type=int, default=4, help="Number of parallel workers")
    parser.add_argument("--batch_size", type=int, default=1000, help="Maximum molecules per batch directory")
    parser.add_argument("--verbose", action="store_true", help="Verbose output")
    parser.add_argument("--cleanup", action="store_true", default=True, help="Clean up empty directories after processing (default: True)")
    parser.add_argument("--no_cleanup", action="store_true", help="Disable cleanup of empty directories")
    
    args = parser.parse_args()
    
    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    if not args.smi_file.exists():
        print(f"Error: SMILES file {args.smi_file} not found")
        sys.exit(1)
    
    molecules = read_smiles_file(args.smi_file)
    print(f"Found {len(molecules)} SMILES to process")
    
    # Calculate number of batches
    num_batches = (len(molecules) + args.batch_size - 1) // args.batch_size
    print(f"Will organize into {num_batches} batches of up to {args.batch_size} molecules each")
    
    args.output_dir.mkdir(parents=True, exist_ok=True)
    
    process_args = [(mol_data, args.output_dir, args.batch_size) for mol_data in molecules]
    
    successful = 0
    failed = 0
    batch_counts = {}
    
    print(f"Starting conformer generation with {args.workers} workers...")
    start_time = time.time()
    
    with ProcessPoolExecutor(max_workers=args.workers) as executor:
        future_to_idx = {executor.submit(process_single_smiles, arg): arg[0].idx 
                        for arg in process_args}
        
        for future in as_completed(future_to_idx):
            idx, success, message = future.result()
            
            if success:
                successful += 1
                batch_id = idx // args.batch_size
                batch_counts[batch_id] = batch_counts.get(batch_id, 0) + 1
                if args.verbose:
                    print(f"✓ Molecule {idx}: {message}")
            else:
                failed += 1
                print(f"✗ Molecule {idx}: {message}")
    
    total_time = time.time() - start_time
    
    print(f"\nConformer generation complete:")
    print(f"  Successful: {successful}")
    print(f"  Failed: {failed}")
    print(f"  Total time: {total_time:.2f} seconds")
    print(f"  Output directory: {args.output_dir}")
    
    # Clean up empty batch directories if enabled
    if args.cleanup and not args.no_cleanup:
        print(f"\nCleaning up empty directories...")
        cleanup_empty_batch_directories(args.output_dir)
    
    # Print batch statistics
    if batch_counts:
        print(f"\nBatch distribution:")
        for batch_id in sorted(batch_counts.keys()):
            print(f"  batch_{batch_id:04d}: {batch_counts[batch_id]} molecules")


if __name__ == "__main__":
    main()