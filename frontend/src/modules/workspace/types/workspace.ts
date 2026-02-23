// Workspace file system types

export interface WorkspaceFile {
  id: string;
  name: string;
  path: string;
  type: 'file' | 'folder';
  size?: number;
  mimeType?: string;
  summary?: string | null;
  createdAt: Date;
  updatedAt: Date;
  parentId?: string;
}

/** JSON response from GET /api/workspace/file/meta */
export interface FileMeta {
  path: string;
  name: string;
  is_folder: boolean;
  mime_type: string | null;
  size: number;
  hash: string | null;
  created_at: string;
  modified_at: string;
  summary: string | null;
  content: string | null;
  is_image?: boolean;
}

export interface SearchResult {
  path: string;
  name: string;
  mime_type: string | null;
  size: number;
  snippet: string | null;
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
  /** Currently open file in the viewer */
  openFile: FileMeta | null;
  openFileLoading: boolean;
  /** Search */
  searchQuery: string;
  searchResults: SearchResult[];
  searchLoading: boolean;
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
  | { type: 'SET_ERROR'; payload: string | null }
  | { type: 'SET_OPEN_FILE'; payload: FileMeta | null }
  | { type: 'SET_OPEN_FILE_LOADING'; payload: boolean }
  | { type: 'SET_SEARCH_QUERY'; payload: string }
  | { type: 'SET_SEARCH_RESULTS'; payload: SearchResult[] }
  | { type: 'SET_SEARCH_LOADING'; payload: boolean }
  | { type: 'UPDATE_FILE_SUMMARY'; payload: { path: string; summary: string } };
