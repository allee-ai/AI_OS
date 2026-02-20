/**
 * Identity ProfilesPage - Profile Manager for Identity thread.
 * User-defined profile types, profiles, and facts with visible weights.
 */

import React, { useState, useEffect, useCallback } from 'react';
import SelectWithAdd from '../components/SelectWithAdd';
import ThemedSelect from '../components/ThemedSelect';
import './ProfilesPage.css';

const API = '/api/identity';

// Types
interface ProfileType {
  type_name: string;
  trust_level: number;
  context_priority: number;
  can_edit: boolean;
  description: string;
}

interface Profile {
  profile_id: string;
  type_name: string;
  display_name: string;
  trust_level?: number;
  context_priority?: number;
  can_edit?: boolean;
  protected?: boolean;
}

interface FactType {
  fact_type: string;
  description: string;
  default_weight: number;
}

interface Fact {
  profile_id: string;
  key: string;
  fact_type: string;
  l1_value: string;
  l2_value: string;
  l3_value: string;
  weight: number;
  access_count: number;
  last_accessed: string;
}

// ============================================================================
// PROFILE SIDEBAR
// ============================================================================

interface ProfileSidebarProps {
  profileTypes: ProfileType[];
  profiles: Profile[];
  factTypes: FactType[];
  selectedType: string;
  selectedProfile: string | null;
  onTypeChange: (type: string) => void;
  onProfileSelect: (profileId: string) => void;
  onAddType: (name: string) => Promise<void>;
  onAddProfile: () => void;
  onDeleteProfile: (profileId: string) => Promise<void>;
  onDeleteAllFacts: () => void;
  onDeleteAllProfiles: () => void;
}

