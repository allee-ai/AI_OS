"""Tests for sync_docs.py — checkbox merging and sync behavior."""
import pytest
import tempfile
from pathlib import Path

# Import helpers directly
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from scripts.sync_docs import (
    _extract_checkboxes,
    _merge_checkboxes,
    extract_section,
    update_doc_section,
    back_sync_checkboxes,
)


# ─── _extract_checkboxes ────────────────────────────────────────────

class TestExtractCheckboxes:
    def test_basic(self):
        text = "- [x] Done item\n- [ ] Todo item"
        result = _extract_checkboxes(text)
        assert result.get("Done item") is True
        assert result.get("Todo item") is False

    def test_nested_indent(self):
        text = "  - [x] Indented done\n  - [ ] Indented todo"
        result = _extract_checkboxes(text)
        assert result["Indented done"] is True
        assert result["Indented todo"] is False

    def test_bold_item(self):
        text = "- [x] **Loop Editor Dashboard** — Visual editor"
        result = _extract_checkboxes(text)
        assert result["**Loop Editor Dashboard** — Visual editor"] is True

    def test_no_checkboxes(self):
        text = "Just a normal line\n- bullet but no checkbox"
        assert _extract_checkboxes(text) == {}


# ─── _merge_checkboxes ──────────────────────────────────────────────

class TestMergeCheckboxes:
    def test_incoming_checked_stays_checked(self):
        incoming = "- [x] Item A\n- [ ] Item B"
        existing = "- [ ] Item A\n- [ ] Item B"
        result = _merge_checkboxes(incoming, existing)
        assert "- [x] Item A" in result
        assert "- [ ] Item B" in result

    def test_existing_checked_preserved(self):
        """If root doc has [x] but module still has [ ], result is [x]."""
        incoming = "- [ ] Item A\n- [ ] Item B"
        existing = "- [x] Item A\n- [ ] Item B"
        result = _merge_checkboxes(incoming, existing)
        assert "- [x] Item A" in result
        assert "- [ ] Item B" in result

    def test_both_checked(self):
        incoming = "- [x] Item A"
        existing = "- [x] Item A"
        result = _merge_checkboxes(incoming, existing)
        assert "- [x] Item A" in result

    def test_new_item_in_incoming(self):
        """New items from module README appear unchecked."""
        incoming = "- [ ] Old item\n- [ ] New item"
        existing = "- [x] Old item"
        result = _merge_checkboxes(incoming, existing)
        assert "- [x] Old item" in result
        assert "- [ ] New item" in result

    def test_non_checkbox_lines_preserved(self):
        incoming = "### Heading\n- [x] Item\nSome text"
        existing = ""
        result = _merge_checkboxes(incoming, existing)
        assert "### Heading" in result
        assert "Some text" in result

    def test_removed_from_incoming_disappears(self):
        """Items removed from module README don't appear (module is canonical for item list)."""
        incoming = "- [ ] Keep this"
        existing = "- [x] Keep this\n- [x] Old removed item"
        result = _merge_checkboxes(incoming, existing)
        assert "Keep this" in result
        assert "Old removed item" not in result


# ─── update_doc_section (integration) ───────────────────────────────

class TestUpdateDocSection:
    def test_merges_checkboxes_on_sync(self, tmp_path):
        # Root doc with a checked item
        root = tmp_path / "ROADMAP.md"
        root.write_text(
            "# Roadmap\n"
            "<!-- INCLUDE:mymod:ROADMAP -->\n"
            "- [x] Done thing\n"
            "- [ ] Todo thing\n"
            "<!-- /INCLUDE:mymod:ROADMAP -->\n"
        )

        # Module content: Done thing is unchecked (stale), but has new item
        module_content = "- [ ] Done thing\n- [ ] Todo thing\n- [ ] New feature"

        updated = update_doc_section(root, "ROADMAP", "mymod", module_content, "mymod")
        assert updated is True

        result = root.read_text()
        # Done thing should stay [x] (merged from root)
        assert "- [x] Done thing" in result
        # New feature should appear
        assert "- [ ] New feature" in result

    def test_idempotent_no_content_change(self, tmp_path):
        """Running sync twice with same content produces no second write."""
        root = tmp_path / "ROADMAP.md"
        root.write_text(
            "<!-- INCLUDE:mod:ROADMAP -->\n"
            "- [ ] Item\n"
            "<!-- /INCLUDE:mod:ROADMAP -->\n"
        )
        # First sync writes header + content
        updated1 = update_doc_section(root, "ROADMAP", "mod", "- [ ] Item", "mod")
        assert updated1 is True
        # Second sync with same content should be no-op
        updated2 = update_doc_section(root, "ROADMAP", "mod", "- [ ] Item", "mod")
        assert updated2 is False


