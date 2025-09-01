import React, { useState } from 'react';
import { FileText, Play, Folder } from 'lucide-react';
import { OrcaConfig, JobStatus } from '../../types';
import { pipelineApi } from '../../api/pipelineApi';
import FileManager from '../FileManager';

interface OrcaPreparationProps {
  onJobUpdate: (job: JobStatus) => void;
}

const OrcaPreparation: React.FC<OrcaPreparationProps> = ({ onJobUpdate }) => {
  const [config, setConfig] = useState<OrcaConfig>({
    conformerDir: '',
    conformerType: 'omol_opt',
    templateFile: '',
    additionalCharge: 0,
    additionalMultiplicity: 0
  });

  const [showFileManager, setShowFileManager] = useState(false);
  const [selecting, setSelecting] = useState<'conformer' | 'template' | 'output' | null>(null);

  const handleFileSelect = (path: string) => {
    if (selecting === 'conformer') {
      setConfig({ ...config, conformerDir: path });
    } else if (selecting === 'template') {
      setConfig({ ...config, templateFile: path });
    } else if (selecting === 'output') {
      setConfig({ ...config, outputDir: path });
    }
    setShowFileManager(false);
    setSelecting(null);
  };

  const handleSubmit = async () => {
    const jobId = `orca-prep-${Date.now()}`;
    const job: JobStatus = {
      id: jobId,
      stepId: 'ORCA Preparation',
      status: 'running',
      startTime: new Date(),
      message: `Preparing ORCA files for ${config.conformerDir}`
    };
    
    onJobUpdate(job);

    try {
      const result = await pipelineApi.prepareOrca(config);
      
      if (result.success) {
        onJobUpdate({ ...job, status: 'completed', endTime: new Date(), message: 'ORCA preparation completed successfully' });
      } else {
        onJobUpdate({ ...job, status: 'failed', endTime: new Date(), message: result.error || 'ORCA preparation failed' });
      }
    } catch (error) {
      onJobUpdate({ ...job, status: 'failed', endTime: new Date(), message: 'Network error' });
    }
  };

  return (
    <div>
      <h2 className="text-2xl font-bold mb-6">ORCA Preparation</h2>
      <p className="text-gray-600 mb-6">
        Prepare ORCA input files for quantum chemistry calculations
      </p>

      <div className="space-y-6">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Conformer Directory
          </label>
          <div className="flex space-x-2">
            <input
              type="text"
              value={config.conformerDir}
              onChange={(e) => setConfig({ ...config, conformerDir: e.target.value })}
              className="flex-1 border border-gray-300 rounded-md px-3 py-2"
              placeholder="Root directory of molecular conformers"
            />
            <button
              onClick={() => { setSelecting('conformer'); setShowFileManager(true); }}
              className="bg-gray-500 text-white px-3 py-2 rounded-md hover:bg-gray-600"
            >
              <Folder className="w-4 h-4" />
            </button>
          </div>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Conformer Type
          </label>
          <select
            value={config.conformerType}
            onChange={(e) => setConfig({ ...config, conformerType: e.target.value })}
            className="w-full border border-gray-300 rounded-md px-3 py-2"
          >
            <option value="omol_opt">omol_opt</option>
            <option value="conformer">conformer</option>
          </select>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Template File
          </label>
          <div className="flex space-x-2">
            <input
              type="text"
              value={config.templateFile}
              onChange={(e) => setConfig({ ...config, templateFile: e.target.value })}
              className="flex-1 border border-gray-300 rounded-md px-3 py-2"
              placeholder="Path to ORCA template file (.inp)"
            />
            <button
              onClick={() => { setSelecting('template'); setShowFileManager(true); }}
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
              placeholder="Leave empty to create alongside conformer_type"
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
              Input File Name (Optional)
            </label>
            <input
              type="text"
              value={config.inpName || ''}
              onChange={(e) => setConfig({ ...config, inpName: e.target.value || undefined })}
              className="w-full border border-gray-300 rounded-md px-3 py-2"
              placeholder="Custom .inp filename"
            />
          </div>
          
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              XYZ Reference Name (Optional)
            </label>
            <input
              type="text"
              value={config.xyzName || ''}
              onChange={(e) => setConfig({ ...config, xyzName: e.target.value || undefined })}
              className="w-full border border-gray-300 rounded-md px-3 py-2"
              placeholder="Custom xyz reference name"
            />
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Additional Charge
            </label>
            <input
              type="number"
              value={config.additionalCharge}
              onChange={(e) => {
                const val = parseInt(e.target.value, 10);
                if (!isNaN(val)) {
                  setConfig({ ...config, additionalCharge: val });
                }
              }}
              className="w-full border border-gray-300 rounded-md px-3 py-2"
            />
          </div>
          
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Additional Multiplicity
            </label>
            <input
              type="number"
              value={config.additionalMultiplicity}
              onChange={(e) => {
                const val = parseInt(e.target.value, 10);
                if (!isNaN(val)) {
                  setConfig({ ...config, additionalMultiplicity: val });
                }
              }}
              className="w-full border border-gray-300 rounded-md px-3 py-2"
            />
          </div>
        </div>

        <button
          onClick={handleSubmit}
          disabled={!config.conformerDir || !config.templateFile}
          className="w-full bg-purple-600 text-white py-2 px-4 rounded-md hover:bg-purple-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center space-x-2"
        >
          <FileText className="w-4 h-4" />
          <span>Prepare ORCA Files</span>
        </button>
      </div>

      {showFileManager && (
        <FileManager
          onSelect={handleFileSelect}
          onClose={() => { setShowFileManager(false); setSelecting(null); }}
          allowFiles={selecting === 'template'}
          allowDirectories={selecting !== 'template'}
        />
      )}
    </div>
  );
};

export default OrcaPreparation;