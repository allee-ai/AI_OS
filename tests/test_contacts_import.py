"""
Tests for Contacts Import (vCard).

Tests the vCard parsing and import functionality for the identity thread.
"""

import pytest
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


# Sample vCard data for tests
SINGLE_CONTACT_VCF = """BEGIN:VCARD
VERSION:3.0
FN:John Doe
N:Doe;John;;;
EMAIL:john@example.com
TEL:+1-555-1234
ORG:Acme Corp
TITLE:Software Engineer
NOTE:Met at conference
BDAY:1985-06-15
END:VCARD"""

MULTI_CONTACT_VCF = """BEGIN:VCARD
VERSION:3.0
FN:Alice Johnson
N:Johnson;Alice;;;
EMAIL:alice@example.com
EMAIL:alice.work@company.com
TEL:+1-555-1111
ORG:Tech Inc
END:VCARD
BEGIN:VCARD
VERSION:3.0
FN:Bob Williams
EMAIL:bob@example.com
TEL:+1-555-2222
TEL:+1-555-2223
END:VCARD
BEGIN:VCARD
VERSION:3.0
FN:Carol Davis
N:Davis;Carol;;;
END:VCARD"""

VCARD_21_FORMAT = """BEGIN:VCARD
VERSION:2.1
N:Smith;Jane
FN:Jane Smith
EMAIL;PREF;INTERNET:jane@example.com
TEL;CELL:555-9999
END:VCARD"""

VCARD_40_FORMAT = """BEGIN:VCARD
VERSION:4.0
FN:Modern Contact
EMAIL:modern@example.com
TEL:+44-20-1234-5678
ORG:Global Corp
END:VCARD"""

MALFORMED_VCF = """BEGIN:VCARD
VERSION:3.0
FN:
END:VCARD
BEGIN:VCARD
VERSION:3.0
FN:Valid Contact
EMAIL:valid@example.com
END:VCARD"""

EMPTY_VCF = """BEGIN:VCARD
VERSION:3.0
END:VCARD"""


class TestVCardParsing:
    """Test vCard file parsing."""
    
    def test_parse_single_contact(self):
        """Should parse a single contact vCard."""
        from agent.threads.identity.import_contacts import parse_vcard_file
        
        contacts = parse_vcard_file(SINGLE_CONTACT_VCF)
        
        assert len(contacts) == 1
        c = contacts[0]
        assert c.full_name == "John Doe"
        assert c.given_name == "John"
        assert c.family_name == "Doe"
        assert "john@example.com" in c.emails
        assert "+1-555-1234" in c.phones
        assert c.organization == "Acme Corp"
        assert c.job_title == "Software Engineer"
        assert c.note == "Met at conference"
        assert c.birthday == "1985-06-15"
    
    def test_parse_multiple_contacts(self):
        """Should parse multiple contacts from one vcf file."""
        from agent.threads.identity.import_contacts import parse_vcard_file
        
        contacts = parse_vcard_file(MULTI_CONTACT_VCF)
        
        assert len(contacts) == 3
        names = [c.full_name for c in contacts]
        assert "Alice Johnson" in names
        assert "Bob Williams" in names
        assert "Carol Davis" in names
    
    def test_parse_multiple_emails_phones(self):
        """Should capture multiple emails and phone numbers."""
        from agent.threads.identity.import_contacts import parse_vcard_file
        
        contacts = parse_vcard_file(MULTI_CONTACT_VCF)
        
        alice = next(c for c in contacts if c.full_name == "Alice Johnson")
        assert len(alice.emails) == 2
        assert "alice@example.com" in alice.emails
        assert "alice.work@company.com" in alice.emails
        
        bob = next(c for c in contacts if c.full_name == "Bob Williams")
        assert len(bob.phones) == 2
    
    def test_parse_vcard_21_format(self):
        """Should parse vCard 2.1 format."""
        from agent.threads.identity.import_contacts import parse_vcard_file
        
        contacts = parse_vcard_file(VCARD_21_FORMAT)
        
        assert len(contacts) == 1
        assert contacts[0].full_name == "Jane Smith"
        assert "jane@example.com" in contacts[0].emails
    
    def test_parse_vcard_40_format(self):
        """Should parse vCard 4.0 format."""
        from agent.threads.identity.import_contacts import parse_vcard_file
        
        contacts = parse_vcard_file(VCARD_40_FORMAT)
        
        assert len(contacts) == 1
        assert contacts[0].full_name == "Modern Contact"
    
    def test_skip_malformed_entries(self):
        """Should skip malformed entries but parse valid ones."""
        from agent.threads.identity.import_contacts import parse_vcard_file
        
        contacts = parse_vcard_file(MALFORMED_VCF)
        
        # Should have at least the valid contact
        valid_names = [c.full_name for c in contacts]
        assert "Valid Contact" in valid_names
    
    def test_skip_empty_contacts(self):
        """Should skip contacts with no name."""
        from agent.threads.identity.import_contacts import parse_vcard_file
        
        contacts = parse_vcard_file(EMPTY_VCF)
        
        # Empty contact should be skipped
        assert len(contacts) == 0
    
    def test_empty_file_returns_empty_list(self):
        """Should return empty list for empty input."""
        from agent.threads.identity.import_contacts import parse_vcard_file
        
        contacts = parse_vcard_file("")
        
        assert contacts == []


