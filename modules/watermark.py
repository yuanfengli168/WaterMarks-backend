"""
Watermark Module - Handles watermark creation and application to PDFs
"""
import os
from io import BytesIO
from typing import Tuple
from PyPDF2 import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
import config


def create_watermark_overlay(
    text: str,
    color: Tuple[float, float, float],
    page_width: float,
    page_height: float,
    font_size: int = None,
    opacity: float = None,
    rotation: int = None
) -> BytesIO:
    """
    Create a watermark overlay as a PDF in memory.
    
    Args:
        text: Watermark text
        color: RGB color tuple (values 0-1)
        page_width: Width of the page in points
        page_height: Height of the page in points
        font_size: Font size (defaults to config)
        opacity: Opacity 0-1 (defaults to config)
        rotation: Rotation angle in degrees (defaults to config)
        
    Returns:
        BytesIO object containing the watermark PDF
    """
    # Use config defaults if not specified
    if font_size is None:
        font_size = config.WATERMARK_FONT_SIZE
    if opacity is None:
        opacity = config.WATERMARK_OPACITY
    if rotation is None:
        rotation = config.WATERMARK_ROTATION
    
    # Create a PDF in memory
    packet = BytesIO()
    can = canvas.Canvas(packet, pagesize=(page_width, page_height))
    
    # Set watermark properties
    can.setFillColorRGB(color[0], color[1], color[2], alpha=opacity)
    can.setFont("Helvetica-Bold", font_size)
    
    # Calculate position (center of page)
    x = page_width / 2
    y = page_height / 2
    
    # Apply rotation and draw text
    can.saveState()
    can.translate(x, y)
    can.rotate(rotation)
    
    # Center the text
    text_width = can.stringWidth(text, "Helvetica-Bold", font_size)
    can.drawString(-text_width / 2, 0, text)
    
    can.restoreState()
    can.save()
    
    packet.seek(0)
    return packet


def apply_watermark_to_page(page, watermark_page):
    """
    Apply a watermark to a single page.
    
    Args:
        page: PyPDF2 page object
        watermark_page: Watermark page to overlay
        
    Returns:
        Modified page with watermark
    """
    page.merge_page(watermark_page)
    return page


def add_watermark_to_pdf(
    input_pdf_path: str,
    output_pdf_path: str,
    color: Tuple[float, float, float],
    watermark_text: str = None
) -> str:
    """
    Add watermark to all pages of a PDF file.
    
    Args:
        input_pdf_path: Path to input PDF
        output_pdf_path: Path to save watermarked PDF
        color: RGB color tuple for watermark (values 0-1)
        watermark_text: Text for watermark (defaults to config)
        
    Returns:
        Path to output PDF
        
    Raises:
        Exception if watermarking fails
    """
    try:
        if watermark_text is None:
            watermark_text = config.WATERMARK_TEXT
        
        # Read input PDF
        reader = PdfReader(input_pdf_path)
        writer = PdfWriter()
        
        # Process each page
        for page_num in range(len(reader.pages)):
            page = reader.pages[page_num]
            
            # Get page dimensions
            page_box = page.mediabox
            page_width = float(page_box.width)
            page_height = float(page_box.height)
            
            # Create watermark overlay for this page size
            watermark_buffer = create_watermark_overlay(
                watermark_text,
                color,
                page_width,
                page_height
            )
            
            # Apply watermark
            watermark_reader = PdfReader(watermark_buffer)
            watermark_page = watermark_reader.pages[0]
            
            page.merge_page(watermark_page)
            writer.add_page(page)
        
        # Write output PDF
        with open(output_pdf_path, 'wb') as output_file:
            writer.write(output_file)
        
        return output_pdf_path
        
    except Exception as e:
        raise Exception(f"Failed to add watermark: {str(e)}")


def get_color_for_chunk(chunk_index: int) -> Tuple[float, float, float]:
    """
    Get a color from the palette for a given chunk index.
    Colors rotate through the configured palette.
    
    Args:
        chunk_index: Index of the chunk (0-based)
        
    Returns:
        RGB color tuple (values 0-1)
    """
    color_index = chunk_index % len(config.WATERMARK_COLORS)
    return config.WATERMARK_COLORS[color_index]
