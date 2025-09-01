#!/usr/bin/env python3
"""
Extract quantum chemistry calculation results from ORCA output files.
Extracts SMILES (mandatory), S1/T1 energies, SOC matrix elements, and absorption spectra based on user-specified parameters.
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

def extract_soc_matrix_elements(output_content, soc_list=None):
    """Extract SOC matrix elements for specified T-S couplings.
    
    Args:
        output_content: ORCA output file content
        soc_list: List of SOC couplings to extract (e.g., ['S1T1', 'S0T1'])
                 If None, extracts all available couplings
    """
    soc_pattern = r'CALCULATED SOCME BETWEEN TRIPLETS AND SINGLETS(.*?)SOC stabilization'
    soc_match = re.search(soc_pattern, output_content, re.DOTALL)
    
    soc_elements = {}
    if soc_match:
        lines = soc_match.group(1).split('\n')
        
        for line in lines:
            pattern = r'^\s*(\d+)\s+(\d+)\s+\(\s*([-\d\.]+)\s*,\s*([-\d\.]+)\s*\)\s+\(\s*([-\d\.]+)\s*,\s*([-\d\.]+)\s*\)\s+\(\s*([-\d\.]+)\s*,\s*([-\d\.]+)\s*\)'
            match = re.match(pattern, line.strip())
            
            if match:
                t_state = int(match.group(1))
                s_state = int(match.group(2))
                
                z_re, z_im = float(match.group(3)), float(match.group(4))
                x_re, x_im = float(match.group(5)), float(match.group(6))
                y_re, y_im = float(match.group(7)), float(match.group(8))
                
                z_mag = np.sqrt(z_re**2 + z_im**2)
                x_mag = np.sqrt(x_re**2 + x_im**2)
                y_mag = np.sqrt(y_re**2 + y_im**2)
                total_mag = np.sqrt(z_mag**2 + x_mag**2 + y_mag**2)
                
                key = f'S{s_state}T{t_state}'
                soc_elements[key] = total_mag
    
    if soc_list:
        return {k: soc_elements.get(k) for k in soc_list}
    return soc_elements

def extract_regular_absorption_spectrum(output_content):
    """Extract regular absorption spectrum data."""
    abs_pattern = r'ABSORPTION SPECTRUM VIA TRANSITION ELECTRIC DIPOLE MOMENTS\s+(.*?)(?=\n\s*\n|\nSOC|$)'
    abs_match = re.search(abs_pattern, output_content, re.DOTALL)
    
    e_abs, f_abs = [], []
    if abs_match:
        lines = abs_match.group(1).split('\n')
        for line in lines:
            pattern = r'^\s*\d+-\d+[A-Z]\s+->\s+\d+-\d+[A-Z]\s+([\d\.]+)\s+[\d\.]+\s+[\d\.]+\s+([\d\.]+)'
            match = re.match(pattern, line.strip())
            if match:
                energy_ev = float(match.group(1))
                osc_strength = float(match.group(2))
                e_abs.append(energy_ev)
                f_abs.append(osc_strength)
    
    return e_abs, f_abs

def extract_soc_corrected_absorption_spectrum(output_content):
    """Extract SOC-corrected absorption spectrum data."""
    soc_abs_pattern = r'SOC CORRECTED ABSORPTION SPECTRUM VIA TRANSITION ELECTRIC DIPOLE MOMENTS\s+(.*?)(?=\n\s*\n|SOC CORRECTED ABSORPTION SPECTRUM VIA TRANSITION VELOCITY|$)'
    soc_abs_match = re.search(soc_abs_pattern, output_content, re.DOTALL)
    
    e_abs_soc, f_abs_soc = [], []
    if soc_abs_match:
        lines = soc_abs_match.group(1).split('\n')
        for line in lines:
            pattern = r'^\s*\d+-[\d\.]+[A-Z]\s+->\s+\d+-[\d\.]+[A-Z]\s+([\d\.]+)\s+[\d\.]+\s+[\d\.]+\s+([\d\.]+)'
            match = re.match(pattern, line.strip())
            if match:
                energy_ev = float(match.group(1))
                osc_strength = float(match.group(2))
                e_abs_soc.append(energy_ev)
                f_abs_soc.append(osc_strength)
    
    return e_abs_soc, f_abs_soc

def process_output_file(output_file, extract_options):
    """Process a single ORCA output file and extract specified data.
    
    Args:
        output_file: Path to ORCA output file
        extract_options: Dict with extraction flags and parameters
    """
    try:
        with open(output_file, 'r') as f:
            content = f.read()
        
        name = os.path.basename(os.path.dirname(output_file))
        
        output_dir = os.path.dirname(output_file)
        folder_name = os.path.basename(output_dir)
        xyz_file = os.path.join(output_dir, f"{folder_name}.xyz")
        smiles = extract_smiles_from_xyz(xyz_file)
        
        result = {'name': name, 'SMILES': smiles}
        
        if extract_options['excited_states']:
            s1_energy, t1_energy = extract_excited_states(content)
            delta_s1t1 = None
            if s1_energy is not None and t1_energy is not None:
                delta_s1t1 = s1_energy - t1_energy
            result.update({
                'E_S1': s1_energy,
                'E_T1': t1_energy,
                'E_Delta_S1T1': delta_s1t1
            })
        
        if extract_options['soc']:
            soc_elements = extract_soc_matrix_elements(content, extract_options.get('soc_list'))
            if extract_options.get('soc_list'):
                for soc_key in extract_options['soc_list']:
                    result[f'SOC_{soc_key}'] = soc_elements.get(soc_key)
            else:
                soc_s1t1 = soc_elements.get('S1T1')
                result['SOC_S1T1'] = soc_s1t1
        
        if extract_options['regular_absorption']:
            e_abs, f_abs = extract_regular_absorption_spectrum(content)
            result.update({
                'E_abs': e_abs,
                'F_abs': f_abs
            })
        
        if extract_options['soc_absorption']:
            e_abs_soc, f_abs_soc = extract_soc_corrected_absorption_spectrum(content)
            result.update({
                'E_abs_soc': e_abs_soc,
                'F_abs_soc': f_abs_soc
            })
        
        return result
        
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
    
    # Extraction options
    parser.add_argument('--excited-states', action='store_true', default=False,
                       help='Extract S1, T1 excited state energies')
    parser.add_argument('--soc-list', type=str, nargs='*',
                       help='Specific SOC couplings to extract (e.g., S1T1 S0T1)')
    parser.add_argument('--regular-absorption', action='store_true', default=False,
                       help='Extract regular absorption spectrum')
    parser.add_argument('--soc-absorption', action='store_true', default=False,
                       help='Extract SOC-corrected absorption spectrum')
    parser.add_argument('--all', action='store_true', default=False,
                       help='Extract all available data')
    
    args = parser.parse_args()
    
    # Set extraction options
    extract_options = {
        'excited_states': args.excited_states or args.all,
        'soc': args.soc_list or args.all,
        'soc_list': args.soc_list,
        'regular_absorption': args.regular_absorption or args.all,
        'soc_absorption': args.soc_absorption or args.all
    }
    
    # Find .output files
    if args.output_name:
        pattern = os.path.join(args.directory, "**", f"{args.output_name}.output")
    else:
        pattern = os.path.join(args.directory, "**", "*.output")
    
    output_files = glob.glob(pattern, recursive=True)
    
    if args.verbose:
        print(f"Found {len(output_files)} ORCA output files in {args.directory}")
        print(f"Extraction options: {extract_options}")
    
    results = []
    for output_file in output_files:
        if args.verbose:
            print(f"Processing {output_file}")
        result = process_output_file(output_file, extract_options)
        if result:
            results.append(result)
    
    # Write results to CSV
    if results:
        # Determine fieldnames based on first result
        fieldnames = list(results[0].keys())
        
        with open(args.output, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            
            for result in results:
                # Convert lists to strings for CSV
                for key, value in result.items():
                    if isinstance(value, list):
                        result[key] = str(value)
                writer.writerow(result)
        
        print(f"Results written to {args.output}")
        print(f"Processed {len(results)} files successfully")
    else:
        print("No results extracted")

if __name__ == "__main__":
    main()