class TestUploadStorage:
    """Test upload storage and retrieval."""
    
    def test_store_upload_returns_id(self):
        """store_upload should return a UUID."""
        from agent.threads.identity.import_contacts import store_upload
        
        upload_id = store_upload(SINGLE_CONTACT_VCF, "test.vcf")
        
        assert upload_id is not None
        assert len(upload_id) == 36  # UUID format
    
    def test_parse_upload_returns_preview(self):
        """parse_upload should return preview with contacts."""
        from agent.threads.identity.import_contacts import store_upload, parse_upload
        
        upload_id = store_upload(MULTI_CONTACT_VCF, "contacts.vcf")
        preview = parse_upload(upload_id)
        
        assert preview["upload_id"] == upload_id
        assert preview["total_contacts"] == 3
        assert len(preview["contacts"]) == 3
        
        # Check preview format
        contact = preview["contacts"][0]
        assert "id" in contact
        assert "full_name" in contact
        assert "email" in contact
    
    def test_parse_upload_invalid_id_raises(self):
        """parse_upload should raise for invalid upload_id."""
        from agent.threads.identity.import_contacts import parse_upload
        
        with pytest.raises(ValueError, match="Upload not found"):
            parse_upload("invalid-uuid-12345")
    
    def test_preview_limits_to_20(self):
        """Preview should limit contacts to 20 max."""
        from agent.threads.identity.import_contacts import store_upload, parse_upload
        
        # Create 25 contacts
        vcf = ""
        for i in range(25):
            vcf += f"""BEGIN:VCARD
VERSION:3.0
FN:Contact {i}
EMAIL:contact{i}@example.com
END:VCARD
"""
        
        upload_id = store_upload(vcf, "many.vcf")
        preview = parse_upload(upload_id)
        
        assert preview["total_contacts"] == 25
        assert len(preview["contacts"]) == 20  # Limited


class TestSlugify:
    """Test profile_id slug generation."""
    
    def test_slugify_basic(self):
        """Should convert name to lowercase slug."""
        from agent.threads.identity.import_contacts import slugify
        
        assert slugify("John Doe") == "john_doe"
        assert slugify("Alice Johnson") == "alice_johnson"
    
    def test_slugify_special_chars(self):
        """Should replace special characters with underscores."""
        from agent.threads.identity.import_contacts import slugify
        
        assert slugify("O'Connor") == "o_connor"
        assert slugify("Mary-Jane Watson") == "mary_jane_watson"
    
    def test_slugify_empty(self):
        """Should return 'contact' for empty input."""
        from agent.threads.identity.import_contacts import slugify
        
        assert slugify("") == "contact"
        assert slugify("   ") == "contact"


class TestParsedContact:
    """Test ParsedContact dataclass."""
    
    def test_parsed_contact_defaults(self):
        """ParsedContact should have sensible defaults."""
        from agent.threads.identity.import_contacts import ParsedContact
        
        contact = ParsedContact(
            identifier="123",
            full_name="Test User"
        )
        
        assert contact.identifier == "123"
        assert contact.full_name == "Test User"
        assert contact.given_name == ""
        assert contact.family_name == ""
        assert contact.emails == []
        assert contact.phones == []
        assert contact.organization == ""
        assert contact.job_title == ""
        assert contact.note == ""
        assert contact.birthday is None


class TestBirthdayParsing:
    """Test birthday format normalization."""
    
    def test_iso_format_birthday(self):
        """Should parse ISO format birthdays."""
        from agent.threads.identity.import_contacts import parse_vcard_file
        
        vcf = """BEGIN:VCARD
VERSION:3.0
FN:Test Person
BDAY:1990-12-25
END:VCARD"""
        
        contacts = parse_vcard_file(vcf)
        assert contacts[0].birthday == "1990-12-25"
    
    def test_compact_format_birthday(self):
        """Should parse compact YYYYMMDD format."""
        from agent.threads.identity.import_contacts import parse_vcard_file
        
        vcf = """BEGIN:VCARD
VERSION:3.0
FN:Test Person
BDAY:19901225
END:VCARD"""
        
        contacts = parse_vcard_file(vcf)
        assert contacts[0].birthday == "1990-12-25"


# Integration test (requires database - mark as slow)
@pytest.mark.slow
class TestImportIntegration:
    """Integration tests for full import flow."""
    
    def test_commit_import_creates_profiles(self):
        """commit_import should create profiles in database."""
        from agent.threads.identity.import_contacts import (
            store_upload, commit_import
        )
        from agent.threads.identity.schema import get_profiles
        
        # Get initial count
        initial_profiles = len(get_profiles())
        
        # Import new contacts
        upload_id = store_upload(SINGLE_CONTACT_VCF, "test.vcf")
        result = commit_import(upload_id)
        
        assert result["imported"] >= 0
        assert "total" in result
        
        # Check profiles increased (if not skipped)
        if result["imported"] > 0:
            final_profiles = len(get_profiles())
            assert final_profiles > initial_profiles
