"""
Import Contacts (macOS)
=======================
Imports contacts from macOS Contacts.app into identity profiles.

Uses pyobjc-framework-Contacts to access the system address book.
Requires user permission on first run.
"""

import re
from typing import List, Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class ParsedContact:
    """A contact parsed from macOS Contacts.app."""
    identifier: str
    given_name: str
    family_name: str
    full_name: str
    emails: List[str]
    phones: List[str]
    organization: str
    job_title: str
    note: str
    birthday: Optional[str]


def slugify(name: str) -> str:
    """Convert name to valid profile_id slug."""
    slug = name.lower().strip()
    slug = re.sub(r'[^a-z0-9]+', '_', slug)
    slug = slug.strip('_')
    return slug or "contact"


def fetch_macos_contacts(limit: int = 0) -> List[ParsedContact]:
    """
    Fetch contacts from macOS Contacts.app.
    
    Args:
        limit: Max contacts to fetch (0 = all)
        
    Returns:
        List of ParsedContact objects
        
    Raises:
        ImportError: If pyobjc-framework-Contacts not installed
        PermissionError: If contacts access denied
    """
    try:
        import Contacts  # pyobjc-framework-Contacts
    except ImportError:
        raise ImportError(
            "pyobjc-framework-Contacts not installed. "
            "Run: pip install pyobjc-framework-Contacts"
        )
    
    store = Contacts.CNContactStore.alloc().init()
    
    # Request access (will prompt user on first run)
    # Note: This is synchronous for simplicity
    keys_to_fetch = [
        Contacts.CNContactGivenNameKey,
        Contacts.CNContactFamilyNameKey,
        Contacts.CNContactEmailAddressesKey,
        Contacts.CNContactPhoneNumbersKey,
        Contacts.CNContactOrganizationNameKey,
        Contacts.CNContactJobTitleKey,
        Contacts.CNContactNoteKey,
        Contacts.CNContactBirthdayKey,
        Contacts.CNContactIdentifierKey,
    ]
    
    # Fetch all contacts
    request = Contacts.CNContactFetchRequest.alloc().initWithKeysToFetch_(keys_to_fetch)
    
    contacts = []
    error = None
    
    def handle_contact(contact, stop):
        nonlocal contacts
        
        # Extract emails
        emails = []
        for email in contact.emailAddresses():
            emails.append(str(email.value()))
        
        # Extract phones
        phones = []
        for phone in contact.phoneNumbers():
            phones.append(str(phone.value().stringValue()))
        
        # Extract birthday
        birthday = None
        if contact.birthday():
            bd = contact.birthday()
            if bd.year() and bd.month() and bd.day():
                birthday = f"{bd.year()}-{bd.month():02d}-{bd.day():02d}"
            elif bd.month() and bd.day():
                birthday = f"{bd.month():02d}-{bd.day():02d}"
        
        given = str(contact.givenName() or "")
        family = str(contact.familyName() or "")
        full_name = f"{given} {family}".strip()
        
        # Skip empty contacts
        if not full_name and not emails and not phones:
            return
        
        contacts.append(ParsedContact(
            identifier=str(contact.identifier()),
            given_name=given,
            family_name=family,
            full_name=full_name or "Unknown",
            emails=emails,
            phones=phones,
            organization=str(contact.organizationName() or ""),
            job_title=str(contact.jobTitle() or ""),
            note=str(contact.note() or ""),
            birthday=birthday,
        ))
        
        if limit and len(contacts) >= limit:
            stop[0] = True
    
    success, error = store.enumerateContactsWithFetchRequest_error_usingBlock_(
        request, None, handle_contact
    )
    
    if not success:
        if error:
            raise PermissionError(f"Cannot access contacts: {error}")
        raise PermissionError("Cannot access contacts. Check System Settings > Privacy > Contacts.")
    
    return contacts


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
    
    imported = 0
    skipped = 0
    failed = 0
    results = []
    
    for contact in contacts:
        try:
            # Generate profile_id from name
            base_id = slugify(contact.full_name)
            profile_id = base_id
            
            # Handle duplicates by appending number
            counter = 1
            while profile_id in existing_profiles:
                if skip_existing:
                    skipped += 1
                    results.append({"name": contact.full_name, "status": "skipped"})
                    break
                profile_id = f"{base_id}_{counter}"
                counter += 1
            else:
                # Create profile
                create_profile(
                    profile_id=profile_id,
                    type_name=type_name,
                    display_name=contact.full_name
                )
                existing_profiles.add(profile_id)
                
                # Push facts
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


def preview_macos_contacts(limit: int = 10) -> List[Dict[str, Any]]:
    """
    Preview contacts without importing.
    
    Args:
        limit: Max contacts to preview
        
    Returns:
        List of contact preview dicts
    """
    contacts = fetch_macos_contacts(limit=limit)
    
    return [
        {
            "full_name": c.full_name,
            "emails": c.emails,
            "phones": c.phones,
            "organization": c.organization,
            "job_title": c.job_title,
            "has_birthday": c.birthday is not None,
            "has_notes": bool(c.note),
        }
        for c in contacts
    ]


def import_all_macos_contacts(skip_existing: bool = True) -> Dict[str, Any]:
    """
    Import all macOS contacts in one call.
    
    Args:
        skip_existing: Skip contacts with matching names
        
    Returns:
        Import summary
    """
    contacts = fetch_macos_contacts()
    return import_contacts_to_identity(contacts, skip_existing=skip_existing)


__all__ = [
    'ParsedContact',
    'fetch_macos_contacts',
    'import_contacts_to_identity',
    'preview_macos_contacts',
    'import_all_macos_contacts',
]
