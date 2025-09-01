# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Architecture Overview

AutoOpt is a molecular computation pipeline that performs automated molecular optimization and quantum chemistry calculations. The pipeline consists of 5 main stages:

1. **Conformer Generation** (`generate_conformers.py`) - Generates 3D conformations from SMILES strings using RDKit
2. **Structure Optimization** (`multi_gpu_omol_optimize.py`, `omol_optimize.py`) - Optimizes molecular structures using FAIRChem's uma-s-1 model
3. **ORCA File Preparation** (`orca_file_prepare.py`) - Prepares quantum chemistry input files for ORCA calculations
4. **ORCA Calculation Submission** (`submit_orca_batch.py`) - Submits DFT/TDDFT calculations to compute clusters
5. **Molecule Extraction/Filtering** (`extract_molecules.py`) - Filters results based on energy criteria

## Directory Structure

The pipeline follows a hierarchical batch/molecule organization:
```
output_dir/
├── batch_0000/
│   ├── molecule_0/
│   │   ├── conformer/conformer.xyz
│   │   ├── omol_opt/optimized.xyz
│   │   └── orca_files/
│   └── molecule_1/...
└── batch_0001/...
```

Data directories (complete/, pubchem/, etc.) contain processed molecular datasets with similar batch structures.

## Core Scripts and Usage

### Conformer Generation
```bash
python core/generate_conformers.py input.smi --output_dir OUTPUT --workers N --verbose
```

### Multi-GPU Optimization  
```bash
python core/multi_gpu_omol_optimize.py INPUT_DIR --gpu_ids "0,1,2" --verbose
# Or with task distribution: --gpu_ids "0*4,1*4"
```

### ORCA File Preparation
```bash
python core/orca_file_prepare.py -d INPUT_DIR -t omol_opt -o OUTPUT_DIR -f core/template/orca_s1t1.inp
```

### ORCA Submission
```bash
python core/submit_orca_batch.py INPUT_DIR TOTAL_CORES --cores-per-task 4
```

### Molecule Extraction
```bash
python core/extract_molecules.py -i results.csv -d OMOL_DIR -o OUTPUT_DIR
```

## Development Environment

- Primary language: Python 3.8+
- Key dependencies: RDKit, FAIRChem, ASE, ORCA (external), pandas, numpy
- GPU support: CUDA-enabled for FAIRChem optimization
- Parallel processing: Multiprocessing and screen sessions for cluster computing

## Frontend Web Interface

A React/TypeScript frontend (`core/molecular-pipeline-frontend/`) provides a web interface for the pipeline:

### Frontend Development
```bash
cd core/molecular-pipeline-frontend
npm install
npm run dev  # Development server on localhost:5173
```

### Backend API
```bash
cd core/molecular-pipeline-frontend/backend
npm install
npm start  # API server on localhost:3000
```

### Start Both Services
```bash
cd core/molecular-pipeline-frontend
./start.sh
```

## Template Files

ORCA calculation templates in `core/template/`:
- `orca_s1t1.inp` - S1/T1 energy gap calculations (B3LYP/def2-SVP TDDFT)
- `step1_orca_t1_opt.inp` - T1 state optimization
- `step2_orca_soc.inp` - Spin-orbit coupling calculations

## Pipeline Workflow (Chinese Documentation Reference)

The complete pipeline workflow is documented in `core/pipeline.md` (in Chinese). Key stages:
1. Conformer generation
2. nitial screening with S1/T1 calculations
3. Advanced filtering with T1 optimization and SOC

## Utility Scripts

Located in `utils/` directory:
- `count_optimization_progress.py` - Monitor optimization job progress
- `extract_optimization_results.py` - Extract completed optimization results  
- `extract_smiles_and_plot.py` - Analyze molecular datasets and create visualizations
- `delete_empty_dirs.py` - Clean up empty batch directories

## Error Handling and Robustness

The codebase includes extensive error handling:
- Fallback force fields in RDKit conformer generation (UFF → MMFF94)
- Completion checking to avoid re-running expensive calculations
- Screen session management for long-running multi-GPU jobs
- Graceful handling of failed molecular optimizations

## Testing and Validation

No formal test suite exists. Validation is typically done by:
- Checking optimization convergence in `omol_opt/info.txt` files
- Monitoring ORCA calculation completion
- Analyzing energy difference distributions in results