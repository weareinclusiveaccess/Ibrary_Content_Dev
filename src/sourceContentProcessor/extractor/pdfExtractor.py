import warnings
import sys
import os
from contextlib import contextmanager
from io import StringIO, TextIOWrapper


class ColorSpaceWarningFilter:
    """Filter stderr to suppress PyMuPDF color space warnings while preserving other errors."""
    def __init__(self, original_stderr):
        self.original_stderr = original_stderr
        
    def write(self, message):
        if message:
            # Check if this is a color space warning (non-fatal)
            if "Cannot set" in message and ("non-stroke color" in message or "stroke color" in message):
                # Suppress only color space warnings - they're non-fatal
                return
            # Write everything else to original stderr
            self.original_stderr.write(message)
    
    def flush(self):
        self.original_stderr.flush()
    
    def __getattr__(self, name):
        return getattr(self.original_stderr, name)


@contextmanager
def suppress_colorspace_warnings():
    """Context manager to suppress PyMuPDF color space warnings while preserving other errors."""
    original_stderr = sys.stderr
    try:
        sys.stderr = ColorSpaceWarningFilter(original_stderr)
        yield
    finally:
        sys.stderr = original_stderr


try:
    from langchain_community.document_loaders import PDFMinerLoader
    PDFMINER_LOADER_AVAILABLE = True
except (ImportError, Exception) as e:
    PDFMINER_LOADER_AVAILABLE = False
    _pdfminer_error = e

try:
    from langchain_community.document_loaders import PyPDFLoader
    PYPDF_LOADER_AVAILABLE = True
except ImportError:
    PYPDF_LOADER_AVAILABLE = False

try:
    from langchain_community.document_loaders import PyMuPDFLoader
    PYMUPDF_LOADER_AVAILABLE = True
except ImportError:
    PYMUPDF_LOADER_AVAILABLE = False


class PDFExtractor:
    def __init__(self):
        """
        Initialize PDFExtractor. No parameters needed for class-level instantiation.
        
        Note: For Jupyter notebooks, if you still see color space warnings,
        you can suppress them at the notebook level:
        
        ```python
        import warnings
        import sys
        from io import StringIO
        
        # Suppress PyMuPDF warnings
        class SuppressOutput:
            def __init__(self, suppress_stderr=True):
                self.suppress_stderr = suppress_stderr
                self.original_stderr = sys.stderr
                
            def __enter__(self):
                if self.suppress_stderr:
                    sys.stderr = StringIO()
                return self
                
            def __exit__(self, *args):
                if self.suppress_stderr:
                    sys.stderr = self.original_stderr
        ```
        """
        pass
    
    def extract(self, pdf_path: str):
        """
        Extract text from PDF file using langchain PDF loaders.
        Uses PyPDFLoader first to avoid PyMuPDF color space warnings.
        
        Args:
            pdf_path: Path to the PDF file
            
        Returns:
            List[Document]: List of langchain Document objects
        """
        errors = []
        
        # Try PyPDFLoader FIRST (most reliable, NO color space issues)
        # This completely avoids the PyMuPDF warnings
        if PYPDF_LOADER_AVAILABLE:
            try:
                loader = PyPDFLoader(pdf_path)
                docs = loader.load()
                return docs
            except Exception as e:
                errors.append(f"PyPDFLoader: {e}")
        
        # Try PDFMinerLoader (most accurate, but may have pydantic issues)
        if PDFMINER_LOADER_AVAILABLE:
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    loader = PDFMinerLoader(pdf_path)
                    docs = loader.load()
                    return docs
            except Exception as e:
                errors.append(f"PDFMinerLoader: {e}")
        
        # Last resort: PyMuPDFLoader (has color warnings, but extractable)
        if PYMUPDF_LOADER_AVAILABLE:
            try:
                # Redirect stderr to suppress color space warnings from C library
                original_stderr = sys.stderr
                try:
                    # Use our filter to suppress only color warnings
                    sys.stderr = ColorSpaceWarningFilter(original_stderr)
                    loader = PyMuPDFLoader(pdf_path)
                    docs = loader.load()
                    return docs
                finally:
                    sys.stderr = original_stderr
            except Exception as e:
                errors.append(f"PyMuPDFLoader: {e}")
                # If we get here, all loaders failed
                error_msg = "All PDF loaders failed:\n  " + "\n  ".join(errors)
                raise RuntimeError(error_msg) from e
        
        # No loader available
        raise ImportError(
            "No PDF loaders available. Please install:\n"
            "  pip install pypdf         # Recommended: Most reliable, no warnings\n"
            "  pip install pdfminer.six  # Alternative: Most accurate\n"
            "  pip install pymupdf       # Alternative: Fast but has color warnings"
        )