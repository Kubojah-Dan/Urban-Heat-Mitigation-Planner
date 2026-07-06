import React, { useState, useRef, useEffect } from 'react';
import { Send, Sparkles, X, Bot, User } from 'lucide-react';

export default function AIChatModal({ onClose, selectedWardName, selectedCityName }) {
  const [messages, setMessages] = useState([
    {
      id: 'welcome',
      sender: 'assistant',
      text: `Greetings! I am the **UrbanCool AI Advisor**. \n\nI can assist you in evaluating thermodynamic simulations, designing urban canopy grids, selecting cooling species (like Neem or Karanj), and planning reflective cool roofs for **${selectedCityName || 'Ahmedabad'}**.\n\nAsk me any scientific questions about microclimatic mitigation!`,
      timestamp: new Date().toLocaleTimeString(),
    },
  ]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const scrollRef = useRef(null);

  // Scroll to bottom when message arrives
  useEffect(() => {
    scrollRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isLoading]);

  const handleSend = async (e) => {
    e.preventDefault();
    if (!input.trim() || isLoading) return;

    const userMsgText = input;
    setInput('');

    const userMessage = {
      id: Date.now().toString(),
      sender: 'user',
      text: userMsgText,
      timestamp: new Date().toLocaleTimeString(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setIsLoading(true);

    try {
      const response = await fetch('http://localhost:8000/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: userMsgText,
          history: messages.map((m) => ({ sender: m.sender, text: m.text })),
        }),
      });

      if (!response.ok) throw new Error('Failed to get chat response.');
      const data = await response.json();

      const assistantMessage = {
        id: (Date.now() + 1).toString(),
        sender: 'assistant',
        text: data.text,
        timestamp: new Date().toLocaleTimeString(),
      };

      setMessages((prev) => [...prev, assistantMessage]);
    } catch (error) {
      console.error('Chat error:', error);
      const errorMessage = {
        id: (Date.now() + 1).toString(),
        sender: 'assistant',
        text: 'Forgive me, my neural linkage is experiencing momentary interference. Please check your network connection or verify your GEMINI_API_KEY.',
        timestamp: new Date().toLocaleTimeString(),
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="fixed right-6 bottom-6 top-24 w-[380px] bg-zinc-950/95 border border-cyan-500/30 rounded-2xl flex flex-col z-50 shadow-2xl animate-slideIn">
      {/* Header */}
      <div className="p-4 border-b border-white/5 flex justify-between items-center bg-cyan-500/5 rounded-t-2xl">
        <div className="flex items-center gap-2 text-cyan-400">
          <Sparkles className="w-4 h-4 animate-pulse" />
          <span className="text-xs font-bold uppercase tracking-widest font-sans">
            AI ECO-PLANNING ADVISOR
          </span>
        </div>
        <button
          onClick={onClose}
          className="text-zinc-400 hover:text-white hover:bg-white/5 p-1.5 rounded-lg cursor-pointer transition-colors"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* Messages */}
      <div
        className="flex-1 p-4 overflow-y-auto flex flex-col gap-4 text-left font-sans"
        style={{ scrollbarWidth: 'none' }}
      >
        {messages.map((m) => {
          const isBot = m.sender === 'assistant';
          return (
            <div key={m.id} className={`flex gap-3 ${isBot ? 'justify-start' : 'justify-end'}`}>
              {isBot && (
                <div className="w-7 h-7 rounded-lg bg-cyan-500/10 border border-cyan-500/20 flex items-center justify-center shrink-0">
                  <Bot className="w-4 h-4 text-cyan-400" />
                </div>
              )}
              <div
                className={`rounded-2xl p-3.5 text-xs max-w-[80%] leading-relaxed ${
                  isBot
                    ? 'bg-zinc-900 border border-white/5 text-zinc-200'
                    : 'bg-cyan-600 text-white font-medium shadow-[0_0_8px_rgba(6,182,212,0.2)]'
                }`}
              >
                <div className="whitespace-pre-line space-y-1.5">
                  {m.text.split('\n').map((line, idx) => {
                    let formattedLine = line;
                    // Bold handling **text**
                    if (formattedLine.includes('**')) {
                      const parts = formattedLine.split('**');
                      return (
                        <p key={idx}>
                          {parts.map((p, i) => (i % 2 === 1 ? <strong key={i} className="text-cyan-300 font-bold">{p}</strong> : p))}
                        </p>
                      );
                    }
                    // Bullet items handling e.g. - item
                    if (formattedLine.startsWith('- ') || formattedLine.startsWith('* ')) {
                      return (
                        <div key={idx} className="flex gap-2 pl-1.5 py-0.5">
                          <span className="text-cyan-400 select-none">•</span>
                          <span>{formattedLine.substring(2)}</span>
                        </div>
                      );
                    }
                    // Headers handling ### text
                    if (formattedLine.startsWith('### ')) {
                      return (
                        <h4 key={idx} className="text-cyan-400 font-bold text-[13px] uppercase tracking-wider pt-1 border-b border-white/5 pb-1 select-none">
                          {formattedLine.substring(4)}
                        </h4>
                      );
                    }
                    return <p key={idx}>{formattedLine}</p>;
                  })}
                </div>
              </div>
            </div>
          );
        })}
        {isLoading && (
          <div className="flex gap-3 justify-start">
            <div className="w-7 h-7 rounded-lg bg-cyan-500/10 border border-cyan-500/20 flex items-center justify-center shrink-0">
              <Bot className="w-4 h-4 text-cyan-400" />
            </div>
            <div className="bg-zinc-900 border border-white/5 rounded-2xl p-3.5 text-xs text-zinc-400">
              Thinking...
            </div>
          </div>
        )}
        <div ref={scrollRef} />
      </div>

      {/* Input */}
      <form onSubmit={handleSend} className="p-3 border-t border-white/5 flex gap-2">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask about cool species or simulated HVI reduction..."
          className="flex-1 bg-zinc-900 border border-white/10 rounded-xl px-4 py-2 text-xs text-white focus:outline-none focus:border-cyan-500/50"
        />
        <button
          type="submit"
          className="bg-cyan-500 hover:bg-cyan-600 text-white rounded-xl p-2.5 cursor-pointer flex items-center justify-center shrink-0"
        >
          <Send className="w-4.5 h-4.5" />
        </button>
      </form>
    </div>
  );
}
