import express from 'express';
import cors from 'cors';
import { spawn } from 'child_process';
import path from 'path';
import fs from 'fs/promises';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const app = express();
const PORT = 3001;

app.use(cors());
app.use(express.json());

const SCRIPTS_DIR = path.resolve(__dirname, '../..');

app.get('/api/files/list', async (req, res) => {
  try {
    const dirPath = req.query.path || '/home/user/data/OMol25/AutoOpt/core';
    const entries = await fs.readdir(dirPath, { withFileTypes: true });
    
    const files = await Promise.all(
      entries.map(async (entry) => {
        const fullPath = path.join(dirPath, entry.name);
        const stats = await fs.stat(fullPath).catch(() => null);
        
        return {
          path: fullPath,
          name: entry.name,
          type: entry.isDirectory() ? 'directory' : 'file',
          size: stats?.size,
          modifiedTime: stats?.mtime
        };
      })
    );
    
    res.json({ files: files.sort((a, b) => {
      if (a.type !== b.type) return a.type === 'directory' ? -1 : 1;
      return a.name.localeCompare(b.name);
    })});
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

app.get('/api/files/download', async (req, res) => {
  try {
    const filePath = req.query.path;
    if (!filePath) {
      return res.status(400).json({ error: 'File path parameter required' });
    }
    
    const stats = await fs.stat(filePath);
    if (!stats.isFile()) {
      return res.status(400).json({ error: 'Path is not a file' });
    }
    
    const fileName = path.basename(filePath);
    res.setHeader('Content-Disposition', `attachment; filename="${fileName}"`);
    res.setHeader('Content-Type', 'text/csv');
    
    const fileBuffer = await fs.readFile(filePath);
    res.send(fileBuffer);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

app.post('/api/conformer/generate', (req, res) => {
  const { smiFile, outputDir, workers, batchSize, verbose } = req.body;
  
  const args = [
    path.join(SCRIPTS_DIR, 'generate_conformers.py'),
    smiFile,
    '--output_dir', outputDir,
    '--workers', workers.toString(),
    '--batch_size', batchSize.toString()
  ];
  
  if (verbose) args.push('--verbose');
  
  const child = spawn('python3', args, {
    cwd: SCRIPTS_DIR,
    stdio: ['pipe', 'pipe', 'pipe']
  });
  
  let output = '';
  let error = '';
  
  child.stdout.on('data', (data) => {
    output += data.toString();
  });
  
  child.stderr.on('data', (data) => {
    error += data.toString();
  });
  
  child.on('close', (code) => {
    res.json({
      success: code === 0,
      code,
      output,
      error
    });
  });
});

app.post('/api/optimize/multi-gpu', (req, res) => {
  const { inputDir, gpuIds, outputDir, fmax, steps, monitor } = req.body;
  
  const args = [
    path.join(SCRIPTS_DIR, 'multi_gpu_omol_optimize.py'),
    inputDir,
    '--gpu_ids', gpuIds,
    '--fmax', fmax.toString(),
    '--steps', steps.toString()
  ];
  
  if (outputDir) {
    args.push('--output_dir', outputDir);
  }
  
  if (monitor) args.push('--monitor');
  
  const child = spawn('python3', args, {
    cwd: SCRIPTS_DIR,
    stdio: ['pipe', 'pipe', 'pipe']
  });
  
  let output = '';
  let error = '';
  
  child.stdout.on('data', (data) => {
    output += data.toString();
  });
  
  child.stderr.on('data', (data) => {
    error += data.toString();
  });
  
  child.on('close', (code) => {
    res.json({
      success: code === 0,
      code,
      output,
      error
    });
  });
});

app.post('/api/orca/prepare', (req, res) => {
  const { 
    conformerDir, 
    conformerType, 
    templateFile, 
    outputDir, 
    inpName, 
    xyzName, 
    additionalCharge, 
    additionalMultiplicity 
  } = req.body;
  
  const args = [
    path.join(SCRIPTS_DIR, 'orca_file_prepare.py'),
    '-d', conformerDir,
    '-t', conformerType,
    '-f', templateFile,
    '--additional_charge', additionalCharge.toString(),
    '--additional_multiplicity', additionalMultiplicity.toString()
  ];
  
  if (outputDir) {
    args.push('-o', outputDir);
  }
  
  if (inpName) {
    args.push('--inp_name', inpName);
  }
  
  if (xyzName) {
    args.push('--xyz_name', xyzName);
  }
  
  const child = spawn('python3', args, {
    cwd: SCRIPTS_DIR,
    stdio: ['pipe', 'pipe', 'pipe']
  });
  
  let output = '';
  let error = '';
  
  child.stdout.on('data', (data) => {
    output += data.toString();
  });
  
  child.stderr.on('data', (data) => {
    error += data.toString();
  });
  
  child.on('close', (code) => {
    res.json({
      success: code === 0,
      code,
      output,
      error
    });
  });
});

app.post('/api/extract/molecules', (req, res) => {
  const { s1t1Results, omolPath, outputDir } = req.body;
  
  const args = [
    path.join(SCRIPTS_DIR, 'extract_molecules.py'),
    '-i', s1t1Results,
    '-d', omolPath,
    '-o', outputDir
  ];
  
  const child = spawn('python3', args, {
    cwd: SCRIPTS_DIR,
    stdio: ['pipe', 'pipe', 'pipe']
  });
  
  let output = '';
  let error = '';
  
  child.stdout.on('data', (data) => {
    output += data.toString();
  });
  
  child.stderr.on('data', (data) => {
    error += data.toString();
  });
  
  child.on('close', (code) => {
    res.json({
      success: code === 0,
      code,
      output,
      error
    });
  });
});

app.post('/api/orca/submit', (req, res) => {
  const { mainDirectory, totalCores, coresPerTask, inpName, forceNotSkip } = req.body;
  
  const args = [
    path.join(SCRIPTS_DIR, 'submit_orca_batch.py'),
    mainDirectory,
    totalCores.toString(),
    '--cores-per-task', coresPerTask.toString()
  ];
  
  if (inpName) {
    args.push('--inp-name', inpName);
  }
  
  if (forceNotSkip) {
    args.push('--force-not-skip');
  }
  
  const child = spawn('python3', args, {
    cwd: SCRIPTS_DIR,
    stdio: ['pipe', 'pipe', 'pipe']
  });
  
  let output = '';
  let error = '';
  
  child.stdout.on('data', (data) => {
    output += data.toString();
  });
  
  child.stderr.on('data', (data) => {
    error += data.toString();
  });
  
  child.on('close', (code) => {
    res.json({
      success: code === 0,
      code,
      output,
      error
    });
  });
});

app.get('/api/optimization/progress', async (req, res) => {
  const { directory, optType = 'omol_opt' } = req.query;
  
  if (!directory) {
    return res.status(400).json({ error: 'Directory parameter required' });
  }
  
  const args = [
    path.join(SCRIPTS_DIR, 'count_optimization_progress.py'),
    directory,
    '--opt-type', optType
  ];
  
  const child = spawn('python3', args, {
    cwd: SCRIPTS_DIR,
    stdio: ['pipe', 'pipe', 'pipe']
  });
  
  let output = '';
  let error = '';
  
  child.stdout.on('data', (data) => {
    output += data.toString();
  });
  
  child.stderr.on('data', (data) => {
    error += data.toString();
  });
  
  child.on('close', (code) => {
    if (code === 0) {
      // Parse the output to extract statistics
      const lines = output.trim().split('\n');
      const stats = {};
      
      for (const line of lines) {
        if (line.includes('Total molecules:')) {
          stats.totalMolecules = parseInt(line.split(':')[1].trim().replace(/,/g, ''));
        } else if (line.includes('Completed optimizations:')) {
          stats.completed = parseInt(line.split(':')[1].trim().replace(/,/g, ''));
        } else if (line.includes('Failed optimizations:')) {
          stats.failed = parseInt(line.split(':')[1].trim().replace(/,/g, ''));
        } else if (line.includes('Success rate:')) {
          stats.successRate = parseFloat(line.split(':')[1].trim().replace('%', ''));
        }
      }
      
      res.json({
        success: true,
        stats: {
          totalMolecules: stats.totalMolecules || 0,
          completed: stats.completed || 0,
          failed: stats.failed || 0,
          remaining: (stats.totalMolecules || 0) - (stats.completed || 0) - (stats.failed || 0),
          successRate: stats.successRate || 0.0
        }
      });
    } else {
      res.status(500).json({
        success: false,
        error: error || 'Failed to get progress statistics'
      });
    }
  });
});

app.post('/api/orca/extract', (req, res) => {
  const { 
    directory, 
    outputFile, 
    outputName, 
    verbose,
    excitedStates,
    socList,
    regularAbsorption,
    socAbsorption,
    extractAll
  } = req.body;
  
  const args = [
    path.join(SCRIPTS_DIR, 'extract_orca_results.py'),
    '-d', directory,
    '-o', outputFile
  ];
  
  if (outputName) {
    args.push('--output_name', outputName);
  }
  
  if (verbose) {
    args.push('-v');
  }
  
  if (extractAll) {
    args.push('--all');
  } else {
    if (excitedStates) {
      args.push('--excited-states');
    }
    
    if (regularAbsorption) {
      args.push('--regular-absorption');
    }
    
    if (socAbsorption) {
      args.push('--soc-absorption');
    }
    
    if (socList && socList.length > 0) {
      args.push('--soc-list', ...socList);
    }
  }
  
  const child = spawn('python3', args, {
    cwd: SCRIPTS_DIR,
    stdio: ['pipe', 'pipe', 'pipe']
  });
  
  let output = '';
  let error = '';
  
  child.stdout.on('data', (data) => {
    output += data.toString();
  });
  
  child.stderr.on('data', (data) => {
    error += data.toString();
  });
  
  child.on('close', (code) => {
    res.json({
      success: code === 0,
      code,
      output,
      error,
      outputFile: code === 0 ? path.resolve(SCRIPTS_DIR, outputFile) : null
    });
  });
});

app.listen(PORT, '0.0.0.0', () => {
  console.log(`Molecular Pipeline API server running on port ${PORT}`);
});