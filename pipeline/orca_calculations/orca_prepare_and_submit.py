#!/usr/bin/env python3
"""
ORCA File Preparation and Submission Script

This script combines the functionality of orca_file_prepare.py and run_all_check.py
to prepare ORCA input files and submit jobs in a single step. It supports both
single-step calculations (S1/T1 gaps) and two-step calculations (S0 optimization + SOC).

Usage Examples:
    # Single-step S1/T1 calculation
    python orca_prepare_and_submit.py -d data_dir -t omol_opt --single-step
    
    # Two-step S0 optimization + SOC calculation  
    python orca_prepare_and_submit.py -d data_dir -t omol_opt --two-step
    
    # Custom templates and submission script
    python orca_prepare_and_submit.py -d data_dir -t omol_opt \
        --template template/custom.inp --submit-script custom.sh
"""

import os
import argparse
import shutil
import subprocess
import time
from pathlib import Path
import periodictable


def _extract_smiles_from_xyz(xyz_file_path):
    """Extract SMILES string from XYZ file comment line (second line)."""
    with open(xyz_file_path, 'r') as f:
        lines = f.readlines()
    
    if len(lines) < 2:
        raise ValueError(f"Invalid XYZ file format: {xyz_file_path}")
    
    return lines[1].strip()


def _extract_atoms_from_xyz(xyz_file_path):
    """Extract atomic symbols from XYZ file."""
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
    """Calculate molecular formal charge using RDKit's internal methods."""
    try:
        from rdkit import Chem
    except ModuleNotFoundError:
        raise ImportError("This function requires RDKit to be installed.")
    
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        raise ValueError(f"Invalid SMILES string: {smiles}")
    
    total_charge = 0
    for atom in mol.GetAtoms():
        total_charge += atom.GetFormalCharge()
    
    return total_charge


def _get_atomic_number(symbol):
    """Get atomic number for common elements in organic molecules."""
    return getattr(periodictable, symbol).number


def _calculate_multiplicity(atoms, total_charge):
    """Calculate spin multiplicity based on total number of electrons."""
    total_electrons = 0
    for atom in atoms:
        try:
            atomic_number = _get_atomic_number(atom)
            total_electrons += atomic_number
        except Exception:
            print(f"Unknown atom: {atom}")
            raise TypeError
    
    total_electrons -= total_charge
    
    if total_electrons % 2 == 0:
        return 1  # Singlet
    else:
        return 2  # Doublet


def create_orca_input(xyz_file_path, template_file, xyz_filename, additional_charge=0, additional_multiplicity=0):
    """Generate ORCA input file content from template file."""
    with open(template_file, 'r') as f:
        template = f.read()
    
    smiles = _extract_smiles_from_xyz(xyz_file_path)
    base_charge = _calculate_formal_charge_from_smiles(smiles)
    charge = base_charge + additional_charge
    atoms = _extract_atoms_from_xyz(xyz_file_path)
    base_multiplicity = _calculate_multiplicity(atoms, base_charge)
    multiplicity = base_multiplicity + additional_multiplicity
    
    orca_content = template.replace('{charge}', str(charge))
    orca_content = orca_content.replace('{multiplicity}', str(multiplicity))
    orca_content = orca_content.replace('{xyz_file}', xyz_filename)
    
    return orca_content


def process_molecule(batch_name, molecule_name, xyz_file_path, output_dir, output_name, 
                     calculation_type, template_files, submit_script, max_jobs):
    """Process a single molecule: prepare files and submit job."""
    print(f"Processing {batch_name}/{molecule_name}")
    
    # Create target directory
    if output_dir:
        target_dir = Path(output_dir) / batch_name / molecule_name
    else:
        mol_dir = xyz_file_path.parent.parent
        target_dir = mol_dir / output_name
    
    # Determine step number based on calculation type
    step_num = 2 if calculation_type == "two-step" else 1
    
    # Check if job is already completed before preparing files
    if target_dir.exists() and output_is_complete(target_dir, step_num):
        print(f"  Job already completed, skipping.")
        return False
    
    # Prepare files based on calculation type
    if calculation_type == "single-step":
        inp_files = prepare_single_step_files(xyz_file_path, target_dir, molecule_name, 
                                              template_files[0])
    elif calculation_type == "two-step":
        inp_files = prepare_two_step_files(xyz_file_path, target_dir, molecule_name, 
                                           template_files[0], template_files[1])
    
    print(f"  Created input files: {[f.name for f in inp_files]}")
    
    # Submit job
    return submit_job(target_dir, submit_script, step_num, max_jobs)


