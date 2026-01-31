/**
 * Philosophy ProfilesPage - Profile Manager for Philosophy thread.
 * User-defined profile types, profiles, and stances with visible weights.
 */

import React, { useState, useEffect, useCallback } from 'react';
import SelectWithAdd from '../components/SelectWithAdd';
import './ProfilesPage.css';

const API = '/api/philosophy';

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
  priority?: number;
  description?: string;
  protected?: boolean;
}

interface FactType {
  fact_type: string;
  description: string;
  default_weight: number;
}

interface Stance {
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
  onDeleteAllStances: () => void;
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
  onDeleteAllStances,
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
                  {p.type_name} • priority: {p.priority || 0}
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
          <button onClick={onDeleteAllStances}>
            🗑️ Clear All Stances
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
  stances: Stance[];
  factTypes: FactType[];
  onAddStance: (stance: Partial<Stance>) => Promise<void>;
  onUpdateStance: (profileId: string, key: string, updates: Partial<Stance>) => Promise<void>;
  onDeleteStance: (profileId: string, key: string) => Promise<void>;
  onAddFactType: (name: string) => Promise<void>;
}

const ProfileView: React.FC<ProfileViewProps> = ({
  profile,
  stances,
  factTypes,
  onAddStance,
  onUpdateStance,
  onDeleteStance,
  onAddFactType,
}) => {
  const [newStance, setNewStance] = useState({ 
    key: '', 
    l1_value: '', 
    l2_value: '', 
    l3_value: '', 
    fact_type: 'value', 
    weight: 0.5 
  });
  const [editingWeight, setEditingWeight] = useState<string | null>(null);
  const [contextLevel, setContextLevel] = useState<1 | 2 | 3>(2);

  if (!profile) {
    return (
      <div className="profile-view-empty">
        <div className="profile-view-empty-content">
          <div className="profile-view-empty-icon">🧭</div>
          <div>Select a profile to view and edit stances</div>
        </div>
      </div>
    );
  }

  const handleAddStance = async () => {
    if (newStance.key && (newStance.l1_value || newStance.l2_value || newStance.l3_value)) {
      await onAddStance({
        profile_id: profile.profile_id,
        ...newStance,
      });
      setNewStance({ key: '', l1_value: '', l2_value: '', l3_value: '', fact_type: 'value', weight: 0.5 });
    }
  };

  return (
    <div className="profile-view">
      {/* Profile Header */}
      <div className="profile-header">
        <h2>{profile.display_name}</h2>
        <div className="profile-header-meta">
          {profile.type_name} • Priority: {profile.priority || 0}
          {profile.description && ` • ${profile.description}`}
        </div>
      </div>

      {/* Add New Stance Form */}
      <div className="add-fact-form">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <h3>Add New Stance</h3>
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
            placeholder="Key (e.g. 'privacy')"
            value={newStance.key}
            onChange={(e) => setNewStance({ ...newStance, key: e.target.value })}
          />
          {contextLevel === 1 && (
            <textarea
              placeholder="L1: Brief (~10 tokens)"
              value={newStance.l1_value}
              onChange={(e) => setNewStance({ ...newStance, l1_value: e.target.value })}
              rows={3}
              style={{ gridColumn: '1 / -1' }}
            />
          )}
          {contextLevel === 2 && (
            <textarea
              placeholder="L2: Standard (~50 tokens)"
              value={newStance.l2_value}
              onChange={(e) => setNewStance({ ...newStance, l2_value: e.target.value })}
              rows={3}
              style={{ gridColumn: '1 / -1' }}
            />
          )}
          {contextLevel === 3 && (
            <textarea
              placeholder="L3: Full detail (~200 tokens)"
              value={newStance.l3_value}
              onChange={(e) => setNewStance({ ...newStance, l3_value: e.target.value })}
              rows={3}
              style={{ gridColumn: '1 / -1' }}
            />
          )}
          <SelectWithAdd
            options={factTypes.map((t) => ({ value: t.fact_type, label: t.fact_type }))}
            value={newStance.fact_type}
            onChange={(v) => setNewStance({ ...newStance, fact_type: v })}
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
              value={newStance.weight}
              onChange={(e) => setNewStance({ ...newStance, weight: parseFloat(e.target.value) })}
              style={{ width: '50px' }}
            />
            <span style={{ fontSize: '11px', width: '28px' }}>
              {newStance.weight.toFixed(1)}
            </span>
          </div>
          <button
            onClick={handleAddStance}
            disabled={!newStance.key || (!newStance.l1_value && !newStance.l2_value && !newStance.l3_value)}
          >
            Add
          </button>
        </div>
      </div>

      {/* Stances Table */}
      <div className="facts-header">
        <h3>Stances</h3>
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
          <span className="facts-count">{stances.length} items</span>
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
          {stances.map((stance) => (
            <tr key={stance.key}>
              <td>
                <span className="fact-key">{stance.key}</span>
              </td>
              <td className="fact-value">
                {contextLevel === 1 && (stance.l1_value || <span style={{ color: 'var(--text-muted)', fontStyle: 'italic' }}>No L1 value</span>)}
                {contextLevel === 2 && (stance.l2_value || <span style={{ color: 'var(--text-muted)', fontStyle: 'italic' }}>No L2 value</span>)}
                {contextLevel === 3 && (stance.l3_value || <span style={{ color: 'var(--text-muted)', fontStyle: 'italic' }}>No L3 value</span>)}
              </td>
              <td>
                <span className="fact-type-badge">{stance.fact_type}</span>
              </td>
              <td>
                {editingWeight === stance.key ? (
                  <div className="fact-weight-container">
                    <input
                      type="range"
                      min="0"
                      max="1"
                      step="0.1"
                      defaultValue={stance.weight}
                      onBlur={(e) => {
                        onUpdateStance(stance.profile_id, stance.key, {
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
                    onClick={() => setEditingWeight(stance.key)}
                    className="fact-weight-container"
                    style={{ cursor: 'pointer' }}
                    title="Click to edit weight"
                  >
                    <div className="fact-weight-bar">
                      <div
                        className="fact-weight-fill"
                        style={{
                          width: `${stance.weight * 100}%`,
                          background: getWeightColor(stance.weight),
                        }}
                      />
                    </div>
                    <span className="fact-weight-text">{stance.weight.toFixed(2)}</span>
                  </div>
                )}
              </td>
              <td style={{ textAlign: 'center', fontSize: '12px', color: 'var(--text-muted)' }}>
                {stance.access_count}
              </td>
              <td>
                <button
                  onClick={() => onDeleteStance(stance.profile_id, stance.key)}
                  className="fact-actions delete-btn"
                  title="Delete stance"
                  style={{ background: 'transparent', border: 'none', cursor: 'pointer', padding: '4px' }}
                >
                  🗑️
                </button>
              </td>
            </tr>
          ))}
          {stances.length === 0 && (
            <tr>
              <td colSpan={6} style={{ textAlign: 'center', color: 'var(--text-muted)', padding: '24px' }}>
                No stances yet. Add one above!
              </td>
            </tr>
          )}
        </tbody>
      </table>
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
            placeholder="Name (e.g. 'ethics', 'privacy')"
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
  const [stances, setStances] = useState<Stance[]>([]);
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

  // Fetch stances for selected profile
  const fetchStances = useCallback(async (profileId: string) => {
    try {
      const res = await fetch(`${API}/${profileId}/facts`);
      setStances(await res.json());
    } catch (err) {
      console.error('Failed to fetch stances:', err);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // Auto-select first profile if none selected
  useEffect(() => {
    if (!selectedProfile && profiles.length > 0) {
      const defaultProfile = profiles.find(p => p.profile_id === 'core.values');
      setSelectedProfile(defaultProfile ? defaultProfile.profile_id : profiles[0].profile_id);
    }
  }, [profiles, selectedProfile]);

  useEffect(() => {
    if (selectedProfile) {
      fetchStances(selectedProfile);
    } else {
      setStances([]);
    }
  }, [selectedProfile, fetchStances]);

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

  const handleAddStance = async (stance: Partial<Stance>) => {
    await fetch(`${API}/facts`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(stance),
    });
    if (selectedProfile) {
      await fetchStances(selectedProfile);
    }
  };

  const handleUpdateStance = async (profileId: string, key: string, updates: Partial<Stance>) => {
    if (updates.weight !== undefined) {
      await fetch(`${API}/${profileId}/facts/${encodeURIComponent(key)}/weight`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ weight: updates.weight }),
      });
    }
    if (selectedProfile) {
      await fetchStances(selectedProfile);
    }
  };

  const handleDeleteStance = async (profileId: string, key: string) => {
    await fetch(`${API}/${profileId}/facts/${encodeURIComponent(key)}`, {
      method: 'DELETE',
    });
    if (selectedProfile) {
      await fetchStances(selectedProfile);
    }
  };

  const currentProfile = profiles.find((p) => p.profile_id === selectedProfile) || null;

  const handleDeleteAllStances = async () => {
    if (confirm('Delete ALL stances from ALL profiles? This cannot be undone.')) {
      await fetch(`${API}/all-facts`, { method: 'DELETE' });
      if (selectedProfile) await fetchStances(selectedProfile);
    }
  };

  const handleDeleteAllProfiles = async () => {
    if (confirm('Delete ALL profiles and their stances? This cannot be undone.')) {
      await fetch(`${API}/all-profiles`, { method: 'DELETE' });
      setSelectedProfile(null);
      setStances([]);
      await fetchData();
    }
  };

  const handleDeleteProfile = async (profileId: string) => {
    await fetch(`${API}/${profileId}`, { method: 'DELETE' });
    if (selectedProfile === profileId) {
      setSelectedProfile(null);
      setStances([]);
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
        onDeleteAllStances={handleDeleteAllStances}
        onDeleteAllProfiles={handleDeleteAllProfiles}
      />
      <ProfileView
        profile={currentProfile}
        stances={stances}
        factTypes={factTypes}
        onAddStance={handleAddStance}
        onUpdateStance={handleUpdateStance}
        onDeleteStance={handleDeleteStance}
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
