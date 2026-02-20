"""
Test PDF Generator
Creates various PDF files for testing purposes
"""
import os
from PyPDF2 import PdfWriter, PdfReader
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from io import BytesIO


def ensure_test_data_dir():
    """Create test_data directory if it doesn't exist"""
    test_dir = "tests/test_data"
    os.makedirs(test_dir, exist_ok=True)
    return test_dir


def generate_simple_pdf(output_path: str, num_pages: int = 1, content_prefix: str = "Test Page"):
    """
    Generate a simple PDF with specified number of pages.
    
    Args:
        output_path: Path to save PDF
        num_pages: Number of pages to generate
        content_prefix: Text prefix for each page
    """
    c = canvas.Canvas(output_path, pagesize=letter)
    width, height = letter
    
    for page_num in range(1, num_pages + 1):
        # Add page number and content
        c.setFont("Helvetica-Bold", 24)
        c.drawString(100, height - 100, f"{content_prefix} {page_num}")
        
        # Add some body text
        c.setFont("Helvetica", 12)
        c.drawString(100, height - 150, f"This is page {page_num} of {num_pages}")
        c.drawString(100, height - 170, "Generated for testing watermark functionality")
        
        # Add page number at bottom
        c.drawString(width / 2 - 20, 30, f"- {page_num} -")
        
        c.showPage()
    
    c.save()
    print(f"✅ Generated: {output_path} ({num_pages} pages)")


def generate_corrupted_pdf(output_path: str):
    """
    Generate a corrupted PDF file by truncating a valid PDF.
    
    Args:
        output_path: Path to save corrupted PDF
    """
    # First create a valid PDF in memory
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    c.drawString(100, 750, "This PDF will be corrupted")
    c.save()
    
    # Get the PDF content and truncate it
    pdf_content = buffer.getvalue()
    corrupted_content = pdf_content[:len(pdf_content) // 2]  # Take only first half
    
    # Write corrupted content
    with open(output_path, 'wb') as f:
        f.write(corrupted_content)
    
    print(f"✅ Generated: {output_path} (corrupted)")


def generate_encrypted_pdf(output_path: str, password: str = "test123"):
    """
    Generate an encrypted (password-protected) PDF.
    
    Args:
        output_path: Path to save encrypted PDF
        password: Password for encryption
    """
    # Create a simple PDF
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    c.setFont("Helvetica", 12)
    c.drawString(100, 750, "This is an encrypted PDF")
    c.drawString(100, 730, f"Password: {password}")
    c.save()
    
    # Read the PDF and encrypt it
    buffer.seek(0)
    reader = PdfReader(buffer)
    writer = PdfWriter()
    
    for page in reader.pages:
        writer.add_page(page)
    
    # Encrypt with password
    writer.encrypt(password)
    
    # Write encrypted PDF
    with open(output_path, 'wb') as f:
        writer.write(f)
    
    print(f"✅ Generated: {output_path} (encrypted with password: {password})")


def generate_fake_pdf(output_path: str):
    """
    Generate a fake PDF (text file with .pdf extension).
    
    Args:
        output_path: Path to save fake PDF
    """
    with open(output_path, 'w') as f:
        f.write("This is not a real PDF file.\n")
        f.write("It's just a text file renamed with .pdf extension.\n")
        f.write("This should be rejected by the validator.\n")
    
    print(f"✅ Generated: {output_path} (fake - text file)")


def generate_empty_pdf(output_path: str):
    """
    Generate an empty file with .pdf extension.
    
    Args:
        output_path: Path to save empty file
    """
    with open(output_path, 'wb') as f:
        f.write(b'')
    
    print(f"✅ Generated: {output_path} (empty file)")


def generate_large_pdf(output_path: str, target_size_mb: float = 5):
    """
    Generate a larger PDF by adding more pages with content.
    
    Args:
        output_path: Path to save PDF
        target_size_mb: Approximate target size in MB
    """
    # Estimate: ~10KB per page with text
    estimated_pages = int((target_size_mb * 1024) / 10)
    
    c = canvas.Canvas(output_path, pagesize=letter)
    width, height = letter
    
    for page_num in range(1, estimated_pages + 1):
        c.setFont("Helvetica-Bold", 16)
        c.drawString(100, height - 50, f"Page {page_num} of {estimated_pages}")
        
        # Add more content to increase file size
        c.setFont("Helvetica", 10)
        y_position = height - 100
        
        for line_num in range(50):  # Add 50 lines per page
            c.drawString(50, y_position, f"Line {line_num}: Lorem ipsum dolor sit amet, consectetur adipiscing elit. " * 2)
            y_position -= 12
            if y_position < 50:
                break
        
        c.showPage()
    
    c.save()
    
    # Check actual size
    actual_size_mb = os.path.getsize(output_path) / (1024 * 1024)
    print(f"✅ Generated: {output_path} ({estimated_pages} pages, {actual_size_mb:.2f} MB)")


def generate_all_test_pdfs():
    """Generate all test PDF files"""
    print("\n🔧 Generating test PDF files...\n")
    
    test_dir = ensure_test_data_dir()
    
    # 1. Valid PDFs of various sizes
    generate_simple_pdf(os.path.join(test_dir, "valid_1_page.pdf"), num_pages=1)
    generate_simple_pdf(os.path.join(test_dir, "valid_5_pages.pdf"), num_pages=5)
    generate_simple_pdf(os.path.join(test_dir, "valid_10_pages.pdf"), num_pages=10)
    generate_simple_pdf(os.path.join(test_dir, "valid_100_pages.pdf"), num_pages=100)
    
    # 2. Small valid PDF (for size testing)
    generate_simple_pdf(os.path.join(test_dir, "small_valid.pdf"), num_pages=1)
    
    # 3. Medium PDF (~5MB)
    generate_large_pdf(os.path.join(test_dir, "medium_valid.pdf"), target_size_mb=5)
    
    # 4. Corrupted PDF
    generate_corrupted_pdf(os.path.join(test_dir, "corrupted.pdf"))
    
    # 5. Encrypted PDF
    generate_encrypted_pdf(os.path.join(test_dir, "encrypted.pdf"), password="test123")
    
    # 6. Fake PDF (text file)
    generate_fake_pdf(os.path.join(test_dir, "fake.pdf"))
    
    # 7. Empty file
    generate_empty_pdf(os.path.join(test_dir, "empty.pdf"))
    
    print("\n✅ All test PDF files generated successfully!")
    print(f"📁 Location: {test_dir}/")
    
    # List all generated files with sizes
    print("\n📊 Generated files:")
    for filename in sorted(os.listdir(test_dir)):
        if filename.endswith('.pdf'):
            filepath = os.path.join(test_dir, filename)
            size = os.path.getsize(filepath)
            size_kb = size / 1024
            size_mb = size / (1024 * 1024)
            
            if size_mb >= 1:
                print(f"   • {filename:<25} ({size_mb:.2f} MB)")
            else:
                print(f"   • {filename:<25} ({size_kb:.2f} KB)")


if __name__ == "__main__":
    generate_all_test_pdfs()
