#!/usr/bin/env python3

import pandas as pd
import os
import argparse
from pathlib import Path

def extract_smiles_from_info(info_file_path):
    """Extract SMILES string from info.txt file."""
    try:
        with open(info_file_path, 'r') as f:
            for line in f:
                if line.startswith('SMILES:'):
                    return line.replace('SMILES:', '').strip()
    except FileNotFoundError:
        return None
    return None

def find_molecule_info_path(root_dir, molecule_name):
    """
    Find the info.txt file for a molecule by searching across all batch directories.
    
    Args:
        root_dir (str): Root directory containing batch_* subdirectories
        molecule_name (str): Name of the molecule (e.g., "molecule_12")
    
    Returns:
        str: Path to info.txt file if found, None otherwise
    """
    # Look for batch_* directories
    for batch_dir in Path(root_dir).glob("batch_*"):
        info_path = batch_dir / molecule_name / "omol_opt" / "info.txt"
        if info_path.exists():
            return str(info_path)
    
    return None

def add_smiles_to_csv(csv_path, root_dir):
    """
    Read CSV file and add SMILES column by extracting SMILES from molecule directories.
    
    Args:
        csv_path (str): Path to the CSV file containing 'Molecule' column
        root_dir (str): Root directory containing batch_*/molecule_{idx}/omol_opt subdirectories
    """
    # Read the CSV file
    df = pd.read_csv(csv_path)
    
    if 'Molecule' not in df.columns:
        raise ValueError("CSV file must contain a 'Molecule' column")
    
    # Initialize SMILES column if it doesn't exist
    if 'SMILES' not in df.columns:
        df['SMILES'] = None
    
    # Extract SMILES for each molecule
    for idx, row in df.iterrows():
        molecule_name = row['Molecule']
        
        # Find the info.txt file across all batch directories
        info_path = find_molecule_info_path(root_dir, molecule_name)
        
        if info_path:
            smiles = extract_smiles_from_info(info_path)
            if smiles:
                df.at[idx, 'SMILES'] = smiles
                print(f"Found SMILES for {molecule_name}: {smiles[:50]}...")
            else:
                print(f"No SMILES found in info.txt for {molecule_name}")
        else:
            print(f"No info.txt found for {molecule_name}")
    
    # Save the updated CSV
    df.to_csv(csv_path, index=False)
    print(f"\nUpdated CSV saved to: {csv_path}")
    
    # Print summary
    smiles_count = df['SMILES'].notna().sum()
    total_count = len(df)
    print(f"SMILES found for {smiles_count}/{total_count} molecules")

def main():
    parser = argparse.ArgumentParser(description='Extract SMILES from molecule directories and add to CSV')
    parser.add_argument('csv_path', help='Path to CSV file containing Molecule column')
    parser.add_argument('root_dir', help='Root directory containing batch_*/molecule_X/omol_opt subdirectories')
    
    args = parser.parse_args()
    
    # Validate inputs
    if not os.path.exists(args.csv_path):
        raise FileNotFoundError(f"CSV file not found: {args.csv_path}")
    
    if not os.path.exists(args.root_dir):
        raise FileNotFoundError(f"Root directory not found: {args.root_dir}")
    
    add_smiles_to_csv(args.csv_path, args.root_dir)

if __name__ == "__main__":
    main()