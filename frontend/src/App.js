import React, { useState, useEffect, useRef } from 'react';
import './App.css';

function App() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [conversationId, setConversationId] = useState(null);
  const [conversations, setConversations] = useState([]); // New state for list of conversations
  const messagesEndRef = useRef(null);

  // IMPORTANT: Ensure this user_id exists in your MySQL 'users' table.
  // In a real app, this would come from authentication.
  const USER_ID = 1; 

  // Backend API URL
  const API_BASE_URL = 'http://localhost:8000';

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // --- NEW: Fetch conversations on component mount and when new conversation starts ---
  useEffect(() => {
    fetchConversations();
  }, [conversationId]); // Re-fetch when conversationId changes (e.g., new chat session starts)

  const fetchConversations = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/users/${USER_ID}/conversations`);
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      const data = await response.json();
      setConversations(data);
    } catch (error) {
      console.error("Failed to fetch conversations:", error);
    }
  };

  // --- NEW: Load messages for a selected conversation ---
  const loadConversationMessages = async (id) => {
    setConversationId(id); // Set the current conversation ID
    setMessages([]); // Clear current messages
    try {
      const response = await fetch(`${API_BASE_URL}/conversations/${id}/messages`);
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      const data = await response.json();
      // Map API response to our local message structure
      const loadedMessages = data.map(msg => ({
        text: msg.content,
        sender: msg.sender,
        timestamp: msg.timestamp // Can use for display if desired
      }));
      setMessages(loadedMessages);
    } catch (error) {
      console.error("Failed to load conversation messages:", error);
      setMessages([{ text: "Error: Could not load conversation history.", sender: 'ai' }]);
    }
  };

  const handleSendMessage = async () => {
    if (input.trim() === '') return;

    const userMessageText = input.trim();
    setMessages((prevMessages) => [...prevMessages, { text: userMessageText, sender: 'user' }]);
    setInput('');

    setMessages((prevMessages) => [...prevMessages, { text: '...', sender: 'ai', isLoading: true }]);

    const payload = {
      user_id: USER_ID,
      message: userMessageText,
      conversation_id: conversationId,
    };

    try {
      const response = await fetch(`${API_BASE_URL}/api/chat`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      
      if (!conversationId && data.conversation_id) {
        setConversationId(data.conversation_id); // Update ID if new conversation
      }

      setMessages((prevMessages) => {
        const newMessages = prevMessages.filter(msg => !msg.isLoading);
        return [...newMessages, { text: data.ai_response, sender: 'ai' }];
      });

    } catch (error) {
      console.error("Failed to send message to backend:", error);
      setMessages((prevMessages) => {
        const newMessages = prevMessages.filter(msg => !msg.isLoading);
        return [...newMessages, { text: "Error: Could not connect to AI.", sender: 'ai' }];
      });
    }
  };

  // --- New function to start a fresh conversation ---
  const startNewConversation = () => {
    setConversationId(null); // Clear conversation ID to start new
    setMessages([]); // Clear messages
    setInput(''); // Clear input
  };

  return (
    <div className="app-container"> {/* Main container for the whole app including sidebar */}
      <div className="sidebar">
        <button className="new-chat-button" onClick={startNewConversation}>+ New Chat</button>
        <div className="conversation-list">
          <h3>Past Chats</h3>
          {conversations.length === 0 ? (
            <p className="no-chats">No past conversations.</p>
          ) : (
            <ul>
              {conversations.map((conv) => (
                <li 
                  key={conv.id} 
                  className={`conversation-item ${conv.id === conversationId ? 'active' : ''}`}
                  onClick={() => loadConversationMessages(conv.id)}
                >
                  <div className="conversation-title">{conv.title || `Chat ${conv.id}`}</div>
                  <div className="conversation-time">
                    {conv.start_time ? new Date(conv.start_time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : 'N/A'}
                  </div>
                  {/* Potentially add snippet of first message here */}
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>

      <div className="chat-container"> {/* Existing chat container */}
        <header className="chat-header">
          <h1>AI Assistant</h1>
          {conversationId && <span className="conversation-status">Conversation ID: {conversationId}</span>}
        </header>
        <div className="message-list">
          {messages.map((msg, index) => (
            <div key={index} className={`message-item ${msg.sender} ${msg.isLoading ? 'loading' : ''}`}>
              {msg.text}
            </div>
          ))}
          <div ref={messagesEndRef} />
        </div>
        <div className="chat-input-area">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyPress={(e) => {
              if (e.key === 'Enter') {
                handleSendMessage();
              }
            }}
            placeholder="Type your message..."
          />
          <button onClick={handleSendMessage}>Send</button>
        </div>
      </div>
    </div>
  );
}

export default App;