def check_job_queue(max_jobs=200):
    """Check if the number of jobs in the queue is smaller than max_jobs."""
    try:
        # Run squeue command to get the number of jobs in the queue for the user
        result = subprocess.run(['squeue', '-u', os.environ['USER']], stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        job_count = len(result.stdout.strip().split('\n')) - 1  # Subtracting the header line
        return job_count < max_jobs
    except subprocess.CalledProcessError as e:
        print(f"Error checking job queue: {e}")
        return False


def output_is_complete(folder_path, step_num=1, success_marker="****ORCA TERMINATED NORMALLY****"):
    """
    Check if output files in the folder contain the success_marker string in the second-to-last line.
    
    Parameters:
    - folder_path: Path to the directory to search for output files.
    - step_num: Number of steps expected (1 for single-step, 2 for two-step calculations).
    - success_marker: The string indicating successful termination.
    
    Returns:
    - True if all required output files contain the success_marker in the second-to-last line.
    - False otherwise.
    """
    output_files = [f for f in os.listdir(folder_path) if f.endswith(".output")]
    
    # Check if we have the expected number of output files
    if len(output_files) < step_num:
        return False
    
    # Check each output file for success marker in second-to-last line
    completed_count = 0
    for filename in output_files:
        output_file_path = os.path.join(folder_path, filename)
        try:
            with open(output_file_path, 'r') as file:
                lines = file.readlines()
                if len(lines) < 2:
                    continue  # File too short, skip
                
                # Check second-to-last line
                second_to_last_line = lines[-2].strip()
                if success_marker in second_to_last_line:
                    completed_count += 1
        except Exception as e:
            print(f"Error reading {output_file_path}: {e}")
            return False
    
    # Return True only if we have at least step_num completed files
    return completed_count >= step_num


def prepare_single_step_files(xyz_file_path, target_dir, molecule_name, template_file):
    """Prepare files for single-step S1/T1 calculation."""
    target_dir.mkdir(parents=True, exist_ok=True)
    
    xyz_target = target_dir / f"{molecule_name}.xyz"
    inp_target = target_dir / f"{molecule_name}.inp"
    
    shutil.copy2(xyz_file_path, xyz_target)
    
    orca_content = create_orca_input(xyz_file_path, template_file, f"{molecule_name}.xyz")
    
    with open(inp_target, 'w') as f:
        f.write(orca_content)
    
    return [inp_target]


def prepare_two_step_files(xyz_file_path, target_dir, molecule_name, step1_template, step2_template):
    """Prepare files for two-step S0 optimization + SOC calculation."""
    target_dir.mkdir(parents=True, exist_ok=True)
    
    xyz_target = target_dir / f"{molecule_name}.xyz"
    s0_opt_target = target_dir / "s0_opt.inp"
    soc_cal_target = target_dir / "soc_cal.inp"
    
    shutil.copy2(xyz_file_path, xyz_target)
    
    # Step 1: S0 optimization
    s0_opt_content = create_orca_input(xyz_file_path, step1_template, f"{molecule_name}.xyz")
    with open(s0_opt_target, 'w') as f:
        f.write(s0_opt_content)
    
    # Step 2: SOC calculation
    soc_cal_content = create_orca_input(xyz_file_path, step2_template, "s0_opt.xyz")
    with open(soc_cal_target, 'w') as f:
        f.write(soc_cal_content)
    
    return [s0_opt_target, soc_cal_target]


def submit_job(target_dir, submit_script_path, step_num=1, max_jobs=200):
    """Submit ORCA job."""
    # Wait for queue space
    while not check_job_queue(max_jobs):
        print("Too many jobs in the queue. Sleeping for 60 second...")
        time.sleep(60)
    
    # Copy submission script
    submit_script_target = target_dir / Path(submit_script_path).name
    try:
        shutil.copy(submit_script_path, submit_script_target)
        print(f"Copied submission script to {target_dir}")
    except Exception as e:
        print(f"Error copying submission script to {target_dir}: {e}")
        return False
    
    # Submit job
    command = ["sbatch", submit_script_target.name]
    try:
        print(f"Submitting job in: {target_dir}")
        subprocess.run(command, cwd=target_dir, check=True)
        time.sleep(0.5)
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error submitting job in {target_dir}: {e}")
        return False


def process_conformers_and_submit(conformer_dir, conformer_type, output_dir, output_name, calculation_type, 
                                  template_files, submit_script, max_jobs=200):
    """Scan conformer directories and submit jobs on-the-fly."""
    conformer_path = Path(conformer_dir)
    
    submitted_count = 0
    skipped_count = 0
    total_count = 0
    
    print("Starting conformer scanning and job submission...")
    
    for batch_dir in conformer_path.glob("batch_*"):
        if not batch_dir.is_dir():
            continue
            
        for mol_dir in batch_dir.glob("*"):
            if not mol_dir.is_dir():
                continue
                
            conf_type_dir = mol_dir / conformer_type
            if not conf_type_dir.exists():
                continue
                
            xyz_file = conf_type_dir / "optimized.xyz"
            if xyz_file.exists():
                molecule_name = mol_dir.name
                total_count += 1
                
                # Process and submit immediately
                if process_molecule(batch_dir.name, molecule_name, xyz_file, output_dir, 
                                  output_name, calculation_type, template_files, submit_script, max_jobs):
                    submitted_count += 1
                    print(f' Submitted Count: {submitted_count}')
                else:
                    skipped_count += 1
            else:
                print(f"Warning: optimized.xyz not found in {conf_type_dir}")
    
    if total_count == 0:
        print(f"No optimized.xyz files found in {conformer_dir} with conformer type {conformer_type}")
        return
    
    print(f"\nJob submission completed!")
    print(f"  Total molecules found: {total_count}")
    print(f"  Submitted: {submitted_count}")
    print(f"  Skipped: {skipped_count}")


def main():
    parser = argparse.ArgumentParser(
        description="Prepare ORCA input files and submit jobs in one step",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        '-d', "--conformer_dir",
        required=True,
        help="The root directory of all molecular conformers"
    )
    
    parser.add_argument(
        '-t', "--conformer_type",
        required=True,
        help="The source of molecular conformations (e.g., omol_opt, xtb_opt)"
    )
    
    parser.add_argument(
        '-o', "--output_dir",
        default=None,
        help="Output directory. If not provided, directories will be created alongside conformer_type"
    )
    
    parser.add_argument(
        '-on', "--output_name",
        default='orca_files',
        help="Name of the output directory when not using --output_dir (default: orca_files)"
    )
    
    # Calculation type selection
    calc_group = parser.add_mutually_exclusive_group(required=True)
    calc_group.add_argument(
        '--single-step',
        action='store_true',
        help="Single-step S1/T1 gap calculation"
    )
    calc_group.add_argument(
        '--two-step',
        action='store_true',
        help="Two-step S0 optimization + SOC calculation"
    )
    
    # Template and script options
    parser.add_argument(
        '--template',
        help="Custom template file (for single-step) or first template (for two-step)"
    )
    parser.add_argument(
        '--template2',
        help="Second template file (only for two-step calculations)"
    )
    parser.add_argument(
        '--submit-script',
        help="Custom submission script path"
    )
    
    # Job management options
    parser.add_argument(
        '--max-jobs',
        type=int,
        default=200,
        help="Maximum number of jobs in queue before waiting (default: 200)"
    )
    
    args = parser.parse_args()
    
    # Validate input directory
    if not os.path.exists(args.conformer_dir):
        print(f"Error: Conformer directory '{args.conformer_dir}' does not exist")
        return 1
    
    # Set default templates and submission scripts based on calculation type
    if args.single_step:
        calculation_type = "single-step"
        default_template = "template/orca_s1t1.inp"
        default_submit_script = "orca_script.sh"
        template_files = [args.template or default_template]
    elif args.two_step:
        calculation_type = "two-step"
        default_template1 = "template/step1_orca_s0_opt.inp"
        default_template2 = "template/step2_orca_soc.inp"
        default_submit_script = "orca_soc.sh"
        template_files = [
            args.template or default_template1,
            args.template2 or default_template2
        ]
    
    submit_script = args.submit_script or default_submit_script
    
    # Validate template files
    for template_file in template_files:
        if not os.path.exists(template_file):
            print(f"Error: Template file '{template_file}' does not exist")
            return 1
    
    # Validate submission script
    if not os.path.exists(submit_script):
        print(f"Error: Submission script '{submit_script}' does not exist")
        return 1
    
    print(f"Starting {calculation_type} ORCA preparation and submission...")
    print(f"Template files: {template_files}")
    print(f"Submission script: {submit_script}")
    print(f"Max jobs in queue: {args.max_jobs}")
    
    # Process conformers and submit jobs
    process_conformers_and_submit(
        args.conformer_dir,
        args.conformer_type,
        args.output_dir,
        args.output_name,
        calculation_type,
        template_files,
        submit_script,
        args.max_jobs
    )
    
    print("ORCA preparation and submission completed!")
    return 0


if __name__ == "__main__":
    exit(main())