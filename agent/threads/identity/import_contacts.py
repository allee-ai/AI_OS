"""
Import Contacts (vCard)
=======================
Imports contacts from vCard (.vcf) files into identity profiles.

Supports vCard 2.1, 3.0, and 4.0 formats exported from:
- Google Contacts
- iCloud
- Outlook
- Any standard contacts app
"""

import re
import uuid
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field

# vobject handles vCard parsing with all the quirks (folding, encoding, etc.)
import vobject


@dataclass
class ParsedContact:
    """A contact parsed from a vCard file."""
    identifier: str
    full_name: str
    given_name: str = ""
    family_name: str = ""
    emails: List[str] = field(default_factory=list)
    phones: List[str] = field(default_factory=list)
    organization: str = ""
    job_title: str = ""
    note: str = ""
    birthday: Optional[str] = None


def slugify(name: str) -> str:
    """Convert name to valid profile_id slug."""
    slug = name.lower().strip()
    slug = re.sub(r'[^a-z0-9]+', '_', slug)
    slug = slug.strip('_')
    return slug or "contact"


# Storage for pending imports (in-memory, cleared on server restart)
_pending_uploads: Dict[str, Dict[str, Any]] = {}


def parse_vcard_file(file_content: str) -> List[ParsedContact]:
    """
    Parse vCard file content into ParsedContact objects.
    
    Args:
        file_content: Raw vCard file content (can contain multiple vCards)
        
    Returns:
        List of ParsedContact objects
    """
    contacts = []
    
    # vobject.readComponents handles multi-contact vcf files
    # Wrap in try-except to handle malformed vCard files gracefully
    try:
        components = list(vobject.readComponents(file_content))
    except Exception:
        # If vobject can't parse at all, return empty list
        return contacts
    
    for vcard in components:
        try:
            contact = _parse_single_vcard(vcard)
            if contact:
                contacts.append(contact)
        except Exception:
            # Skip malformed contacts
            continue
    
    return contacts


def _parse_single_vcard(vcard) -> Optional[ParsedContact]:
    """Parse a single vCard component into a ParsedContact."""
    
    # Get name - try FN (formatted name) first, then N (structured name)
    full_name = ""
    given_name = ""
    family_name = ""
    
    if hasattr(vcard, 'fn'):
        full_name = str(vcard.fn.value).strip()
    
    if hasattr(vcard, 'n'):
        n = vcard.n.value
        given_name = str(n.given) if n.given else ""
        family_name = str(n.family) if n.family else ""
        if not full_name:
            full_name = f"{given_name} {family_name}".strip()
    
    # Skip if no name
    if not full_name:
        return None
    
    # Extract emails
    emails = []
    if hasattr(vcard, 'email'):
        # Handle single or multiple emails
        email_objs = vcard.contents.get('email', [])
        for email_obj in email_objs:
            email = str(email_obj.value).strip()
            if email and '@' in email:
                emails.append(email)
    
    # Extract phones
    phones = []
    if hasattr(vcard, 'tel'):
        tel_objs = vcard.contents.get('tel', [])
        for tel_obj in tel_objs:
            phone = str(tel_obj.value).strip()
            if phone:
                phones.append(phone)
    
    # Organization
    organization = ""
    if hasattr(vcard, 'org'):
        org_val = vcard.org.value
        if isinstance(org_val, list):
            organization = org_val[0] if org_val else ""
        else:
            organization = str(org_val)
    
    # Job title
    job_title = ""
    if hasattr(vcard, 'title'):
        job_title = str(vcard.title.value).strip()
    
    # Note
    note = ""
    if hasattr(vcard, 'note'):
        note = str(vcard.note.value).strip()
    
    # Birthday
    birthday = None
    if hasattr(vcard, 'bday'):
        bday = str(vcard.bday.value).strip()
        # Normalize various date formats to YYYY-MM-DD or MM-DD
        if bday:
            # Remove dashes for re-formatting
            bday_clean = bday.replace('-', '').replace('/', '')
            if len(bday_clean) == 8:  # YYYYMMDD
                birthday = f"{bday_clean[:4]}-{bday_clean[4:6]}-{bday_clean[6:]}"
            elif len(bday_clean) == 4:  # MMDD
                birthday = f"{bday_clean[:2]}-{bday_clean[2:]}"
            else:
                birthday = bday  # Keep original
    
    return ParsedContact(
        identifier=str(uuid.uuid4()),
        full_name=full_name,
        given_name=given_name,
        family_name=family_name,
        emails=emails,
        phones=phones,
        organization=organization,
        job_title=job_title,
        note=note,
        birthday=birthday,
    )


def store_upload(file_content: str, filename: str) -> str:
    """
    Store uploaded file content for later parsing.
    
    Args:
        file_content: Raw vCard file content
        filename: Original filename
        
    Returns:
        upload_id for retrieving the upload
    """
    upload_id = str(uuid.uuid4())
    _pending_uploads[upload_id] = {
        "content": file_content,
        "filename": filename,
        "parsed": None,
    }
    return upload_id


def parse_upload(upload_id: str) -> Dict[str, Any]:
    """
    Parse a previously uploaded file.
    
    Args:
        upload_id: ID from store_upload
        
    Returns:
        Preview dict with contacts list
        
    Raises:
        ValueError: If upload_id not found
    """
    if upload_id not in _pending_uploads:
        raise ValueError(f"Upload not found: {upload_id}")
    
    upload = _pending_uploads[upload_id]
    
    # Parse if not already parsed
    if upload["parsed"] is None:
        contacts = parse_vcard_file(upload["content"])
        upload["parsed"] = contacts
    
    contacts = upload["parsed"]
    
    # Return preview format
    return {
        "upload_id": upload_id,
        "total_contacts": len(contacts),
        "contacts": [
            {
                "id": c.identifier,
                "full_name": c.full_name,
                "email": c.emails[0] if c.emails else None,
                "phone": c.phones[0] if c.phones else None,
                "organization": c.organization or None,
            }
            for c in contacts[:20]  # Preview first 20
        ]
    }


