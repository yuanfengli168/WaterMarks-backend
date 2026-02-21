"""
Processor Module - Handles PDF splitting, merging, and orchestration
"""
import os
from typing import List, Dict
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from PyPDF2 import PdfReader, PdfWriter, PdfMerger
import config
from modules.watermark import add_watermark_to_pdf, get_color_for_chunk


@dataclass
class ChunkInfo:
    """Information about a PDF chunk"""
    chunk_id: int
    start_page: int
    end_page: int
    order: int
    input_path: str
    output_path: str = None
    color: tuple = None
    status: str = "pending"  # pending, processing, completed, error
    error: str = None


def split_pdf_into_chunks(
    pdf_path: str,
    chunk_size: int,
    output_dir: str
) -> List[ChunkInfo]:
    """
    Split PDF into chunks based on chunk size.
    
    Args:
        pdf_path: Path to input PDF
        chunk_size: Maximum pages per chunk
        output_dir: Directory to save chunk files
        
    Returns:
        List of ChunkInfo objects with metadata
        
    Raises:
        Exception if splitting fails
    """
    try:
        # Read PDF
        reader = PdfReader(pdf_path)
        total_pages = len(reader.pages)
        
        # Calculate actual chunk size (minimum of requested and total pages)
        actual_chunk_size = min(chunk_size, total_pages)
        
        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)
        
        chunks = []
        chunk_id = 0
        
        # Split into chunks
        for start_page in range(0, total_pages, actual_chunk_size):
            end_page = min(start_page + actual_chunk_size, total_pages)
            
            # Create chunk file
            chunk_filename = f"chunk_{chunk_id:04d}.pdf"
            chunk_path = os.path.join(output_dir, chunk_filename)
            
            # Write chunk to file
            writer = PdfWriter()
            for page_num in range(start_page, end_page):
                writer.add_page(reader.pages[page_num])
            
            with open(chunk_path, 'wb') as output_file:
                writer.write(output_file)
            
            # Create chunk info
            chunk = ChunkInfo(
                chunk_id=chunk_id,
                start_page=start_page,
                end_page=end_page,
                order=chunk_id,
                input_path=chunk_path,
                color=get_color_for_chunk(chunk_id)
            )
            chunks.append(chunk)
            
            chunk_id += 1
        
        return chunks
        
    except Exception as e:
        raise Exception(f"Failed to split PDF into chunks: {str(e)}")


def process_single_chunk(chunk: ChunkInfo, output_dir: str) -> ChunkInfo:
    """
    Process a single chunk by adding watermark.
    
    Args:
        chunk: ChunkInfo object
        output_dir: Directory to save watermarked chunk
        
    Returns:
        Updated ChunkInfo object
    """
    try:
        chunk.status = "processing"
        
        # Create output path
        watermarked_filename = f"watermarked_chunk_{chunk.chunk_id:04d}.pdf"
        output_path = os.path.join(output_dir, watermarked_filename)
        
        # Add watermark
        add_watermark_to_pdf(
            input_pdf_path=chunk.input_path,
            output_pdf_path=output_path,
            color=chunk.color
        )
        
        chunk.output_path = output_path
        chunk.status = "completed"
        
        return chunk
        
    except Exception as e:
        chunk.status = "error"
        chunk.error = str(e)
        return chunk


def parallel_watermark_chunks(
    chunks: List[ChunkInfo],
    output_dir: str,
    max_workers: int = None
) -> List[ChunkInfo]:
    """
    Process multiple chunks in parallel, adding watermarks.
    
    Args:
        chunks: List of ChunkInfo objects
        output_dir: Directory to save watermarked chunks
        max_workers: Maximum number of parallel workers
        
    Returns:
        List of processed ChunkInfo objects
        
    Raises:
        Exception if any chunk fails to process
    """
    try:
        if max_workers is None:
            max_workers = config.MAX_PARALLEL_WORKERS
        
        # Create output directory
        os.makedirs(output_dir, exist_ok=True)
        
        # Process chunks in parallel
        processed_chunks = []
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all chunks for processing
            future_to_chunk = {
                executor.submit(process_single_chunk, chunk, output_dir): chunk
                for chunk in chunks
            }
            
            # Collect results as they complete
            for future in as_completed(future_to_chunk):
                chunk = future_to_chunk[future]
                try:
                    processed_chunk = future.result()
                    processed_chunks.append(processed_chunk)
                    
                    # Check for errors
                    if processed_chunk.status == "error":
                        raise Exception(
                            f"Chunk {processed_chunk.chunk_id} failed: {processed_chunk.error}"
                        )
                except Exception as e:
                    raise Exception(f"Error processing chunk {chunk.chunk_id}: {str(e)}")
        
        # Sort by order to maintain sequence
        processed_chunks.sort(key=lambda x: x.order)
        
        return processed_chunks
        
    except Exception as e:
        raise Exception(f"Failed to process chunks in parallel: {str(e)}")


