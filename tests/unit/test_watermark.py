"""
Unit tests for watermark module
"""
import pytest
import os
import tempfile
from PyPDF2 import PdfReader
from modules.watermark import (
    create_watermark_overlay,
    add_watermark_to_pdf,
    get_color_for_chunk
)
import config


class TestWatermarkCreation:
    """Tests for watermark creation"""
    
    def test_create_watermark_overlay(self):
        """Test creating watermark overlay"""
        overlay = create_watermark_overlay(
            text="TEST",
            color=(1, 0, 0),
            page_width=612,
            page_height=792
        )
        
        assert overlay is not None
        assert overlay.tell() == 0  # Should be at beginning
        
        # Should be readable as PDF
        reader = PdfReader(overlay)
        assert len(reader.pages) == 1
    
    def test_watermark_with_custom_settings(self):
        """Test watermark with custom settings"""
        overlay = create_watermark_overlay(
            text="CUSTOM",
            color=(0, 1, 0),
            page_width=500,
            page_height=700,
            font_size=72,
            opacity=0.5,
            rotation=30
        )
        
        assert overlay is not None
        reader = PdfReader(overlay)
        assert len(reader.pages) == 1


class TestWatermarkApplication:
    """Tests for applying watermarks to PDFs"""
    
    def test_add_watermark_to_single_page(self, valid_pdf_1_page):
        """Test adding watermark to single-page PDF"""
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = os.path.join(temp_dir, "watermarked.pdf")
            
            result = add_watermark_to_pdf(
                input_pdf_path=valid_pdf_1_page,
                output_pdf_path=output_path,
                color=(1, 0, 0)
            )
            
            assert result == output_path
            assert os.path.exists(output_path)
            
            # Verify output is valid PDF with same page count
            reader = PdfReader(output_path)
            assert len(reader.pages) == 1
    
    def test_add_watermark_to_multi_page(self, valid_pdf_10_pages):
        """Test adding watermark to multi-page PDF"""
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = os.path.join(temp_dir, "watermarked.pdf")
            
            result = add_watermark_to_pdf(
                input_pdf_path=valid_pdf_10_pages,
                output_pdf_path=output_path,
                color=(0, 0, 1)
            )
            
            assert os.path.exists(output_path)
            
            # Verify page count matches
            original_reader = PdfReader(valid_pdf_10_pages)
            watermarked_reader = PdfReader(output_path)
            assert len(watermarked_reader.pages) == len(original_reader.pages)
    
    def test_add_watermark_with_custom_text(self, valid_pdf_1_page):
        """Test adding watermark with custom text"""
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = os.path.join(temp_dir, "watermarked.pdf")
            
            result = add_watermark_to_pdf(
                input_pdf_path=valid_pdf_1_page,
                output_pdf_path=output_path,
                color=(0, 1, 0),
                watermark_text="CONFIDENTIAL"
            )
            
            assert os.path.exists(output_path)
    
    def test_watermark_nonexistent_file_fails(self):
        """Test that watermarking non-existent file fails"""
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = os.path.join(temp_dir, "output.pdf")
            
            with pytest.raises(Exception):
                add_watermark_to_pdf(
                    input_pdf_path="/nonexistent/file.pdf",
                    output_pdf_path=output_path,
                    color=(1, 0, 0)
                )


class TestColorSelection:
    """Tests for color selection"""
    
    def test_get_color_for_chunk(self):
        """Test getting color for chunk index"""
        color = get_color_for_chunk(0)
        assert color is not None
        assert len(color) == 3
        assert all(0 <= c <= 1 for c in color)
    
    def test_colors_rotate_through_palette(self):
        """Test that colors rotate through palette"""
        num_colors = len(config.WATERMARK_COLORS)
        
        # Get colors for indices that should repeat
        color_0 = get_color_for_chunk(0)
        color_n = get_color_for_chunk(num_colors)
        
        # Should be the same color (rotated)
        assert color_0 == color_n
    
    def test_different_chunks_get_different_colors(self):
        """Test that consecutive chunks get different colors"""
        colors = [get_color_for_chunk(i) for i in range(min(5, len(config.WATERMARK_COLORS)))]
        
        # All should be different (up to palette size)
        assert len(set(colors)) == len(colors)
