# VS Code Conversation Import Guide

## Quick Steps

### 1. Find Your VS Code Chats

Your VS Code GitHub Copilot conversations are stored at:
- **Empty window chats**: `~/Library/Application Support/Code/User/globalStorage/emptyWindowChatSessions/`
- **Workspace chats**: `~/Library/Application Support/Code/User/workspaceStorage/*/chatSessions/`

### 2. Using the Import Feature in Nola

1. Open Nola's chat interface
2. Click the **Import** button in the left sidebar
3. Select **VS Code Copilot** from the platform dropdown
4. Either:
   - Drag and drop a folder (it will be zipped automatically), OR
   - Click to browse and select a `.zip` file containing your chat sessions

### 3. What Gets Imported

- All conversation turns (user messages and assistant responses)
- Timestamps and metadata
- Request IDs and variable data (files referenced in chat)
- Session information

### 4. Using the Standalone Script (Alternative)

If you prefer to bulk import all conversations at once:

```bash
cd /Users/cade/Desktop/AI_OS
python3 import_vscode_conversations.py
```

This will:
- Find all VS Code chat sessions automatically
- Import all 163+ conversations to `Nola/Stimuli/conversations/`
- Generate a log file: `vscode_import_log.json`

## Archive Feature

After importing, conversations appear in your active chat list. You can:
- **Archive** old conversations to keep your main list clean
- View archived conversations by expanding the "Archive" section at the bottom
- **Unarchive** to bring conversations back to your main list

The archive is now visually separated with a clear divider for better organization.

## Supported Formats

The VS Code parser supports the native GitHub Copilot chat session format (`.json` files).
