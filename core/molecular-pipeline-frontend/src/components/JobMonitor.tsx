import React, { useState } from 'react';
import { Clock, CheckCircle, XCircle, Play, ChevronDown, ChevronRight } from 'lucide-react';
import { JobStatus } from '../types';

interface JobMonitorProps {
  jobs: JobStatus[];
  className?: string;
}

const JobMonitor: React.FC<JobMonitorProps> = ({ jobs, className }) => {
  const [expandedJobs, setExpandedJobs] = useState<Set<string>>(new Set());

  const toggleJobExpansion = (jobId: string) => {
    const newExpanded = new Set(expandedJobs);
    if (newExpanded.has(jobId)) {
      newExpanded.delete(jobId);
    } else {
      newExpanded.add(jobId);
    }
    setExpandedJobs(newExpanded);
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'completed': return <CheckCircle className="w-4 h-4 text-green-600" />;
      case 'running': return <Play className="w-4 h-4 text-blue-600" />;
      case 'failed': return <XCircle className="w-4 h-4 text-red-600" />;
      default: return <Clock className="w-4 h-4 text-gray-600" />;
    }
  };

  const formatTime = (date?: Date) => {
    if (!date) return '';
    return date.toLocaleTimeString();
  };

  return (
    <div className={`bg-white rounded-lg shadow-md p-4 ${className || ''}`}>
      <h3 className="text-lg font-semibold mb-3">Job Monitor</h3>
      
      {jobs.length === 0 ? (
        <p className="text-gray-500 text-sm">No active jobs</p>
      ) : (
        <div className="space-y-2 max-h-96 overflow-y-auto">
          {jobs.map((job) => {
            const isExpanded = expandedJobs.has(job.id);
            const hasLongMessage = job.message && job.message.length > 60;
            
            return (
              <div key={job.id} className="border rounded">
                <div className="flex items-center space-x-3 p-2">
                  {getStatusIcon(job.status)}
                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-medium truncate">{job.stepId}</div>
                    {job.message && (
                      <div className={`text-xs ${job.status === 'failed' ? 'text-red-600' : 'text-gray-500'} ${!isExpanded && hasLongMessage ? 'truncate' : 'whitespace-pre-wrap'}`}>
                        {job.message}
                      </div>
                    )}
                    {job.progress && (
                      <div className="w-full bg-gray-200 rounded-full h-1 mt-1">
                        <div 
                          className="bg-blue-600 h-1 rounded-full" 
                          style={{ width: `${job.progress}%` }}
                        />
                      </div>
                    )}
                  </div>
                  <div className="text-xs text-gray-500">
                    {formatTime(job.startTime)}
                  </div>
                  {hasLongMessage && (
                    <button
                      onClick={() => toggleJobExpansion(job.id)}
                      className="p-1 hover:bg-gray-100 rounded"
                    >
                      {isExpanded ? 
                        <ChevronDown className="w-4 h-4 text-gray-600" /> : 
                        <ChevronRight className="w-4 h-4 text-gray-600" />
                      }
                    </button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};

export default JobMonitor;