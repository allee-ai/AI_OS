import React, { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import type { ChatMessage } from '../../types/chat';
import './MessageList.css';

interface MessageListProps {
  messages: ChatMessage[];
  isAgentTyping?: boolean;
  conversationId?: string;
}

// Track which messages have been rated
const ratedMessages = new Set<string>();

export const MessageList: React.FC<MessageListProps> = ({ 
  messages, 
  isAgentTyping = false,
  conversationId
}) => {
  const messagesEndRef = React.useRef<HTMLDivElement>(null);
  const [ratings, setRatings] = useState<Record<string, 'up' | 'down'>>({});
  const [ratingInProgress, setRatingInProgress] = useState<string | null>(null);
  const [feedbackOpen, setFeedbackOpen] = useState<string | null>(null);
  const [feedbackText, setFeedbackText] = useState('');
  const [pendingDownvote, setPendingDownvote] = useState<{message: ChatMessage, index: number} | null>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  React.useEffect(() => {
    scrollToBottom();
  }, [messages, isAgentTyping]);

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
        {messages.length === 0 && !isAgentTyping && (
          <div className="empty-state">
            <div className="empty-icon">👋</div>
            <h3>Welcome!</h3>
            <p>Start a conversation with Nola. Try saying:</p>
            <div className="suggestion-chips">
              <span className="chip">"Hi Nola!"</span>
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
                  <ReactMarkdown 
                    remarkPlugins={[remarkGfm]}
                    components={{
                      code({ className, children, ...props }) {
                        const isInline = !className;
                        return isInline ? (
                          <code className="inline-code" {...props}>{children}</code>
                        ) : (
                          <pre className="code-block">
                            <code className={className} {...props}>{children}</code>
                          </pre>
                        );
                      }
                    }}
                  >
                    {message.content}
                  </ReactMarkdown>
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