import React from 'react';
import { marked } from 'marked';

interface SkillPreviewProps {
  skillId: string;
  onClose: () => void;
}

interface HistoryEntry {
  sha: string;
  full_sha: string;
  message: string;
  author: string;
  date: string;
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

export default function SkillPreview({ skillId, onClose }: SkillPreviewProps) {
  const [content, setContent] = React.useState<string>("Loading...");
  const [skillMeta, setSkillMeta] = React.useState<{
    title?: string;
    vault_tier?: string;
    trust_tier?: string;
    skill_status?: string;
    created_at?: string;
    updated_at?: string;
    is_searchable?: boolean;
  }>({});
  const [error, setError] = React.useState<string | null>(null);
  const [showHistory, setShowHistory] = React.useState(false);
  const [history, setHistory] = React.useState<HistoryEntry[]>([]);
  const [historyLoading, setHistoryLoading] = React.useState(false);
  const [rollbackSha, setRollbackSha] = React.useState<string | null>(null);
  const [rollbackStatus, setRollbackStatus] = React.useState<string>("");

  // Phase 5.1: Use preview endpoint with max_tokens=2000 for full view
  React.useEffect(() => {
    fetch(`http://localhost:8000/skills/${skillId}/preview?max_tokens=2000`)
      .then(res => {
        if (!res.ok) throw new Error("Failed to fetch skill details");
        return res.json();
      })
      .then(data => {
        setContent(data.content || "");
        setSkillMeta({
          title: data.title,
          vault_tier: data.vault_tier,
          skill_status: data.skill_status,
          created_at: data.created_at,
          updated_at: data.updated_at,
        });
      })
      .catch(e => setError(e.message));
  }, [skillId]);

  // Phase 8.1: Fetch git history
  const fetchHistory = () => {
    setShowHistory(true);
    setHistoryLoading(true);
    fetch(`http://localhost:8000/skills/${skillId}/history`)
      .then(r => r.json())
      .then(d => { setHistory(d.history || []); setHistoryLoading(false); })
      .catch(() => { setHistoryLoading(false); });
  };

  // Phase 8.2: Rollback
  const handleRollback = async (sha: string) => {
    if (!confirm(`Roll back to commit ${sha}? This will overwrite the current version.`)) return;
    setRollbackSha(sha);
    setRollbackStatus("Rolling back...");
    try {
      const res = await fetch(`http://localhost:8000/skills/${skillId}/rollback/${sha}`, { method: "POST" });
      if (res.ok) {
        setRollbackStatus("✅ Rollback successful!");
        // Reload content
        fetch(`http://localhost:8000/skills/${skillId}/preview?max_tokens=2000`)
          .then(r => r.json())
          .then(d => setContent(d.content || ""));
      } else {
        setRollbackStatus("❌ Rollback failed.");
      }
    } catch {
      setRollbackStatus("❌ Error during rollback.");
    }
    setTimeout(() => { setRollbackSha(null); setRollbackStatus(""); }, 4000);
  };

  const handleDelete = async () => {
    if (!confirm("Are you sure you want to permanently delete this skill?")) return;
    try {
      const res = await fetch(`http://localhost:8000/skills/${skillId}`, { method: 'DELETE' });
      if (res.ok) {
        onClose();
      } else {
        setError("Failed to delete skill.");
      }
    } catch {
      setError("Error deleting skill.");
    }
  };

  const statusColor = (s?: string) => {
    if (s === 'completed') return '#10b981';
    if (s === 'processing') return '#fbbf24';
    if (s === 'failed') return '#ef4444';
    return '#6b7280';
  };

  return (
    <div style={{
      position: "fixed", top: 0, left: 0, right: 0, bottom: 0,
      background: "rgba(0,0,0,0.75)", display: "flex",
      justifyContent: "center", alignItems: "center", zIndex: 1000
    }}>
      <div style={{
        background: "var(--sidebar-bg)", width: "85%", maxWidth: "860px",
        maxHeight: "85vh", borderRadius: "12px", display: "flex",
        flexDirection: "column", border: "1px solid var(--panel-border)",
        boxShadow: "0 20px 60px rgba(0,0,0,0.6)"
      }}>
        {/* Header */}
        <div style={{
          padding: "18px 20px", borderBottom: "1px solid var(--panel-border)",
          display: "flex", justifyContent: "space-between", alignItems: "flex-start"
        }}>
          <div style={{ display: "flex", flexDirection: "column", gap: "6px", flex: 1 }}>
            <h2 style={{ margin: 0, fontSize: "1.15rem", fontWeight: "bold", display: "flex", alignItems: "center", flexWrap: "wrap", gap: "8px" }}>
              {skillMeta.title || "Skill Preview"}
              {skillMeta.vault_tier && (
                <span style={{ fontSize: "0.68rem", padding: "2px 7px", borderRadius: 10, background: skillMeta.vault_tier === "global" ? "#10b981" : "#3b82f6", color: "white" }}>
                  {skillMeta.vault_tier}
                </span>
              )}
              {skillMeta.skill_status && (
                <span style={{ fontSize: "0.68rem", padding: "2px 7px", borderRadius: 10, background: statusColor(skillMeta.skill_status), color: "white" }}>
                  {skillMeta.skill_status}
                </span>
              )}
            </h2>
            {/* Phase 8.3: created_at + updated_at */}
            <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)", display: "flex", gap: "12px", flexWrap: "wrap" }}>
              {skillMeta.created_at && (
                <span>Created: {relativeTime(skillMeta.created_at)} ({new Date(skillMeta.created_at).toLocaleDateString()})</span>
              )}
              {skillMeta.updated_at && (
                <span>Updated: {relativeTime(skillMeta.updated_at)}</span>
              )}
            </div>
          </div>
          <div style={{ display: "flex", gap: "8px", alignItems: "center", flexShrink: 0, marginLeft: "10px" }}>
            {/* Phase 8.1: History button */}
            <button
              onClick={fetchHistory}
              style={{ background: "rgba(255,255,255,0.07)", border: "1px solid var(--panel-border)", color: "var(--text-secondary)", padding: "5px 10px", borderRadius: "4px", cursor: "pointer", fontSize: "0.8rem" }}
              title="View Git History"
            >
              📜 History
            </button>
            <button
              onClick={handleDelete}
              style={{ background: "#ef4444", border: "none", color: "white", padding: "5px 12px", borderRadius: "4px", cursor: "pointer", fontSize: "0.85rem" }}
            >
              Delete
            </button>
            <button
              onClick={onClose}
              style={{ background: "transparent", border: "none", color: "var(--text-secondary)", cursor: "pointer", fontSize: "1.5rem", lineHeight: 1 }}
            >
              &times;
            </button>
          </div>
        </div>

        {/* Phase 8.1/8.2: History panel */}
        {showHistory && (
          <div style={{ padding: "12px 20px", borderBottom: "1px solid var(--panel-border)", background: "rgba(0,0,0,0.2)", maxHeight: "180px", overflowY: "auto" }}>
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "8px" }}>
              <span style={{ fontSize: "0.85rem", fontWeight: "600", color: "var(--text-primary)" }}>Git History</span>
              <button onClick={() => setShowHistory(false)} style={{ background: "transparent", border: "none", color: "var(--text-secondary)", cursor: "pointer", fontSize: "0.8rem" }}>Hide</button>
            </div>
            {rollbackStatus && (
              <div style={{ fontSize: "0.8rem", marginBottom: "6px", color: rollbackStatus.includes("✅") ? "#10b981" : "#ef4444" }}>
                {rollbackStatus}
              </div>
            )}
            {historyLoading ? (
              <div style={{ color: "var(--text-secondary)", fontSize: "0.85rem" }}>Loading history...</div>
            ) : history.length === 0 ? (
              <div style={{ color: "var(--text-secondary)", fontSize: "0.85rem" }}>No commits found.</div>
            ) : (
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.8rem" }}>
                <thead>
                  <tr style={{ color: "var(--text-secondary)", textAlign: "left" }}>
                    <th style={{ paddingBottom: 4 }}>SHA</th>
                    <th style={{ paddingBottom: 4 }}>Message</th>
                    <th style={{ paddingBottom: 4 }}>Date</th>
                    <th style={{ paddingBottom: 4 }}></th>
                  </tr>
                </thead>
                <tbody>
                  {history.map(h => (
                    <tr key={h.full_sha} style={{ borderTop: "1px solid var(--panel-border)" }}>
                      <td style={{ padding: "4px 8px 4px 0", fontFamily: "monospace", color: "#fbbf24" }}>{h.sha}</td>
                      <td style={{ padding: "4px 8px 4px 0", color: "var(--text-primary)" }}>{h.message}</td>
                      <td style={{ padding: "4px 8px 4px 0", color: "var(--text-secondary)", whiteSpace: "nowrap" }}>
                        {relativeTime(h.date)}
                      </td>
                      <td style={{ padding: "4px 0" }}>
                        <button
                          onClick={() => handleRollback(h.full_sha)}
                          disabled={rollbackSha === h.full_sha}
                          style={{ background: "rgba(251,191,36,0.15)", border: "1px solid #fbbf24", color: "#fbbf24", padding: "2px 8px", borderRadius: 4, cursor: "pointer", fontSize: "0.75rem" }}
                        >
                          {rollbackSha === h.full_sha ? "..." : "↩ Rollback"}
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        )}

        {/* Content */}
        <div style={{ padding: "20px", overflowY: "auto", flex: 1, color: "var(--text-primary)" }}>
          {error ? (
            <div style={{ color: "#ef4444" }}>{error}</div>
          ) : (
            <div dangerouslySetInnerHTML={{ __html: marked.parse(content) as string }} />
          )}
        </div>
      </div>
    </div>
  );
}
