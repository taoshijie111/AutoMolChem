import React, { useState, useEffect } from 'react';
import { X, Folder, File, ArrowLeft, Home } from 'lucide-react';
import { FileInfo } from '../types';

interface FileManagerProps {
  onSelect: (path: string) => void;
  onClose: () => void;
  allowFiles?: boolean;
  allowDirectories?: boolean;
  initialPath?: string;
}

const FileManager: React.FC<FileManagerProps> = ({ 
  onSelect, 
  onClose, 
  allowFiles = true, 
  allowDirectories = true,
  initialPath = '/home/user/data/OMol25/AutoOpt/core'
}) => {
  const [currentPath, setCurrentPath] = useState(initialPath);
  const [files, setFiles] = useState<FileInfo[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    let mounted = true;
    loadDirectory(currentPath).finally(() => {
      if (!mounted) setLoading(false);
    });
    return () => { mounted = false; };
  }, [currentPath]);

  const loadDirectory = async (path: string) => {
    setLoading(true);
    try {
      const response = await fetch(`/api/files/list?path=${encodeURIComponent(path)}`);
      if (response.ok) {
        const data = await response.json();
        setFiles(data.files || []);
      } else {
        setFiles([]);
      }
    } catch (error) {
      setFiles([]);
    } finally {
      setLoading(false);
    }
  };

  const handleItemClick = (item: FileInfo) => {
    if (item.type === 'directory') {
      setCurrentPath(item.path);
    } else if (allowFiles && item.type === 'file') {
      onSelect(item.path);
    }
  };

  const canSelect = (item: FileInfo) => {
    if (item.type === 'directory' && allowDirectories) return true;
    if (item.type === 'file' && allowFiles) return true;
    return false;
  };

  const navigateUp = () => {
    if (currentPath === '/') return;
    const pathParts = currentPath.split('/').filter(Boolean);
    const parentPath = pathParts.length > 1 ? '/' + pathParts.slice(0, -1).join('/') : '/';
    setCurrentPath(parentPath);
  };

  const navigateHome = () => {
    setCurrentPath(initialPath);
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-xl w-full max-w-4xl h-3/4 flex flex-col">
        <div className="flex items-center justify-between p-4 border-b">
          <div className="flex items-center space-x-2">
            <h3 className="text-lg font-semibold">File Manager</h3>
            <span className="text-sm text-gray-500">
              {allowFiles && allowDirectories ? 'Select file or directory' : 
               allowFiles ? 'Select file' : 'Select directory'}
            </span>
          </div>
          <button
            onClick={onClose}
            className="text-gray-500 hover:text-gray-700"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="flex items-center space-x-2 p-4 bg-gray-50 border-b">
          <button
            onClick={navigateHome}
            className="p-1 hover:bg-gray-200 rounded"
            title="Go to home"
          >
            <Home className="w-4 h-4" />
          </button>
          <button
            onClick={navigateUp}
            className="p-1 hover:bg-gray-200 rounded"
            title="Go up one level"
          >
            <ArrowLeft className="w-4 h-4" />
          </button>
          <span className="text-sm text-gray-600 font-mono">{currentPath}</span>
        </div>

        <div className="flex-1 overflow-auto p-4">
          {loading ? (
            <div className="flex justify-center items-center h-32">
              <div className="text-gray-500">Loading...</div>
            </div>
          ) : (
            <div className="grid gap-2">
              {files.map((file) => (
                <div
                  key={file.path}
                  onClick={() => handleItemClick(file)}
                  className={`flex items-center space-x-3 p-3 rounded-md cursor-pointer border ${
                    canSelect(file) 
                      ? 'hover:bg-blue-50 hover:border-blue-300 border-gray-200' 
                      : 'opacity-50 cursor-not-allowed border-gray-100'
                  }`}
                >
                  {file.type === 'directory' ? (
                    <Folder className="w-5 h-5 text-blue-500" />
                  ) : (
                    <File className="w-5 h-5 text-gray-500" />
                  )}
                  <div className="flex-1">
                    <div className="font-medium">{file.name}</div>
                    {file.size && (
                      <div className="text-xs text-gray-500">
                        {(file.size / 1024).toFixed(1)} KB
                      </div>
                    )}
                  </div>
                  {canSelect(file) && allowDirectories && file.type === 'directory' && (
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        onSelect(file.path);
                      }}
                      className="bg-blue-600 text-white px-3 py-1 rounded text-sm hover:bg-blue-700"
                    >
                      Select
                    </button>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="flex justify-end space-x-2 p-4 border-t bg-gray-50">
          <button
            onClick={onClose}
            className="px-4 py-2 text-gray-700 border border-gray-300 rounded-md hover:bg-gray-50"
          >
            Cancel
          </button>
          {allowDirectories && (
            <button
              onClick={() => onSelect(currentPath)}
              className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700"
            >
              Select Current Directory
            </button>
          )}
        </div>
      </div>
    </div>
  );
};

export default FileManager;