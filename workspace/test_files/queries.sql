-- SQL Preview Test — workspace FileViewer syntax highlighting
-- Sample queries against the AI_OS state database

-- Identity facts
SELECT id, profile, key, value, updated_at
FROM identity_facts
WHERE profile = 'default'
ORDER BY updated_at DESC
LIMIT 20;

-- Memory extraction pipeline
SELECT f.id, f.text, f.status, f.source, f.created_at
FROM memory_facts f
WHERE f.status = 'pending'
  AND f.created_at > datetime('now', '-24 hours')
ORDER BY f.created_at DESC;

-- Knowledge graph nodes with edge count
SELECT
    n.id,
    n.label,
    n.thread,
    COUNT(e.id) AS edge_count
FROM graph_nodes n
LEFT JOIN graph_edges e ON e.source_id = n.id OR e.target_id = n.id
GROUP BY n.id
HAVING edge_count > 3
ORDER BY edge_count DESC
LIMIT 50;

-- Conversation search
SELECT c.id, c.name, t.role, t.content, t.created_at
FROM conversations c
JOIN conversation_turns t ON t.conversation_id = c.id
WHERE t.content LIKE '%identity%'
ORDER BY t.created_at DESC
LIMIT 10;