# ─── back_sync_checkboxes ───────────────────────────────────────────

class TestBackSync:
    def test_back_sync_propagates_checks(self, tmp_path, monkeypatch):
        """[x] in root doc should propagate back to module README."""
        # Set up module README
        mod_dir = tmp_path / "mymod"
        mod_dir.mkdir()
        readme = mod_dir / "README.md"
        readme.write_text(
            "# MyMod\n"
            "<!-- ROADMAP:mymod -->\n"
            "- [ ] Feature A\n"
            "- [ ] Feature B\n"
            "<!-- /ROADMAP:mymod -->\n"
        )

        # Set up root ROADMAP with Feature A checked
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        roadmap = docs_dir / "ROADMAP.md"
        roadmap.write_text(
            "# Roadmap\n"
            "<!-- INCLUDE:mymod:ROADMAP -->\n"
            "- [x] Feature A\n"
            "- [ ] Feature B\n"
            "<!-- /INCLUDE:mymod:ROADMAP -->\n"
        )

        # Monkeypatch globals
        import scripts.sync_docs as sd
        monkeypatch.setattr(sd, "PROJECT_ROOT", tmp_path)
        monkeypatch.setattr(sd, "MODULES", [("mymod", "mymod", "MyMod")])
        monkeypatch.setattr(sd, "ROOT_DOCS", {"ROADMAP": roadmap})

        result = back_sync_checkboxes()
        assert result["total"] >= 1
        assert "mymod" in result["modules"]

        updated = readme.read_text()
        assert "- [x] Feature A" in updated
        assert "- [ ] Feature B" in updated

    def test_back_sync_never_unchecks(self, tmp_path, monkeypatch):
        """Back-sync must never change [x] → [ ] in module README."""
        mod_dir = tmp_path / "mymod"
        mod_dir.mkdir()
        readme = mod_dir / "README.md"
        readme.write_text(
            "# MyMod\n"
            "<!-- ROADMAP:mymod -->\n"
            "- [x] Already done\n"
            "<!-- /ROADMAP:mymod -->\n"
        )

        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        roadmap = docs_dir / "ROADMAP.md"
        roadmap.write_text(
            "<!-- INCLUDE:mymod:ROADMAP -->\n"
            "- [ ] Already done\n"
            "<!-- /INCLUDE:mymod:ROADMAP -->\n"
        )

        import scripts.sync_docs as sd
        monkeypatch.setattr(sd, "PROJECT_ROOT", tmp_path)
        monkeypatch.setattr(sd, "MODULES", [("mymod", "mymod", "MyMod")])
        monkeypatch.setattr(sd, "ROOT_DOCS", {"ROADMAP": roadmap})

        back_sync_checkboxes()
        updated = readme.read_text()
        assert "- [x] Already done" in updated  # must stay checked

    def test_back_sync_never_adds_lines(self, tmp_path, monkeypatch):
        """Back-sync must never add new items to module READMEs."""
        mod_dir = tmp_path / "mymod"
        mod_dir.mkdir()
        readme = mod_dir / "README.md"
        original = (
            "# MyMod\n"
            "<!-- ROADMAP:mymod -->\n"
            "- [ ] Only item\n"
            "<!-- /ROADMAP:mymod -->\n"
        )
        readme.write_text(original)

        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        roadmap = docs_dir / "ROADMAP.md"
        roadmap.write_text(
            "<!-- INCLUDE:mymod:ROADMAP -->\n"
            "- [ ] Only item\n"
            "- [x] Extra root item\n"
            "<!-- /INCLUDE:mymod:ROADMAP -->\n"
        )

        import scripts.sync_docs as sd
        monkeypatch.setattr(sd, "PROJECT_ROOT", tmp_path)
        monkeypatch.setattr(sd, "MODULES", [("mymod", "mymod", "MyMod")])
        monkeypatch.setattr(sd, "ROOT_DOCS", {"ROADMAP": roadmap})

        back_sync_checkboxes()
        updated = readme.read_text()
        assert "Extra root item" not in updated  # never added
        # Only the original checkbox item, no new lines inserted
        lines_with_checkbox = [l for l in updated.splitlines() if l.strip().startswith("- [")]
        assert len(lines_with_checkbox) == 1
