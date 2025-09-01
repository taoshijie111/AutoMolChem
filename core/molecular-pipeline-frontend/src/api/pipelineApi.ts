import axios from 'axios';
import { ConformerConfig, OptimizeConfig, OrcaConfig, ExtractConfig, OrcaExtractConfig } from '../types';

const API_BASE = 'http://localhost:3001/api';

export const pipelineApi = {
  generateConformers: async (config: ConformerConfig) => {
    const response = await axios.post(`${API_BASE}/conformer/generate`, config);
    return response.data;
  },

  optimizeMultiGpu: async (config: OptimizeConfig) => {
    const response = await axios.post(`${API_BASE}/optimize/multi-gpu`, config);
    return response.data;
  },

  getOptimizationProgress: async (directory: string, optType = 'omol_opt') => {
    const response = await axios.get(`${API_BASE}/optimization/progress`, {
      params: { directory, optType }
    });
    return response.data;
  },

  prepareOrca: async (config: OrcaConfig) => {
    const response = await axios.post(`${API_BASE}/orca/prepare`, config);
    return response.data;
  },

  extractMolecules: async (config: ExtractConfig) => {
    const response = await axios.post(`${API_BASE}/extract/molecules`, config);
    return response.data;
  },

  submitOrcaBatch: async (config: {
    mainDirectory: string;
    totalCores: number;
    coresPerTask: number;
    inpName?: string;
    forceNotSkip?: boolean;
  }) => {
    const response = await axios.post(`${API_BASE}/orca/submit`, config);
    return response.data;
  },

  extractOrcaResults: async (config: OrcaExtractConfig) => {
    const response = await axios.post(`${API_BASE}/orca/extract`, config);
    return response.data;
  }
};