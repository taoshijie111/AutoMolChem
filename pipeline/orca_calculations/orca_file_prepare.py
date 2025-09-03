#!/usr/bin/env python3
"""
ORCA File Preparation Script

This script prepares ORCA input files based on XYZ files from molecular conformers.
It scans for optimized.xyz files in conformer directories and generates corresponding
ORCA input files using a template file. The charge and multiplicity are automatically
estimated from the SMILES string found in the XYZ file comment line.
"""

import os
import argparse
import shutil
from pathlib import Path
import periodictable

def _extract_smiles_from_xyz(xyz_file_path):
    """
    Extract SMILES string from XYZ file comment line (second line).
    
    Args:
        xyz_file_path: Path to the XYZ file
        
    Returns:
        str: SMILES string from the comment line
    """
    with open(xyz_file_path, 'r') as f:
        lines = f.readlines()
    
    if len(lines) < 2:
        raise ValueError(f"Invalid XYZ file format: {xyz_file_path}")
    
    return lines[1].strip()


def _extract_atoms_from_xyz(xyz_file_path):
    """
    Extract atomic symbols from XYZ file.
    
    Args:
        xyz_file_path: Path to the XYZ file
        
    Returns:
        List[str]: List of atomic symbols
    """
    with open(xyz_file_path, 'r') as f:
        lines = f.readlines()
    
    if len(lines) < 3:
        raise ValueError(f"Invalid XYZ file format: {xyz_file_path}")
    
    try:
        num_atoms = int(lines[0].strip())
    except ValueError:
        raise ValueError(f"Invalid number of atoms in XYZ file: {xyz_file_path}")
    
    atoms = []
    for i in range(2, num_atoms + 2):
        if i >= len(lines):
            raise ValueError(f"Insufficient coordinate lines in XYZ file: {xyz_file_path}")
        
        parts = lines[i].strip().split()
        if len(parts) < 4:
            raise ValueError(f"Invalid coordinate line {i} in XYZ file: {xyz_file_path}")
        
        atoms.append(parts[0])
    
    return atoms


def _calculate_formal_charge_from_smiles(smiles):
    """
    Calculate molecular formal charge using RDKit's internal methods.
    
    Args:
        smiles (str): SMILES string to analyze for molecular charge.
        
    Returns:
        int: Total molecular formal charge calculated by RDKit.
        
    Raises:
        ImportError: If RDKit is not available.
        ValueError: If SMILES string is invalid.
    """
    try:
        from rdkit import Chem
    except ModuleNotFoundError:
        raise ImportError("This function requires RDKit to be installed.")
    
    # Create molecule object from SMILES
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        raise ValueError(f"Invalid SMILES string: {smiles}")
    
    # Calculate total formal charge by summing individual atom charges
    total_charge = 0
    for atom in mol.GetAtoms():
        total_charge += atom.GetFormalCharge()
    
    return total_charge


def _get_atomic_number(symbol):
    """
    Get atomic number for common elements in organic molecules.
    
    Args:
        symbol (str): Atomic symbol.
        
    Returns:
        int: Atomic number of the element.
    """

    return getattr(periodictable, symbol).number  # Default to carbon if unknown


def _calculate_multiplicity(atoms, total_charge):
    """
    Calculate spin multiplicity based on total number of electrons.
    
    Args:
        atoms (List[str]): List of atomic symbols in the molecule.
        total_charge (int): Total molecular charge.
        
    Returns:
        int: Spin multiplicity (2S + 1), where S is total spin.
    """
    # Calculate total number of electrons
    total_electrons = 0
    for atom in atoms:
        try:
            atomic_number = _get_atomic_number(atom)
            total_electrons += atomic_number
        except Exception:
            print(atom)
            raise TypeError
        
    
    # Adjust for charge
    total_electrons -= total_charge
    
    # Determine multiplicity based on electron count
    # For organic molecules, typically:
    # Even electrons -> singlet (multiplicity = 1)
    # Odd electrons -> doublet (multiplicity = 2)
    if total_electrons % 2 == 0:
        return 1  # Singlet
    else:
        return 2  # Doublet


