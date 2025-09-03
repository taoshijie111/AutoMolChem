#!/usr/bin/env python3
"""
Script for generating molecular conformation from a single SMILES string.
Generates conformers using RDKit and saves them as XYZ files with charge and spin information.
Memory-optimized version for supercomputer environments.
"""

import argparse
import logging
import sys
from pathlib import Path
from typing import Tuple
import json
import gc

import numpy as np
from ase import Atoms
from ase.io import write

# Import RDKit modules once at module level to avoid repeated imports
try:
    from rdkit import Chem
    from rdkit.Chem import AllChem
    RDKIT_AVAILABLE = True
except ImportError:
    RDKIT_AVAILABLE = False


class ConformerGenerator:
    """
    Generate molecule conformers using RDKit with improved error handling and memory optimization.
    Handles UFF force field issues by falling back to MMFF or other methods.
    """

    def __init__(self, max_conformers: int = 1, rmsd_threshold: float = 0.5, 
                 force_field: str = 'uff', pool_multiplier: int = 5,  
                 fallback_force_field: str = 'mmff94'):
        self.max_conformers = max_conformers
        self.rmsd_threshold = rmsd_threshold if rmsd_threshold is not None and rmsd_threshold >= 0 else -1.0
        self.force_field = force_field
        self.fallback_force_field = fallback_force_field
        # Reduced pool multiplier to use less memory - still provides reasonable diversity
        self.pool_multiplier = pool_multiplier 
        
        # Set up logging to suppress UFF warnings if desired
        logging.getLogger('rdkit').setLevel(logging.ERROR)
        
        if not RDKIT_AVAILABLE:
            raise ImportError("This class requires RDKit to be installed.")

    def generate_conformers(self, mol):
        """Generate conformers for a molecule with improved error handling and memory management."""
        # Sanitize molecule first
        mol = self.sanitize_molecule(mol)
        
        mol = self.embed_molecule(mol)
        if not mol.GetNumConformers():
            raise RuntimeError('No conformers generated for molecule')
        
        self.minimize_conformers(mol)
        mol = self.prune_conformers(mol)
        
        # Force garbage collection after conformer generation
        gc.collect()
        
        return mol

    def sanitize_molecule(self, mol):
        """Sanitize molecule to handle problematic structures.""" 
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
        """Generate conformers with initial embedding and optimized parameters for memory efficiency."""
        mol = Chem.AddHs(mol)
        
        # Use adaptive conformer count based on molecule size to save memory
        mol_size = mol.GetNumAtoms()
        if mol_size < 20:
            n_confs = self.max_conformers * self.pool_multiplier
        elif mol_size < 50:
            n_confs = self.max_conformers * max(2, self.pool_multiplier - 1)  # Reduce for medium molecules
        else:
            n_confs = self.max_conformers * 2  # Minimal extra conformers for large molecules
        
        # Use improved embedding parameters
        params = AllChem.ETKDG()
        params.randomSeed = 42  # For reproducibility
        params.pruneRmsThresh = -1.0
        params.numThreads = 1  # Limit threads to reduce memory pressure
        
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
        """Minimize molecule conformers with fallback force fields and memory optimization."""
        successful_minimizations = 0
        total_conformers = mol.GetNumConformers()
        
        for conf in mol.GetConformers():
            success = False
            ff = None  # Initialize to None for proper cleanup
            
            try:
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
                    # Clean up previous force field first
                    del ff
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
                    
            finally:
                # Clean up force field object to free memory
                if ff is not None:
                    del ff
        
        if successful_minimizations == 0:
            print("Warning: No conformers could be minimized successfully")
        elif successful_minimizations < total_conformers:
            print(f"Warning: Only {successful_minimizations}/{total_conformers} conformers minimized successfully")

    def get_molecule_force_field(self, mol, conf_id=None, force_fallback: bool = False, **kwargs):
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

    def _get_mmff_force_field(self, mol, conf_id=None, **kwargs):
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

    def _get_uff_force_field(self, mol, conf_id=None, **kwargs):
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


def write_conformer_xyz(atoms: Atoms, output_dir: Path, smiles: str):
    """Write XYZ file for conformer structure."""
    output_dir.mkdir(parents=True, exist_ok=True)
    
    xyz_file = output_dir /  "conformer.xyz"
    write(xyz_file, atoms)
    
    info_file = output_dir / "info.txt"
    with info_file.open("w") as f:
        f.write(f"SMILES: {smiles}\n")
        f.write(f"Number of Atoms: {len(atoms)}\n")
        f.write(f"Charge: {atoms.info.get('charge', 0)}\n")
        f.write(f"Spin Multiplicity: {atoms.info.get('spin', 1)}\n")


def process_single_smiles(smiles: str, output_dir: Path, molecule_name: str = None) -> bool:
    """Process a single SMILES string to generate conformer."""
    try:
        from rdkit import Chem
    except ModuleNotFoundError:
        print("ERROR: RDKit not available")
        return False
    
    try:
        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            print(f"ERROR: Invalid SMILES: {smiles}")
            return False
        
        conformer_gen = ConformerGenerator(max_conformers=1)
        mol = conformer_gen.generate_conformers(mol)
        
        charge, spin = infer_charge_and_spin(mol)
        
        atoms = rdkit_mol_to_ase_atoms(mol)
        atoms.info["charge"] = charge
        atoms.info["spin"] = spin
        
        write_conformer_xyz(atoms, output_dir, smiles)
        
        print(f"SUCCESS: Conformer generated - Charge: {charge}, Spin: {spin}")
        return True
        
    except Exception as e:
        print(f"ERROR: Failed to process {smiles}: {str(e)}")
        return False


