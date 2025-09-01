import React, { useState } from 'react';
import { Settings, Play, Folder } from 'lucide-react';
import { pipelineApi } from '../../api/pipelineApi';
import { JobStatus } from '../../types';
import FileManager from '../FileManager';

interface OrcaSubmissionProps {
  onJobUpdate: (job: JobStatus) => void;
}

const OrcaSubmission: React.FC<OrcaSubmissionProps> = ({ onJobUpdate }) => {
  const [config, setConfig] = useState({
    mainDirectory: '',
    totalCores: 8,
    coresPerTask: 4,
    inpName: '',
    forceNotSkip: false
  });

  const [showFileManager, setShowFileManager] = useState(false);

  const handleFileSelect = (path: string) => {
    setConfig({ ...config, mainDirectory: path });
    setShowFileManager(false);
  };

  const handleSubmit = async () => {
    const jobId = `orca-submit-${Date.now()}`;
    const job: JobStatus = {
      id: jobId,
      stepId: 'ORCA Submission',
      status: 'running',
      startTime: new Date(),
      message: `Submitting ORCA calculations for ${config.mainDirectory}`
    };
    
    onJobUpdate(job);

    try {
      const result = await pipelineApi.submitOrcaBatch(config);
      
      if (result.success) {
        onJobUpdate({ ...job, status: 'completed', endTime: new Date(), message: 'ORCA submission completed successfully' });
      } else {
        onJobUpdate({ ...job, status: 'failed', endTime: new Date(), message: result.error || 'ORCA submission failed' });
      }
    } catch (error) {
      onJobUpdate({ ...job, status: 'failed', endTime: new Date(), message: 'Network error' });
    }
  };

  return (
    <div>
      <h2 className="text-2xl font-bold mb-6">ORCA Batch Submission</h2>
      <p className="text-gray-600 mb-6">
        Submit ORCA calculations in parallel using available CPU cores
      </p>

      <div className="space-y-6">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Main Directory
          </label>
          <div className="flex space-x-2">
            <input
              type="text"
              value={config.mainDirectory}
              onChange={(e) => setConfig({ ...config, mainDirectory: e.target.value })}
              className="flex-1 border border-gray-300 rounded-md px-3 py-2"
              placeholder="Directory containing ORCA input files"
            />
            <button
              onClick={() => setShowFileManager(true)}
              className="bg-gray-500 text-white px-3 py-2 rounded-md hover:bg-gray-600"
            >
              <Folder className="w-4 h-4" />
            </button>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Total CPU Cores
            </label>
            <input
              type="number"
              value={config.totalCores}
              onChange={(e) => setConfig({ ...config, totalCores: parseInt(e.target.value) })}
              className="w-full border border-gray-300 rounded-md px-3 py-2"
              min="1"
            />
          </div>
          
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Cores per Task
            </label>
            <input
              type="number"
              value={config.coresPerTask}
              onChange={(e) => setConfig({ ...config, coresPerTask: parseInt(e.target.value) })}
              className="w-full border border-gray-300 rounded-md px-3 py-2"
              min="1"
            />
          </div>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Input File Pattern (Optional)
          </label>
          <input
            type="text"
            value={config.inpName}
            onChange={(e) => setConfig({ ...config, inpName: e.target.value })}
            className="w-full border border-gray-300 rounded-md px-3 py-2"
            placeholder="e.g., 't1_opt' to match t1_opt.inp files"
          />
        </div>

        <div>
          <label className="flex items-center space-x-2">
            <input
              type="checkbox"
              checked={config.forceNotSkip}
              onChange={(e) => setConfig({ ...config, forceNotSkip: e.target.checked })}
              className="rounded"
            />
            <span className="text-sm text-gray-700">Force reprocessing (ignore completed calculations)</span>
          </label>
        </div>

        <button
          onClick={handleSubmit}
          disabled={!config.mainDirectory}
          className="w-full bg-red-600 text-white py-2 px-4 rounded-md hover:bg-red-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center space-x-2"
        >
          <Play className="w-4 h-4" />
          <span>Submit ORCA Calculations</span>
        </button>
      </div>

      {showFileManager && (
        <FileManager
          onSelect={handleFileSelect}
          onClose={() => setShowFileManager(false)}
          allowDirectories={true}
          allowFiles={false}
        />
      )}
    </div>
  );
};

export default OrcaSubmission;