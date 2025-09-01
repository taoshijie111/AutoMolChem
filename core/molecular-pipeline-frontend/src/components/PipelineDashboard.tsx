import React, { useState, useEffect } from 'react';
import { Play, Settings, FileText, Cpu, Database, Send, Download } from 'lucide-react';
import { PipelineStep, JobStatus } from '../types';
import ConformerGenerator from './steps/ConformerGenerator';
import MolecularOptimizer from './steps/MolecularOptimizer';
import OrcaPreparation from './steps/OrcaPreparation';
import OrcaSubmission from './steps/OrcaSubmission';
import MoleculeExtractor from './steps/MoleculeExtractor';
import OrcaResultsExtract from './steps/OrcaResultsExtract';
import JobMonitor from './JobMonitor';
import ErrorBoundary from './ErrorBoundary';

const PipelineDashboard: React.FC = () => {
  const [activeStep, setActiveStep] = useState<string>('conformer');
  const [pipelineSteps, setPipelineSteps] = useState<PipelineStep[]>([
    {
      id: 'conformer',
      name: 'Conformer Generation',
      description: 'Generate molecular conformations from SMILES',
      status: 'pending'
    },
    {
      id: 'optimize',
      name: 'Molecular Optimization', 
      description: 'Optimize structures using OMol on GPU',
      status: 'pending'
    },
    {
      id: 'orca-prep',
      name: 'ORCA Preparation',
      description: 'Prepare ORCA input files for calculations',
      status: 'pending'
    },
    {
      id: 'orca-submit',
      name: 'ORCA Submission',
      description: 'Submit ORCA calculations to compute cluster',
      status: 'pending'
    },
    {
      id: 'extract',
      name: 'Molecule Extraction',
      description: 'Filter molecules by energy criteria',
      status: 'pending'
    },
    {
      id: 'orca-extract',
      name: 'ORCA Results Extract',
      description: 'Extract quantum chemistry results from ORCA output files',
      status: 'pending'
    }
  ]);
  
  const [jobs, setJobs] = useState<JobStatus[]>([]);

  const getStepIcon = (stepId: string) => {
    switch (stepId) {
      case 'conformer': return <Database className="w-5 h-5" />;
      case 'optimize': return <Cpu className="w-5 h-5" />;
      case 'orca-prep': return <FileText className="w-5 h-5" />;
      case 'orca-submit': return <Send className="w-5 h-5" />;
      case 'extract': return <Settings className="w-5 h-5" />;
      case 'orca-extract': return <Download className="w-5 h-5" />;
      default: return <Play className="w-5 h-5" />;
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed': return 'text-green-600';
      case 'running': return 'text-blue-600';
      case 'failed': return 'text-red-600';
      default: return 'text-gray-600';
    }
  };

  const handleJobUpdate = (job: JobStatus) => {
    setJobs(prevJobs => {
      const existingIndex = prevJobs.findIndex(j => j.id === job.id);
      if (existingIndex >= 0) {
        const updated = [...prevJobs];
        updated[existingIndex] = job;
        return updated;
      }
      return [...prevJobs.slice(-9), job];
    });
  };

  const renderStepComponent = () => {
    switch (activeStep) {
      case 'conformer':
        return <ConformerGenerator onJobUpdate={handleJobUpdate} />;
      case 'optimize':
        return <MolecularOptimizer onJobUpdate={handleJobUpdate} />;
      case 'orca-prep':
        return <OrcaPreparation onJobUpdate={handleJobUpdate} />;
      case 'orca-submit':
        return <OrcaSubmission onJobUpdate={handleJobUpdate} />;
      case 'extract':
        return <MoleculeExtractor onJobUpdate={handleJobUpdate} />;
      case 'orca-extract':
        return <OrcaResultsExtract onJobUpdate={handleJobUpdate} />;
      default:
        return null;
    }
  };

  return (
    <div className="min-h-screen bg-gray-100">
      <div className="container mx-auto px-4 py-8">
        <h1 className="text-3xl font-bold text-gray-900 mb-8">
          Molecular Computation Pipeline
        </h1>
        
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
          <div className="lg:col-span-1">
            <div className="bg-white rounded-lg shadow-md p-6">
              <h2 className="text-xl font-semibold mb-4">Pipeline Steps</h2>
              <nav className="space-y-2">
                {pipelineSteps.map((step) => (
                  <button
                    key={step.id}
                    onClick={() => setActiveStep(step.id)}
                    className={`w-full flex items-center space-x-3 px-3 py-2 rounded-md text-left transition-colors ${
                      activeStep === step.id
                        ? 'bg-blue-50 text-blue-700 border-l-4 border-blue-500'
                        : 'text-gray-700 hover:bg-gray-50'
                    }`}
                  >
                    <span className={getStatusColor(step.status)}>
                      {getStepIcon(step.id)}
                    </span>
                    <div className="flex-1">
                      <div className="font-medium">{step.name}</div>
                      <div className="text-sm text-gray-500">{step.description}</div>
                    </div>
                  </button>
                ))}
              </nav>
            </div>
          </div>
          
          <div className="lg:col-span-3">
            <ErrorBoundary>
              <div className="bg-white rounded-lg shadow-md p-6">
                {renderStepComponent()}
              </div>
            </ErrorBoundary>
          </div>
          
          <div className="lg:col-span-4">
            <JobMonitor jobs={jobs} className="mt-6" />
          </div>
        </div>
      </div>
    </div>
  );
};

export default PipelineDashboard;