const ProfileSidebar: React.FC<ProfileSidebarProps> = ({
  profileTypes,
  profiles,
  selectedType,
  selectedProfile,
  onTypeChange,
  onProfileSelect,
  onAddType,
  onAddProfile,
  onDeleteProfile,
  onDeleteAllFacts,
  onDeleteAllProfiles,
}) => {
  const filteredProfiles = selectedType
    ? profiles.filter((p) => p.type_name === selectedType)
    : profiles;

  return (
    <div className="profile-sidebar">
      {/* Type Selector */}
      <div>
        <label>Profile Type</label>
        <SelectWithAdd
          options={[
            { value: '', label: 'All Types' },
            ...profileTypes.map((t) => ({
              value: t.type_name,
              label: t.type_name,
            })),
          ]}
          value={selectedType}
          onChange={onTypeChange}
          onAddNew={onAddType}
          placeholder="Filter by type..."
          addNewLabel="Add new type"
        />
      </div>

      {/* Profile List */}
      <div className="profile-list">
        <div className="profile-list-header">
          <label>Profiles ({filteredProfiles.length})</label>
          <button
            onClick={onAddProfile}
            disabled={!selectedType}
            title={selectedType ? 'Add profile' : 'Select a type first'}
          >
            + Add
          </button>
        </div>

        <div>
          {filteredProfiles.map((p) => (
            <div
              key={p.profile_id}
              onClick={() => onProfileSelect(p.profile_id)}
              className={`profile-item ${selectedProfile === p.profile_id ? 'active' : ''}`}
            >
              <div className="profile-item-content">
                <div className="profile-item-name">{p.display_name}</div>
                <div className="profile-item-meta">
                  {p.type_name} • trust: {p.trust_level}
                </div>
              </div>
              {!p.protected && (
                <button
                  className="profile-item-delete"
                  onClick={(e) => {
                    e.stopPropagation();
                    if (confirm(`Delete profile "${p.display_name}"?`)) {
                      onDeleteProfile(p.profile_id);
                    }
                  }}
                  title="Delete profile"
                >
                  🗑️
                </button>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Danger Zone */}
      <div className="profile-danger-zone">
        <label>Danger Zone</label>
        <div className="profile-danger-buttons">
          <button onClick={onDeleteAllFacts}>
            🗑️ Clear All Facts
          </button>
          <button onClick={onDeleteAllProfiles}>
            ⚠️ Delete All Profiles
          </button>
        </div>
      </div>
    </div>
  );
};

// ============================================================================
// PROFILE VIEW (Main Area)
// ============================================================================

interface ProfileViewProps {
  profile: Profile | null;
  facts: Fact[];
  factTypes: FactType[];
  onAddFact: (fact: Partial<Fact>) => Promise<void>;
  onUpdateFact: (profileId: string, key: string, updates: Partial<Fact>) => Promise<void>;
  onDeleteFact: (profileId: string, key: string) => Promise<void>;
  onAddFactType: (name: string) => Promise<void>;
}

const ProfileView: React.FC<ProfileViewProps> = ({
  profile,
  facts,
  factTypes,
  onAddFact,
  onUpdateFact,
  onDeleteFact,
  onAddFactType,
}) => {
  const [newFact, setNewFact] = useState({ 
    key: '', 
    l1_value: '', 
    l2_value: '', 
    l3_value: '', 
    fact_type: 'note', 
    weight: 0.5 
  });
  const [editingWeight, setEditingWeight] = useState<string | null>(null);
  const [contextLevel, setContextLevel] = useState<1 | 2 | 3>(2);
  const [editingFact, setEditingFact] = useState<Fact | null>(null);

  const onEditFact = (fact: Fact) => {
    setEditingFact(fact);
  };

  const handleSaveEdit = async () => {
    if (editingFact) {
      await onUpdateFact(editingFact.profile_id, editingFact.key, {
        l1_value: editingFact.l1_value,
        l2_value: editingFact.l2_value,
        l3_value: editingFact.l3_value,
        fact_type: editingFact.fact_type,
        weight: editingFact.weight,
      });
      setEditingFact(null);
    }
  };

  if (!profile) {
    return (
      <div className="profile-view-empty">
        <div className="profile-view-empty-content">
          <div className="profile-view-empty-icon">👤</div>
          <div>Select a profile to view and edit facts</div>
        </div>
      </div>
    );
  }

  const handleAddFact = async () => {
    if (newFact.key && (newFact.l1_value || newFact.l2_value || newFact.l3_value)) {
      await onAddFact({
        profile_id: profile.profile_id,
        ...newFact,
      });
      setNewFact({ key: '', l1_value: '', l2_value: '', l3_value: '', fact_type: 'note', weight: 0.5 });
    }
  };

  return (
    <div className="profile-view">
      {/* Profile Header */}
      <div className="profile-header">
        <h2>{profile.display_name}</h2>
        <div className="profile-header-meta">
          {profile.type_name} • Trust Level: {profile.trust_level} • Context Priority:{' '}
          {profile.context_priority}
        </div>
      </div>

      {/* Add New Fact Form */}
      <div className="add-fact-form">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <h3>Add New Fact</h3>
          <div className="level-toggle">
            <button 
              className={contextLevel === 1 ? 'active' : ''}
              onClick={() => setContextLevel(1)}
              title="Brief (~10 tokens)"
            >
              L1
            </button>
            <button 
              className={contextLevel === 2 ? 'active' : ''}
              onClick={() => setContextLevel(2)}
              title="Standard (~50 tokens)"
            >
              L2
            </button>
            <button 
              className={contextLevel === 3 ? 'active' : ''}
              onClick={() => setContextLevel(3)}
              title="Full detail (~200 tokens)"
            >
              L3
            </button>
          </div>
        </div>
        <div className="add-fact-grid">
          <input
            type="text"
            placeholder="Key (e.g. 'birthday')"
            value={newFact.key}
            onChange={(e) => setNewFact({ ...newFact, key: e.target.value })}
          />
          {contextLevel === 1 && (
            <textarea
              placeholder="L1: Brief (~10 tokens)"
              value={newFact.l1_value}
              onChange={(e) => setNewFact({ ...newFact, l1_value: e.target.value })}
              rows={3}
              style={{ gridColumn: '1 / -1' }}
            />
          )}
          {contextLevel === 2 && (
            <textarea
              placeholder="L2: Standard (~50 tokens)"
              value={newFact.l2_value}
              onChange={(e) => setNewFact({ ...newFact, l2_value: e.target.value })}
              rows={3}
              style={{ gridColumn: '1 / -1' }}
            />
          )}
          {contextLevel === 3 && (
            <textarea
              placeholder="L3: Full detail (~200 tokens)"
              value={newFact.l3_value}
              onChange={(e) => setNewFact({ ...newFact, l3_value: e.target.value })}
              rows={3}
              style={{ gridColumn: '1 / -1' }}
            />
          )}
          <SelectWithAdd
            options={factTypes.map((t) => ({ value: t.fact_type, label: t.fact_type }))}
            value={newFact.fact_type}
            onChange={(v) => setNewFact({ ...newFact, fact_type: v })}
            onAddNew={onAddFactType}
            placeholder="Type"
            addNewLabel="New type"
          />
          <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
            <input
              type="range"
              min="0"
              max="1"
              step="0.1"
              value={newFact.weight}
              onChange={(e) => setNewFact({ ...newFact, weight: parseFloat(e.target.value) })}
              style={{ width: '50px' }}
            />
            <span style={{ fontSize: '11px', width: '28px' }}>
              {newFact.weight.toFixed(1)}
            </span>
          </div>
          <button
            onClick={handleAddFact}
            disabled={!newFact.key || (!newFact.l1_value && !newFact.l2_value && !newFact.l3_value)}
          >
            Add
          </button>
        </div>
      </div>

      {/* Facts Table */}
      <div className="facts-header">
        <h3>Facts</h3>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div className="level-toggle">
            <button 
              className={contextLevel === 1 ? 'active' : ''}
              onClick={() => setContextLevel(1)}
              title="Brief"
            >
              L1
            </button>
            <button 
              className={contextLevel === 2 ? 'active' : ''}
              onClick={() => setContextLevel(2)}
              title="Standard"
            >
              L2
            </button>
            <button 
              className={contextLevel === 3 ? 'active' : ''}
              onClick={() => setContextLevel(3)}
              title="Full"
            >
              L3
            </button>
          </div>
          <span className="facts-count">{facts.length} items</span>
        </div>
      </div>
      <table className="facts-table">
        <thead>
          <tr>
            <th style={{ width: '150px' }}>Key</th>
            <th>Value</th>
            <th style={{ width: '100px' }}>Type</th>
            <th style={{ width: '120px' }}>Weight</th>
            <th style={{ width: '60px' }}>Uses</th>
            <th style={{ width: '50px' }}></th>
          </tr>
        </thead>
        <tbody>
          {facts.map((fact) => (
            <tr key={fact.key}>
              <td>
                <span className="fact-key">{fact.key}</span>
              </td>
              <td className="fact-value">
                {contextLevel === 1 && (fact.l1_value || <span style={{ color: 'var(--text-muted)', fontStyle: 'italic' }}>No L1 value</span>)}
                {contextLevel === 2 && (fact.l2_value || <span style={{ color: 'var(--text-muted)', fontStyle: 'italic' }}>No L2 value</span>)}
                {contextLevel === 3 && (fact.l3_value || <span style={{ color: 'var(--text-muted)', fontStyle: 'italic' }}>No L3 value</span>)}
              </td>
              <td>
                <span className="fact-type-badge">{fact.fact_type}</span>
              </td>
              <td>
                {editingWeight === fact.key ? (
                  <div className="fact-weight-container">
                    <input
                      type="range"
                      min="0"
                      max="1"
                      step="0.1"
                      defaultValue={fact.weight}
                      onBlur={(e) => {
                        onUpdateFact(fact.profile_id, fact.key, {
                          weight: parseFloat(e.target.value),
                        });
                        setEditingWeight(null);
                      }}
                      autoFocus
                      className="fact-weight-input"
                    />
                  </div>
                ) : (
                  <div
                    onClick={() => setEditingWeight(fact.key)}
                    className="fact-weight-container"
                    style={{ cursor: 'pointer' }}
                    title="Click to edit weight"
                  >
                    <div className="fact-weight-bar">
                      <div
                        className="fact-weight-fill"
                        style={{
                          width: `${fact.weight * 100}%`,
                          background: getWeightColor(fact.weight),
                        }}
                      />
                    </div>
                    <span className="fact-weight-text">{fact.weight.toFixed(2)}</span>
                  </div>
                )}
              </td>
              <td style={{ textAlign: 'center', fontSize: '12px', color: 'var(--text-muted)' }}>
                {fact.access_count}
              </td>
              <td>
                <div style={{ display: 'flex', gap: '4px' }}>
                  <button
                    onClick={() => onEditFact(fact)}
                    className="fact-actions edit-btn"
                    title="Edit fact"
                    style={{ background: 'transparent', border: 'none', cursor: 'pointer', padding: '4px' }}
                  >
                    ✏️
                  </button>
                  <button
                    onClick={() => onDeleteFact(fact.profile_id, fact.key)}
                    className="fact-actions delete-btn"
                    title="Delete fact"
                    style={{ background: 'transparent', border: 'none', cursor: 'pointer', padding: '4px' }}
                  >
                    🗑️
                  </button>
                </div>
              </td>
            </tr>
          ))}
          {facts.length === 0 && (
            <tr>
              <td colSpan={6} style={{ textAlign: 'center', color: 'var(--text-muted)', padding: '24px' }}>
                No facts yet. Add one above!
              </td>
            </tr>
          )}
        </tbody>
      </table>

      {/* Edit Fact Modal */}
      {editingFact && (
        <div className="modal-overlay" onClick={() => setEditingFact(null)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <h3>Edit Fact: {editingFact.key}</h3>
            <div className="edit-fact-form">
              <div className="form-group">
                <label>L1 (Brief ~10 tokens)</label>
                <textarea
                  value={editingFact.l1_value || ''}
                  onChange={(e) => setEditingFact({ ...editingFact, l1_value: e.target.value })}
                  rows={2}
                />
              </div>
              <div className="form-group">
                <label>L2 (Standard ~50 tokens)</label>
                <textarea
                  value={editingFact.l2_value || ''}
                  onChange={(e) => setEditingFact({ ...editingFact, l2_value: e.target.value })}
                  rows={3}
                />
              </div>
              <div className="form-group">
                <label>L3 (Full ~200 tokens)</label>
                <textarea
                  value={editingFact.l3_value || ''}
                  onChange={(e) => setEditingFact({ ...editingFact, l3_value: e.target.value })}
                  rows={4}
                />
              </div>
              <div className="form-row">
                <div className="form-group">
                  <label>Type</label>
                  <ThemedSelect
                    options={factTypes.map((t) => ({ value: t.fact_type, label: t.fact_type }))}
                    value={editingFact.fact_type}
                    onChange={(v) => setEditingFact({ ...editingFact, fact_type: v })}
                  />
                </div>
                <div className="form-group">
                  <label>Weight: {editingFact.weight.toFixed(1)}</label>
                  <input
                    type="range"
                    min="0"
                    max="1"
                    step="0.1"
                    value={editingFact.weight}
                    onChange={(e) => setEditingFact({ ...editingFact, weight: parseFloat(e.target.value) })}
                  />
                </div>
              </div>
              <div className="modal-actions">
                <button className="btn-secondary" onClick={() => setEditingFact(null)}>Cancel</button>
                <button className="btn-primary" onClick={handleSaveEdit}>Save Changes</button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

const getWeightColor = (weight: number): string => {
  if (weight >= 0.8) return 'var(--primary)';
  if (weight >= 0.5) return 'var(--warning)';
  return 'var(--text-muted)';
};

// ============================================================================
// ADD PROFILE MODAL
// ============================================================================

interface AddProfileModalProps {
  isOpen: boolean;
  typeName: string;
  onClose: () => void;
  onAdd: (profileId: string, displayName: string) => Promise<void>;
}

const AddProfileModal: React.FC<AddProfileModalProps> = ({ 
  isOpen, 
  typeName, 
  onClose, 
  onAdd 
}) => {
  const [name, setName] = useState('');
  const [displayName, setDisplayName] = useState('');

  if (!isOpen) return null;

  const handleSubmit = async () => {
    if (name.trim()) {
      const profileId = `${typeName}.${name.trim().toLowerCase().replace(/\s+/g, '_')}`;
      await onAdd(profileId, displayName || name.trim());
      setName('');
      setDisplayName('');
      onClose();
    }
  };

  return (
    <div className="profile-modal-overlay" onClick={onClose}>
      <div className="profile-modal" onClick={(e) => e.stopPropagation()}>
        <h3>Add {typeName} Profile</h3>
        <div className="profile-modal-form">
          <input
            type="text"
            placeholder="Name (e.g. 'mom', 'john')"
            value={name}
            onChange={(e) => setName(e.target.value)}
            autoFocus
          />
          <input
            type="text"
            placeholder="Display Name (optional)"
            value={displayName}
            onChange={(e) => setDisplayName(e.target.value)}
          />
          <div style={{ color: 'var(--text-muted)', fontSize: '12px' }}>
            Profile ID: {typeName}.{name.trim().toLowerCase().replace(/\s+/g, '_') || '...'}
          </div>
          <div className="profile-modal-buttons">
            <button onClick={onClose}>Cancel</button>
            <button onClick={handleSubmit} disabled={!name.trim()}>
              Add Profile
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

// ============================================================================
// MAIN PAGE
// ============================================================================

const ProfilesPage: React.FC = () => {
  // State
  const [profileTypes, setProfileTypes] = useState<ProfileType[]>([]);
  const [profiles, setProfiles] = useState<Profile[]>([]);
  const [factTypes, setFactTypes] = useState<FactType[]>([]);
  const [facts, setFacts] = useState<Fact[]>([]);
  const [selectedType, setSelectedType] = useState('');
  const [selectedProfile, setSelectedProfile] = useState<string | null>(null);
  const [showAddModal, setShowAddModal] = useState(false);
  const [loading, setLoading] = useState(true);

  // Fetch all data
  const fetchData = useCallback(async () => {
    try {
      const [typesRes, profilesRes, factTypesRes] = await Promise.all([
        fetch(`${API}/types`),
        fetch(API),
        fetch(`${API}/fact-types`),
      ]);
      setProfileTypes(await typesRes.json());
      setProfiles(await profilesRes.json());
      setFactTypes(await factTypesRes.json());
    } catch (err) {
      console.error('Failed to fetch profiles data:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  // Fetch facts for selected profile
  const fetchFacts = useCallback(async (profileId: string) => {
    try {
      const res = await fetch(`${API}/${profileId}/facts`);
      setFacts(await res.json());
    } catch (err) {
      console.error('Failed to fetch facts:', err);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // Auto-select first profile if none selected
  useEffect(() => {
    if (!selectedProfile && profiles.length > 0) {
      const defaultProfile = profiles.find(p => p.profile_id === 'primary_user');
      setSelectedProfile(defaultProfile ? defaultProfile.profile_id : profiles[0].profile_id);
    }
  }, [profiles, selectedProfile]);

  useEffect(() => {
    if (selectedProfile) {
      fetchFacts(selectedProfile);
    } else {
      setFacts([]);
    }
  }, [selectedProfile, fetchFacts]);

  // Handlers
  const handleAddType = async (name: string) => {
    await fetch(`${API}/types`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ type_name: name }),
    });
    await fetchData();
  };

  const handleAddProfile = async (profileId: string, displayName: string) => {
    await fetch(API, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ profile_id: profileId, type_name: selectedType, display_name: displayName }),
    });
    await fetchData();
    setSelectedProfile(profileId);
  };

  const handleAddFactType = async (name: string) => {
    await fetch(`${API}/fact-types`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ fact_type: name }),
    });
    await fetchData();
  };

  const handleAddFact = async (fact: Partial<Fact>) => {
    await fetch(`${API}/facts`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(fact),
    });
    if (selectedProfile) {
      await fetchFacts(selectedProfile);
    }
  };

  const handleUpdateFact = async (profileId: string, key: string, updates: Partial<Fact>) => {
    // Update fact values (l1, l2, l3, fact_type)
    if (updates.l1_value !== undefined || updates.l2_value !== undefined || 
        updates.l3_value !== undefined || updates.fact_type !== undefined) {
      await fetch(`${API}/${profileId}/facts/${encodeURIComponent(key)}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          fact_type: updates.fact_type,
          l1_value: updates.l1_value,
          l2_value: updates.l2_value,
          l3_value: updates.l3_value,
          weight: updates.weight,
        }),
      });
    } else if (updates.weight !== undefined) {
      // Weight-only update uses PATCH endpoint
      await fetch(`${API}/${profileId}/facts/${encodeURIComponent(key)}/weight`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ weight: updates.weight }),
      });
    }
    if (selectedProfile) {
      await fetchFacts(selectedProfile);
    }
  };

  const handleDeleteFact = async (profileId: string, key: string) => {
    await fetch(`${API}/${profileId}/facts/${encodeURIComponent(key)}`, {
      method: 'DELETE',
    });
    if (selectedProfile) {
      await fetchFacts(selectedProfile);
    }
  };

  const currentProfile = profiles.find((p) => p.profile_id === selectedProfile) || null;

  const handleDeleteAllFacts = async () => {
    if (confirm('Delete ALL facts from ALL profiles? This cannot be undone.')) {
      await fetch(`${API}/all-facts`, { method: 'DELETE' });
      if (selectedProfile) await fetchFacts(selectedProfile);
    }
  };

  const handleDeleteAllProfiles = async () => {
    if (confirm('Delete ALL profiles and their facts? This cannot be undone.')) {
      await fetch(`${API}/all-profiles`, { method: 'DELETE' });
      setSelectedProfile(null);
      setFacts([]);
      await fetchData();
    }
  };

  const handleDeleteProfile = async (profileId: string) => {
    await fetch(`${API}/${profileId}`, { method: 'DELETE' });
    if (selectedProfile === profileId) {
      setSelectedProfile(null);
      setFacts([]);
    }
    await fetchData();
  };

  if (loading) {
    return (
      <div className="profiles-page-loading">
        Loading profiles...
      </div>
    );
  }

  return (
    <div className="profiles-page">
      <ProfileSidebar
        profileTypes={profileTypes}
        profiles={profiles}
        factTypes={factTypes}
        selectedType={selectedType}
        selectedProfile={selectedProfile}
        onTypeChange={setSelectedType}
        onProfileSelect={setSelectedProfile}
        onAddType={handleAddType}
        onAddProfile={() => setShowAddModal(true)}
        onDeleteProfile={handleDeleteProfile}
        onDeleteAllFacts={handleDeleteAllFacts}
        onDeleteAllProfiles={handleDeleteAllProfiles}
      />
      <ProfileView
        profile={currentProfile}
        facts={facts}
        factTypes={factTypes}
        onAddFact={handleAddFact}
        onUpdateFact={handleUpdateFact}
        onDeleteFact={handleDeleteFact}
        onAddFactType={handleAddFactType}
      />
      <AddProfileModal
        isOpen={showAddModal}
        typeName={selectedType}
        onClose={() => setShowAddModal(false)}
        onAdd={handleAddProfile}
      />
    </div>
  );
};

export default ProfilesPage;
