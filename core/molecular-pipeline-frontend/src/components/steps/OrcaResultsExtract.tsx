import React, { useState } from 'react';
import { Download, Folder, FileText, CheckSquare, Square } from 'lucide-react';
import { OrcaExtractConfig, JobStatus } from '../../types';
import { pipelineApi } from '../../api/pipelineApi';
import FileManager from '../FileManager';

interface OrcaResultsExtractProps {
  onJobUpdate: (job: JobStatus) => void;
}

const OrcaResultsExtract: React.FC<OrcaResultsExtractProps> = ({ onJobUpdate }) => {
  const [config, setConfig] = useState<OrcaExtractConfig>({
    directory: '',
    outputFile: 'orca_results.csv',
    outputName: '',
    verbose: false,
    excitedStates: false,
    socList: [],
    regularAbsorption: false,
    socAbsorption: false,
    extractAll: false
  });

  const [showFileManager, setShowFileManager] = useState(false);
  const [customSoc, setCustomSoc] = useState('');
  const [downloadUrl, setDownloadUrl] = useState<string | null>(null);

  const handleDirectorySelect = (path: string) => {
    setConfig({ ...config, directory: path });
    setShowFileManager(false);
  };

  const handleSocListChange = (socValue: string, checked: boolean) => {
    if (checked) {
      setConfig({ ...config, socList: [...config.socList, socValue] });
    } else {
      setConfig({ ...config, socList: config.socList.filter(s => s !== socValue) });
    }
  };

  const handleAddCustomSoc = () => {
    if (customSoc && !config.socList.includes(customSoc)) {
      setConfig({ ...config, socList: [...config.socList, customSoc] });
      setCustomSoc('');
    }
  };

  const handleRemoveSoc = (socValue: string) => {
    setConfig({ ...config, socList: config.socList.filter(s => s !== socValue) });
  };

  const handleExtractAllChange = (checked: boolean) => {
    setConfig({ 
      ...config, 
      extractAll: checked,
      excitedStates: checked,
      regularAbsorption: checked,
      socAbsorption: checked
    });
  };

  const handleSubmit = async () => {
    const jobId = `orca-extract-${Date.now()}`;
    const job: JobStatus = {
      id: jobId,
      stepId: 'ORCA Results Extract',
      status: 'running',
      startTime: new Date(),
      message: `Extracting ORCA results from ${config.directory}`
    };
    
    onJobUpdate(job);
    setDownloadUrl(null);

    try {
      const result = await pipelineApi.extractOrcaResults(config);
      
      if (result.success) {
        onJobUpdate({ 
          ...job, 
          status: 'completed', 
          endTime: new Date(), 
          message: `Extraction completed. Results saved to ${config.outputFile}` 
        });
        
        if (result.outputFile) {
          setDownloadUrl(`/api/files/download?path=${encodeURIComponent(result.outputFile)}`);
        }
      } else {
        onJobUpdate({ 
          ...job, 
          status: 'failed', 
          endTime: new Date(), 
          message: result.error || 'Extraction failed' 
        });
      }
    } catch (error) {
      onJobUpdate({ 
        ...job, 
        status: 'failed', 
        endTime: new Date(), 
        message: 'Network error during extraction' 
      });
    }
  };

  return (
    <div>
      <h2 className="text-2xl font-bold mb-6">ORCA Results Extract</h2>
      <p className="text-gray-600 mb-6">
        Extract quantum chemistry calculation results from ORCA output files including SMILES, excited states, SOC matrix elements, and absorption spectra.
      </p>

      <div className="space-y-6">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            ORCA Output Directory
          </label>
          <div className="flex space-x-2">
            <input
              type="text"
              value={config.directory}
              onChange={(e) => setConfig({ ...config, directory: e.target.value })}
              className="flex-1 border border-gray-300 rounded-md px-3 py-2"
              placeholder="Directory containing ORCA .output files"
            />
            <button
              onClick={() => setShowFileManager(true)}
              className="bg-gray-500 text-white px-3 py-2 rounded-md hover:bg-gray-600"
            >
              <Folder className="w-4 h-4" />
            </button>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Output CSV File
            </label>
            <input
              type="text"
              value={config.outputFile}
              onChange={(e) => setConfig({ ...config, outputFile: e.target.value })}
              className="w-full border border-gray-300 rounded-md px-3 py-2"
              placeholder="orca_results.csv"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Specific Output Name (optional)
            </label>
            <input
              type="text"
              value={config.outputName}
              onChange={(e) => setConfig({ ...config, outputName: e.target.value })}
              className="w-full border border-gray-300 rounded-md px-3 py-2"
              placeholder="Search for specific .output filename"
            />
          </div>
        </div>

        <div className="bg-gray-50 border border-gray-200 rounded-md p-4">
          <h3 className="text-lg font-medium text-gray-900 mb-4">Extraction Options</h3>
          
          <div className="space-y-3">
            <div className="flex items-center space-x-3">
              <button
                onClick={() => handleExtractAllChange(!config.extractAll)}
                className="flex items-center"
              >
                {config.extractAll ? 
                  <CheckSquare className="w-5 h-5 text-blue-600" /> : 
                  <Square className="w-5 h-5 text-gray-400" />
                }
              </button>
              <label className="text-sm font-medium text-gray-700">
                Extract All Data
              </label>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 ml-8">
              <div className="flex items-center space-x-3">
                <button
                  onClick={() => setConfig({ ...config, excitedStates: !config.excitedStates })}
                  className="flex items-center"
                  disabled={config.extractAll}
                >
                  {config.excitedStates ? 
                    <CheckSquare className="w-4 h-4 text-blue-600" /> : 
                    <Square className="w-4 h-4 text-gray-400" />
                  }
                </button>
                <label className="text-sm text-gray-600">S1/T1 Excited States</label>
              </div>

              <div className="flex items-center space-x-3">
                <button
                  onClick={() => setConfig({ ...config, regularAbsorption: !config.regularAbsorption })}
                  className="flex items-center"
                  disabled={config.extractAll}
                >
                  {config.regularAbsorption ? 
                    <CheckSquare className="w-4 h-4 text-blue-600" /> : 
                    <Square className="w-4 h-4 text-gray-400" />
                  }
                </button>
                <label className="text-sm text-gray-600">Regular Absorption</label>
              </div>

              <div className="flex items-center space-x-3">
                <button
                  onClick={() => setConfig({ ...config, socAbsorption: !config.socAbsorption })}
                  className="flex items-center"
                  disabled={config.extractAll}
                >
                  {config.socAbsorption ? 
                    <CheckSquare className="w-4 h-4 text-blue-600" /> : 
                    <Square className="w-4 h-4 text-gray-400" />
                  }
                </button>
                <label className="text-sm text-gray-600">SOC-Corrected Absorption</label>
              </div>
            </div>
          </div>
        </div>

        <div className="bg-blue-50 border border-blue-200 rounded-md p-4">
          <h3 className="text-sm font-medium text-blue-900 mb-3">SOC Matrix Elements</h3>
          
          <div className="space-y-3">
            <div className="flex flex-wrap gap-2">
              {['S1T1', 'S0T1', 'S2T1', 'S1T2'].map(soc => (
                <div key={soc} className="flex items-center space-x-2">
                  <button
                    onClick={() => handleSocListChange(soc, !config.socList.includes(soc))}
                    className="flex items-center"
                  >
                    {config.socList.includes(soc) ? 
                      <CheckSquare className="w-4 h-4 text-blue-600" /> : 
                      <Square className="w-4 h-4 text-gray-400" />
                    }
                  </button>
                  <label className="text-sm text-blue-700">{soc}</label>
                </div>
              ))}
            </div>

            <div className="flex space-x-2">
              <input
                type="text"
                value={customSoc}
                onChange={(e) => setCustomSoc(e.target.value)}
                className="flex-1 text-sm border border-blue-300 rounded px-2 py-1"
                placeholder="Custom SOC (e.g., S3T2)"
              />
              <button
                onClick={handleAddCustomSoc}
                className="bg-blue-600 text-white px-3 py-1 rounded text-sm hover:bg-blue-700"
              >
                Add
              </button>
            </div>

            {config.socList.length > 0 && (
              <div className="flex flex-wrap gap-2 mt-2">
                {config.socList.map(soc => (
                  <span
                    key={soc}
                    className="inline-flex items-center bg-blue-100 text-blue-800 px-2 py-1 rounded-full text-xs"
                  >
                    {soc}
                    <button
                      onClick={() => handleRemoveSoc(soc)}
                      className="ml-1 text-blue-600 hover:text-blue-800"
                    >
                      ×
                    </button>
                  </span>
                ))}
              </div>
            )}
          </div>
        </div>

        <div className="flex items-center space-x-3">
          <button
            onClick={() => setConfig({ ...config, verbose: !config.verbose })}
            className="flex items-center"
          >
            {config.verbose ? 
              <CheckSquare className="w-5 h-5 text-green-600" /> : 
              <Square className="w-5 h-5 text-gray-400" />
            }
          </button>
          <label className="text-sm text-gray-700">Verbose Output</label>
        </div>

        <button
          onClick={handleSubmit}
          disabled={!config.directory}
          className="w-full bg-purple-600 text-white py-2 px-4 rounded-md hover:bg-purple-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center space-x-2"
        >
          <Download className="w-4 h-4" />
          <span>Extract ORCA Results</span>
        </button>

        {downloadUrl && (
          <div className="bg-green-50 border border-green-200 rounded-md p-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-2">
                <FileText className="w-5 h-5 text-green-600" />
                <span className="text-sm font-medium text-green-900">Results Ready</span>
              </div>
              <a
                href={downloadUrl}
                download={config.outputFile}
                className="bg-green-600 text-white px-3 py-1 rounded text-sm hover:bg-green-700 flex items-center space-x-1"
              >
                <Download className="w-4 h-4" />
                <span>Download CSV</span>
              </a>
            </div>
            <p className="text-sm text-green-700 mt-2">
              ORCA results have been extracted and are ready for download as CSV.
            </p>
          </div>
        )}
      </div>

      {showFileManager && (
        <FileManager
          onSelect={handleDirectorySelect}
          onClose={() => setShowFileManager(false)}
          allowFiles={false}
          allowDirectories={true}
        />
      )}
    </div>
  );
};

export default OrcaResultsExtract;