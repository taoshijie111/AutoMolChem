import React, { useState } from 'react';
import { Filter, Play, Folder, Upload } from 'lucide-react';
import { ExtractConfig, JobStatus } from '../../types';
import { pipelineApi } from '../../api/pipelineApi';
import FileManager from '../FileManager';

interface MoleculeExtractorProps {
  onJobUpdate: (job: JobStatus) => void;
}

const MoleculeExtractor: React.FC<MoleculeExtractorProps> = ({ onJobUpdate }) => {
  const [config, setConfig] = useState<ExtractConfig>({
    s1t1Results: '',
    omolPath: '',
    outputDir: ''
  });

  const [showFileManager, setShowFileManager] = useState(false);
  const [selecting, setSelecting] = useState<'results' | 'omol' | 'output' | null>(null);

  const handleFileSelect = (path: string) => {
    if (selecting === 'results') {
      setConfig({ ...config, s1t1Results: path });
    } else if (selecting === 'omol') {
      setConfig({ ...config, omolPath: path });
    } else if (selecting === 'output') {
      setConfig({ ...config, outputDir: path });
    }
    setShowFileManager(false);
    setSelecting(null);
  };

  const handleSubmit = async () => {
    const jobId = `extract-${Date.now()}`;
    const job: JobStatus = {
      id: jobId,
      stepId: 'Molecule Extraction',
      status: 'running',
      startTime: new Date(),
      message: `Extracting molecules with energy difference < 0.2 eV`
    };
    
    onJobUpdate(job);

    try {
      const result = await pipelineApi.extractMolecules(config);
      
      if (result.success) {
        onJobUpdate({ ...job, status: 'completed', endTime: new Date(), message: 'Extraction completed successfully' });
      } else {
        onJobUpdate({ ...job, status: 'failed', endTime: new Date(), message: result.error || 'Extraction failed' });
      }
    } catch (error) {
      onJobUpdate({ ...job, status: 'failed', endTime: new Date(), message: 'Network error' });
    }
  };

  return (
    <div>
      <h2 className="text-2xl font-bold mb-6">Molecule Extraction</h2>
      <p className="text-gray-600 mb-6">
        Extract molecules with energy difference less than 0.2 eV from S1T1 results
      </p>

      <div className="space-y-6">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            S1T1 Results File (.csv)
          </label>
          <div className="flex space-x-2">
            <input
              type="text"
              value={config.s1t1Results}
              onChange={(e) => setConfig({ ...config, s1t1Results: e.target.value })}
              className="flex-1 border border-gray-300 rounded-md px-3 py-2"
              placeholder="CSV file containing Molecule and Energy_Difference_eV columns"
            />
            <button
              onClick={() => { setSelecting('results'); setShowFileManager(true); }}
              className="bg-gray-500 text-white px-3 py-2 rounded-md hover:bg-gray-600"
            >
              <Folder className="w-4 h-4" />
            </button>
          </div>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            OMol Path
          </label>
          <div className="flex space-x-2">
            <input
              type="text"
              value={config.omolPath}
              onChange={(e) => setConfig({ ...config, omolPath: e.target.value })}
              className="flex-1 border border-gray-300 rounded-md px-3 py-2"
              placeholder="Directory containing batch folders with OMol optimization results"
            />
            <button
              onClick={() => { setSelecting('omol'); setShowFileManager(true); }}
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
              placeholder="Directory for extracted molecules"
            />
            <button
              onClick={() => { setSelecting('output'); setShowFileManager(true); }}
              className="bg-gray-500 text-white px-3 py-2 rounded-md hover:bg-gray-600"
            >
              <Folder className="w-4 h-4" />
            </button>
          </div>
        </div>

        <div className="bg-blue-50 border border-blue-200 rounded-md p-4">
          <h3 className="text-sm font-medium text-blue-900 mb-2">Filter Criteria</h3>
          <p className="text-sm text-blue-700">
            Only molecules with <strong>Energy_Difference_eV &lt; 0.2</strong> will be extracted
          </p>
        </div>

        <button
          onClick={handleSubmit}
          disabled={!config.s1t1Results || !config.omolPath || !config.outputDir}
          className="w-full bg-orange-600 text-white py-2 px-4 rounded-md hover:bg-orange-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center space-x-2"
        >
          <Filter className="w-4 h-4" />
          <span>Extract Molecules</span>
        </button>
      </div>

      {showFileManager && (
        <FileManager
          onSelect={handleFileSelect}
          onClose={() => { setShowFileManager(false); setSelecting(null); }}
          allowFiles={selecting === 'results'}
          allowDirectories={selecting !== 'results'}
        />
      )}
    </div>
  );
};

export default MoleculeExtractor;