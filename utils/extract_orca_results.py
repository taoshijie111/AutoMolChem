#!/usr/bin/env python3
"""
Extract quantum chemistry calculation results from ORCA output files.
Extracts S1, T1 energies, SOC matrix elements, and absorption spectrum data.
"""

import os
import re
import csv
import glob
import numpy as np
import argparse

def extract_smiles_from_xyz(xyz_file):
    """Extract SMILES string from the second line of .xyz file."""
    try:
        with open(xyz_file, 'r') as f:
            f.readline()  # Skip first line (atom count)
            smiles = f.readline().strip()
            return smiles
    except (FileNotFoundError, IndexError):
        return ""

def extract_excited_states(output_content):
    """Extract S1 and T1 excited state energies."""
    # Extract S1 energy (STATE 1 in singlets section)
    s1_pattern = r'STATE\s+1:\s+E=\s+[\d\.-]+\s+au\s+([\d\.]+)\s+eV.*?<S\*\*2>\s+=\s+[\d\.]+\s+Mult\s+1'
    s1_match = re.search(s1_pattern, output_content)
    s1_energy = float(s1_match.group(1)) if s1_match else None
    
    # Extract T1 energy (first triplet state with Mult 3)
    t1_pattern = r'STATE\s+\d+:\s+E=\s+[\d\.-]+\s+au\s+([\d\.]+)\s+eV.*?<S\*\*2>\s+=\s+[\d\.]+\s+Mult\s+3'
    t1_match = re.search(t1_pattern, output_content)
    t1_energy = float(t1_match.group(1)) if t1_match else None
    
    return s1_energy, t1_energy

def extract_soc_matrix_elements(output_content):
    """Extract SOC matrix elements for all T-S couplings."""
    # Look for SOC matrix elements section
    soc_pattern = r'CALCULATED SOCME BETWEEN TRIPLETS AND SINGLETS(.*?)SOC stabilization'
    soc_match = re.search(soc_pattern, output_content, re.DOTALL)
    
    soc_elements = {}
    if soc_match:
        lines = soc_match.group(1).split('\n')
        
        for line in lines:
            # Pattern to match SOC matrix element lines
            # Format: T S (Re_Z, Im_Z) (Re_X, Im_X) (Re_Y, Im_Y)
            pattern = r'^\s*(\d+)\s+(\d+)\s+\(\s*([-\d\.]+)\s*,\s*([-\d\.]+)\s*\)\s+\(\s*([-\d\.]+)\s*,\s*([-\d\.]+)\s*\)\s+\(\s*([-\d\.]+)\s*,\s*([-\d\.]+)\s*\)'
            match = re.match(pattern, line.strip())
            
            if match:
                t_state = int(match.group(1))
                s_state = int(match.group(2))
                
                # Extract real and imaginary parts for Z, X, Y components
                z_re, z_im = float(match.group(3)), float(match.group(4))
                x_re, x_im = float(match.group(5)), float(match.group(6))
                y_re, y_im = float(match.group(7)), float(match.group(8))
                
                # Calculate magnitude of the SOC matrix element
                # Total magnitude = sqrt(|Z|^2 + |X|^2 + |Y|^2)
                z_mag = np.sqrt(z_re**2 + z_im**2)
                x_mag = np.sqrt(x_re**2 + x_im**2)
                y_mag = np.sqrt(y_re**2 + y_im**2)
                total_mag = np.sqrt(z_mag**2 + x_mag**2 + y_mag**2)
                
                # Store with key format 'S*-T*'
                key = f'S{s_state}-T{t_state}'
                soc_elements[key] = total_mag
    
    return soc_elements

