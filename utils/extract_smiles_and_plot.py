#!/usr/bin/env python3
"""
Extract SMILES strings from conformer info.txt files and generate Nature-standard plots
for heavy atom distribution and molecular atom count distribution.
"""

import os
import re
import argparse
from pathlib import Path
from collections import defaultdict, Counter
import matplotlib.pyplot as plt
import matplotlib as mpl
from rdkit import Chem
from rdkit.Chem import Descriptors
import numpy as np
import pandas as pd

# Set matplotlib parameters for Nature journal standards
mpl.rcParams.update({
    'font.size': 8,
    'font.family': 'sans-serif',
    'font.sans-serif': ['Arial', 'DejaVu Sans', 'Liberation Sans'],
    'axes.linewidth': 0.5,
    'axes.labelsize': 8,
    'axes.titlesize': 9,
    'xtick.labelsize': 7,
    'ytick.labelsize': 7,
    'legend.fontsize': 7,
    'figure.titlesize': 9,
    'lines.linewidth': 1.0,
    'patch.linewidth': 0.5,
    'xtick.major.width': 0.5,
    'ytick.major.width': 0.5,
    'xtick.minor.width': 0.3,
    'ytick.minor.width': 0.3,
})

def extract_smiles_from_info(info_file_path):
    """Extract SMILES string from info.txt file."""
    try:
        with open(info_file_path, 'r') as f:
            content = f.read()
        
        # Look for SMILES pattern
        match = re.search(r'SMILES:\s*(.+)', content)
        if match:
            return match.group(1).strip()
        return None
    except Exception as e:
        print(f"Error reading {info_file_path}: {e}")
        return None

def find_all_smiles(base_dir, conformer_type='conformer'):
    """Find all SMILES strings from info.txt files in the specified conformer type."""
    smiles_list = []
    base_path = Path(base_dir)
    
    # Find all info.txt files in conformer directories
    pattern = f"**/molecule_*/{conformer_type}/info.txt"
    info_files = list(base_path.glob(pattern))
    
    print(f"Found {len(info_files)} info.txt files in {conformer_type} directories")
    
    for info_file in info_files:
        smiles = extract_smiles_from_info(info_file)
        if smiles:
            smiles_list.append(smiles)
        else:
            print(f"Could not extract SMILES from {info_file}")
    
    return smiles_list

def calculate_molecular_properties(smiles_list):
    """Calculate molecular properties for each SMILES."""
    properties = []
    
    for smiles in smiles_list:
        try:
            mol = Chem.MolFromSmiles(smiles)
            if mol is not None:
                # Total atom count
                num_atoms = mol.GetNumAtoms()
                
                # Heavy atom count (non-hydrogen atoms)
                num_heavy_atoms = mol.GetNumHeavyAtoms()
                
                # Heavy atom types (count of each element)
                heavy_atom_types = Counter()
                for atom in mol.GetAtoms():
                    if atom.GetAtomicNum() != 1:  # Skip hydrogen
                        heavy_atom_types[atom.GetSymbol()] += 1
                
                # Number of different heavy atom types
                num_heavy_atom_types = len(heavy_atom_types)
                
                properties.append({
                    'smiles': smiles,
                    'num_atoms': num_atoms,
                    'num_heavy_atoms': num_heavy_atoms,
                    'num_heavy_atom_types': num_heavy_atom_types,
                    'heavy_atom_types': dict(heavy_atom_types)
                })
            else:
                print(f"Could not parse SMILES: {smiles}")
        except Exception as e:
            print(f"Error processing SMILES {smiles}: {e}")
    
    return properties

def create_nature_plot(data, column, xlabel, output_file, bins=30):
    """Create a Nature journal standard histogram plot."""
    # Create figure with Nature journal standard size (single column: 89mm, double: 183mm)
    fig_width = 89/25.4  # Convert mm to inches (single column)
    fig_height = fig_width * 0.75  # Maintain good aspect ratio
    
    fig, ax = plt.subplots(1, 1, figsize=(fig_width, fig_height))
    
    # Create histogram
    values = [item[column] for item in data]
    n, bins, patches = ax.hist(values, bins=bins, color='#2E86AB', alpha=0.8, 
                              edgecolor='black', linewidth=0.3)
    
    # Customize axes
    ax.set_xlabel(xlabel, fontweight='bold', labelpad=1)
    ax.set_ylabel('Frequency', fontweight='bold', labelpad=1)
    
    # Add statistics text box
    mean_val = np.mean(values)
    std_val = np.std(values)
    median_val = np.median(values)
    
    stats_text = f'n = {len(values)}\nMean = {mean_val:.1f}\nStd = {std_val:.1f}\nMedian = {median_val:.1f}'
    
    # Position text box in upper right
    ax.text(0.95, 0.95, stats_text, transform=ax.transAxes,
            verticalalignment='top', horizontalalignment='right',
            bbox=dict(boxstyle='round', facecolor='white', alpha=0.8, pad=0.3),
            fontsize=6)
    
    # Customize grid
    ax.grid(True, alpha=0.3, linewidth=0.3)
    ax.set_axisbelow(True)
    
    # Tight layout
    plt.tight_layout()
    
    # Save with high DPI for publication
    plt.savefig(output_file, dpi=300, bbox_inches='tight', 
                facecolor='white', edgecolor='none')
    plt.close()
    
    print(f"Plot saved as {output_file}")
    return values

