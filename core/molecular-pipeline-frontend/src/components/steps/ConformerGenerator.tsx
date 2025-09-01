import React, { useState } from 'react';
import { Upload, Folder, Play } from 'lucide-react';
import { ConformerConfig, JobStatus } from '../../types';
import { pipelineApi } from '../../api/pipelineApi';
import FileManager from '../FileManager';

interface ConformerGeneratorProps {
  onJobUpdate: (job: JobStatus) => void;
}

const ConformerGenerator: React.FC<ConformerGeneratorProps> = ({ onJobUpdate }) => {
  const [config, setConfig] = useState<ConformerConfig>({
    smiFile: '',
    outputDir: './conformers',
    workers: 4,
    batchSize: 1000,
    verbose: false
  });

  const [showFileManager, setShowFileManager] = useState(false);
  const [selecting, setSelecting] = useState<'smi' | 'output' | null>(null);

  const handleFileSelect = (path: string) => {
    if (selecting === 'smi') {
      setConfig({ ...config, smiFile: path });
    } else if (selecting === 'output') {
      setConfig({ ...config, outputDir: path });
    }
    setShowFileManager(false);
    setSelecting(null);
  };

  const handleSubmit = async () => {
    const jobId = `conformer-${Date.now()}`;
    const job: JobStatus = {
      id: jobId,
      stepId: 'Conformer Generation',
      status: 'running',
      startTime: new Date(),
      message: `Processing ${config.smiFile}`
    };
    
    onJobUpdate(job);

    try {
      const result = await pipelineApi.generateConformers(config);
      
      if (result.success) {
        onJobUpdate({ ...job, status: 'completed', endTime: new Date(), message: 'Generation completed successfully' });
      } else {
        onJobUpdate({ ...job, status: 'failed', endTime: new Date(), message: result.error || 'Generation failed' });
      }
    } catch (error) {
      onJobUpdate({ ...job, status: 'failed', endTime: new Date(), message: 'Network error' });
    }
  };

  return (
    <div>
      <h2 className="text-2xl font-bold mb-6">Conformer Generation</h2>
      <p className="text-gray-600 mb-6">
        Generate molecular conformations from SMILES strings using RDKit
      </p>

      <div className="space-y-6">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            SMILES Input File (.smi)
          </label>
          <div className="flex space-x-2">
            <input
              type="text"
              value={config.smiFile}
              onChange={(e) => setConfig({ ...config, smiFile: e.target.value })}
              className="flex-1 border border-gray-300 rounded-md px-3 py-2"
              placeholder="Path to .smi file"
            />
            <button
              onClick={() => { setSelecting('smi'); setShowFileManager(true); }}
              className="bg-gray-500 text-white px-3 py-2 rounded-md hover:bg-gray-600"
            >
              <Folder className="w-4 h-4" />
            </button>
          </div>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Output Directory
          </label>
          <div className="flex space-x-2">
            <input
              type="text"
              value={config.outputDir}
              onChange={(e) => setConfig({ ...config, outputDir: e.target.value })}
              className="flex-1 border border-gray-300 rounded-md px-3 py-2"
            />
            <button
              onClick={() => { setSelecting('output'); setShowFileManager(true); }}
              className="bg-gray-500 text-white px-3 py-2 rounded-md hover:bg-gray-600"
            >
              <Folder className="w-4 h-4" />
            </button>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Workers
            </label>
            <input
              type="number"
              value={config.workers}
              onChange={(e) => {
                const val = parseInt(e.target.value, 10);
                if (!isNaN(val) && val > 0) {
                  setConfig({ ...config, workers: val });
                }
              }}
              className="w-full border border-gray-300 rounded-md px-3 py-2"
              min="1"
            />
          </div>
          
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Batch Size
            </label>
            <input
              type="number"
              value={config.batchSize}
              onChange={(e) => {
                const val = parseInt(e.target.value, 10);
                if (!isNaN(val) && val > 0) {
                  setConfig({ ...config, batchSize: val });
                }
              }}
              className="w-full border border-gray-300 rounded-md px-3 py-2"
              min="1"
            />
          </div>
        </div>

        <div>
          <label className="flex items-center space-x-2">
            <input
              type="checkbox"
              checked={config.verbose}
              onChange={(e) => setConfig({ ...config, verbose: e.target.checked })}
              className="rounded"
            />
            <span className="text-sm text-gray-700">Verbose output</span>
          </label>
        </div>

        <button
          onClick={handleSubmit}
          disabled={!config.smiFile}
          className="w-full bg-blue-600 text-white py-2 px-4 rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center space-x-2"
        >
          <Play className="w-4 h-4" />
          <span>Generate Conformers</span>
        </button>
      </div>

      {showFileManager && (
        <FileManager
          onSelect={handleFileSelect}
          onClose={() => { setShowFileManager(false); setSelecting(null); }}
          allowFiles={selecting === 'smi'}
          allowDirectories={selecting === 'output'}
        />
      )}
    </div>
  );
};

export default ConformerGenerator;