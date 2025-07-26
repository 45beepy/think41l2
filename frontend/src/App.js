import React, { useState, useEffect, useRef } from 'react';
import './App.css';

function App() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [conversationId, setConversationId] = useState(null);
  const messagesEndRef = useRef(null);

  const USER_ID = 1; 

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

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
      const response = await fetch('http://localhost:8000/api/chat', {
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
        setConversationId(data.conversation_id);
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

  return (
    <div className="chat-container">
      <header className="chat-header">
        <h1>AI Assistant</h1>
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
  );
}

export default App;