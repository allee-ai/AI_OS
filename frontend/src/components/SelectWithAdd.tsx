/**
 * SelectWithAdd - Custom styled dropdown with "Add New" option.
 * Uses a custom dropdown instead of native select for full theme control.
 */

import React, { useState, useRef, useEffect } from 'react';

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
  const [isOpen, setIsOpen] = useState(false);
  const [isAdding, setIsAdding] = useState(false);
  const [newValue, setNewValue] = useState('');
  const containerRef = useRef<HTMLDivElement>(null);

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleSelect = (val: string) => {
    if (val === '__add_new__') {
      setIsAdding(true);
      setIsOpen(false);
    } else {
      onChange(val);
      setIsOpen(false);
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

  const selectedLabel = options.find(o => o.value === value)?.label || placeholder;

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
            borderRadius: '6px',
            border: '1px solid var(--border)',
            background: 'var(--surface)',
            color: 'var(--text)',
            fontSize: '13px',
          }}
        />
        <button
          onClick={handleAdd}
          style={{
            padding: '6px 10px',
            background: 'var(--primary)',
            color: '#fff',
            border: 'none',
            borderRadius: '6px',
            cursor: 'pointer',
          }}
        >
          ✓
        </button>
        <button
          onClick={handleCancel}
          style={{
            padding: '6px 10px',
            background: 'var(--surface)',
            color: 'var(--text-muted)',
            border: '1px solid var(--border)',
            borderRadius: '6px',
            cursor: 'pointer',
          }}
        >
          ✕
        </button>
      </div>
    );
  }

  return (
    <div ref={containerRef} style={{ position: 'relative', width: '100%' }}>
      {/* Trigger button */}
      <button
        type="button"
        onClick={() => !disabled && setIsOpen(!isOpen)}
        disabled={disabled}
        style={{
          width: '100%',
          padding: '8px 32px 8px 12px',
          borderRadius: '6px',
          border: '1px solid var(--border)',
          background: 'var(--surface)',
          color: value ? 'var(--text)' : 'var(--text-muted)',
          fontSize: '13px',
          cursor: disabled ? 'not-allowed' : 'pointer',
          textAlign: 'left',
          position: 'relative',
          opacity: disabled ? 0.5 : 1,
        }}
      >
        {selectedLabel}
        <span style={{
          position: 'absolute',
          right: '10px',
          top: '50%',
          transform: `translateY(-50%) rotate(${isOpen ? '180deg' : '0deg'})`,
          transition: 'transform 0.15s ease',
          color: 'var(--text-muted)',
          fontSize: '10px',
        }}>
          ▼
        </span>
      </button>

      {/* Dropdown */}
      {isOpen && (
        <div style={{
          position: 'absolute',
          top: '100%',
          left: 0,
          right: 0,
          marginTop: '4px',
          background: 'var(--surface)',
          border: '1px solid var(--border)',
          borderRadius: '6px',
          boxShadow: '0 4px 12px rgba(0,0,0,0.3)',
          zIndex: 1000,
          maxHeight: '200px',
          overflowY: 'auto',
        }}>
          {options.map((opt) => (
            <div
              key={opt.value}
              onClick={() => handleSelect(opt.value)}
              style={{
                padding: '8px 12px',
                cursor: 'pointer',
                background: opt.value === value ? 'var(--primary)' : 'transparent',
                color: opt.value === value ? '#fff' : 'var(--text)',
                fontSize: '13px',
                transition: 'background 0.1s',
              }}
              onMouseEnter={(e) => {
                if (opt.value !== value) {
                  e.currentTarget.style.background = 'var(--bg)';
                }
              }}
              onMouseLeave={(e) => {
                if (opt.value !== value) {
                  e.currentTarget.style.background = 'transparent';
                }
              }}
            >
              {opt.label}
            </div>
          ))}
          {/* Add new option */}
          <div
            onClick={() => handleSelect('__add_new__')}
            style={{
              padding: '8px 12px',
              cursor: 'pointer',
              background: 'transparent',
              color: 'var(--text-muted)',
              fontSize: '13px',
              fontStyle: 'italic',
              borderTop: '1px solid var(--border)',
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = 'var(--bg)';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = 'transparent';
            }}
          >
            ➕ {addNewLabel}
          </div>
        </div>
      )}
    </div>
  );
};

export default SelectWithAdd;
