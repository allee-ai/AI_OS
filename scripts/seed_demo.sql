-- Seed demo database with sample profiles and facts
-- Run with: sqlite3 data/db/state_demo.db < scripts/seed_demo.sql

-- Add profiles
INSERT OR REPLACE INTO profiles (profile_id, type_name, display_name) VALUES 
    ('family.sister', 'family', 'Sister'),
    ('friend.sam', 'friend', 'Sam'),
    ('acquaintance.neighbor', 'acquaintance', 'Neighbor'),
    ('acquaintance.coworker', 'acquaintance', 'Coworker');

-- Machine facts
INSERT OR REPLACE INTO profile_facts (profile_id, key, fact_type, l1_value, l2_value, weight) VALUES 
    ('machine', 'name', 'name', 'Nola', 'Nola - a personal AI that learns and remembers', 0.9),
    ('machine', 'purpose', 'note', 'AI companion', 'To be a thoughtful companion that grows with you over time', 0.85),
    ('machine', 'os', 'os', 'macOS', 'Running on macOS with local-first architecture', 0.7);

-- Primary user facts
INSERT OR REPLACE INTO profile_facts (profile_id, key, fact_type, l1_value, l2_value, weight) VALUES 
    ('primary_user', 'name', 'name', 'Demo User', 'A curious person exploring what personal AI can do', 0.9),
    ('primary_user', 'occupation', 'occupation', 'Explorer', 'Someone interested in AI and personal computing', 0.6),
    ('primary_user', 'location', 'location', 'Home', 'Working from home office', 0.5);

-- Family: Mom
INSERT OR REPLACE INTO profile_facts (profile_id, key, fact_type, l1_value, l2_value, weight) VALUES 
    ('family.mom', 'relationship', 'relationship', 'Mother', 'Your mother who lives nearby', 0.8),
    ('family.mom', 'birthday', 'birthday', 'March 15', 'Birthday is March 15th - loves flowers', 0.6),
    ('family.mom', 'preference', 'preference', 'Calls on Sunday', 'Prefers phone calls on Sunday afternoons', 0.5);

-- Family: Dad
INSERT OR REPLACE INTO profile_facts (profile_id, key, fact_type, l1_value, l2_value, weight) VALUES 
    ('family.dad', 'relationship', 'relationship', 'Father', 'Your father, retired engineer', 0.8),
    ('family.dad', 'birthday', 'birthday', 'July 4th', 'Birthday is July 4th - likes grilling', 0.6),
    ('family.dad', 'preference', 'preference', 'Black coffee', 'Takes his coffee black, no sugar', 0.4);

-- Family: Sister
INSERT OR REPLACE INTO profile_facts (profile_id, key, fact_type, l1_value, l2_value, weight) VALUES 
    ('family.sister', 'relationship', 'relationship', 'Sister', 'Your younger sister, lives in Seattle', 0.8),
    ('family.sister', 'birthday', 'birthday', 'November 22', 'Birthday is November 22nd', 0.6),
    ('family.sister', 'interest', 'interest', 'Photography', 'Really into photography, especially landscapes', 0.5);

-- Friend: Alex
INSERT OR REPLACE INTO profile_facts (profile_id, key, fact_type, l1_value, l2_value, weight) VALUES 
    ('friend.alex', 'relationship', 'relationship', 'Close friend', 'College friend, works in tech', 0.7),
    ('friend.alex', 'interest', 'interest', 'AI/ML', 'Interested in artificial intelligence and machine learning', 0.5),
    ('friend.alex', 'hangout', 'preference', 'Coffee shops', 'Likes meeting at coffee shops to chat', 0.4);

-- Friend: Jordan
INSERT OR REPLACE INTO profile_facts (profile_id, key, fact_type, l1_value, l2_value, weight) VALUES 
    ('friend.jordan', 'relationship', 'relationship', 'Hobby friend', 'Friend from your hiking group', 0.7),
    ('friend.jordan', 'interest', 'interest', 'Outdoors', 'Loves hiking and camping', 0.5),
    ('friend.jordan', 'schedule', 'preference', 'Weekends', 'Usually free on weekends for activities', 0.4);

-- Friend: Sam
INSERT OR REPLACE INTO profile_facts (profile_id, key, fact_type, l1_value, l2_value, weight) VALUES 
    ('friend.sam', 'relationship', 'relationship', 'Work friend', 'Former coworker who became a good friend', 0.7),
    ('friend.sam', 'interest', 'interest', 'Board games', 'Hosts monthly board game nights', 0.5),
    ('friend.sam', 'contact', 'contact', 'Signal', 'Prefers Signal for messaging', 0.4);

-- Acquaintance: Barista
INSERT OR REPLACE INTO profile_facts (profile_id, key, fact_type, l1_value, l2_value, weight) VALUES 
    ('acquaintance.barista', 'relationship', 'relationship', 'Coffee shop', 'Barista at your regular coffee spot', 0.5),
    ('acquaintance.barista', 'note', 'note', 'Knows your order', 'Remembers your usual order - oat milk latte', 0.3);

-- Acquaintance: Neighbor
INSERT OR REPLACE INTO profile_facts (profile_id, key, fact_type, l1_value, l2_value, weight) VALUES 
    ('acquaintance.neighbor', 'relationship', 'relationship', 'Neighbor', 'Lives two doors down', 0.5),
    ('acquaintance.neighbor', 'note', 'note', 'Has a dog', 'Has a friendly golden retriever named Max', 0.3);

-- Acquaintance: Coworker
INSERT OR REPLACE INTO profile_facts (profile_id, key, fact_type, l1_value, l2_value, weight) VALUES 
    ('acquaintance.coworker', 'relationship', 'relationship', 'Coworker', 'Works on the marketing team', 0.5),
    ('acquaintance.coworker', 'note', 'note', 'Lunch buddy', 'Sometimes joins for lunch on Fridays', 0.3);