def commit_import(
    upload_id: str,
    selected_ids: Optional[List[str]] = None,
    type_name: str = "contact",
    skip_existing: bool = True
) -> Dict[str, Any]:
    """
    Commit a parsed upload to identity profiles.
    
    Args:
        upload_id: ID from store_upload
        selected_ids: Only import these contact IDs (None = all)
        type_name: Profile type to use
        skip_existing: Skip contacts with matching names
        
    Returns:
        Import summary
    """
    if upload_id not in _pending_uploads:
        raise ValueError(f"Upload not found: {upload_id}")
    
    upload = _pending_uploads[upload_id]
    
    # Parse if needed
    if upload["parsed"] is None:
        upload["parsed"] = parse_vcard_file(upload["content"])
    
    contacts = upload["parsed"]
    
    # Filter to selected if provided
    if selected_ids:
        selected_set = set(selected_ids)
        contacts = [c for c in contacts if c.identifier in selected_set]
    
    # Import to identity
    result = import_contacts_to_identity(
        contacts=contacts,
        type_name=type_name,
        skip_existing=skip_existing
    )
    
    # Clean up
    del _pending_uploads[upload_id]
    
    return result


def import_contacts_to_identity(
    contacts: List[ParsedContact],
    type_name: str = "contact",
    skip_existing: bool = True
) -> Dict[str, Any]:
    """
    Import parsed contacts into identity profiles.
    
    Args:
        contacts: List of ParsedContact objects
        type_name: Profile type to use (default: "contact")
        skip_existing: Whether to skip contacts that already exist
        
    Returns:
        Summary dict with imported/skipped/failed counts
    """
    from .schema import (
        create_profile_type, create_profile, push_profile_fact,
        get_profiles, get_profile_types
    )
    
    # Ensure contact type exists
    existing_types = [t["type_name"] for t in get_profile_types()]
    if type_name not in existing_types:
        create_profile_type(
            type_name=type_name,
            trust_level=3,
            context_priority=1,
            can_edit=True,
            description="Imported contact"
        )
    
    existing_profiles = {p["profile_id"] for p in get_profiles()}
    existing_names = {p["display_name"].lower() for p in get_profiles()}
    
    imported = 0
    skipped = 0
    failed = 0
    results = []
    
    for contact in contacts:
        try:
            # Check for existing by name
            if skip_existing and contact.full_name.lower() in existing_names:
                skipped += 1
                results.append({"name": contact.full_name, "status": "skipped"})
                continue
            
            # Generate profile_id from name
            base_id = slugify(contact.full_name)
            profile_id = base_id
            
            # Handle duplicates by appending number
            counter = 1
            while profile_id in existing_profiles:
                profile_id = f"{base_id}_{counter}"
                counter += 1
            
            # Create profile
            create_profile(
                profile_id=profile_id,
                type_name=type_name,
                display_name=contact.full_name
            )
            existing_profiles.add(profile_id)
            existing_names.add(contact.full_name.lower())
            
            # Push facts (L1 values only - brief)
            if contact.full_name:
                push_profile_fact(
                    profile_id=profile_id,
                    key="name",
                    fact_type="name",
                    l1_value=contact.full_name,
                    l2_value=contact.full_name,
                    weight=0.9
                )
            
            if contact.emails:
                push_profile_fact(
                    profile_id=profile_id,
                    key="email",
                    fact_type="email",
                    l1_value=contact.emails[0],
                    l2_value=", ".join(contact.emails) if len(contact.emails) > 1 else contact.emails[0],
                    weight=0.7
                )
            
            if contact.phones:
                push_profile_fact(
                    profile_id=profile_id,
                    key="phone",
                    fact_type="phone",
                    l1_value=contact.phones[0],
                    l2_value=", ".join(contact.phones) if len(contact.phones) > 1 else contact.phones[0],
                    weight=0.6
                )
            
            if contact.organization:
                push_profile_fact(
                    profile_id=profile_id,
                    key="organization",
                    fact_type="organization",
                    l1_value=contact.organization,
                    weight=0.5
                )
            
            if contact.job_title:
                push_profile_fact(
                    profile_id=profile_id,
                    key="occupation",
                    fact_type="occupation",
                    l1_value=contact.job_title,
                    weight=0.6
                )
            
            if contact.birthday:
                push_profile_fact(
                    profile_id=profile_id,
                    key="birthday",
                    fact_type="birthday",
                    l1_value=contact.birthday,
                    weight=0.4
                )
            
            if contact.note:
                push_profile_fact(
                    profile_id=profile_id,
                    key="notes",
                    fact_type="note",
                    l1_value=contact.note[:100] if len(contact.note) > 100 else contact.note,
                    l2_value=contact.note,
                    weight=0.3
                )
            
            imported += 1
            results.append({
                "name": contact.full_name,
                "profile_id": profile_id,
                "status": "imported"
            })
                
        except Exception as e:
            failed += 1
            results.append({
                "name": contact.full_name,
                "status": "failed",
                "error": str(e)
            })
    
    return {
        "imported": imported,
        "skipped": skipped,
        "failed": failed,
        "total": len(contacts),
        "results": results
    }


__all__ = [
    'ParsedContact',
    'parse_vcard_file',
    'store_upload',
    'parse_upload',
    'commit_import',
    'import_contacts_to_identity',
]
