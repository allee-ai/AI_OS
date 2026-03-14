import React, { useState, useMemo } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import type { ChatMessage } from '../types/chat';
import './MessageList.css';

/* ── Tool block rendering ────────────────────────────────────────── */

interface ContentSegment {
  type: 'text' | 'execute' | 'result';
  content: string;
  meta?: Record<string, string>;  // parsed key:value for execute blocks
}

/**
 * Split assistant message content into segments: plain text, :::execute blocks,
 * and :::result blocks.  This lets us render each with its own component while
 * leaving the rest of the message to ReactMarkdown.
 */
function parseToolBlocks(raw: string): ContentSegment[] {
  const BLOCK_RE = /:::(execute|result)\s*\n([\s\S]*?):::/g;
  const segments: ContentSegment[] = [];
  let cursor = 0;

  for (const match of raw.matchAll(BLOCK_RE)) {
    const start = match.index!;
    // push preceding text
    if (start > cursor) {
      segments.push({ type: 'text', content: raw.slice(cursor, start) });
    }

    const kind = match[1] as 'execute' | 'result';
    const body = match[2].trim();

    if (kind === 'execute') {
      const meta: Record<string, string> = {};
      for (const line of body.split('\n')) {
        const idx = line.indexOf(':');
        if (idx > 0) {
          meta[line.slice(0, idx).trim().toLowerCase()] = line.slice(idx + 1).trim();
        }
      }
      segments.push({ type: 'execute', content: body, meta });
    } else {
      segments.push({ type: 'result', content: body });
    }

    cursor = start + match[0].length;
  }

  // trailing text
  if (cursor < raw.length) {
    segments.push({ type: 'text', content: raw.slice(cursor) });
  }

  return segments;
}

const ToolCallBlock: React.FC<{ meta?: Record<string, string> }> = ({ meta }) => (
  <div className="tool-call">
    <div className="tool-call-header">
      <span className="tool-call-icon">⚡</span>
      <span className="tool-call-label">
        {meta?.tool ?? 'tool'}<span className="tool-call-action">.{meta?.action ?? 'run'}</span>
      </span>
    </div>
    {meta && Object.keys(meta).filter(k => k !== 'tool' && k !== 'action').length > 0 && (
      <div className="tool-call-params">
        {Object.entries(meta)
          .filter(([k]) => k !== 'tool' && k !== 'action')
          .map(([k, v]) => (
            <div key={k} className="tool-param">
              <span className="tool-param-key">{k}</span>
              <span className="tool-param-val">{v}</span>
            </div>
          ))}
      </div>
    )}
  </div>
);

const ToolResultBlock: React.FC<{ content: string }> = ({ content }) => (
  <div className="tool-result">
    <div className="tool-result-header">
      <span className="tool-result-icon">✓</span>
      <span className="tool-result-label">Result</span>
    </div>
    <pre className="tool-result-body">{content}</pre>
  </div>
);

const markdownComponents = {
  code({ className, children, ...props }: any) {
    const isInline = !className;
    return isInline ? (
      <code className="inline-code" {...props}>{children}</code>
    ) : (
      <pre className="code-block">
        <code className={className} {...props}>{children}</code>
      </pre>
    );
  }
};

const AssistantContent: React.FC<{ content: string }> = ({ content }) => {
  const segments = useMemo(() => parseToolBlocks(content), [content]);
  const hasToolBlocks = segments.some(s => s.type !== 'text');

  if (!hasToolBlocks) {
    return (
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>
        {content}
      </ReactMarkdown>
    );
  }

  return (
    <>
      {segments.map((seg, i) => {
        switch (seg.type) {
          case 'execute':
            return <ToolCallBlock key={i} meta={seg.meta} />;
          case 'result':
            return <ToolResultBlock key={i} content={seg.content} />;
          default:
            return seg.content.trim() ? (
              <ReactMarkdown key={i} remarkPlugins={[remarkGfm]} components={markdownComponents}>
                {seg.content}
              </ReactMarkdown>
            ) : null;
        }
      })}
    </>
  );
};

interface MessageListProps {
  messages: ChatMessage[];
  isAgentTyping?: boolean;
  conversationId?: string;
  hasMore?: boolean;
  onLoadMore?: () => void;
}

// Track which messages have been rated
const ratedMessages = new Set<string>();

