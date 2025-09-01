export interface PipelineStep {
  id: string;
  name: string;
  description: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  inputDir?: string;
  outputDir?: string;
  config?: Record<string, any>;
}

export interface JobStatus {
  id: string;
  stepId: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  progress?: number;
  message?: string;
  startTime?: Date;
  endTime?: Date;
}

export interface FileInfo {
  path: string;
  name: string;
  type: 'file' | 'directory';
  size?: number;
  modifiedTime?: Date;
}

export interface ConformerConfig {
  smiFile: string;
  outputDir: string;
  workers: number;
  batchSize: number;
  verbose: boolean;
}

export interface OptimizeConfig {
  inputDir: string;
  gpuIds: string;
  outputDir?: string;
  fmax: number;
  steps: number;
  monitor: boolean;
}

export interface OrcaConfig {
  conformerDir: string;
  conformerType: string;
  templateFile: string;
  outputDir?: string;
  inpName?: string;
  xyzName?: string;
  additionalCharge: number;
  additionalMultiplicity: number;
}

export interface ExtractConfig {
  s1t1Results: string;
  omolPath: string;
  outputDir: string;
}

export interface OrcaExtractConfig {
  directory: string;
  outputFile: string;
  outputName?: string;
  verbose: boolean;
  excitedStates: boolean;
  socList: string[];
  regularAbsorption: boolean;
  socAbsorption: boolean;
  extractAll: boolean;
}