#!/bin/bash

# Script to reorganize conformer output files with parallel processing
# Usage: ./reorganize_conformer_files.sh /path/to/conformer_output [num_processes]

if [ $# -lt 1 ] || [ $# -gt 2 ]; then
    echo "Usage: $0 <conformer_output_directory> [num_processes]"
    echo "Example: $0 /path/to/conformer_output 8"
    echo "Default num_processes: 10 (optimized for Slurm)"
    exit 1
fi

CONFORMER_OUTPUT_DIR="$1"
NUM_PROCESSES=${2:-10}

# Check if the directory exists
if [ ! -d "$CONFORMER_OUTPUT_DIR" ]; then
    echo "Error: Directory '$CONFORMER_OUTPUT_DIR' does not exist."
    exit 1
fi

echo "Reorganizing conformer files in: $CONFORMER_OUTPUT_DIR"
echo "Using $NUM_PROCESSES parallel processes"

# Create a temporary directory for progress tracking
TEMP_DIR=$(mktemp -d)
PROGRESS_FILE="$TEMP_DIR/progress.txt"
echo "0" > "$PROGRESS_FILE"

# Function to process a single batch
process_batch() {
    local batch_dir="$1"
    local progress_file="$2"
    local batch_processed=0
    
    if [ ! -d "$batch_dir" ]; then
        return
    fi
    
    batch_name=$(basename "$batch_dir")
    echo "Processing $batch_name (PID: $$)..."
    
    # Process each molecule directory within the batch
    for molecule_dir in "$batch_dir"/molecule_*/; do
        if [ ! -d "$molecule_dir" ]; then
            continue
        fi
        
        molecule_name=$(basename "$molecule_dir")
        rdkit_conformer_dir="$molecule_dir/rdkit_conformer"
        
        # Check if conformer.xyz or info.txt exist in the molecule directory
        # and haven't already been moved to rdkit_conformer subdirectory
        conformer_in_root=$([ -f "$molecule_dir/conformer.xyz" ] && echo "true" || echo "false")
        info_in_root=$([ -f "$molecule_dir/info.txt" ] && echo "true" || echo "false")
        conformer_in_subdir=$([ -f "$rdkit_conformer_dir/conformer.xyz" ] && echo "true" || echo "false")
        info_in_subdir=$([ -f "$rdkit_conformer_dir/info.txt" ] && echo "true" || echo "false")
        
        # Skip if files are already in the correct location
        if [ "$conformer_in_root" = "false" ] && [ "$info_in_root" = "false" ] && 
           [ "$conformer_in_subdir" = "true" ] && [ "$info_in_subdir" = "true" ]; then
            continue  # Already processed, skip silently
        fi
        
        # Process if there are files to move
        if [ "$conformer_in_root" = "true" ] || [ "$info_in_root" = "true" ]; then
            # Create rdkit_conformer directory if it doesn't exist
            if [ ! -d "$rdkit_conformer_dir" ]; then
                mkdir -p "$rdkit_conformer_dir"
                echo "  [$batch_name] Created: $rdkit_conformer_dir"
            fi
            
            # Move conformer.xyz if it exists in root and not already in subdirectory
            if [ "$conformer_in_root" = "true" ]; then
                mv "$molecule_dir/conformer.xyz" "$rdkit_conformer_dir/"
                echo "  [$batch_name] Moved: conformer.xyz -> $molecule_name/rdkit_conformer/"
            fi
            
            # Move info.txt if it exists in root and not already in subdirectory
            if [ "$info_in_root" = "true" ]; then
                mv "$molecule_dir/info.txt" "$rdkit_conformer_dir/"
                echo "  [$batch_name] Moved: info.txt -> $molecule_name/rdkit_conformer/"
            fi
            
            ((batch_processed++))
        else
            # Check if this molecule has any files at all (either in root or subdirectory)
            if [ "$conformer_in_subdir" = "false" ] && [ "$info_in_subdir" = "false" ]; then
                echo "  [$batch_name] Warning: No conformer.xyz or info.txt found in $molecule_name"
            fi
        fi
        
        # Update global progress counter (with file locking)
        if [ $((batch_processed % 50)) -eq 0 ] && [ $batch_processed -gt 0 ]; then
            (
                flock -x 200
                current=$(cat "$progress_file")
                echo $((current + 50)) > "$progress_file"
                echo "  Global progress: $((current + 50)) molecules processed"
            ) 200<"$progress_file"
        fi
    done
    
    # Final update for this batch
    if [ $batch_processed -gt 0 ]; then
        (
            flock -x 200
            current=$(cat "$progress_file")
            remainder=$((batch_processed % 50))
            if [ $remainder -gt 0 ]; then
                echo $((current + remainder)) > "$progress_file"
            fi
        ) 200<"$progress_file"
    fi
    
    echo "Completed $batch_name: $batch_processed molecules processed"
}

# Export the function so it can be used by parallel processes
export -f process_batch

# Get all batch directories
batch_dirs=("$CONFORMER_OUTPUT_DIR"/batch_*/)

# Check if there are any batch directories
if [ ${#batch_dirs[@]} -eq 0 ] || [ ! -d "${batch_dirs[0]}" ]; then
    echo "No batch directories found in $CONFORMER_OUTPUT_DIR"
    rm -rf "$TEMP_DIR"
    exit 1
fi

echo "Found ${#batch_dirs[@]} batch directories to process"

# Process batches in parallel using xargs
printf '%s\n' "${batch_dirs[@]}" | xargs -n 1 -P "$NUM_PROCESSES" -I {} bash -c 'process_batch "$@"' _ {} "$PROGRESS_FILE"

# Wait for all background processes to complete
wait

# Get final count
final_count=$(cat "$PROGRESS_FILE")

echo ""
echo "Reorganization complete!"
echo "Total molecules processed: $final_count"

# Cleanup
rm -rf "$TEMP_DIR"

# Verify the reorganization by checking a few directories
echo ""
echo "Verification - checking first few reorganized directories:"
find "$CONFORMER_OUTPUT_DIR" -type d -name "rdkit_conformer" | head -5 | while read dir; do
    echo "  $dir:"
    ls -la "$dir" | grep -E "\.(xyz|txt)$" | sed 's/^/    /'
done