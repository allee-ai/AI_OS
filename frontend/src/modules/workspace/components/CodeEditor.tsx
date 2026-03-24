import React, { useRef, useEffect } from 'react';
import { EditorView, keymap, lineNumbers, highlightActiveLine, highlightActiveLineGutter } from '@codemirror/view';
import { EditorState } from '@codemirror/state';
import { defaultKeymap, indentWithTab, history, historyKeymap } from '@codemirror/commands';
import { syntaxHighlighting, defaultHighlightStyle, bracketMatching, foldGutter, indentOnInput } from '@codemirror/language';
import { oneDark } from '@codemirror/theme-one-dark';

// Language imports
import { javascript } from '@codemirror/lang-javascript';
import { python } from '@codemirror/lang-python';
import { html } from '@codemirror/lang-html';
import { css } from '@codemirror/lang-css';
import { json } from '@codemirror/lang-json';
import { markdown } from '@codemirror/lang-markdown';
import { sql } from '@codemirror/lang-sql';
import { xml } from '@codemirror/lang-xml';
import { yaml } from '@codemirror/lang-yaml';

interface CodeEditorProps {
  value: string;
  onChange: (value: string) => void;
  language?: string | null;
  readOnly?: boolean;
}

function getLanguageExtension(lang: string | null | undefined) {
  switch (lang) {
    case 'python': return python();
    case 'javascript': return javascript();
    case 'typescript': return javascript({ typescript: true });
    case 'jsx': return javascript({ jsx: true });
    case 'tsx': return javascript({ jsx: true, typescript: true });
    case 'html': return html();
    case 'css': return css();
    case 'json': return json();
    case 'markdown': return markdown();
    case 'sql': return sql();
    case 'xml': return xml();
    case 'yaml': return yaml();
    case 'shell': case 'bash': return null; // No built-in shell lang
    default: return null;
  }
}

export const CodeEditor: React.FC<CodeEditorProps> = ({ value, onChange, language, readOnly }) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const viewRef = useRef<EditorView | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;

    const extensions = [
      lineNumbers(),
      highlightActiveLine(),
      highlightActiveLineGutter(),
      bracketMatching(),
      foldGutter(),
      indentOnInput(),
      history(),
      syntaxHighlighting(defaultHighlightStyle, { fallback: true }),
      oneDark,
      keymap.of([...defaultKeymap, ...historyKeymap, indentWithTab]),
      EditorView.updateListener.of((update) => {
        if (update.docChanged) {
          onChange(update.state.doc.toString());
        }
      }),
    ];

    if (readOnly) {
      extensions.push(EditorState.readOnly.of(true));
    }

    const langExt = getLanguageExtension(language);
    if (langExt) extensions.push(langExt);

    // Tab size
    extensions.push(EditorState.tabSize.of(4));

    const state = EditorState.create({ doc: value, extensions });
    const view = new EditorView({ state, parent: containerRef.current });
    viewRef.current = view;

    return () => {
      view.destroy();
      viewRef.current = null;
    };
    // Only recreate on language change, not on every value change
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [language, readOnly]);

  // Sync external value changes (e.g. opening a different file)
  useEffect(() => {
    const view = viewRef.current;
    if (!view) return;
    const current = view.state.doc.toString();
    if (current !== value) {
      view.dispatch({
        changes: { from: 0, to: current.length, insert: value },
      });
    }
  }, [value]);

  return <div ref={containerRef} className="code-editor-container" />;
};
