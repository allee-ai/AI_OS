/**
 * SelectWithAdd - Reusable dropdown with "Add New" option.
 */

import React, { useState } from 'react';

interface Option {
  value: string;
  label: string;
}

interface SelectWithAddProps {
  options: Option[];
  value: string;
  onChange: (value: string) => void;
  onAddNew: (value: string) => Promise<void>;
  placeholder?: string;
  addNewLabel?: string;
  disabled?: boolean;
}

export const SelectWithAdd: React.FC<SelectWithAddProps> = ({
  options,
  value,
  onChange,
  onAddNew,
  placeholder = 'Select...',
  addNewLabel = 'Add new...',
  disabled = false,
}) => {
  const [isAdding, setIsAdding] = useState(false);
  const [newValue, setNewValue] = useState('');

  const handleChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const val = e.target.value;
    if (val === '__add_new__') {
      setIsAdding(true);
    } else {
      onChange(val);
    }
  };

  const handleAdd = async () => {
    if (newValue.trim()) {
      await onAddNew(newValue.trim());
      onChange(newValue.trim());
      setNewValue('');
      setIsAdding(false);
    }
  };

  const handleCancel = () => {
    setNewValue('');
    setIsAdding(false);
  };

  if (isAdding) {
    return (
      <div style={{ display: 'flex', gap: '4px' }}>
        <input
          type="text"
          value={newValue}
          onChange={(e) => setNewValue(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') handleAdd();
            if (e.key === 'Escape') handleCancel();
          }}
          placeholder="Enter name..."
          autoFocus
          style={{
            flex: 1,
            padding: '6px 8px',
            borderRadius: '4px',
            border: '1px solid #444',
            background: '#1e1e1e',
            color: '#fff',
            fontSize: '13px',
          }}
        />
        <button
          onClick={handleAdd}
          style={{
            padding: '6px 10px',
            background: '#4CAF50',
            color: '#fff',
            border: 'none',
            borderRadius: '4px',
            cursor: 'pointer',
          }}
        >
          ✓
        </button>
        <button
          onClick={handleCancel}
          style={{
            padding: '6px 10px',
            background: '#666',
            color: '#fff',
            border: 'none',
            borderRadius: '4px',
            cursor: 'pointer',
          }}
        >
          ✕
        </button>
      </div>
    );
  }

  return (
    <select
      value={value}
      onChange={handleChange}
      disabled={disabled}
      style={{
        width: '100%',
        padding: '8px',
        borderRadius: '4px',
        border: '1px solid #444',
        background: '#1e1e1e',
        color: '#fff',
        fontSize: '13px',
        cursor: 'pointer',
      }}
    >
      <option value="" disabled>
        {placeholder}
      </option>
      {options.map((opt) => (
        <option key={opt.value} value={opt.value}>
          {opt.label}
        </option>
      ))}
      <option value="__add_new__" style={{ fontStyle: 'italic', color: '#888' }}>
        ➕ {addNewLabel}
      </option>
    </select>
  );
};

export default SelectWithAdd;
