"use client";

import { useEffect, useState } from "react";

interface ChatMeta {
  conversation_id: string;
  title: string;
}

interface SidebarProps {
  currentChatId: string | null;
  onSelectChat: (id: string) => void;
  onNewChat: () => void;
  refreshTrigger?: number;
}

export default function Sidebar({ currentChatId, onSelectChat, onNewChat, refreshTrigger }: SidebarProps) {
  const [chats, setChats] = useState<ChatMeta[]>([]);
  const [loading, setLoading] = useState(true);
  const [hoveredChatId, setHoveredChatId] = useState<string | null>(null);

  const loadChats = async () => {
    try {
      const res = await fetch("http://localhost:8000/chats");
      const data = await res.json();
      setChats(data);
    } catch (e) {
      console.error("Failed to load chats:", e);
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteChat = async (e: React.MouseEvent, id: string) => {
    e.stopPropagation();
    if (!confirm("Are you sure you want to delete this chat?")) return;
    try {
      await fetch(`http://localhost:8000/chat/${id}`, { method: "DELETE" });
      if (currentChatId === id) {
        onNewChat(); // Switches to a new chat, triggering useEffect to reload chats
      } else {
        loadChats();
      }
    } catch (err) {
      console.error("Failed to delete chat:", err);
    }
  };

  // We should reload chats periodically or when told, but for now just load on mount
  useEffect(() => {
    loadChats();
  }, [currentChatId, refreshTrigger]); // Reload when currentChatId changes or refresh triggered

  return (
    <aside style={{
      width: "280px",
      background: "var(--sidebar-bg)",
      backdropFilter: "blur(12px)",
      borderRight: "1px solid var(--panel-border)",
      display: "flex",
      flexDirection: "column",
      padding: "20px"
    }}>
      <button 
        onClick={onNewChat}
        style={{
          background: "var(--accent-primary)",
          color: "white",
          border: "none",
          padding: "12px",
          borderRadius: "8px",
          cursor: "pointer",
          fontWeight: "600",
          marginBottom: "20px",
          transition: "background 0.2s"
        }}
        onMouseOver={e => e.currentTarget.style.background = "var(--accent-hover)"}
        onMouseOut={e => e.currentTarget.style.background = "var(--accent-primary)"}
      >
        ➕ New Chat
      </button>

      <div style={{ flex: 1, overflowY: "auto" }}>
        <h3 style={{ fontSize: "0.85rem", color: "var(--text-secondary)", marginBottom: "10px", textTransform: "uppercase", letterSpacing: "1px" }}>History</h3>
        
        {loading ? (
          <p style={{ color: "var(--text-secondary)", fontSize: "0.9rem" }}>Loading...</p>
        ) : (
          <ul style={{ listStyle: "none", padding: 0 }}>
            {chats.map(chat => (
              <li 
                key={chat.conversation_id}
                onClick={() => onSelectChat(chat.conversation_id)}
                style={{
                  padding: "12px",
                  marginBottom: "8px",
                  background: currentChatId === chat.conversation_id ? "rgba(255, 255, 255, 0.1)" : "rgba(255, 255, 255, 0.03)",
                  border: "1px solid var(--panel-border)",
                  borderRadius: "8px",
                  cursor: "pointer",
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  fontSize: "0.9rem",
                  transition: "background 0.2s, borderColor 0.2s",
                  position: "relative"
                }}
                onMouseEnter={e => {
                  setHoveredChatId(chat.conversation_id);
                  if (currentChatId !== chat.conversation_id) e.currentTarget.style.background = "rgba(255, 255, 255, 0.06)";
                  e.currentTarget.style.borderColor = "var(--accent-primary)";
                }}
                onMouseLeave={e => {
                  setHoveredChatId(null);
                  if (currentChatId !== chat.conversation_id) e.currentTarget.style.background = "rgba(255, 255, 255, 0.03)";
                  e.currentTarget.style.borderColor = "var(--panel-border)";
                }}
              >
                <span style={{ whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis", marginRight: "10px", flex: 1 }}>
                  {chat.title}
                </span>
                
                {hoveredChatId === chat.conversation_id && (
                  <div style={{
                    position: "absolute",
                    left: "20px",
                    top: "35px",
                    background: "var(--accent-primary)",
                    color: "#ffffff",
                    padding: "8px 12px",
                    borderRadius: "6px",
                    boxShadow: "0 4px 15px rgba(0,0,0,0.5)",
                    zIndex: 99999,
                    fontSize: "0.85rem",
                    whiteSpace: "normal",
                    minWidth: "200px",
                    border: "1px solid rgba(255,255,255,0.1)",
                    pointerEvents: "none"
                  }}>
                    {chat.title}
                  </div>
                )}
                <button
                  onClick={(e) => handleDeleteChat(e, chat.conversation_id)}
                  style={{
                    background: "transparent",
                    border: "none",
                    color: "var(--text-secondary)",
                    cursor: "pointer",
                    fontSize: "1.1rem",
                    padding: "0 5px"
                  }}
                  onMouseOver={e => e.currentTarget.style.color = "#ef4444"}
                  onMouseOut={e => e.currentTarget.style.color = "var(--text-secondary)"}
                  title="Delete Chat"
                >
                  &times;
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </aside>
  );
}
