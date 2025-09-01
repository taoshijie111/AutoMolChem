#!/usr/bin/env python3
"""
Extract optimization results from omol_opt or xtb_opt directories and compress into tar.gz
Usage: python extract_optimization_results.py <input_directory> [output_archive_name]
"""

import os
import sys
import tarfile
import argparse
from pathlib import Path


def find_optimization_directories(root_dir, opt_types=['omol_opt', 'xtb_opt']):
    """Find all optimization result directories recursively."""
    opt_dirs = []
    
    for root, dirs, files in os.walk(root_dir):
        for opt_type in opt_types:
            if opt_type in dirs:
                opt_path = os.path.join(root, opt_type)
                # Check if directory contains optimization results
                if os.listdir(opt_path):  # Not empty
                    opt_dirs.append(opt_path)
    
    return opt_dirs


def create_tar_archive(opt_dirs, output_path, compression='gz'):
    """Create a compressed tar archive from specific files in optimization directories."""
    
    # Files to extract from each optimization directory
    target_files = ['optimized.xyz', 'info.txt', 'xtbopt.xyz']  # xtbopt.xyz for xTB results
    
    total_files = 0
    with tarfile.open(output_path, f'w:{compression}') as tar:
        for opt_dir in opt_dirs:
            # Get relative path from base directory for archive structure
            # Convert absolute path to relative path starting from the molecule directory
            path_parts = Path(opt_dir).parts
            
            # Find the molecule directory index
            mol_idx = None
            for i, part in enumerate(path_parts):
                if part.startswith('molecule_'):
                    mol_idx = i
                    break
            
            if mol_idx is not None:
                # Create archive path: batch_xxxx/molecule_xxxx/opt_type/
                batch_part = path_parts[mol_idx - 1] if mol_idx > 0 else 'unknown_batch'
                molecule_part = path_parts[mol_idx]
                opt_type = path_parts[-1]
                
                base_arcname = os.path.join(batch_part, molecule_part, opt_type)
            else:
                # Fallback: use the last 3 parts of the path
                base_arcname = os.path.join(*path_parts[-3:])
            
            # Add only specific files from the optimization directory
            files_added = 0
            for target_file in target_files:
                file_path = os.path.join(opt_dir, target_file)
                if os.path.exists(file_path):
                    arcname = os.path.join(base_arcname, target_file)
                    tar.add(file_path, arcname=arcname)
                    files_added += 1
            
            total_files += files_added
            if files_added > 0:
                print(f"Added {files_added} files from {opt_dir}")
            else:
                print(f"Warning: No target files found in {opt_dir}")
    
    return total_files


def main():
    parser = argparse.ArgumentParser(description='Extract optimization results and compress to tar.gz')
    parser.add_argument('input_dir', help='Input directory containing optimization results')
    parser.add_argument('output_archive', nargs='?', default='optimization_results.tar.gz',
                       help='Output archive name (default: optimization_results.tar.gz)')
    parser.add_argument('--opt-types', nargs='+', default=['omol_opt', 'xtb_opt'],
                       help='Optimization directory types to extract (default: omol_opt xtb_opt)')
    parser.add_argument('--compression', choices=['gz', 'bz2', 'xz'], default='gz',
                       help='Compression type (default: gz)')
    
    args = parser.parse_args()
    
    # Validate input directory
    if not os.path.isdir(args.input_dir):
        print(f"Error: Input directory '{args.input_dir}' does not exist.")
        sys.exit(1)
    
    print(f"Searching for optimization directories in: {args.input_dir}")
    print(f"Looking for directory types: {args.opt_types}")
    
    # Find optimization directories
    opt_dirs = find_optimization_directories(args.input_dir, args.opt_types)
    
    if not opt_dirs:
        print("No optimization directories found.")
        sys.exit(1)
    
    print(f"Found {len(opt_dirs)} optimization directories:")
    for opt_dir in opt_dirs[:10]:  # Show first 10
        print(f"  {opt_dir}")
    if len(opt_dirs) > 10:
        print(f"  ... and {len(opt_dirs) - 10} more")
    
    # Create output archive
    output_path = args.output_archive
    if not output_path.endswith(f'.tar.{args.compression}'):
        output_path += f'.tar.{args.compression}'
    
    print(f"\nCreating archive: {output_path}")
    
    total_files = 0
    try:
        total_files = create_tar_archive(opt_dirs, output_path, args.compression)
        
        # Get archive size
        archive_size = os.path.getsize(output_path)
        size_mb = archive_size / (1024 * 1024)
        
        print(f"Archive created successfully!")
        print(f"Archive size: {size_mb:.2f} MB")
        print(f"Total files archived: {total_files}")
        print(f"Total directories processed: {len(opt_dirs)}")
        
    except Exception as e:
        print(f"Error creating archive: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()