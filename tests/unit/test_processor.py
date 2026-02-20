"""
Unit tests for processor module
"""
import pytest
import os
import tempfile
from PyPDF2 import PdfReader
from modules.processor import (
    split_pdf_into_chunks,
    merge_chunks,
    ChunkInfo
)


class TestPDFSplitting:
    """Tests for PDF splitting functionality"""
    
    def test_split_single_page_pdf(self, valid_pdf_1_page):
        """Test splitting a single-page PDF"""
        with tempfile.TemporaryDirectory() as temp_dir:
            chunks = split_pdf_into_chunks(valid_pdf_1_page, chunk_size=5, output_dir=temp_dir)
            
            assert len(chunks) == 1
            assert chunks[0].start_page == 0
            assert chunks[0].end_page == 1
            assert os.path.exists(chunks[0].input_path)
    
    def test_split_10_page_pdf_into_3_page_chunks(self, valid_pdf_10_pages):
        """Test splitting 10-page PDF with chunk_size=3"""
        with tempfile.TemporaryDirectory() as temp_dir:
            chunks = split_pdf_into_chunks(valid_pdf_10_pages, chunk_size=3, output_dir=temp_dir)
            
            # Should create 4 chunks: 3+3+3+1
            assert len(chunks) == 4
            
            # Verify first chunk
            assert chunks[0].start_page == 0
            assert chunks[0].end_page == 3
            
            # Verify last chunk
            assert chunks[3].start_page == 9
            assert chunks[3].end_page == 10
            
            # Verify all chunks exist
            for chunk in chunks:
                assert os.path.exists(chunk.input_path)
    
    def test_split_with_large_chunk_size(self, valid_pdf_5_pages):
        """Test splitting with chunk_size larger than total pages"""
        with tempfile.TemporaryDirectory() as temp_dir:
            chunks = split_pdf_into_chunks(valid_pdf_5_pages, chunk_size=100, output_dir=temp_dir)
            
            # Should create only 1 chunk containing all pages
            assert len(chunks) == 1
            assert chunks[0].start_page == 0
            assert chunks[0].end_page == 5
    
    def test_chunks_have_colors(self, valid_pdf_10_pages):
        """Test that chunks are assigned colors"""
        with tempfile.TemporaryDirectory() as temp_dir:
            chunks = split_pdf_into_chunks(valid_pdf_10_pages, chunk_size=3, output_dir=temp_dir)
            
            for chunk in chunks:
                assert chunk.color is not None
                assert len(chunk.color) == 3  # RGB tuple
                assert all(0 <= c <= 1 for c in chunk.color)
    
    def test_chunks_maintain_order(self, valid_pdf_10_pages):
        """Test that chunks maintain their order"""
        with tempfile.TemporaryDirectory() as temp_dir:
            chunks = split_pdf_into_chunks(valid_pdf_10_pages, chunk_size=2, output_dir=temp_dir)
            
            for i, chunk in enumerate(chunks):
                assert chunk.order == i
                assert chunk.chunk_id == i


class TestPDFMerging:
    """Tests for PDF merging functionality"""
    
    def test_merge_single_chunk(self, valid_pdf_1_page):
        """Test merging a single chunk"""
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = os.path.join(temp_dir, "merged.pdf")
            
            merge_chunks([valid_pdf_1_page], output_path)
            
            assert os.path.exists(output_path)
            
            # Verify merged PDF
            reader = PdfReader(output_path)
            assert len(reader.pages) == 1
    
    def test_merge_multiple_chunks(self, valid_pdf_1_page):
        """Test merging multiple chunks"""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Use same PDF multiple times as chunks
            output_path = os.path.join(temp_dir, "merged.pdf")
            
            merge_chunks([valid_pdf_1_page, valid_pdf_1_page, valid_pdf_1_page], output_path)
            
            assert os.path.exists(output_path)
            
            # Verify merged PDF has 3 pages
            reader = PdfReader(output_path)
            assert len(reader.pages) == 3
    
    def test_merge_nonexistent_chunk_fails(self):
        """Test that merging non-existent chunks fails"""
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = os.path.join(temp_dir, "merged.pdf")
            
            with pytest.raises(Exception):
                merge_chunks(["/nonexistent/file.pdf"], output_path)


class TestChunkInfo:
    """Tests for ChunkInfo dataclass"""
    
    def test_create_chunk_info(self):
        """Test creating ChunkInfo"""
        chunk = ChunkInfo(
            chunk_id=0,
            start_page=0,
            end_page=5,
            order=0,
            input_path="/path/to/chunk.pdf",
            color=(1, 0, 0)
        )
        
        assert chunk.chunk_id == 0
        assert chunk.start_page == 0
        assert chunk.end_page == 5
        assert chunk.order == 0
        assert chunk.status == "pending"
        assert chunk.color == (1, 0, 0)