def create_atom_type_bar_plot(properties, output_file):
    """Create a Nature journal standard bar plot for heavy atom type distribution."""
    # Collect all heavy atom types
    all_atom_types = Counter()
    for prop in properties:
        for atom_type, count in prop['heavy_atom_types'].items():
            all_atom_types[atom_type] += count
    
    # Sort by frequency (descending)
    sorted_atoms = sorted(all_atom_types.items(), key=lambda x: x[1], reverse=True)
    atom_types, counts = zip(*sorted_atoms)
    
    # Create figure with Nature journal standard size
    fig_width = 89/25.4  # Convert mm to inches (single column)
    fig_height = fig_width * 0.8  # Slightly taller for bar plot
    
    fig, ax = plt.subplots(1, 1, figsize=(fig_width, fig_height))
    
    # Create bar plot with Nature-appropriate colors
    colors = plt.cm.Set3(np.linspace(0, 1, len(atom_types)))
    bars = ax.bar(atom_types, counts, color=colors, alpha=0.8, 
                  edgecolor='black', linewidth=0.3)
    
    # Customize axes
    ax.set_xlabel('Heavy Atom Type', fontweight='bold', labelpad=1)
    ax.set_ylabel('Total Count', fontweight='bold', labelpad=1)
    
    # Rotate x-axis labels if needed
    if len(atom_types) > 10:
        ax.tick_params(axis='x', rotation=45)
    
    # Add value labels on bars
    for bar, count in zip(bars, counts):
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height + max(counts)*0.01,
                f'{count}', ha='center', va='bottom', fontsize=6)
    
    # Add statistics text box
    total_atoms = sum(counts)
    num_types = len(atom_types)
    most_common = atom_types[0] if atom_types else 'N/A'
    
    stats_text = f'Total atoms: {total_atoms}\nUnique types: {num_types}\nMost common: {most_common}'
    
    # Position text box in upper right
    ax.text(0.95, 0.95, stats_text, transform=ax.transAxes,
            verticalalignment='top', horizontalalignment='right',
            bbox=dict(boxstyle='round', facecolor='white', alpha=0.8, pad=0.3),
            fontsize=6)
    
    # Customize grid
    ax.grid(True, alpha=0.3, linewidth=0.3, axis='y')
    ax.set_axisbelow(True)
    
    # Tight layout
    plt.tight_layout()
    
    # Save with high DPI for publication
    plt.savefig(output_file, dpi=300, bbox_inches='tight', 
                facecolor='white', edgecolor='none')
    plt.close()
    
    print(f"Atom type distribution plot saved as {output_file}")
    return sorted_atoms

def main():
    parser = argparse.ArgumentParser(description='Extract SMILES and create molecular distribution plots')
    parser.add_argument('--input_dir', default='uspto',
                       help='Input directory containing molecular data')
    parser.add_argument('--conformer_type', choices=['conformer', 'omol_opt', 'xtb_opt'], 
                       default='conformer', help='Type of conformer to analyze')
    parser.add_argument('--output_prefix', default='molecular_analysis',
                       help='Prefix for output files')
    
    args = parser.parse_args()
    args.output_prefix = args.input_dir +  '/' + args.output_prefix
    print(f"Extracting SMILES from {args.input_dir} using {args.conformer_type} conformers...")
    
    # Extract SMILES strings
    smiles_list = find_all_smiles(args.input_dir, args.conformer_type)
    print(f"Extracted {len(smiles_list)} SMILES strings")
    
    if not smiles_list:
        print("No SMILES strings found!")
        return
    
    # Calculate molecular properties
    print("Calculating molecular properties...")
    properties = calculate_molecular_properties(smiles_list)
    print(f"Successfully processed {len(properties)} molecules")
    
    # Save SMILES to file
    smiles_file = f"{args.output_prefix}_{args.conformer_type}_smiles.txt"
    with open(smiles_file, 'w') as f:
        for prop in properties:
            f.write(f"{prop['smiles']}\n")
    print(f"SMILES saved to {smiles_file}")
    
    # Save detailed data to CSV
    df = pd.DataFrame(properties)
    csv_file = f"{args.output_prefix}_{args.conformer_type}_data.csv"
    df.to_csv(csv_file, index=False)
    print(f"Data saved to {csv_file}")
    
    # Create plots
    heavy_atom_plot = f"{args.output_prefix}_{args.conformer_type}_heavy_atoms.png"
    total_atom_plot = f"{args.output_prefix}_{args.conformer_type}_total_atoms.png"
    atom_type_dist_plot = f"{args.output_prefix}_{args.conformer_type}_atom_type_distribution.png"
    
    print("Creating heavy atom distribution plot...")
    heavy_values = create_nature_plot(
        properties, 'num_heavy_atoms', 
        'Number of Heavy Atoms',
        heavy_atom_plot
    )
    
    print("Creating total atom distribution plot...")
    total_values = create_nature_plot(
        properties, 'num_atoms',
        'Number of Atoms',
        total_atom_plot
    )
    
    print("Creating atom type distribution bar plot...")
    atom_type_dist = create_atom_type_bar_plot(properties, atom_type_dist_plot)
    
    # Print summary statistics
    print("\n=== Summary Statistics ===")
    print(f"Total molecules analyzed: {len(properties)}")
    print(f"Heavy atoms - Mean: {np.mean(heavy_values):.1f}, Std: {np.std(heavy_values):.1f}, Range: {min(heavy_values)}-{max(heavy_values)}")
    print(f"Total atoms - Mean: {np.mean(total_values):.1f}, Std: {np.std(total_values):.1f}, Range: {min(total_values)}-{max(total_values)}")
        
    print("\n=== Most Common Heavy Atom Types ===")
    for atom_type, count in atom_type_dist[:10]:  # Show top 10
        print(f"{atom_type}: {count} atoms")

if __name__ == "__main__":
    main()