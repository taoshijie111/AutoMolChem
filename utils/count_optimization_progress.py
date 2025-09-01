#!/usr/bin/env python3
"""
Script to count completed optimization calculations and show progress.
Supports both omol_opt and xtb_opt optimization methods.
"""

import argparse
from pathlib import Path


def count_molecules_and_progress(base_dir, opt_type='omol_opt'):
    """
    Count total molecules and completed optimization calculations.
    
    Args:
        base_dir (str): Base directory containing batch folders with molecules
        opt_type (str): Type of optimization to check ('omol_opt' or 'xtb_opt')
        
    Returns:
        tuple: (total_molecules, completed_calculations, failed_calculations, progress_percentage)
    """
    base_path = Path(base_dir)
    
    if not base_path.exists():
        print(f"Error: Directory {base_dir} does not exist")
        return 0, 0, 0, 0.0
    
    # Count total molecule directories
    total_molecules = 0
    completed_calculations = 0
    failed_calculations = 0
    
    # Find all molecule directories
    for batch_dir in base_path.glob("batch_*"):
        if batch_dir.is_dir():
            molecule_dirs = list(batch_dir.glob("*"))
            total_molecules += len(molecule_dirs)
            
            # Count completed optimization calculations in this batch
            for mol_dir in molecule_dirs:
                opt_dir = mol_dir / opt_type
                if opt_dir.exists() and opt_dir.is_dir():
                    # Check if optimization completed successfully
                    optimized_file = opt_dir / "optimized.xyz"
                    if optimized_file.exists():
                        completed_calculations += 1
                    else:
                        # Check if optimization was attempted but failed
                        # Look for log files or other indicators of failed optimization
                        log_files = list(opt_dir.glob("*.log")) + list(opt_dir.glob("*.out"))
                        if log_files:
                            failed_calculations += 1
    
    # Calculate progress percentage
    progress_percentage = (completed_calculations / total_molecules * 100) if total_molecules > 0 else 0.0
    
    return total_molecules, completed_calculations, failed_calculations, progress_percentage


def get_detailed_statistics(base_dir, opt_type='omol_opt'):
    """
    Get detailed statistics about optimization status.
    
    Args:
        base_dir (str): Base directory containing batch folders with molecules
        opt_type (str): Type of optimization to check ('omol_opt' or 'xtb_opt')
        
    Returns:
        dict: Detailed statistics
    """
    base_path = Path(base_dir)
    
    stats = {
        'total_molecules': 0,
        'completed': 0,
        'failed': 0,
        'not_started': 0,
        'in_progress': 0,
        'batches': {}
    }
    
    # Find all molecule directories organized by batch
    for batch_dir in base_path.glob("batch_*"):
        if batch_dir.is_dir():
            batch_name = batch_dir.name
            molecule_dirs = list(batch_dir.glob("*"))
            stats['total_molecules'] += len(molecule_dirs)
            
            batch_stats = {
                'total': len(molecule_dirs),
                'completed': 0,
                'failed': 0,
                'not_started': 0,
                'in_progress': 0
            }
            
            for mol_dir in molecule_dirs:
                opt_dir = mol_dir / opt_type
                
                if not opt_dir.exists():
                    batch_stats['not_started'] += 1
                    stats['not_started'] += 1
                elif opt_dir.is_dir():
                    optimized_file = opt_dir / "optimized.xyz"
                    if optimized_file.exists():
                        batch_stats['completed'] += 1
                        stats['completed'] += 1
                    else:
                        # Check for log files indicating attempted optimization
                        log_files = list(opt_dir.glob("*.log")) + list(opt_dir.glob("*.out"))
                        if log_files:
                            batch_stats['failed'] += 1
                            stats['failed'] += 1
                        else:
                            batch_stats['in_progress'] += 1
                            stats['in_progress'] += 1
            
            stats['batches'][batch_name] = batch_stats
    
    return stats


def print_summary_report(base_dir, opt_type='omol_opt'):
    """Print a summary report of optimization progress."""
    total, completed, failed, percentage = count_molecules_and_progress(base_dir, opt_type)
    
    print(f"OMol25 {opt_type.upper()} Optimization Progress Report")
    print("=" * 60)
    print(f"Scanning directory: {base_dir}")
    print(f"Optimization type: {opt_type}")
    print()
    
    print(f"Total molecules: {total:,}")
    print(f"Completed optimizations: {completed:,}")
    print(f"Failed optimizations: {failed:,}")
    print(f"Remaining calculations: {(total - completed - failed):,}")
    print(f"Success rate: {percentage:.1f}%")
    print()
    
    # Progress bar
    bar_length = 50
    filled_length = int(bar_length * percentage / 100)
    bar = "█" * filled_length + "░" * (bar_length - filled_length)
    print(f"[{bar}] {percentage:.1f}%")
    
    if completed > 0 or failed > 0:
        print(f"\nCalculation Status:")
        print(f"✓ {completed:,} molecules optimized successfully")
        if failed > 0:
            print(f"✗ {failed:,} molecules failed optimization")
        print(f"⏳ {(total - completed - failed):,} molecules pending")


def print_detailed_report(base_dir, opt_type='omol_opt'):
    """Print a detailed report with per-batch statistics."""
    stats = get_detailed_statistics(base_dir, opt_type)
    
    print(f"OMol25 {opt_type.upper()} Detailed Progress Report")
    print("=" * 60)
    print(f"Scanning directory: {base_dir}")
    print(f"Optimization type: {opt_type}")
    print()
    
    # Overall statistics
    print("Overall Statistics:")
    print(f"  Total molecules: {stats['total_molecules']:,}")
    print(f"  Completed: {stats['completed']:,} ({stats['completed']/stats['total_molecules']*100:.1f}%)")
    print(f"  Failed: {stats['failed']:,} ({stats['failed']/stats['total_molecules']*100:.1f}%)")
    print(f"  In progress: {stats['in_progress']:,} ({stats['in_progress']/stats['total_molecules']*100:.1f}%)")
    print(f"  Not started: {stats['not_started']:,} ({stats['not_started']/stats['total_molecules']*100:.1f}%)")
    print()
    
    # Per-batch statistics
    print("Per-Batch Statistics:")
    print(f"{'Batch':<15} {'Total':<8} {'Done':<8} {'Failed':<8} {'Progress':<8} {'Success %':<10}")
    print("-" * 70)
    
    for batch_name in sorted(stats['batches'].keys()):
        batch = stats['batches'][batch_name]
        progress = f"{batch['completed']}/{batch['total']}"
        success_rate = (batch['completed'] / batch['total'] * 100) if batch['total'] > 0 else 0
        
        print(f"{batch_name:<15} {batch['total']:<8} {batch['completed']:<8} {batch['failed']:<8} "
              f"{progress:<8} {success_rate:<10.1f}")


def main():
    parser = argparse.ArgumentParser(description='Count optimization progress for molecular calculations')
    parser.add_argument('directory', nargs='?', 
                       default='/home/user/data/OMol25/AutoOpt/INVEST',
                       help='Directory containing batch folders (default: oclot-plus_s1t1_smaller-than-0)')
    parser.add_argument('--opt-type', choices=['omol_opt', 'xtb_opt'], default='omol_opt',
                       help='Optimization type to check (default: omol_opt)')
    parser.add_argument('--detailed', action='store_true',
                       help='Show detailed per-batch statistics')
    
    args = parser.parse_args()
    
    if args.detailed:
        print_detailed_report(args.directory, args.opt_type)
    else:
        print_summary_report(args.directory, args.opt_type)


if __name__ == "__main__":
    main()