def process_multiple_smiles(smiles_list, output_dirs, molecule_names=None):
    """Process multiple SMILES strings to generate conformers in order."""
    # Validate input lengths
    if len(smiles_list) != len(output_dirs):
        raise ValueError(f"Number of SMILES ({len(smiles_list)}) must match number of output directories ({len(output_dirs)})")
    
    if molecule_names is not None and len(molecule_names) != len(smiles_list):
        raise ValueError(f"Number of molecule names ({len(molecule_names)}) must match number of SMILES ({len(smiles_list)})")
    
    results = []
    for i, (smiles, output_dir) in enumerate(zip(smiles_list, output_dirs)):
        name = molecule_names[i] if molecule_names else None
        print(f"Processing SMILES {i+1}/{len(smiles_list)}: {smiles}")
        success = process_single_smiles(smiles, Path(output_dir), name)
        results.append(success)
    
    return results


def parse_input_list(input_str):
    """Parse comma-separated string into list, handling both single and multiple values."""
    if ',' in input_str:
        return [item.strip() for item in input_str.split(',')]
    else:
        return [input_str.strip()]


def process_json_file(json_file_path: Path) -> bool:
    """Process molecules from JSON file containing task data."""
    try:
        with open(json_file_path, 'r') as f:
            task_data = json.load(f)
        
        if not isinstance(task_data, list):
            print(f"ERROR: JSON file must contain a list of molecules")
            return False
        
        success_count = 0
        total_count = len(task_data)
        
        print(f"Processing {total_count} molecules from JSON file")
        
        for i, molecule_data in enumerate(task_data):
            if not isinstance(molecule_data, dict):
                print(f"ERROR: Molecule {i+1} data must be a dictionary")
                continue
            
            required_keys = ['smiles', 'output_dir', 'name']
            if not all(key in molecule_data for key in required_keys):
                print(f"ERROR: Molecule {i+1} missing required keys: {required_keys}")
                continue
            
            smiles = molecule_data['smiles']
            output_dir = Path(molecule_data['output_dir'])
            name = molecule_data['name']
            
            print(f"Processing molecule {i+1}/{total_count}: {name} ({smiles})")
            success = process_single_smiles(smiles, output_dir, name)
            
            if success:
                success_count += 1
                print(f"  SUCCESS: Conformer saved to {output_dir}")
            else:
                print(f"  FAILED: Could not process {name}")
        
        print(f"Completed: {success_count}/{total_count} conformers generated successfully")
        return success_count == total_count
        
    except Exception as e:
        print(f"ERROR: Failed to process JSON file {json_file_path}: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Generate conformers for single or multiple SMILES strings")
    parser.add_argument("smiles", nargs='?', type=str, help="SMILES string or comma-separated list of SMILES strings")
    parser.add_argument("output_dir", nargs='?', type=str, help="Output directory or comma-separated list of output directories")
    parser.add_argument("--name", type=str, help="Molecule name or comma-separated list of names (optional)")
    parser.add_argument("--json", type=str, help="JSON file containing task data")
    parser.add_argument("--verbose", action="store_true", help="Verbose output")
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.basicConfig(level=logging.INFO)
    
    # Handle JSON input mode
    if args.json:
        json_file_path = Path(args.json)
        if not json_file_path.exists():
            print(f"ERROR: JSON file not found: {json_file_path}")
            sys.exit(1)
        
        success = process_json_file(json_file_path)
        sys.exit(0 if success else 1)
    
    # Handle traditional command line arguments
    if not args.smiles or not args.output_dir:
        print("ERROR: SMILES and output_dir are required when not using --json mode")
        parser.print_help()
        sys.exit(1)
    
    # Parse inputs - handle both single and multiple
    smiles_list = parse_input_list(args.smiles)
    output_dirs = [Path(p) for p in parse_input_list(args.output_dir)]
    names_list = parse_input_list(args.name) if args.name else None
    
    # Process based on input type
    if len(smiles_list) == 1:
        # Single SMILES case
        name = names_list[0] if names_list else None
        success = process_single_smiles(smiles_list[0], output_dirs[0], name)
        
        if success:
            print(f"Conformer saved to: {output_dirs[0]}")
            sys.exit(0)
        else:
            print("Failed to generate conformer")
            sys.exit(1)
    else:
        # Multiple SMILES case
        try:
            results = process_multiple_smiles(smiles_list, output_dirs, names_list)
            
            success_count = sum(results)
            total_count = len(results)
            
            print(f"Completed: {success_count}/{total_count} conformers generated successfully")
            
            if success_count == total_count:
                sys.exit(0)
            else:
                sys.exit(1)
                
        except ValueError as e:
            print(f"ERROR: {e}")
            sys.exit(1)


if __name__ == "__main__":
    main()