#!/usr/bin/env python3
import os
import sys
import argparse


def delete_empty_directories(root_dir):
    """
    Iteratively delete empty directories within the specified directory.
    Returns the number of directories deleted.
    """
    deleted_count = 0
    
    while True:
        dirs_deleted_this_pass = 0
        
        for dirpath, dirnames, filenames in os.walk(root_dir, topdown=False):
            if dirpath == root_dir:
                continue
                
            if not dirnames and not filenames:
                try:
                    os.rmdir(dirpath)
                    print(f"Deleted empty directory: {dirpath}")
                    dirs_deleted_this_pass += 1
                except OSError as e:
                    print(f"Error deleting {dirpath}: {e}")
        
        deleted_count += dirs_deleted_this_pass
        
        if dirs_deleted_this_pass == 0:
            break
    
    return deleted_count


def main():
    parser = argparse.ArgumentParser(description="Delete empty directories iteratively")
    parser.add_argument("directory", help="Directory to clean up")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be deleted without actually deleting")
    
    args = parser.parse_args()
    
    if not os.path.exists(args.directory):
        print(f"Error: Directory '{args.directory}' does not exist")
        sys.exit(1)
    
    if not os.path.isdir(args.directory):
        print(f"Error: '{args.directory}' is not a directory")
        sys.exit(1)
    
    if args.dry_run:
        print(f"DRY RUN: Would delete empty directories in: {args.directory}")
        for dirpath, dirnames, filenames in os.walk(args.directory, topdown=False):
            if dirpath == args.directory:
                continue
            if not dirnames and not filenames:
                print(f"Would delete: {dirpath}")
        return
    
    print(f"Deleting empty directories in: {args.directory}")
    deleted_count = delete_empty_directories(args.directory)
    print(f"Total directories deleted: {deleted_count}")


if __name__ == "__main__":
    main()