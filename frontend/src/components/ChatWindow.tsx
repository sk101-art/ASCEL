"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { marked } from "marked";
import SkillPreview from "./SkillPreview";

interface Message {
  role: "user" | "assistant";
  content: string;
}

interface Skill {
  skill_id: string;
  title: string;
  summary?: string;
  snippet?: string;
  vault_tier?: string;
  domain_type?: string;
  skill_status?: string;
  is_searchable?: boolean;
  score?: number;
  trust_tier?: string;
  updated_at?: string;
  created_at?: string;
}

interface ChatWindowProps {
  conversationId: string;
  messages: Message[];
  onSendMessage: (msg: string, activeSkills: {skill_id: string}[]) => Promise<void>;
  loading: boolean;
}

const API = "http://localhost:8000";

// Phase 3.6: Virtualised list — render only visible items
const ITEM_HEIGHT = 66;
const VISIBLE_COUNT = 8;

function VirtualSkillList({
  skills,
  activeSkills,
  onToggle,
  onPreview,
  onDelete,
}: {
  skills: Skill[];
  activeSkills: Skill[];
  onToggle: (s: Skill) => void;
  onPreview: (id: string) => void;
  onDelete: (e: React.MouseEvent, id: string) => void;
}) {
  const [scrollTop, setScrollTop] = useState(0);
  const containerRef = useRef<HTMLDivElement>(null);
  const totalHeight = skills.length * ITEM_HEIGHT;
  const startIdx = Math.floor(scrollTop / ITEM_HEIGHT);
  const endIdx = Math.min(skills.length, startIdx + VISIBLE_COUNT + 2);
  const visibleSkills = skills.slice(startIdx, endIdx);
  const paddingTop = startIdx * ITEM_HEIGHT;

  return (
    <div
      ref={containerRef}
      style={{ overflowY: "auto", maxHeight: `${VISIBLE_COUNT * ITEM_HEIGHT}px` }}
      onScroll={(e) => setScrollTop((e.target as HTMLDivElement).scrollTop)}
    >
      <div style={{ height: totalHeight, position: "relative" }}>
        <div style={{ position: "absolute", top: paddingTop, width: "100%" }}>
          {visibleSkills.map((skill) => {
            const isActive = activeSkills.some(s => s.skill_id === skill.skill_id);
            return (
              <div
                key={skill.skill_id}
                style={{
                  height: ITEM_HEIGHT,
                  padding: "8px 10px",
                  borderRadius: "4px",
                  fontSize: "0.85rem",
                  background: isActive ? "rgba(59, 130, 246, 0.12)" : "transparent",
                  color: isActive ? "var(--accent-primary)" : "var(--text-primary)",
                  transition: "background 0.2s",
                  display: "flex",
                  alignItems: "center",
                  gap: "8px",
                  boxSizing: "border-box",
                }}
                onMouseOver={e => !isActive && (e.currentTarget.style.background = "rgba(255,255,255,0.04)")}
                onMouseOut={e => !isActive && (e.currentTarget.style.background = "transparent")}
              >
                {/* Checkbox */}
                <input
                  type="checkbox"
                  checked={isActive}
                  onChange={() => onToggle(skill)}
                  onClick={e => e.stopPropagation()}
                  style={{ cursor: "pointer", width: 15, height: 15, flexShrink: 0, accentColor: "var(--accent-primary)" }}
                />
                {/* Main info — click to preview */}
                <div style={{ flex: 1, overflow: "hidden", cursor: "pointer" }} onClick={() => onPreview(skill.skill_id)}>
                  <div style={{ fontWeight: "600", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                    {skill.title}
                  </div>
                  <div style={{ display: "flex", gap: 4, flexWrap: "wrap", marginTop: 2 }}>
                    {/* Phase 3.5: is_searchable badge */}
                    {skill.is_searchable === false && (
                      <span style={{ fontSize: "0.65rem", padding: "1px 5px", borderRadius: 8, background: "#ef4444", color: "white" }}>
                        no embedding
                      </span>
                    )}
                    {skill.vault_tier && (
                      <span style={{ fontSize: "0.65rem", padding: "1px 5px", borderRadius: 8, background: skill.vault_tier === "global" ? "#10b981" : "#3b82f6", color: "white" }}>
                        {skill.vault_tier}
                      </span>
                    )}
                    {skill.domain_type && (
                      <span style={{ fontSize: "0.65rem", padding: "1px 5px", borderRadius: 8, background: "#7c3aed", color: "white" }}>
                        {skill.domain_type}
                      </span>
                    )}
                    {/* Phase 8.3: relative time */}
                    {skill.updated_at && (
                      <span style={{ fontSize: "0.65rem", color: "var(--text-secondary)" }}>
                        {relativeTime(skill.updated_at)}
                      </span>
                    )}
                  </div>
                </div>
                {/* Delete */}
                <button
                  onClick={(e) => onDelete(e, skill.skill_id)}
                  style={{ background: "transparent", border: "none", color: "var(--text-secondary)", cursor: "pointer", fontSize: "1.2rem", flexShrink: 0 }}
                  title="Delete Skill"
                  onMouseOver={e => e.currentTarget.style.color = "#ef4444"}
                  onMouseOut={e => e.currentTarget.style.color = "var(--text-secondary)"}
                >
                  &times;
                </button>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

function relativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

export default function ChatWindow({ conversationId, messages, onSendMessage, loading }: ChatWindowProps) {
  const [input, setInput] = useState("");
  const [distilling, setDistilling] = useState(false);
  const [distillStatus, setDistillStatus] = useState("");
  const [availableSkills, setAvailableSkills] = useState<Skill[]>([]);
  const [skillCount, setSkillCount] = useState<number | null>(null);
  const [activeSkills, setActiveSkills] = useState<Skill[]>([]);
  const [showDropdown, setShowDropdown] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [previewSkillId, setPreviewSkillId] = useState<string | null>(null);
  const [toast, setToast] = useState<{message: string, type: 'error' | 'success'} | null>(null);
  // Phase 3.4: Filter state
  const [filterDomain, setFilterDomain] = useState("");
  const [filterTier, setFilterTier] = useState("");

  const showToast = (message: string, type: 'error' | 'success' = 'error') => {
    setToast({message, type});
    setTimeout(() => setToast(null), 3000);
  };

  // Phase 2.4: fetch count
  const fetchSkillCount = useCallback(() => {
    fetch(`${API}/skills/count`)
      .then(r => r.json())
      .then(d => setSkillCount(d.count))
      .catch(() => {});
  }, []);

  // Main skills fetcher — Phase 2.1/2.2/2.3/3.1/3.2/3.3/4.4/5.3
  const fetchSkills = useCallback((opts: {domain?: string; tier?: string; q?: string} = {}) => {
    const params = new URLSearchParams();
    params.set("limit", "100");
    params.set("snippet", "true");
    if (opts.domain) params.set("domain_type", opts.domain);
    if (opts.tier) params.set("vault_tier", opts.tier);
    if (opts.q) params.set("search", opts.q);
    fetch(`${API}/skills?${params}`)
      .then(res => res.json())
      .then(data => {
        if (Array.isArray(data)) setAvailableSkills(data);
        else setAvailableSkills([]);
      })
      .catch(e => console.error("Failed to load skills", e));
    fetchSkillCount();
  }, [fetchSkillCount]);

  // Phase 2.5 / 2.6: SSE listener for real-time updates
  useEffect(() => {
    let evtSource: EventSource | null = null;
    let retryTimeout: NodeJS.Timeout;

    const connect = () => {
      evtSource = new EventSource(`${API}/events/skills`);
      evtSource.onmessage = (e) => {
        try {
          const payload = JSON.parse(e.data);
          if (payload.event === "skill_created" || payload.event === "skill_deleted" || payload.event === "skill_updated") {
            fetchSkills({ domain: filterDomain, tier: filterTier, q: searchQuery });
          }
        } catch {}
      };
      evtSource.onerror = () => {
        evtSource?.close();
        retryTimeout = setTimeout(connect, 5000);
      };
    };

    connect();
    return () => {
      evtSource?.close();
      clearTimeout(retryTimeout);
    };
  }, [fetchSkills, filterDomain, filterTier, searchQuery]);

  // Search debounce
  useEffect(() => {
    const timer = setTimeout(() => {
      fetchSkills({ domain: filterDomain, tier: filterTier, q: searchQuery });
    }, 300);
    return () => clearTimeout(timer);
  }, [searchQuery, filterDomain, filterTier, fetchSkills]);

  // Initial load
  useEffect(() => {
    fetchSkills();
  }, [fetchSkills]);

  // Distillation polling
  useEffect(() => {
    let interval: NodeJS.Timeout;
    if (distilling) {
      interval = setInterval(() => {
        fetch(`${API}/distillation-status/${conversationId}`)
          .then(res => res.json())
          .then(data => {
            if (data.status === "completed") {
              setDistillStatus("Completed! ✅");
              setDistilling(false);
              fetchSkills();
              setTimeout(() => setDistillStatus(""), 4000);
            } else if (data.status === "processing") {
              setDistillStatus("Processing in background...");
            } else if (data.status === "failed") {
              setDistillStatus("Failed ❌");
              setDistilling(false);
              showToast("Skill distillation failed.", "error");
              setTimeout(() => setDistillStatus(""), 4000);
            } else if (data.status === "idle") {
              // No trigger file found — distillation was never started or already cleaned up.
              // Stop polling to avoid an infinite loop.
              setDistillStatus("No active distillation.");
              setDistilling(false);
              setTimeout(() => setDistillStatus(""), 3000);
            }
          })
          .catch(() => {});
      }, 3000);
    }
    return () => clearInterval(interval);
  }, [distilling, conversationId, fetchSkills]);

  const handleSend = () => {
    if (!input.trim() || loading) return;
    onSendMessage(input.trim(), activeSkills.map(s => ({ skill_id: s.skill_id })));
    setInput("");
    setActiveSkills([]);
  };

  const toggleSkill = (skill: Skill) => {
    if (activeSkills.find(s => s.skill_id === skill.skill_id)) {
      setActiveSkills(activeSkills.filter(s => s.skill_id !== skill.skill_id));
    } else {
      setActiveSkills([...activeSkills, skill]);
    }
  };

  const handleDistill = async () => {
    const skillName = prompt("Enter a name for this skill (optional):");
    if (skillName === null) return;
    setDistilling(true);
    setDistillStatus("Triggering...");
    try {
      const response = await fetch(`${API}/save-skill`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ conversation_id: conversationId, skill_name: skillName || undefined })
      });
      if (response.ok) {
        setDistillStatus("Processing in background...");
      } else {
        throw new Error();
      }
    } catch {
      setDistillStatus("Failed!");
      showToast("Skill distillation failed.", "error");
      setTimeout(() => { setDistilling(false); setDistillStatus(""); }, 3000);
    }
  };

  // Phase 6.1 + 6.2: Delete with confirmation + SSE auto-refresh (SSE handles refresh)
  const handleDeleteSkill = async (e: React.MouseEvent, skillId: string) => {
    e.stopPropagation();
    if (!confirm("Are you sure you want to permanently delete this skill?")) return;
    try {
      const res = await fetch(`${API}/skills/${skillId}`, { method: "DELETE" });
      if (res.ok) {
        showToast("Skill deleted.", "success");
        setActiveSkills(prev => prev.filter(s => s.skill_id !== skillId));
        // SSE will trigger auto-refresh; also do immediate local removal for snappiness
        setAvailableSkills(prev => prev.filter(s => s.skill_id !== skillId));
        setSkillCount(prev => prev !== null ? prev - 1 : null);
      } else {
        showToast("Failed to delete skill.", "error");
      }
    } catch {
      showToast("Error deleting skill.", "error");
    }
  };

  return (
    <div style={{ flex: 1, display: "flex", flexDirection: "column", background: "var(--bg-color)", position: "relative" }}>
      {toast && (
        <div className="animate-fade-in" style={{
          position: "absolute", top: "20px", left: "50%", transform: "translateX(-50%)", zIndex: 2000,
          background: toast.type === "error" ? "#ef4444" : "#10b981", color: "white", padding: "10px 20px",
          borderRadius: "8px", boxShadow: "0 4px 6px rgba(0,0,0,0.1)", fontWeight: "bold", fontSize: "0.9rem"
        }}>
          {toast.message}
        </div>
      )}

      {previewSkillId && (
        <SkillPreview
          skillId={previewSkillId}
          onClose={() => {
            setPreviewSkillId(null);
            fetchSkills({ domain: filterDomain, tier: filterTier, q: searchQuery });
          }}
        />
      )}

      {/* Header */}
      <div style={{ padding: "20px 30px", borderBottom: "1px solid var(--panel-border)", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div>
          <h2 style={{ fontSize: "1.2rem", fontWeight: "600" }}>ASCEL Healing Session</h2>
          <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)", marginTop: "4px" }}>Session: {conversationId}</p>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: "15px" }}>
          <span style={{
            fontSize: "0.9rem",
            color: distillStatus.includes("Failed") ? "#ef4444" : "#4ade80",
            fontStyle: "italic",
            opacity: distillStatus ? 1 : 0,
            transition: "opacity 0.3s"
          }}>
            {distillStatus}
          </span>
          <button
            onClick={handleDistill}
            disabled={distilling}
            style={{
              background: "transparent", border: "1px solid #fbbf24", color: "#fbbf24",
              padding: "8px 15px", borderRadius: "6px", cursor: distilling ? "not-allowed" : "pointer",
              fontWeight: "600", opacity: distilling ? 0.5 : 1, transition: "all 0.2s"
            }}
            onMouseOver={e => !distilling && (e.currentTarget.style.background = "rgba(251, 191, 36, 0.1)")}
            onMouseOut={e => !distilling && (e.currentTarget.style.background = "transparent")}
          >
            ⭐ Star / Distill
          </button>
        </div>
      </div>

      {/* Messages */}
      <div style={{ flex: 1, padding: "30px", overflowY: "auto", display: "flex", flexDirection: "column", gap: "20px" }}>
        {messages.length === 0 && (
          <div style={{ textAlign: "center", color: "var(--text-secondary)", marginTop: "100px" }}>
            <p>Start a new conversation.</p>
          </div>
        )}
        {messages.map((msg, i) => {
          const isUser = msg.role === "user";
          return (
            <div key={i} className="animate-fade-in" style={{
              alignSelf: isUser ? "flex-end" : "flex-start",
              background: isUser ? "var(--accent-primary)" : "var(--sidebar-bg)",
              color: isUser ? "white" : "var(--text-primary)",
              border: isUser ? "none" : "1px solid var(--panel-border)",
              maxWidth: "80%", padding: "15px 20px", borderRadius: "12px",
              lineHeight: "1.6", fontSize: "0.95rem"
            }}>
              {isUser ? (
                <div>{msg.content}</div>
              ) : (
                <div dangerouslySetInnerHTML={{ __html: marked.parse(msg.content) as string }} />
              )}
            </div>
          );
        })}
        {loading && (
          <div className="animate-fade-in" style={{ alignSelf: "flex-start", padding: "15px 20px", color: "var(--text-secondary)" }}>
            ASCEL is typing...
          </div>
        )}
      </div>

      {/* Input Area */}
      <div style={{ padding: "20px 30px", borderTop: "1px solid var(--panel-border)", background: "var(--glass-bg)", backdropFilter: "blur(10px)" }}>

        {/* Active skill pills */}
        {activeSkills.length > 0 && (
          <div style={{ display: "flex", gap: "10px", flexWrap: "wrap", marginBottom: "15px" }}>
            {activeSkills.map(skill => (
              <div key={skill.skill_id} className="animate-fade-in" style={{
                background: "rgba(59, 130, 246, 0.2)", border: "1px solid var(--accent-primary)",
                color: "var(--accent-primary)", padding: "6px 12px", borderRadius: "20px",
                fontSize: "0.85rem", display: "flex", alignItems: "center", gap: "8px"
              }}>
                <span style={{ cursor: "pointer", textDecoration: "underline" }} onClick={() => setPreviewSkillId(skill.skill_id)}>
                  🔌 {skill.title}
                </span>
                <button onClick={() => toggleSkill(skill)} style={{ background: "transparent", border: "none", color: "var(--accent-primary)", cursor: "pointer", fontSize: "1.1rem" }}>
                  &times;
                </button>
              </div>
            ))}
          </div>
        )}

        <div style={{ display: "flex", gap: "15px", position: "relative" }}>

          {/* Skill picker button */}
          <div style={{ position: "relative" }}>
            <button
              onClick={() => { setShowDropdown(!showDropdown); if (!showDropdown) fetchSkills({ domain: filterDomain, tier: filterTier, q: searchQuery }); }}
              style={{
                background: "rgba(255,255,255,0.05)", border: "1px solid var(--panel-border)",
                color: "var(--text-secondary)", padding: "15px", borderRadius: "8px",
                cursor: "pointer", height: "60px", display: "flex", alignItems: "center",
                justifyContent: "center", transition: "all 0.2s", position: "relative"
              }}
              onMouseOver={e => e.currentTarget.style.color = "var(--accent-primary)"}
              onMouseOut={e => e.currentTarget.style.color = "var(--text-secondary)"}
              title="Attach Skill"
            >
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"></path>
                <polyline points="3.27 6.96 12 12.01 20.73 6.96"></polyline>
                <line x1="12" y1="22.08" x2="12" y2="12"></line>
              </svg>
              {/* Phase 3.5: skill count badge */}
              {skillCount !== null && skillCount > 0 && (
                <span style={{
                  position: "absolute", top: "-6px", right: "-6px",
                  background: "var(--accent-primary)", color: "white",
                  fontSize: "0.65rem", fontWeight: "bold",
                  width: "18px", height: "18px", borderRadius: "50%",
                  display: "flex", alignItems: "center", justifyContent: "center"
                }}>
                  {skillCount > 99 ? "99+" : skillCount}
                </span>
              )}
            </button>

            {showDropdown && (
              <div className="animate-fade-in" style={{
                position: "absolute", bottom: "70px", left: "0", width: "380px",
                display: "flex", flexDirection: "column",
                background: "var(--sidebar-bg)", border: "1px solid var(--panel-border)",
                borderRadius: "8px", boxShadow: "0 10px 25px rgba(0,0,0,0.5)", zIndex: 10
              }}>
                {/* Search + filters header */}
                <div style={{ padding: "10px", borderBottom: "1px solid var(--panel-border)", display: "flex", flexDirection: "column", gap: "6px" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                    <span style={{ fontSize: "0.75rem", color: "var(--text-secondary)" }}>
                      {/* Phase 3.5: count display */}
                      {skillCount !== null ? `${skillCount} skill${skillCount !== 1 ? "s" : ""} total` : "Skills"}
                    </span>
                    <button onClick={() => setShowDropdown(false)} style={{ background: "transparent", border: "none", color: "var(--text-secondary)", cursor: "pointer", fontSize: "1rem" }}>&times;</button>
                  </div>
                  <input
                    type="text"
                    placeholder="Search skills..."
                    value={searchQuery}
                    onChange={e => setSearchQuery(e.target.value)}
                    style={{ width: "100%", padding: "7px", borderRadius: "4px", border: "1px solid var(--panel-border)", background: "rgba(255,255,255,0.05)", color: "white", boxSizing: "border-box" }}
                    autoFocus
                  />
                  {/* Phase 3.4: Filter dropdowns */}
                  <div style={{ display: "flex", gap: "6px" }}>
                    <select
                      value={filterDomain}
                      onChange={e => setFilterDomain(e.target.value)}
                      style={{ flex: 1, padding: "5px", borderRadius: "4px", border: "1px solid var(--panel-border)", background: "var(--sidebar-bg)", color: "var(--text-primary)", fontSize: "0.78rem" }}
                    >
                      <option value="">All Domains</option>
                      <option value="Remediation">Remediation</option>
                      <option value="Diagnostic">Diagnostic</option>
                    </select>
                    <select
                      value={filterTier}
                      onChange={e => setFilterTier(e.target.value)}
                      style={{ flex: 1, padding: "5px", borderRadius: "4px", border: "1px solid var(--panel-border)", background: "var(--sidebar-bg)", color: "var(--text-primary)", fontSize: "0.78rem" }}
                    >
                      <option value="">All Tiers</option>
                      <option value="project_local">project_local</option>
                      <option value="global">global</option>
                    </select>
                  </div>
                </div>

                {/* Phase 3.6: Virtualized list */}
                <div style={{ padding: "5px" }}>
                  {availableSkills.length === 0 ? (
                    <div style={{ padding: "20px", color: "var(--text-secondary)", fontSize: "0.9rem", textAlign: "center" }}>No skills found</div>
                  ) : (
                    <VirtualSkillList
                      skills={availableSkills}
                      activeSkills={activeSkills}
                      onToggle={toggleSkill}
                      onPreview={setPreviewSkillId}
                      onDelete={handleDeleteSkill}
                    />
                  )}
                </div>
              </div>
            )}
          </div>

          <textarea
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={e => {
              if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleSend(); }
            }}
            placeholder="Describe the bug or request a fix..."
            disabled={loading}
            style={{
              flex: 1, background: "rgba(255,255,255,0.05)", border: "1px solid var(--panel-border)",
              color: "var(--text-primary)", padding: "15px", borderRadius: "8px",
              resize: "none", height: "60px", fontFamily: "inherit", outline: "none"
            }}
          />
          <button
            onClick={handleSend}
            disabled={loading || !input.trim()}
            style={{
              background: "var(--accent-primary)", color: "white", border: "none",
              padding: "0 30px", borderRadius: "8px",
              cursor: loading || !input.trim() ? "not-allowed" : "pointer",
              fontWeight: "600", opacity: loading || !input.trim() ? 0.5 : 1, transition: "background 0.2s"
            }}
          >
            Send
          </button>
        </div>
      </div>
    </div>
  );
}
