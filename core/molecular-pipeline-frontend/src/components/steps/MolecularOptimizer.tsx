import React, { useState, useEffect } from 'react';
import { Cpu, Play, Monitor, Folder, BarChart3 } from 'lucide-react';
import type { OptimizeConfig, JobStatus } from '../../types';
import { pipelineApi } from '../../api/pipelineApi';
import FileManager from '../FileManager';

interface MolecularOptimizerProps {
  onJobUpdate: (job: JobStatus) => void;
}

const MolecularOptimizer: React.FC<MolecularOptimizerProps> = ({ onJobUpdate }) => {
  const [config, setConfig] = useState<OptimizeConfig>({
    inputDir: '',
    gpuIds: '0,1,2,3',
    fmax: 5e-4,
    steps: 10000,
    monitor: true
  });

  const [showFileManager, setShowFileManager] = useState(false);
  const [selecting, setSelecting] = useState<'input' | 'output' | null>(null);
  const [progressStats, setProgressStats] = useState<{
    totalMolecules: number;
    completed: number;
    failed: number;
    remaining: number;
    successRate: number;
  } | null>(null);
  const [monitoringProgress, setMonitoringProgress] = useState(false);

  const handleFileSelect = (path: string) => {
    if (selecting === 'input') {
      setConfig({ ...config, inputDir: path });
    } else if (selecting === 'output') {
      setConfig({ ...config, outputDir: path });
    }
    setShowFileManager(false);
    setSelecting(null);
  };

  const fetchProgress = async () => {
    if (!config.inputDir) return;
    
    try {
      const result = await pipelineApi.getOptimizationProgress(config.inputDir);
      if (result.success) {
        setProgressStats(result.stats);
      }
    } catch (error) {
      console.error('Failed to fetch progress:', error);
    }
  };

  const handleSubmit = async () => {
    const jobId = `optimize-${Date.now()}`;
    const job: JobStatus = {
      id: jobId,
      stepId: 'Molecular Optimization',
      status: 'running',
      startTime: new Date(),
      message: `Optimizing ${config.inputDir} on GPUs: ${config.gpuIds}`
    };
    
    onJobUpdate(job);
    setMonitoringProgress(true);

    try {
      const result = await pipelineApi.optimizeMultiGpu(config);
      
      if (result.success) {
        onJobUpdate({ ...job, status: 'completed', endTime: new Date(), message: 'Optimization completed successfully' });
      } else {
        onJobUpdate({ ...job, status: 'failed', endTime: new Date(), message: result.error || 'Optimization failed' });
      }
    } catch (error) {
      onJobUpdate({ ...job, status: 'failed', endTime: new Date(), message: 'Network error' });
    } finally {
      setMonitoringProgress(false);
    }
  };

  useEffect(() => {
    if (monitoringProgress && config.inputDir) {
      const interval = setInterval(fetchProgress, 10000);
      return () => clearInterval(interval);
    }
  }, [monitoringProgress, config.inputDir]);

  return (
    <div>
      <h2 className="text-2xl font-bold mb-6">Molecular Optimization</h2>
      <p className="text-gray-600 mb-6">
        Optimize molecular structures using OMol across multiple GPUs
      </p>

      <div className="space-y-6">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Input Directory (Conformers)
          </label>
          <div className="flex space-x-2">
            <input
              type="text"
              value={config.inputDir}
              onChange={(e) => setConfig({ ...config, inputDir: e.target.value })}
              className="flex-1 border border-gray-300 rounded-md px-3 py-2"
              placeholder="Directory containing conformer subdirectories"
            />
            <button
              onClick={() => { setSelecting('input'); setShowFileManager(true); }}
              className="bg-gray-500 text-white px-3 py-2 rounded-md hover:bg-gray-600"
            >
              <Folder className="w-4 h-4" />
            </button>
          </div>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Output Directory (Optional)
          </label>
          <div className="flex space-x-2">
            <input
              type="text"
              value={config.outputDir || ''}
              onChange={(e) => setConfig({ ...config, outputDir: e.target.value || undefined })}
              className="flex-1 border border-gray-300 rounded-md px-3 py-2"
              placeholder="Leave empty to optimize in place"
            />
            <button
              onClick={() => { setSelecting('output'); setShowFileManager(true); }}
              className="bg-gray-500 text-white px-3 py-2 rounded-md hover:bg-gray-600"
            >
              <Folder className="w-4 h-4" />
            </button>
          </div>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            GPU IDs
          </label>
          <input
            type="text"
            value={config.gpuIds}
            onChange={(e) => setConfig({ ...config, gpuIds: e.target.value })}
            className="w-full border border-gray-300 rounded-md px-3 py-2"
            placeholder="e.g., 0,1,2,3 or 0*4,1*4"
          />
          <p className="text-xs text-gray-500 mt-1">
            Use comma-separated GPU IDs or multiplication syntax (e.g., "1*4" for 4 tasks on GPU 1)
          </p>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Force Threshold (eV/Å)
            </label>
            <input
              type="number"
              value={config.fmax}
              onChange={(e) => {
                const val = parseFloat(e.target.value);
                if (!isNaN(val) && val > 0) {
                  setConfig({ ...config, fmax: val });
                }
              }}
              className="w-full border border-gray-300 rounded-md px-3 py-2"
              step="0.0001"
            />
          </div>
          
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Max Steps
            </label>
            <input
              type="number"
              value={config.steps}
              onChange={(e) => {
                const val = parseInt(e.target.value, 10);
                if (!isNaN(val) && val > 0) {
                  setConfig({ ...config, steps: val });
                }
              }}
              className="w-full border border-gray-300 rounded-md px-3 py-2"
              min="1"
            />
          </div>
        </div>

        <div className="space-y-4">
          <div>
            <label className="flex items-center space-x-2">
              <input
                type="checkbox"
                checked={config.monitor}
                onChange={(e) => setConfig({ ...config, monitor: e.target.checked })}
                className="rounded"
              />
              <span className="text-sm text-gray-700">Monitor sessions until completion</span>
            </label>
          </div>
          
          <div className="flex space-x-2">
            <button
              onClick={fetchProgress}
              disabled={!config.inputDir}
              className="bg-blue-600 text-white py-1 px-3 rounded text-sm hover:bg-blue-700 disabled:opacity-50 flex items-center space-x-1"
            >
              <BarChart3 className="w-3 h-3" />
              <span>Check Progress</span>
            </button>
            
            {progressStats && (
              <span className="text-sm text-gray-600 py-1 px-2">
                {progressStats.completed}/{progressStats.totalMolecules} complete ({progressStats.successRate.toFixed(1)}%)
              </span>
            )}
          </div>
        </div>

        {progressStats && (
          <div className="bg-gray-50 rounded-lg p-4 space-y-3">
            <h4 className="text-sm font-semibold text-gray-700">Optimization Progress</h4>
            
            <div className="grid grid-cols-4 gap-4 text-sm">
              <div className="text-center">
                <div className="text-lg font-bold text-blue-600">{progressStats.totalMolecules}</div>
                <div className="text-gray-600">Total</div>
              </div>
              <div className="text-center">
                <div className="text-lg font-bold text-green-600">{progressStats.completed}</div>
                <div className="text-gray-600">Completed</div>
              </div>
              <div className="text-center">
                <div className="text-lg font-bold text-red-600">{progressStats.failed}</div>
                <div className="text-gray-600">Failed</div>
              </div>
              <div className="text-center">
                <div className="text-lg font-bold text-yellow-600">{progressStats.remaining}</div>
                <div className="text-gray-600">Remaining</div>
              </div>
            </div>
            
            <div className="w-full bg-gray-200 rounded-full h-2">
              <div 
                className="bg-green-600 h-2 rounded-full transition-all duration-300" 
                style={{ width: `${progressStats.successRate}%` }}
              />
            </div>
            
            <div className="text-center text-sm text-gray-600">
              {progressStats.successRate.toFixed(1)}% Success Rate
            </div>
          </div>
        )}

        <button
          onClick={handleSubmit}
          disabled={!config.inputDir}
          className="w-full bg-green-600 text-white py-2 px-4 rounded-md hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center space-x-2"
        >
          <Cpu className="w-4 h-4" />
          <span>Start Optimization</span>
        </button>
      </div>

      {showFileManager && (
        <FileManager
          onSelect={handleFileSelect}
          onClose={() => { setShowFileManager(false); setSelecting(null); }}
          allowDirectories={true}
          allowFiles={false}
        />
      )}
    </div>
  );
};

export default MolecularOptimizer;