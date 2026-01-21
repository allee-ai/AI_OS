import { useReducer, useCallback, useEffect } from 'react';
import type { WorkspaceState, WorkspaceAction, WorkspaceFile } from '../types/workspace';
import { workspaceApi } from '../services/workspaceApi';

// Mock files for when backend isn't available
const MOCK_FILES: WorkspaceFile[] = [
  {
    id: '1',
    name: 'Stimuli',
    path: '/Stimuli',
    type: 'folder',
    createdAt: new Date(),
    updatedAt: new Date(),
  },
  {
    id: '2',
    name: 'identity_thread',
    path: '/identity_thread',
    type: 'folder',
    createdAt: new Date(),
    updatedAt: new Date(),
  },
  {
    id: '3',
    name: 'Nola.json',
    path: '/Nola.json',
    type: 'file',
    size: 4096,
    mimeType: 'application/json',
    createdAt: new Date(),
    updatedAt: new Date(),
  },
];

const initialState: WorkspaceState = {
  files: [],
  currentPath: '/',
  selectedFiles: [],
  isLoading: false,
  error: null,
};

function workspaceReducer(state: WorkspaceState, action: WorkspaceAction): WorkspaceState {
  switch (action.type) {
    case 'SET_FILES':
      return { ...state, files: action.payload, isLoading: false };
    case 'ADD_FILE':
      return { ...state, files: [...state.files, action.payload] };
    case 'REMOVE_FILE':
      return { ...state, files: state.files.filter(f => f.id !== action.payload) };
    case 'UPDATE_FILE':
      return {
        ...state,
        files: state.files.map(f => f.id === action.payload.id ? action.payload : f),
      };
    case 'SET_CURRENT_PATH':
      return { ...state, currentPath: action.payload, selectedFiles: [] };
    case 'SELECT_FILE':
      return {
        ...state,
        selectedFiles: state.selectedFiles.includes(action.payload)
          ? state.selectedFiles
          : [...state.selectedFiles, action.payload],
      };
    case 'DESELECT_FILE':
      return {
        ...state,
        selectedFiles: state.selectedFiles.filter(id => id !== action.payload),
      };
    case 'CLEAR_SELECTION':
      return { ...state, selectedFiles: [] };
    case 'SET_LOADING':
      return { ...state, isLoading: action.payload };
    case 'SET_ERROR':
      return { ...state, error: action.payload, isLoading: false };
    default:
      return state;
  }
}

export function useWorkspace() {
  const [state, dispatch] = useReducer(workspaceReducer, initialState);

  // Load files for current path
  const loadFiles = useCallback(async (path?: string) => {
    const targetPath = path ?? state.currentPath;
    dispatch({ type: 'SET_LOADING', payload: true });
    dispatch({ type: 'SET_ERROR', payload: null });

    try {
      const files = await workspaceApi.listFiles(targetPath);
      dispatch({ type: 'SET_FILES', payload: files });
      if (path) {
        dispatch({ type: 'SET_CURRENT_PATH', payload: path });
      }
    } catch (error) {
      // Use mock files when API isn't available
      console.warn('Workspace API unavailable, using mock data');
      dispatch({ type: 'SET_FILES', payload: MOCK_FILES });
      if (path) {
        dispatch({ type: 'SET_CURRENT_PATH', payload: path });
      }
    }
  }, [state.currentPath]);

  // Navigate to a folder
  const navigateTo = useCallback((path: string) => {
    loadFiles(path);
  }, [loadFiles]);

  // Go up one directory
  const navigateUp = useCallback(() => {
    if (state.currentPath === '/') return;
    const parentPath = state.currentPath.split('/').slice(0, -1).join('/') || '/';
    navigateTo(parentPath);
  }, [state.currentPath, navigateTo]);

  // Upload files
  const uploadFiles = useCallback(async (files: FileList) => {
    dispatch({ type: 'SET_LOADING', payload: true });
    dispatch({ type: 'SET_ERROR', payload: null });

    try {
      for (const file of Array.from(files)) {
        const uploadedFile = await workspaceApi.uploadFile({
          file,
          targetPath: state.currentPath,
        });
        dispatch({ type: 'ADD_FILE', payload: uploadedFile });
      }
    } catch (error) {
      dispatch({ type: 'SET_ERROR', payload: (error as Error).message });
    } finally {
      dispatch({ type: 'SET_LOADING', payload: false });
    }
  }, [state.currentPath]);

  // Move file
  const moveFile = useCallback(async (sourceId: string, targetPath: string) => {
    dispatch({ type: 'SET_LOADING', payload: true });
    dispatch({ type: 'SET_ERROR', payload: null });

    try {
      const movedFile = await workspaceApi.moveFile({ sourceId, targetPath });
      dispatch({ type: 'UPDATE_FILE', payload: movedFile });
      // Reload to get fresh state
      await loadFiles();
    } catch (error) {
      dispatch({ type: 'SET_ERROR', payload: (error as Error).message });
    }
  }, [loadFiles]);

  // Delete file
  const deleteFile = useCallback(async (fileId: string, filePath?: string) => {
    dispatch({ type: 'SET_LOADING', payload: true });
    dispatch({ type: 'SET_ERROR', payload: null });

    try {
      await workspaceApi.deleteFile(fileId, filePath);
      dispatch({ type: 'REMOVE_FILE', payload: fileId });
    } catch (error) {
      dispatch({ type: 'SET_ERROR', payload: (error as Error).message });
    } finally {
      dispatch({ type: 'SET_LOADING', payload: false });
    }
  }, []);

  // Create folder
  const createFolder = useCallback(async (name: string) => {
    dispatch({ type: 'SET_LOADING', payload: true });
    dispatch({ type: 'SET_ERROR', payload: null });

    try {
      const folder = await workspaceApi.createFolder({
        name,
        parentPath: state.currentPath,
      });
      dispatch({ type: 'ADD_FILE', payload: folder });
    } catch (error) {
      dispatch({ type: 'SET_ERROR', payload: (error as Error).message });
    } finally {
      dispatch({ type: 'SET_LOADING', payload: false });
    }
  }, [state.currentPath]);

  // Download file
  const downloadFile = useCallback(async (file: WorkspaceFile) => {
    try {
      const blob = await workspaceApi.downloadFile(file.id, file.path);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = file.name;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (error) {
      dispatch({ type: 'SET_ERROR', payload: (error as Error).message });
    }
  }, []);

  // Selection helpers
  const selectFile = useCallback((fileId: string) => {
    dispatch({ type: 'SELECT_FILE', payload: fileId });
  }, []);

  const deselectFile = useCallback((fileId: string) => {
    dispatch({ type: 'DESELECT_FILE', payload: fileId });
  }, []);

  const clearSelection = useCallback(() => {
    dispatch({ type: 'CLEAR_SELECTION' });
  }, []);

  const toggleSelect = useCallback((fileId: string) => {
    if (state.selectedFiles.includes(fileId)) {
      deselectFile(fileId);
    } else {
      selectFile(fileId);
    }
  }, [state.selectedFiles, selectFile, deselectFile]);

  // Load files on mount
  useEffect(() => {
    loadFiles();
  }, []);

  return {
    ...state,
    loadFiles,
    navigateTo,
    navigateUp,
    uploadFiles,
    moveFile,
    deleteFile,
    createFolder,
    downloadFile,
    selectFile,
    deselectFile,
    clearSelection,
    toggleSelect,
  };
}