def merge_chunks(chunk_paths: List[str], output_path: str, status_callback=None) -> str:
    """
    Merge watermarked chunks back into a single PDF.
    
    Args:
        chunk_paths: List of paths to watermarked chunk PDFs (in order)
        output_path: Path to save merged PDF
        status_callback: Optional callback for progress updates
        
    Returns:
        Path to merged PDF
        
    Raises:
        Exception if merging fails
    """
    try:
        merger = PdfMerger()
        total_chunks = len(chunk_paths)
        
        # Add each chunk in order with progress reporting
        for i, chunk_path in enumerate(chunk_paths):
            if not os.path.exists(chunk_path):
                raise Exception(f"Chunk file not found: {chunk_path}")
            merger.append(chunk_path)
            
            # Report progress: 80% (start of merge) to 95% (end of merge)
            if status_callback and total_chunks > 1:
                progress = 80 + int((i + 1) / total_chunks * 15)  # 80-95%
                status_callback("merging", progress=progress)
        
        # Write merged PDF (final 5% of progress)
        if status_callback:
            status_callback("merging", progress=95)
            
        with open(output_path, 'wb') as output_file:
            merger.write(output_file)
        
        merger.close()
        
        # Final merge complete
        if status_callback:
            status_callback("merging", progress=100)
        
        return output_path
        
    except Exception as e:
        raise Exception(f"Failed to merge chunks: {str(e)}")


def process_pdf_with_watermarks(
    input_pdf_path: str,
    chunk_size: int,
    job_id: str,
    status_callback=None
) -> str:
    """
    Complete workflow: split PDF, add watermarks in parallel, merge back.
    
    Args:
        input_pdf_path: Path to input PDF
        chunk_size: Pages per chunk
        job_id: Unique job identifier
        status_callback: Optional callback function for status updates
        
    Returns:
        Path to final watermarked PDF
        
    Raises:
        Exception if any step fails
    """
    try:
        # Create working directories
        job_dir = os.path.join(config.PROCESSING_DIR, job_id)
        chunks_dir = os.path.join(job_dir, "chunks")
        watermarked_dir = os.path.join(job_dir, "watermarked")
        
        os.makedirs(chunks_dir, exist_ok=True)
        os.makedirs(watermarked_dir, exist_ok=True)
        os.makedirs(config.OUTPUT_DIR, exist_ok=True)
        
        # Step 1: Split into chunks
        if status_callback:
            status_callback("splitting")
        
        chunks = split_pdf_into_chunks(input_pdf_path, chunk_size, chunks_dir)
        
        # Step 2: Add watermarks in parallel
        if status_callback:
            status_callback("adding_watermarks")
        
        processed_chunks = parallel_watermark_chunks(chunks, watermarked_dir)
        
        # Step 3: Merge chunks
        if status_callback:
            status_callback("merging", progress=80)
        
        # Get watermarked chunk paths in order
        chunk_paths = [chunk.output_path for chunk in processed_chunks]
        
        # Create final output path
        output_filename = f"watermarked_{job_id}.pdf"
        output_path = os.path.join(config.OUTPUT_DIR, output_filename)
        
        merge_chunks(chunk_paths, output_path, status_callback=status_callback)
        
        # Update status to finished
        if status_callback:
            status_callback("finished")
        
        return output_path
        
    except Exception as e:
        raise Exception(f"Failed to process PDF: {str(e)}")
