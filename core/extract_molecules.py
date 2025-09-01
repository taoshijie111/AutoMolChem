#!/usr/bin/env python3

import argparse
import pandas as pd
import os
import shutil
from pathlib import Path
import glob
from collections import defaultdict

def parse_arguments():
    parser = argparse.ArgumentParser(description='Extract molecules with energy difference < 0.2 eV')
    parser.add_argument('-i','--s1t1_results', required=True, help='Path to CSV file containing results')
    parser.add_argument('-d','--omol_path', required=True, help='Path to directory containing batch folders')
    parser.add_argument('-o', '--output_dir', required=True, help='Output directory for extracted molecules')
    return parser.parse_args()

def read_and_filter_molecules(csv_file):
    df = pd.read_csv(csv_file)
    filtered_molecules = df[df['Energy_Difference_eV'] < 0.2]['Molecule'].tolist()
    return filtered_molecules

def find_molecule_folders(omol_path, target_molecules):
    molecule_paths = []
    batch_dirs = glob.glob(os.path.join(omol_path, 'batch_*'))
    
    for batch_dir in batch_dirs:
        batch_name = os.path.basename(batch_dir)
        for molecule in target_molecules:
            molecule_path = os.path.join(batch_dir, molecule)
            omol_opt_path = os.path.join(molecule_path, 'omol_opt')
            
            if os.path.exists(omol_opt_path):
                molecule_paths.append({
                    'batch': batch_name,
                    'molecule': molecule,
                    'source_path': omol_opt_path,
                    'molecule_dir': molecule_path
                })
    
    return molecule_paths

def organize_into_batches(molecule_paths, max_per_batch=1000):
    batches = defaultdict(list)
    current_batch = 0
    current_count = 0
    
    for mol_info in molecule_paths:
        if current_count >= max_per_batch:
            current_batch += 1
            current_count = 0
        
        batches[f'batch_{current_batch:03d}'].append(mol_info)
        current_count += 1
    
    return batches

def copy_molecules(batches, output_dir):
    os.makedirs(output_dir, exist_ok=True)
    
    for batch_name, molecules in batches.items():
        batch_output_dir = os.path.join(output_dir, batch_name)
        os.makedirs(batch_output_dir, exist_ok=True)
        
        for mol_info in molecules:
            molecule_output_dir = os.path.join(batch_output_dir, mol_info['molecule'])
            omol_opt_output = os.path.join(molecule_output_dir, 'omol_opt')
            
            os.makedirs(molecule_output_dir, exist_ok=True)
            
            if os.path.exists(omol_opt_output):
                shutil.rmtree(omol_opt_output)
            
            shutil.copytree(mol_info['source_path'], omol_opt_output)
            print(f"Copied {mol_info['molecule']} to {batch_name}")

def main():
    args = parse_arguments()
    
    print(f"Reading molecules from {args.s1t1_results}")
    target_molecules = read_and_filter_molecules(args.s1t1_results)
    print(f"Found {len(target_molecules)} molecules with energy difference < 0.2 eV")
    
    print(f"Searching for molecules in {args.omol_path}")
    molecule_paths = find_molecule_folders(args.omol_path, target_molecules)
    print(f"Found {len(molecule_paths)} molecule folders with omol_opt directories")
    
    print("Organizing molecules into batches")
    batches = organize_into_batches(molecule_paths)
    print(f"Organized into {len(batches)} batches")
    
    print(f"Copying molecules to {args.output_dir}")
    copy_molecules(batches, args.output_dir)
    
    print("Extraction complete!")
    
    for batch_name, molecules in batches.items():
        print(f"{batch_name}: {len(molecules)} molecules")

if __name__ == "__main__":
    main()