import os
import shutil
import subprocess
import time

def check_job_queue():
    """Check if the number of jobs in the queue is smaller than 200."""
    try:
        # Run squeue command to get the number of jobs in the queue for the user
        result = subprocess.run(['sh', '-c', 'squeue -u $USER -t pending | wc -l'], 
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        job_count = int(result.stdout.strip()) - 1  # Subtract 1 to exclude the header line
        return job_count < 2000
    except subprocess.CalledProcessError as e:
        print(f"Error checking job queue: {e}")
        return False

def output_is_complete(folder_path, success_marker="****ORCA TERMINATED NORMALLY****"):
    """
    Check if any output file in the folder contains the success_marker string.
    
    Parameters:
    - folder_path: Path to the directory to search for output files.
    - success_marker: The string indicating successful termination.
    
    Returns:
    - True if at least one output file contains the success_marker.
    - False otherwise.
    """
    for filename in os.listdir(folder_path):
        if filename.endswith(".output"):
            output_file_path = os.path.join(folder_path, filename)
            try:
                with open(output_file_path, 'r') as file:
                    for line in file:
                        if success_marker in line:
                            print(f"Found success marker in {output_file_path}")
                            return True
            except Exception as e:
                print(f"Error reading {output_file_path}: {e}")
    return False

def run_psi4_in_subfolders(folder_path):
    """
    Recursively traverse folders starting from folder_path.
    For each .inp file, check if the corresponding output indicates completion.
    If not, submit a new job.
    
    Parameters:
    - folder_path: The root directory to start the traversal.
    """
    # List all files and directories in the given folder
    try:
        items = os.listdir(folder_path)
    except Exception as e:
        print(f"Error accessing {folder_path}: {e}")
        return

    # Loop through each item
    for item in items:
        item_path = os.path.join(folder_path, item)

        # If it's a directory, recurse into it
        if os.path.isdir(item_path):
            print(f"Entering directory: {item_path}")
            run_psi4_in_subfolders(item_path)

        # If the item is a .inp file, proceed to check/output submission
        elif item.endswith(".inp"):
            print(f"Processing input file: {item_path}")
            # Check if the output indicates successful completion
            if not output_is_complete(folder_path):
                # Wait until the job queue has space
                while not check_job_queue():
                    print("Too many jobs in the queue. Sleeping for 1 second...")
                    time.sleep(1)

                # Copy the submission script to the folder
                submission_script_src = '/work/home/huangm/script/orca_soc.sh'
                submission_script_dst = os.path.join(folder_path, 'orca_soc.sh')
                try:
                    shutil.copy(submission_script_src, submission_script_dst)
                    print(f"Copied submission script to {folder_path}")
                except Exception as e:
                    print(f"Error copying submission script to {folder_path}: {e}")
                    continue  # Skip submitting if copy fails

                # Submit the job using sbatch
                command = ["sbatch", "orca_soc.sh"]
                try:
                    print(f"Submitting job in: {folder_path}")
                    subprocess.run(command, cwd=folder_path, check=True)
                    time.sleep(0.5)  # Small delay to avoid overwhelming the scheduler
                except subprocess.CalledProcessError as e:
                    print(f"Error submitting job in {folder_path}: {e.stderr}")
            else:
                print(f"Skipping submission in {folder_path}, job already completed.")

        else:
            # For any other file types, do nothing
            continue

if __name__ == "__main__":
    # Get the current working directory
    current_directory = os.getcwd()

    print("Starting the script...")
    run_psi4_in_subfolders(current_directory)
    print("Script execution is complete.")

