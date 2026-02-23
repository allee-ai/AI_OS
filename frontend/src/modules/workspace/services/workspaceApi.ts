import type { 
  WorkspaceFile, 
  FileUploadRequest, 
  FileMoveRequest,
  CreateFolderRequest,
  FileMeta,
  SearchResult,
} from '../types/workspace';
import { API_CONFIG } from '../utils/constants';

class WorkspaceAPIService {
  private baseUrl: string;

  constructor() {
    this.baseUrl = API_CONFIG.BASE_URL;
  }

  /**
   * List files in a directory
   */
  async listFiles(path: string = '/'): Promise<WorkspaceFile[]> {
    const response = await fetch(
      `${this.baseUrl}/api/workspace/files?path=${encodeURIComponent(path)}`
    );

    if (!response.ok) {
      throw new Error(`Failed to list files: ${response.status}`);
    }

    const data = await response.json();
    return data.map((file: any) => ({
      ...file,
      createdAt: new Date(file.createdAt),
      updatedAt: new Date(file.updatedAt),
    }));
  }

  /**
   * Upload a file to the workspace
   */
  async uploadFile(request: FileUploadRequest): Promise<WorkspaceFile> {
    const formData = new FormData();
    formData.append('file', request.file);
    formData.append('targetPath', request.targetPath);

    const response = await fetch(`${this.baseUrl}/api/workspace/upload`, {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) {
      throw new Error(`Failed to upload file: ${response.status}`);
    }

    const data = await response.json();
    return {
      ...data,
      createdAt: new Date(data.createdAt),
      updatedAt: new Date(data.updatedAt),
    };
  }

  /**
   * Move or rename a file
   */
  async moveFile(request: FileMoveRequest): Promise<WorkspaceFile> {
    const response = await fetch(`${this.baseUrl}/api/workspace/move`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(request),
    });

    if (!response.ok) {
      throw new Error(`Failed to move file: ${response.status}`);
    }

    const data = await response.json();
    return {
      ...data,
      createdAt: new Date(data.createdAt),
      updatedAt: new Date(data.updatedAt),
    };
  }

  /**
   * Delete a file or folder
   */
  async deleteFile(fileId: string, path?: string): Promise<void> {
    // Use path-based delete if path provided
    const url = path 
      ? `${this.baseUrl}/api/workspace/delete?path=${encodeURIComponent(path)}`
      : `${this.baseUrl}/api/workspace/files/${fileId}`;
    
    const response = await fetch(url, {
      method: 'DELETE',
    });

    if (!response.ok) {
      throw new Error(`Failed to delete file: ${response.status}`);
    }
  }

  /**
   * Create a new folder
   */
  async createFolder(request: CreateFolderRequest): Promise<WorkspaceFile> {
    const response = await fetch(`${this.baseUrl}/api/workspace/folder`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(request),
    });

    if (!response.ok) {
      throw new Error(`Failed to create folder: ${response.status}`);
    }

    const data = await response.json();
    return {
      ...data,
      createdAt: new Date(data.createdAt),
      updatedAt: new Date(data.updatedAt),
    };
  }

  /**
   * Download a file
   */
  async downloadFile(fileId: string, path: string): Promise<Blob> {
    const response = await fetch(
      `${this.baseUrl}/api/workspace/download/${fileId}?path=${encodeURIComponent(path)}`
    );

    if (!response.ok) {
      throw new Error(`Failed to download file: ${response.status}`);
    }

    return response.blob();
  }

  /**
   * Get file metadata + text content + summary as JSON
   */
  async getFileMeta(path: string): Promise<FileMeta> {
    const response = await fetch(
      `${this.baseUrl}/api/workspace/file/meta?path=${encodeURIComponent(path)}`
    );
    if (!response.ok) {
      throw new Error(`Failed to get file meta: ${response.status}`);
    }
    return response.json();
  }

  /**
   * Summarize a file using the LLM
   */
  async summarizeFile(path: string): Promise<string> {
    const response = await fetch(
      `${this.baseUrl}/api/workspace/summarize?path=${encodeURIComponent(path)}`,
      { method: 'POST' }
    );
    if (!response.ok) {
      throw new Error(`Failed to summarize file: ${response.status}`);
    }
    const data = await response.json();
    return data.summary;
  }

  /**
   * Full-text search across workspace files
   */
  async searchFiles(query: string, limit: number = 20): Promise<SearchResult[]> {
    const response = await fetch(
      `${this.baseUrl}/api/workspace/search?q=${encodeURIComponent(query)}&limit=${limit}`
    );
    if (!response.ok) {
      throw new Error(`Search failed: ${response.status}`);
    }
    return response.json();
  }

  /**
   * Get raw file content as a blob (for images, downloads)
   */
  async getFileBlob(path: string): Promise<Blob> {
    const response = await fetch(
      `${this.baseUrl}/api/workspace/file?path=${encodeURIComponent(path)}`
    );
    if (!response.ok) {
      throw new Error(`Failed to get file: ${response.status}`);
    }
    return response.blob();
  }
}

export const workspaceApi = new WorkspaceAPIService();
