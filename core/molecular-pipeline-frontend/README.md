# Molecular Computation Pipeline Frontend

A React-based web interface for managing automated molecular computation workflows.

## Overview

This frontend provides an intuitive web interface for the molecular computation pipeline that includes:

1. **Conformer Generation** - Generate molecular conformations from SMILES strings
2. **Molecular Optimization** - Optimize structures using OMol on GPU clusters  
3. **ORCA Preparation** - Prepare quantum chemistry calculation input files
4. **ORCA Submission** - Submit calculations to compute clusters
5. **Molecule Extraction** - Filter results by energy criteria

## Architecture

- **Frontend**: React 19 + TypeScript + Tailwind CSS
- **Backend**: Express.js API server
- **Scripts**: Existing Python computational scripts

## Quick Start

### Prerequisites

- Node.js 18+ 
- Python 3.8+ with required packages (RDKit, FAIRChem, etc.)
- ORCA quantum chemistry package (for calculations)

### Installation

1. Install dependencies:
```bash
npm install
cd backend && npm install
```

2. Start both frontend and backend:
```bash
./start.sh
```

Or start them separately:

```bash
# Backend (Terminal 1)
cd backend && npm start

# Frontend (Terminal 2) 
npm run dev
```

3. Open http://localhost:5173 in your browser

## Usage

### Step 1: Conformer Generation
- Upload a `.smi` file containing SMILES strings
- Configure output directory and processing parameters
- Monitor job progress in real-time

### Step 2: Molecular Optimization  
- Select conformer directory from previous step
- Configure GPU allocation (e.g., "0,1,2,3" or "0*4,1*4")
- Set optimization parameters (force threshold, max steps)

### Step 3: ORCA Preparation
- Select optimized structures directory
- Choose ORCA template file
- Configure charge and multiplicity adjustments

### Step 4: ORCA Submission
- Select directory with prepared ORCA input files
- Set CPU core allocation
- Submit calculations to compute cluster

### Step 5: Molecule Extraction
- Upload S1T1 results CSV file
- Select OMol optimization directory
- Extract molecules meeting energy criteria

## File Organization

The pipeline maintains a structured directory hierarchy:

```
output/
├── batch_0000/
│   ├── molecule_0/
│   │   ├── conformer/
│   │   │   ├── conformer.xyz
│   │   │   └── info.txt
│   │   ├── omol_opt/
│   │   │   ├── optimized.xyz
│   │   │   └── info.txt
│   │   └── orca_files/
│   │       ├── molecule_0.xyz
│   │       └── t1_opt.inp
│   └── molecule_1/
│       └── ...
└── batch_0001/
    └── ...
```

## API Endpoints

- `GET /api/files/list` - List directory contents
- `POST /api/conformer/generate` - Generate conformers
- `POST /api/optimize/multi-gpu` - Multi-GPU optimization
- `POST /api/orca/prepare` - Prepare ORCA files
- `POST /api/orca/submit` - Submit ORCA calculations
- `POST /api/extract/molecules` - Extract filtered molecules

## Development

### Adding New Steps

1. Create component in `src/components/steps/`
2. Add step configuration to `PipelineDashboard.tsx`
3. Implement API endpoint in `backend/server.js`
4. Update type definitions in `src/types/index.ts`

### Customization

The interface can be extended to support:
- Custom calculation templates
- Advanced parameter validation
- Result visualization
- Progress persistence
- Multi-user access

## Script Integration

The frontend wraps these existing Python scripts:
- `generate_conformers.py` - RDKit conformer generation
- `multi_gpu_omol_optimize.py` - Multi-GPU molecular optimization
- `orca_file_prepare.py` - ORCA input file preparation
- `submit_orca_batch.py` - ORCA calculation submission
- `extract_molecules.py` - Energy-based filtering
