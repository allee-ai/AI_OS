# Conversation Search and Recovery Guide

## Overview

AI OS now includes powerful search and backup features to help you find and recover your conversations, including lost project discussions.

## Features

### 1. Conversation Search

Search through all your conversations by keywords to quickly find specific discussions.

**How to use:**
1. Open the chat interface
2. In the conversation sidebar (left panel), look for the search box
3. Type keywords to search (e.g., "python project", "machine learning", "lost code")
4. Results update automatically as you type
5. Click on any result to open that conversation

**What it searches:**
- Conversation names/titles
- User messages
- Assistant responses
- Conversation summaries

**Search tips:**
- Use specific keywords related to your project (e.g., "React component", "data analysis")
- Search for terms you remember using (e.g., "I lost", "help me build")
- Try different variations if you don't find what you're looking for

### 2. Export Conversations

Back up your conversations to protect against data loss.

**Export a single conversation:**
1. Find the conversation in the sidebar
2. Hover over it to reveal action buttons
3. Click the download/export icon (↓)
4. The conversation will be saved as a JSON file

**Export all conversations:**
1. In the conversation sidebar, click "Export All"
2. All your active conversations will be saved to a single JSON file
3. File includes conversation metadata, messages, and timestamps

**What's included in exports:**
- Session ID and conversation name
- All messages (user and assistant)
- Timestamps
- Turn count
- State snapshots

### 3. Import Conversations

Recover conversations from previous exports or VS Code Copilot chats.

**How to import:**
1. Click the "Import" button in the conversation sidebar
2. Select your export source:
   - **AI OS Export**: Previously exported JSON files
   - **VS Code Copilot**: GitHub Copilot chat sessions from VS Code
   - **ChatGPT**: OpenAI ChatGPT conversation exports
   - **Claude**: Anthropic Claude conversation exports
   - **Gemini**: Google Gemini conversation exports
3. Choose your export file or folder
4. Conversations will be imported and available in your list

### 4. Finding Lost Project Conversations

If you've lost a project and need to recover the conversations:

**Method 1: Search by project name**
```
Search: "TaskMaster project"
Search: "React dashboard"
Search: "ML model"
```

**Method 2: Search by technology**
```
Search: "Python"
Search: "TypeScript"
Search: "machine learning"
```

**Method 3: Search by context**
```
Search: "I lost"
Search: "help me build"
Search: "recreate"
```

**Method 4: Browse all conversations**
- Scroll through your conversation list
- Conversations are sorted by most recent
- Each shows a preview of the first message

## API Endpoints

For developers integrating with AI OS:

### Search Conversations
```http
GET /api/conversations?search={query}&limit={limit}&archived={false|true}
```

**Parameters:**
- `search`: Search query string (optional)
- `limit`: Maximum results (default: 50)
- `archived`: Include archived conversations (default: false)

**Example:**
```bash
curl "http://localhost:8000/api/conversations?search=python&limit=10"
```

### Export Single Conversation
```http
GET /api/conversations/{session_id}/export
```

**Returns:** JSON file download

**Example:**
```bash
curl "http://localhost:8000/api/conversations/react_20240115_143022/export" -o conversation.json
```

### Export All Conversations
```http
GET /api/conversations/export/all?archived={false|true}
```

**Parameters:**
- `archived`: Export archived conversations (default: false)

**Returns:** JSON file with all conversations

**Example:**
```bash
curl "http://localhost:8000/api/conversations/export/all" -o all_conversations.json
```

## Best Practices

### Regular Backups
- Export all conversations regularly (weekly recommended)
- Store exports in multiple locations (cloud storage, external drive)
- Name exports with dates: `ai_os_backup_2024_01_15.json`

### Organization
- Use descriptive conversation names
- Archive old conversations to keep active list manageable
- Search before starting new conversations to continue existing ones

### Recovery Strategy
If you've lost a project:
1. Search for the project name
2. Search for key technologies used
3. Search for phrases you remember using
4. Check archived conversations
5. If found, export immediately for backup

## Troubleshooting

**Search returns no results:**
- Check spelling of search terms
- Try broader keywords
- Check if conversation was archived
- Verify conversation exists in database

**Export fails:**
- Check browser console for errors
- Ensure sufficient disk space
- Try exporting individual conversations if bulk export fails

**Import fails:**
- Verify file format is correct JSON
- Check file isn't corrupted
- Ensure import source matches file format
- Review error messages for specific issues

## Technical Details

### Database Schema
Conversations are stored in SQLite with full-text search capabilities:
- `convos`: Conversation metadata
- `convo_turns`: Individual message turns

### Search Implementation
- Uses SQL LIKE queries with COLLATE NOCASE for case-insensitive search
- Searches across names, messages, and summaries
- Returns results sorted by last updated time

### Export Format
```json
{
  "version": "1.0",
  "platform": "AI_OS",
  "exported_at": "2024-01-15T14:30:22",
  "conversation": {
    "session_id": "react_20240115_143022",
    "name": "Python Data Analysis",
    "started": "2024-01-15T14:30:22",
    "turns": [
      {
        "timestamp": "2024-01-15T14:30:22",
        "user": "User message",
        "assistant": "Assistant response"
      }
    ]
  }
}
```

## Future Enhancements

Planned improvements:
- Advanced search with filters (date range, message count)
- Full-text search indexing for faster queries
- Search result highlighting
- Automatic daily backups
- Cloud sync options
- Conversation tagging and categories

## Support

If you need help:
1. Check this documentation
2. Review error messages carefully
3. Open an issue on GitHub: https://github.com/allee-ai/AI_OS/issues
4. Include: steps to reproduce, error messages, and screenshots

---

*Remember: Your conversations are valuable. Back them up regularly!*
