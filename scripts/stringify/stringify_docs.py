"""
Stringify Agent - Collect all .md files and combine into a single string.
"""

import os
from pathlib import Path


def stringify_docs(root_dir: str = None, output_dir: str = None) -> str:
    """
    Collect all .md files from the project directory and combine them into a single string.
    
    Args:
        root_dir: Root directory to search for .md files. Defaults to project root.
        output_dir: Directory to save output. Defaults to 'stringify' folder.
    
    Returns:
        The combined string of all markdown files.
    """
    # Default to project root (parent of stringify folder)
    if root_dir is None:
        root_dir = Path(__file__).parent.parent
    else:
        root_dir = Path(root_dir)
    
    # Default output directory
    if output_dir is None:
        output_dir = Path(__file__).parent
    else:
        output_dir = Path(output_dir)
    
    # Ensure output directory exists
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Collect all .md files
    md_files = []
    for md_file in root_dir.rglob("*.md"):
        # Skip files in stringify folder to avoid recursion
        if "stringify" in md_file.parts:
            continue
        # Skip node_modules and other common ignored directories
        skip_dirs = {"node_modules", ".git", "__pycache__", "venv", ".venv", "dist", "build"}
        if any(skip_dir in md_file.parts for skip_dir in skip_dirs):
            continue
        md_files.append(md_file)
    
    # Sort files for consistent output
    md_files.sort()
    
    # Build the combined string
    sections = []
    for md_file in md_files:
        relative_path = md_file.relative_to(root_dir)
        try:
            content = md_file.read_text(encoding="utf-8")
        except Exception as e:
            content = f"[Error reading file: {e}]"
        
        section = f"""
{'='*80}
FILE: {relative_path}
{'='*80}

{content}
"""
        sections.append(section)
    
    # Combine all sections
    doc_string = f"""# Agent Documentation - Combined String
# Generated: {__import__('datetime').datetime.now().isoformat()}
# Total files: {len(md_files)}

{''.join(sections)}
"""
    
    # Save to docs_string.txt
    output_file = output_dir / "docs_string.txt"
    output_file.write_text(doc_string, encoding="utf-8")
    
    print(f"🌀 Collected {len(md_files)} markdown files")
    print(f"📄 Output saved to: {output_file}")
    print(f"📊 Total size: {len(doc_string):,} characters")
    
    return doc_string


def list_md_files(root_dir: str = None) -> list:
    """List all .md files that would be collected."""
    if root_dir is None:
        root_dir = Path(__file__).parent.parent
    else:
        root_dir = Path(root_dir)
    
    md_files = []
    skip_dirs = {"node_modules", ".git", "__pycache__", "venv", ".venv", "dist", "build", "stringify"}
    
    for md_file in root_dir.rglob("*.md"):
        if any(skip_dir in md_file.parts for skip_dir in skip_dirs):
            continue
        md_files.append(md_file.relative_to(root_dir))
    
    return sorted(md_files)


if __name__ == "__main__":
    # When run directly, execute the stringify function
    print("🔍 Searching for markdown files...")
    
    # Show what will be collected
    files = list_md_files()
    print(f"\nFound {len(files)} markdown files:")
    for f in files:
        print(f"  - {f}")
    
    print("\n📝 Combining files...")
    result = stringify_docs()
    
    print("\n✨ Done!")