def create_orca_input(xyz_file_path, template_file, xyz_filename, additional_charge=0, additional_multiplicity=0):
    """
    Generate ORCA input file content from template file.
    
    Args:
        xyz_file_path: Path to the XYZ file (for reading SMILES and atoms)
        template_file: Path to the ORCA template file
        xyz_filename: Filename to reference in the ORCA input
    
    Returns:
        String containing the ORCA input file content
    """
    # Read template file
    with open(template_file, 'r') as f:
        template = f.read()
    
    # Extract SMILES from XYZ file comment line
    smiles = _extract_smiles_from_xyz(xyz_file_path)
    
    # Calculate charge and multiplicity from SMILES
    base_charge = _calculate_formal_charge_from_smiles(smiles)
    charge = base_charge + additional_charge
    atoms = _extract_atoms_from_xyz(xyz_file_path)
    base_multiplicity = _calculate_multiplicity(atoms, base_charge)
    multiplicity = base_multiplicity + additional_multiplicity
    
    # Substitute template variables
    orca_content = template.replace('{charge}', str(charge))
    orca_content = orca_content.replace('{multiplicity}', str(multiplicity))
    orca_content = orca_content.replace('{xyz_file}', xyz_filename)
    
    return orca_content


def scan_conformer_directories(conformer_dir, conformer_type):
    """
    Scan for optimized.xyz files in conformer directories.
    
    Args:
        conformer_dir: Root directory of molecular conformers
        conformer_type: Source of molecular conformations
    
    Returns:
        List of tuples (batch_dir, molecule_name, xyz_file_path)
    """
    xyz_files = []
    conformer_path = Path(conformer_dir)
    
    # Look for batch_* directories
    for batch_dir in conformer_path.glob("batch_*"):
        if not batch_dir.is_dir():
            continue
            
        # Look for molecule_* directories within each batch
        for mol_dir in batch_dir.glob("*"):
            if not mol_dir.is_dir():
                continue
                
            # Look for conformer_type directory within molecule directory
            conf_type_dir = mol_dir / conformer_type
            if not conf_type_dir.exists():
                continue
                
            # Look for optimized.xyz file
            xyz_file = conf_type_dir / "optimized.xyz"
            if xyz_file.exists():
                molecule_name = mol_dir.name  # Use full directory name
                xyz_files.append((batch_dir.name, molecule_name, xyz_file))
            else:
                print(f"Warning: optimized.xyz not found in {conf_type_dir}")
    
    return xyz_files


def create_output_structure(output_dir, batch_name, molecule_name):
    """
    Create output directory structure and return the target directory path.
    
    Args:
        output_dir: Base output directory (None for default behavior)
        batch_name: Name of the batch (e.g., batch_0)
        molecule_name: Molecule directory name
    
    Returns:
        Path object for the target directory
    """
    if output_dir:
        # Create structure under specified output_dir
        target_dir = Path(output_dir) / batch_name / molecule_name
    else:
        # This will be handled differently - create alongside conformer_type
        target_dir = None
    
    if target_dir:
        target_dir.mkdir(parents=True, exist_ok=True)
    
    return target_dir


