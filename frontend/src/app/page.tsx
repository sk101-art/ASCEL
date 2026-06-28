"use client";

import { useState, useEffect } from "react";
import Sidebar from "@/components/Sidebar";
import ChatWindow from "@/components/ChatWindow";

export default function Home() {
  const [currentChatId, setCurrentChatId] = useState<string | null>(null);
  const [messages, setMessages] = useState<{ role: "user" | "assistant"; content: string }[]>([]);
  const [loading, setLoading] = useState(false);
  const [refreshSidebar, setRefreshSidebar] = useState(0);

  // Load chat history when currentChatId changes
  useEffect(() => {
    if (!currentChatId) return;

    const fetchHistory = async () => {
      try {
        const res = await fetch(`http://localhost:8000/chat/${currentChatId}`);
        const data = await res.json();
        setMessages(data);
      } catch (e) {
        console.error("Failed to load chat history:", e);
      }
    };

    fetchHistory();
  }, [currentChatId]);

  const handleNewChat = () => {
    const newId = 'chat_' + Math.random().toString(36).substr(2, 9) + '_' + Date.now();
    setCurrentChatId(newId);
    setMessages([{ role: "assistant", content: "Welcome to ASCEL. I am your autonomous AI healing agent. How can I help you?" }]);
  };

  // If no chat selected, create one on mount
  useEffect(() => {
    if (typeof window !== "undefined") {
      const savedChatId = localStorage.getItem("ascel_currentChatId");
      if (savedChatId) {
        setCurrentChatId(savedChatId);
      } else {
        handleNewChat();
      }
    }
  }, []);

  // Save to localStorage when currentChatId changes
  useEffect(() => {
    if (currentChatId && typeof window !== "undefined") {
      localStorage.setItem("ascel_currentChatId", currentChatId);
    }
  }, [currentChatId]);

  const handleSendMessage = async (msg: string, activeSkills: { skill_id: string }[] = []) => {
    if (!currentChatId) return;

    // Optimistically add user message
    setMessages(prev => [...prev, { role: "user", content: msg }]);
    setLoading(true);

    try {
      const isFirstUserMessage = messages.filter(m => m.role === "user").length === 0;
      const title = isFirstUserMessage ? msg.substring(0, 30) + (msg.length > 30 ? "..." : "") : undefined;

      const response = await fetch("http://localhost:8000/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          conversation_id: currentChatId,
          message: msg,
          active_skills: activeSkills.length > 0 ? activeSkills : null,
          title: title
        })
      });

      const data = await response.json();
      setMessages(prev => [...prev, { role: "assistant", content: data.response }]);
      setRefreshSidebar(prev => prev + 1);
    } catch (e) {
      setMessages(prev => [...prev, { role: "assistant", content: "Error connecting to ASCEL Backend." }]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ display: "flex", height: "100vh", width: "100vw", overflow: "hidden" }}>
      <Sidebar 
        currentChatId={currentChatId} 
        onSelectChat={setCurrentChatId} 
        onNewChat={handleNewChat}
        refreshTrigger={refreshSidebar}
      />
      {currentChatId && (
        <ChatWindow 
          conversationId={currentChatId}
          messages={messages}
          onSendMessage={handleSendMessage}
          loading={loading}
        />
      )}
    </div>
  );
}