export const MessageList: React.FC<MessageListProps> = ({ 
  messages, 
  isAgentTyping = false,
  conversationId,
  hasMore = false,
  onLoadMore
}) => {
  const messagesEndRef = React.useRef<HTMLDivElement>(null);
  const prevMessageCountRef = React.useRef(0);
  const [ratings, setRatings] = useState<Record<string, 'up' | 'down'>>({});
  const [ratingInProgress, setRatingInProgress] = useState<string | null>(null);
  const [feedbackOpen, setFeedbackOpen] = useState<string | null>(null);
  const [feedbackText, setFeedbackText] = useState('');
  const [pendingDownvote, setPendingDownvote] = useState<{message: ChatMessage, index: number} | null>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  React.useEffect(() => {
    const prevCount = prevMessageCountRef.current;
    const newCount = messages.length;
    // Only auto-scroll if messages were appended (new message at end), not prepended (load older)
    if (newCount > prevCount && prevCount > 0) {
      // Check if the last message changed (new message was appended)
      scrollToBottom();
    } else if (prevCount === 0 && newCount > 0) {
      // Initial load — scroll to bottom
      scrollToBottom();
    }
    prevMessageCountRef.current = newCount;
  }, [messages]);

  React.useEffect(() => {
    if (isAgentTyping) scrollToBottom();
  }, [isAgentTyping]);

  const formatTime = (timestamp: Date) => {
    return new Intl.DateTimeFormat('en-US', {
      hour: '2-digit',
      minute: '2-digit'
    }).format(timestamp);
  };

  // Find the user message that preceded an assistant message
  const findPrecedingUserMessage = (assistantIndex: number): string | null => {
    for (let i = assistantIndex - 1; i >= 0; i--) {
      if (messages[i].role === 'user') {
        return messages[i].content;
      }
    }
    return null;
  };

  const handleRate = async (message: ChatMessage, messageIndex: number, rating: 'up' | 'down', reason?: string) => {
    if (ratingInProgress || ratings[message.id]) return;
    
    setRatingInProgress(message.id);
    
    const userMessage = findPrecedingUserMessage(messageIndex);
    if (!userMessage) {
      console.error('Could not find preceding user message');
      setRatingInProgress(null);
      return;
    }

    try {
      const response = await fetch('/api/ratings/rate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message_id: message.id,
          conversation_id: conversationId || 'unknown',
          rating,
          user_message: userMessage,
          assistant_message: message.content,
          reason: reason || undefined
        })
      });

      if (response.ok) {
        setRatings(prev => ({ ...prev, [message.id]: rating }));
        ratedMessages.add(message.id);
      }
    } catch (error) {
      console.error('Failed to rate message:', error);
    } finally {
      setRatingInProgress(null);
    }
  };

  const handleThumbsDown = (message: ChatMessage, index: number) => {
    setPendingDownvote({ message, index });
    setFeedbackOpen(message.id);
    setFeedbackText('');
  };

  const submitFeedback = () => {
    if (pendingDownvote) {
      handleRate(pendingDownvote.message, pendingDownvote.index, 'down', feedbackText);
      setFeedbackOpen(null);
      setPendingDownvote(null);
      setFeedbackText('');
    }
  };

  const cancelFeedback = () => {
    setFeedbackOpen(null);
    setPendingDownvote(null);
    setFeedbackText('');
  };

  return (
    <div className="message-list">
      <div className="messages-container">
        {hasMore && onLoadMore && (
          <div className="load-more-container">
            <button className="load-more-btn" onClick={onLoadMore}>
              Load older messages
            </button>
          </div>
        )}

        {messages.length === 0 && !isAgentTyping && (
          <div className="empty-state">
            <div className="empty-icon">👋</div>
            <h3>Welcome!</h3>
            <p>Start a conversation. Try saying:</p>
            <div className="suggestion-chips">
              <span className="chip">"Hello!"</span>
              <span className="chip">"How can you help me?"</span>
              <span className="chip">"Tell me about yourself"</span>
            </div>
          </div>
        )}
        
        {messages.map((message, index) => (
          <div
            key={message.id}
            className={`message ${message.role === 'user' ? 'user-message' : 'assistant-message'}`}
          >
            <div className="message-content">
              <div className="message-text">
                {message.role === 'assistant' ? (
                  <AssistantContent content={message.content} />
                ) : (
                  message.content
                )}
              </div>
              <div className="message-footer">
                <div className="message-timestamp">
                  {formatTime(message.timestamp)}
                </div>
                {message.role === 'assistant' && (
                  <div className="rating-buttons">
                    <button
                      className={`rating-btn ${ratings[message.id] === 'up' ? 'rated-up' : ''}`}
                      onClick={() => handleRate(message, index, 'up')}
                      disabled={!!ratings[message.id] || ratingInProgress === message.id}
                      title="Good response - save for training"
                    >
                      👍
                    </button>
                    <button
                      className={`rating-btn ${ratings[message.id] === 'down' ? 'rated-down' : ''}`}
                      onClick={() => handleThumbsDown(message, index)}
                      disabled={!!ratings[message.id] || ratingInProgress === message.id}
                      title="Not helpful"
                    >
                      👎
                    </button>
                  </div>
                )}
              </div>
              {feedbackOpen === message.id && (
                <div className="feedback-form">
                  <textarea
                    className="feedback-input"
                    placeholder="What was wrong with this response?"
                    value={feedbackText}
                    onChange={(e) => setFeedbackText(e.target.value)}
                    autoFocus
                  />
                  <div className="feedback-actions">
                    <button className="feedback-btn cancel" onClick={cancelFeedback}>
                      Cancel
                    </button>
                    <button className="feedback-btn submit" onClick={submitFeedback}>
                      Submit
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>
        ))}
        
        {isAgentTyping && (
          <div className="message assistant-message">
            <div className="message-content">
              <div className="typing-indicator">
                <div className="typing-dot"></div>
                <div className="typing-dot"></div>
                <div className="typing-dot"></div>
              </div>
            </div>
          </div>
        )}
        
        <div ref={messagesEndRef} />
      </div>
    </div>
  );
};