def process_conformers(conformer_dir, conformer_type, template_file, output_dir=None, output_name=None, inp_name=None, xyz_name=None, additional_charge=0, additional_multiplicity=0):
    """
    Process all conformer directories and generate ORCA input files.
    
    Args:
        conformer_dir: Root directory of molecular conformers
        conformer_type: Source of molecular conformations
        template_file: Path to ORCA template file
        output_dir: Output directory (None for default behavior)
        inp_name: Custom name for .inp file (without extension)
        xyz_name: Custom name for {xyz_file} template variable
    """
    # Scan for XYZ files
    xyz_files = scan_conformer_directories(conformer_dir, conformer_type)
    
    if not xyz_files:
        print(f"No optimized.xyz files found in {conformer_dir} with conformer type {conformer_type}")
        return
    
    print(f"Found {len(xyz_files)} XYZ files to process")
    
    for batch_name, molecule_name, xyz_file_path in xyz_files:
        print(f"Processing {batch_name}/{molecule_name}")
        
        # Determine file names
        inp_filename = inp_name if inp_name else molecule_name
        xyz_template_name = f"{xyz_name}.xyz" if xyz_name else f"{molecule_name}.xyz"
        
        if output_dir:
            # Create structure under specified output_dir
            target_dir = create_output_structure(output_dir, batch_name, molecule_name)
            xyz_target = target_dir / f"{molecule_name}.xyz"
            inp_target = target_dir / f"{inp_filename}.inp"
        else:
            # Create orca_files directory alongside conformer_type
            mol_dir = xyz_file_path.parent.parent  # Go up from conformer_type to molecule directory
            orca_dir = mol_dir / output_name
            orca_dir.mkdir(exist_ok=True)
            
            xyz_target = orca_dir / f"{molecule_name}.xyz"
            inp_target = orca_dir / f"{inp_filename}.inp"
        
        # Copy and rename XYZ file
        shutil.copy2(xyz_file_path, xyz_target)
        
        # Generate ORCA input file
        orca_content = create_orca_input(xyz_file_path, template_file, xyz_template_name, additional_charge, additional_multiplicity)
        
        # Write ORCA input file
        with open(inp_target, 'w') as f:
            f.write(orca_content)
        
        print(f"  Created: {xyz_target}")
        print(f"  Created: {inp_target}")


def main():
    """
    step1 T1 OPT:
    python orca_file_prepare.py -d * -t omol_opt -o * -f template/step1_orca_t1_opt.inp --inp_name t1_opt --additional_multiplicity 2
    
    step2 SOC:
    python orca_file_prepare.py -d * -t omol_opt -o * -f template/step2_orca_soc.inp --inp_name soc_cal --xyz_name t1_opt
    """
    parser = argparse.ArgumentParser(
        description="Prepare ORCA input files based on XYZ files from molecular conformers",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        '-d', "--conformer_dir",
        required=True,
        help="The root directory of all molecular conformers (e.g., uspto/)"
    )
    
    parser.add_argument(
        '-t', "--conformer_type",
        required=True,
        help="The source of molecular conformations (e.g., omol_opt, xtb_opt)"
    )
    
    parser.add_argument(
        '-o',"--output_dir",
        default=None,
        help="Output directory. If not provided, orca_files directories will be created alongside conformer_type"
    )
    
    parser.add_argument(
        '-on', "--output_name",
        default='orca_files',
        help="Name of the output directory (default: orca_files)"
    )
    
    parser.add_argument(
       '-f', "--template_file",
        required=True,
        help="Path to ORCA template file (e.g., utils/template/orca.inp)"
    )
    
    parser.add_argument(
        '--inp_name',
        default=None,
        help="Custom name for the .inp file (without extension). If not provided, uses directory name"
    )
    
    parser.add_argument(
        '--xyz_name', 
        default=None,
        help="Custom name for {xyz_file} template variable. If not provided, uses directory name + .xyz"
    )
    
    parser.add_argument(
        '--additional_charge',
        type=int,
        default=0,
        help="Additional charge to add to the SMILES-derived charge (default: 0)"
    )
    
    parser.add_argument(
        '--additional_multiplicity',
        type=int,
        default=0,
        help="Additional multiplicity to add to the SMILES-derived multiplicity (default: 0)"
    )
    
    args = parser.parse_args()
    
    # Validate input directory
    if not os.path.exists(args.conformer_dir):
        print(f"Error: Conformer directory '{args.conformer_dir}' does not exist")
        return 1
    
    # Validate template file
    if not os.path.exists(args.template_file):
        print(f"Error: Template file '{args.template_file}' does not exist")
        return 1
    
    # Process conformers
    process_conformers(
        args.conformer_dir,
        args.conformer_type,
        args.template_file,
        args.output_dir,
        args.output_name,
        args.inp_name,
        args.xyz_name,
        args.additional_charge,
        args.additional_multiplicity
    )
    
    print("ORCA file preparation completed!")
    return 0


if __name__ == "__main__":
    exit(main())