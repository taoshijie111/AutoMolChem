import axios from 'axios';
import { FileInfo } from '../types';

const API_BASE = 'http://localhost:3001/api';

export const fileApi = {
  listFiles: async (path: string): Promise<{ files: FileInfo[] }> => {
    const response = await axios.get(`${API_BASE}/files/list`, {
      params: { path }
    });
    return response.data;
  },

  uploadFile: async (file: File, targetPath: string) => {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('targetPath', targetPath);
    
    const response = await axios.post(`${API_BASE}/files/upload`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    });
    return response.data;
  },

  createDirectory: async (path: string) => {
    const response = await axios.post(`${API_BASE}/files/mkdir`, { path });
    return response.data;
  }
};