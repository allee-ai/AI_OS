// Workspace file system types

export interface WorkspaceFile {
  id: string;
  name: string;
  path: string;
  type: 'file' | 'folder';
  size?: number;
  mimeType?: string;
  createdAt: Date;
  updatedAt: Date;
  parentId?: string;
}

export interface FileUploadRequest {
  file: File;
  targetPath: string;
}

export interface FileMoveRequest {
  sourceId: string;
  targetPath: string;
}

export interface FileDeleteRequest {
  fileId: string;
}

export interface CreateFolderRequest {
  name: string;
  parentPath: string;
}

export interface WorkspaceState {
  files: WorkspaceFile[];
  currentPath: string;
  selectedFiles: string[];
  isLoading: boolean;
  error: string | null;
}

export type WorkspaceAction =
  | { type: 'SET_FILES'; payload: WorkspaceFile[] }
  | { type: 'ADD_FILE'; payload: WorkspaceFile }
  | { type: 'REMOVE_FILE'; payload: string }
  | { type: 'UPDATE_FILE'; payload: WorkspaceFile }
  | { type: 'SET_CURRENT_PATH'; payload: string }
  | { type: 'SELECT_FILE'; payload: string }
  | { type: 'DESELECT_FILE'; payload: string }
  | { type: 'CLEAR_SELECTION' }
  | { type: 'SET_LOADING'; payload: boolean }
  | { type: 'SET_ERROR'; payload: string | null };