def extract_absorption_spectrum(output_content):
    """Extract absorption spectrum data (regular and SOC-corrected)."""
    # Regular absorption spectrum
    abs_pattern = r'ABSORPTION SPECTRUM VIA TRANSITION ELECTRIC DIPOLE MOMENTS\s+(.*?)(?=\n\s*\n|\nSOC|$)'
    abs_match = re.search(abs_pattern, output_content, re.DOTALL)
    
    e_abs, f_abs = [], []
    if abs_match:
        lines = abs_match.group(1).split('\n')
        for line in lines:
            # Parse transition lines: look for energy and oscillator strength
            pattern = r'^\s*\d+-\d+[A-Z]\s+->\s+\d+-\d+[A-Z]\s+([\d\.]+)\s+[\d\.]+\s+[\d\.]+\s+([\d\.]+)'
            match = re.match(pattern, line.strip())
            if match:
                energy_ev = float(match.group(1))
                osc_strength = float(match.group(2))
                e_abs.append(energy_ev)
                f_abs.append(osc_strength)
    
    # SOC-corrected absorption spectrum
    soc_abs_pattern = r'SOC CORRECTED ABSORPTION SPECTRUM VIA TRANSITION ELECTRIC DIPOLE MOMENTS\s+(.*?)(?=\n\s*\n|SOC CORRECTED ABSORPTION SPECTRUM VIA TRANSITION VELOCITY|$)'
    soc_abs_match = re.search(soc_abs_pattern, output_content, re.DOTALL)
    
    e_abs_soc, f_abs_soc = [], []
    if soc_abs_match:
        lines = soc_abs_match.group(1).split('\n')
        for line in lines:
            # Parse SOC transition lines
            pattern = r'^\s*\d+-[\d\.]+[A-Z]\s+->\s+\d+-[\d\.]+[A-Z]\s+([\d\.]+)\s+[\d\.]+\s+[\d\.]+\s+([\d\.]+)'
            match = re.match(pattern, line.strip())
            if match:
                energy_ev = float(match.group(1))
                osc_strength = float(match.group(2))
                e_abs_soc.append(energy_ev)
                f_abs_soc.append(osc_strength)
    
    return e_abs, f_abs, e_abs_soc, f_abs_soc

def process_output_file(output_file):
    """Process a single ORCA output file and extract all data."""
    try:
        with open(output_file, 'r') as f:
            content = f.read()
        
        # Get molecule name from filename
        name = os.path.basename(os.path.dirname(output_file))
        
        # Look for corresponding .xyz file in same directory with folder name
        output_dir = os.path.dirname(output_file)
        folder_name = os.path.basename(output_dir)
        xyz_file = os.path.join(output_dir, f"{folder_name}.xyz")
        smiles = extract_smiles_from_xyz(xyz_file)
        
        # Extract energies
        s1_energy, t1_energy = extract_excited_states(content)
        delta_s1t1 = None
        if s1_energy is not None and t1_energy is not None:
            delta_s1t1 = s1_energy - t1_energy
        
        # Extract SOC matrix elements
        soc_elements = extract_soc_matrix_elements(content)
        soc_s1t1 = soc_elements.get('S1-T1', None) if soc_elements else None
        
        # Extract absorption spectra
        e_abs, f_abs, e_abs_soc, f_abs_soc = extract_absorption_spectrum(content)
        
        return {
            'name': name,
            'SMILES': smiles,
            'E_S1': s1_energy,
            'E_T1': t1_energy,
            'E_Delta_S1T1': delta_s1t1,
            'SOC_S1T1': soc_s1t1,
            'E_abs': e_abs,
            'F_abs': f_abs,
            'E_abs_soc': e_abs_soc,
            'F_abs_soc': f_abs_soc
        }
        
    except Exception as e:
        print(f"Error processing {output_file}: {e}")
        return None

def main():
    """Main function to process all ORCA output files and generate CSV."""
    parser = argparse.ArgumentParser(description='Extract quantum chemistry results from ORCA output files')
    parser.add_argument('-d', '--directory', required=True, 
                       help='Base directory containing ORCA output files')
    parser.add_argument('-o', '--output', default='orca_results.csv',
                       help='Output CSV file name (default: orca_results.csv)')
    parser.add_argument('-v', '--verbose', action='store_true',
                       help='Enable verbose output')
    parser.add_argument('--output_name', 
                       help='Specific output file name to search for (without .output extension)')
    
    args = parser.parse_args()
    
    # Find .output files in specified directory
    if args.output_name:
        pattern = os.path.join(args.directory, "**", f"{args.output_name}.output")
    else:
        pattern = os.path.join(args.directory, "**", "*.output")
    
    output_files = glob.glob(pattern, recursive=True)
    
    if args.verbose:
        print(f"Found {len(output_files)} ORCA output files in {args.directory}")
    
    results = []
    for output_file in output_files:
        if args.verbose:
            print(f"Processing {output_file}")
        result = process_output_file(output_file)
        if result:
            results.append(result)
    
    # Write results to CSV
    if results:
        with open(args.output, 'w', newline='') as f:
            fieldnames = ['name', 'SMILES', 'E_S1', 'E_T1', 'E_Delta_S1T1', 'SOC_S1T1', 
                         'E_abs', 'F_abs', 'E_abs_soc', 'F_abs_soc']
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            
            for result in results:
                # Convert lists to strings for CSV
                result['E_abs'] = str(result['E_abs'])
                result['F_abs'] = str(result['F_abs'])
                result['E_abs_soc'] = str(result['E_abs_soc'])
                result['F_abs_soc'] = str(result['F_abs_soc'])
                writer.writerow(result)
        
        print(f"Results written to {args.output}")
        print(f"Processed {len(results)} files successfully")
    else:
        print("No results extracted")

if __name__ == "__main__":
    main()