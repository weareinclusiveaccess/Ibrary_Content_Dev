"""
Parser for extracting Table of Contents (TOC) from PDF documents.
Extracts chapter structure including chapters, topics, subtopics, and subsubtopics.
"""
import re
from typing import List, Dict, Optional, Tuple
from langchain_core.documents import Document


class TOCParser:
    """Parse table of contents from textbook documents."""
    
    def __init__(self):
        # Patterns for different TOC levels
        self.chapter_pattern = re.compile(r'^\s*(\d+)\s+(.+?)\s+(\d+)\s*$')  # e.g., " 1 Biology: The Science of Life 1"
        self.part_pattern = re.compile(r'^PART\s+(I{1,7}|[IVXLCDM]+)\s+(.+)$', re.IGNORECASE)  # e.g., "PART I The Cell"
        self.subtopic_pattern = re.compile(r'^\s*(\d+\.\d+)\s+(.+?)\s+(\d+)\s*$')  # e.g., " 1.1  The Characteristics of Life 2"
        self.subsubtopic_pattern = re.compile(r'^\s*(\d+\.\d+\.\d+)\s+(.+?)\s+(\d+)\s*$')  # e.g., " 1.1.1 Some Title 5"
        
    def parse_brief_toc(self, document: Document) -> List[Dict]:
        """
        Parse brief table of contents (chapter numbers, titles, and page numbers).
        Handles multi-line chapter titles (e.g., Chapter 9, Chapter 17).
        
        Args:
            document: Document containing brief TOC (usually index 3)
            
        Returns:
            List of chapter entries with number, title, and page_label
        """
        content = document.page_content
        lines = content.split('\n')
        
        # Preprocess to join multi-line chapter entries
        # e.g., " 9  Meiosis and the Genetic Basis of Sexual \n'Reproduction 145" 
        # should become " 9  Meiosis and the Genetic Basis of Sexual Reproduction 145"
        preprocessed_lines = self._preprocess_brief_toc_lines(lines)
        
        chapters = []
        current_part = None
        
        for line in preprocessed_lines:
            line = line.strip()
            if not line:
                continue
            
            # Skip page label (e.g., "iii")
            if re.match(r'^[ivxlcdm]+$', line, re.IGNORECASE):
                continue
            
            # Skip "Brief Contents" marker
            if "Brief Contents" in line or "BRIEF CONTENTS" in line:
                continue
            
            # Check for PART markers
            part_match = self.part_pattern.match(line)
            if part_match:
                current_part = {
                    "part_number": part_match.group(1),
                    "part_title": part_match.group(2).strip()
                }
                continue
            
            # Match chapter pattern: " 1 Biology: The Science of Life 1"
            # Or multi-line: " 9  Meiosis and the Genetic Basis of Sexual Reproduction 145"
            chapter_match = self.chapter_pattern.match(line)
            if chapter_match:
                chapter_num = chapter_match.group(1)
                chapter_title = chapter_match.group(2).strip()
                page_num = chapter_match.group(3)
                
                # Clean up title - remove any trailing whitespace or special characters
                chapter_title = chapter_title.rstrip('\xa0 \t')
                
                # Handle titles that might still be incomplete
                if not chapter_title or len(chapter_title) < 3:
                    # Skip if title is too short or missing
                    continue
                
                chapters.append({
                    "chapter_number": chapter_num,
                    "chapter_title": chapter_title,
                    "page_label": page_num,
                    "part": current_part.copy() if current_part else None
                })
        
        # Sort brief TOC by chapter_number (as integer for proper numeric sorting)
        try:
            chapters.sort(key=lambda ch: int(ch.get('chapter_number', 0)))
        except (ValueError, TypeError):
            # Fallback to string sorting if conversion fails
            chapters.sort(key=lambda ch: str(ch.get('chapter_number', '')))
        
        return chapters
    
    def _preprocess_brief_toc_lines(self, lines: List[str]) -> List[str]:
        """
        Preprocess brief TOC lines to join multi-line chapter entries.
        Handles cases like:
        - " 9  Meiosis and the Genetic Basis of Sexual \n'Reproduction 145"
        - " 17  The Microorganisms: Viruses, Bacteria, and \n'Protists 286"
        
        Args:
            lines: Raw lines from brief TOC document
            
        Returns:
            List of preprocessed lines with multi-line entries joined
        """
        preprocessed = []
        i = 0
        
        while i < len(lines):
            # Don't strip yet - we need original for checking
            original_line = lines[i]
            current_line = original_line.strip()
            
            # Clean up non-breaking spaces and other special characters
            current_line = current_line.replace('\xa0', ' ').strip()
            
            # Skip empty lines
            if not current_line:
                preprocessed.append(original_line)  # Keep original for spacing
                i += 1
                continue
            
            # Skip page labels, PART markers, etc.
            if (re.match(r'^[ivxlcdm]+$', current_line, re.IGNORECASE) or
                "Brief Contents" in current_line.upper() or
                self.part_pattern.match(current_line)):
                preprocessed.append(current_line)
                i += 1
                continue
            
            # Check if this line starts with a chapter number pattern
            # Pattern: " 9  Title starts here" or " 17  Title starts"
            chapter_start_match = re.match(r'^\s*(\d+)\s+(.+)$', current_line)
            if chapter_start_match:
                chapter_num = chapter_start_match.group(1)
                title_part = chapter_start_match.group(2).strip()
                # Clean up title part - remove trailing special characters
                title_part = title_part.rstrip('\xa0 \t').strip()
                
                # Check if this line ends with the page number (complete entry)
                # Pattern: "Title 145" or "Title 286"
                complete_match = re.match(r'^(.+?)\s+(\d+)\s*$', title_part)
                if complete_match:
                    # Complete entry on one line - use as-is but clean it
                    clean_line = f" {chapter_num}  {complete_match.group(1).strip()} {complete_match.group(2)}"
                    preprocessed.append(clean_line)
                    i += 1
                    continue
                
                # Not complete - check next line(s) for continuation
                # Next line should have the rest of the title and page number
                if i + 1 < len(lines):
                    next_line_raw = lines[i + 1]
                    next_line = next_line_raw.strip()
                    # Clean up next line too - remove non-breaking spaces and other special chars
                    next_line = next_line.replace('\xa0', ' ').replace('\u2009', ' ').strip()
                    
                    # Check if next line looks like continuation:
                    # - Not empty
                    # - Starts with capital letter (title continuation)
                    # - Ends with a page number (digits)
                    # - Not a new chapter (doesn't start with digits and space)
                    # - Not a PART marker
                    # - Not "Brief Contents" or similar
                    if (next_line and 
                        not re.match(r'^\d+\s+', next_line) and 
                        not self.part_pattern.match(next_line) and
                        "Brief Contents" not in next_line.upper() and
                        not re.match(r'^[ivxlcdm]+$', next_line, re.IGNORECASE)):
                        
                        # Pattern: starts with capital, has content, ends with page number
                        # Simple pattern: "Reproduction 145" or "Protists 286"
                        continuation_match = re.match(r'^([A-Z].+?)\s+(\d+)\s*$', next_line)
                        if continuation_match:
                            # This is a continuation - join the lines
                            title_continuation = continuation_match.group(1).strip()
                            page_num = continuation_match.group(2).strip()
                            
                            # Clean up both title parts
                            title_part_clean = title_part.rstrip('\xa0 \t').strip()
                            title_continuation_clean = title_continuation.rstrip('\xa0 \t').strip()
                            
                            # Combine: "Title part 1" + "Title part 2 PageNum"
                            combined_title = f"{title_part_clean} {title_continuation_clean}".strip()
                            combined_line = f" {chapter_num}  {combined_title} {page_num}"
                            preprocessed.append(combined_line)
                            i += 2  # Skip both lines
                            continue
            
            # No special handling needed - add as-is but clean it
            clean_line = current_line.replace('\xa0', ' ').strip()
            preprocessed.append(clean_line)
            i += 1
        
        return preprocessed
    
    def _preprocess_lines(self, lines: List[str]) -> List[str]:
        """
        Preprocess lines to join multi-line entries.
        Joins lines where continuation is indicated (e.g., ends with "of" or missing page number).
        
        Args:
            lines: List of raw lines from TOC
            
        Returns:
            List of preprocessed lines with continuations joined
        """
        # Use iterative approach to handle multi-line entries spanning 2+ lines
        # Continue joining until no more joins are possible
        max_iterations = 10  # Safety limit to prevent infinite loops
        iteration = 0
        current_lines = lines[:]
        
        while iteration < max_iterations:
            iteration += 1
            preprocessed = []
            i = 0
            made_changes = False
            
            while i < len(current_lines):
                original_line = current_lines[i]
                line = original_line.strip()
                
                # Skip empty lines but keep them
                if not line:
                    preprocessed.append(original_line)
                    i += 1
                    continue
                
                # Check if this line might continue on the next line
                if i + 1 < len(current_lines):
                    next_line_raw = current_lines[i + 1]
                    next_line = next_line_raw.strip()
                    
                    if next_line:  # Next line is not empty
                        # Check if current line has a subtopic pattern (X.Y like " 5.1" or " 8.2")
                        has_subtopic_pattern = bool(re.match(r'^\s+\d+\.\d+\s+', original_line))
                        
                        # Check if current line has a page number at the end
                        has_page_number = bool(re.search(r'\s+\d+\s*$', line))
                        
                        # Check if current line looks like a subsubtopic (no X.Y pattern, starts with letter, no page number yet)
                        looks_like_subsubtopic = (
                            not has_subtopic_pattern and
                            re.match(r'^[A-Za-z]', line) and  # Allow lowercase for continuation
                            not has_page_number and
                            not re.match(r'^\s*CHAPTER', line, re.IGNORECASE) and
                            not self.part_pattern.match(line) and
                            not re.match(r'^[ivxlcdm]+$', line, re.IGNORECASE) and
                            line.upper() != "CONTENTS"
                        )
                        
                        # Check if line ends with continuation indicators
                        ends_with_colon = line.endswith(':') or line.endswith(',')
                        ends_with_continuation_word = bool(re.search(r'\s+(of|and|the|in|on|at|to|for|with|from)\s*$', line, re.IGNORECASE))
                        ends_incomplete = original_line.rstrip() != original_line.rstrip(' \t')
                        
                        # Check if next line looks like a continuation
                        next_starts_letter = bool(re.match(r'^[A-Za-z]', next_line))  # Allow lowercase (e.g., "and Cytokinesis")
                        next_has_page_number = bool(re.search(r'\s+\d+\s*$', next_line))
                        next_is_pattern = bool(re.match(r'^\s*\d+\.\d+\s+', next_line_raw))
                        next_is_chapter_marker = (next_line.upper() in ["CHAPTER", "CONTENTS", "PART"] or 
                                                  re.match(r'^\s*CHAPTER', next_line, re.IGNORECASE))
                        next_is_roman_numeral = bool(re.match(r'^[ivxlcdm]+$', next_line, re.IGNORECASE))
                        next_is_part_marker = self.part_pattern.match(next_line)
                        
                        # Decision: join if current line is incomplete and next line continues it
                        should_join = False
                        
                        if has_subtopic_pattern and not has_page_number:
                            # Subtopic pattern without page number - needs continuation
                            # e.g., " 6.3 The Calvin Cycle Reactions—Making" -> "Sugars 103"
                            if (next_starts_letter and next_has_page_number and 
                                not next_is_pattern and not next_is_chapter_marker and 
                                not next_is_roman_numeral and not next_is_part_marker):
                                should_join = True
                        elif looks_like_subsubtopic:
                            # Subsubtopic without page number - check if next line completes it
                            # e.g., "Phases of Complete Glucose" -> "Breakdown 112"
                            # e.g., "Interphase, Mitosis," -> "and Cytokinesis 128"
                            if (next_starts_letter and 
                                not next_is_pattern and not next_is_chapter_marker and 
                                not next_is_roman_numeral and not next_is_part_marker):
                                # Join if next line has page number OR if current line ends with continuation indicator
                                if next_has_page_number or ends_with_colon or ends_with_continuation_word:
                                    should_join = True
                        elif ends_with_colon or ends_with_continuation_word or ends_incomplete:
                            # Ends with colon, comma, continuation word, or trailing whitespace
                            # e.g., "The Cell Cycle:" -> "Interphase, Mitosis,"
                            # e.g., "Interphase, Mitosis," -> "and Cytokinesis 128"
                            if (next_starts_letter and 
                                not next_is_pattern and not next_is_chapter_marker and 
                                not next_is_roman_numeral and not next_is_part_marker):
                                should_join = True
                        elif not has_page_number and next_starts_letter:
                            # Current line has no page number, next might continue or complete it
                            if (not next_is_pattern and not next_is_chapter_marker and 
                                not next_is_roman_numeral and not next_is_part_marker):
                                # Additional check: current line should look incomplete
                                if not line.endswith('.') and len(line) > 3:
                                    should_join = True
                        
                        if should_join:
                            # Join the lines - remove trailing whitespace from first, add space, then next line
                            combined = original_line.rstrip() + " " + next_line
                            preprocessed.append(combined)
                            i += 2  # Skip both lines
                            made_changes = True
                            continue
                
                # No continuation, add line as-is
                preprocessed.append(original_line)
                i += 1
            
            # If no changes were made in this iteration, we're done
            if not made_changes:
                break
            
            # Use preprocessed result as input for next iteration to handle 3+ line spans
            current_lines = preprocessed
        
        return current_lines
    
    def parse_detailed_toc(
        self, 
        documents: List[Document],
        brief_toc: Optional[List[Dict]] = None
    ) -> List[Dict]:
        """
        Parse detailed table of contents with subtopics and subsubtopics.
        Uses brief_toc to ensure correct chapter boundaries and maps subtopics by chapter number.
        
        Args:
            documents: List of documents containing detailed TOC (usually indices 11-18)
            brief_toc: Brief TOC to get chapter numbers and boundaries
            
        Returns:
            List of chapter entries with full structure including subtopics
        """
        # Combine all TOC documents
        full_content = '\n'.join([doc.page_content for doc in documents])
        lines = full_content.split('\n')
        
        # Preprocess to join multi-line entries
        lines = self._preprocess_lines(lines)
        
        # Create chapter lookup from brief_toc (REQUIRED for correct mapping)
        if not brief_toc:
            # Cannot parse correctly without brief_toc
            # The brief_toc provides chapter boundaries - without it, subtopics can scatter
            return []
        
        chapter_lookup = {}
        chapter_numbers = set()
        if brief_toc:
            for ch in brief_toc:
                chapter_num = str(ch['chapter_number'])  # Ensure string for consistent comparison
                chapter_lookup[chapter_num] = {
                    'title': ch['chapter_title'],
                    'page_label': ch['page_label'],
                    'part': ch.get('part')
                }
                chapter_numbers.add(chapter_num)
        
        # First pass: Collect all subtopics and subsubtopics with their chapter numbers
        all_subtopics = {}  # key: (chapter_num, subtopic_num), value: subtopic data
        all_subsubtopics = {}  # key: (chapter_num, subtopic_num, subsubtopic_num), value: subsubtopic data
        
        current_chapter_num = None
        current_subtopic_num = None
        
        i = 0
        while i < len(lines):
            original_line = lines[i]
            line = original_line.strip()
            
            # Skip empty lines
            if not line:
                i += 1
                continue
            
            # Skip page labels (roman numerals)
            if re.match(r'^[ivxlcdm]+$', line, re.IGNORECASE):
                i += 1
                continue
            
            # Skip "Contents" header
            if line.upper() == "CONTENTS":
                i += 1
                continue
            
            # Detect "CHAPTER" marker to update current chapter
            if line.upper() == "CHAPTER":
                i += 1
                if i < len(lines):
                    chapter_num_line = lines[i].strip()
                    chapter_num_str = str(chapter_num_line)
                    if re.match(r'^\d+$', chapter_num_line) and chapter_num_str in chapter_numbers:
                        current_chapter_num = chapter_num_str
                        i += 1
                        # Skip chapter title line
                        if i < len(lines):
                            i += 1
                        continue
                i += 1
                continue
            
            # Check for PART markers - don't reset chapter, just note
            if self.part_pattern.match(line):
                i += 1
                continue
            
            # Match subtopic pattern: " 1.1 The Characteristics of Life 2"
            # More flexible pattern: allows for missing page numbers or different formatting
            # Pattern 1: " 1.1 Title 123" (with page number)
            # Pattern 2: " 1.1 Title" (without page number)
            subtopic_match = re.match(r'^\s+(\d+\.\d+)\s+(.+?)(?:\s+(\d+))?\s*$', original_line)
            if subtopic_match:
                subtopic_num = subtopic_match.group(1)
                subtopic_title_raw = subtopic_match.group(2).strip()
                page_num = subtopic_match.group(3) if subtopic_match.group(3) else ""
                
                # Clean up title - remove trailing numbers that might be page numbers
                # But be careful not to remove numbers that are part of the title
                subtopic_title = subtopic_title_raw
                if not page_num and re.search(r'\s+\d+\s*$', subtopic_title):
                    # Might have a page number that wasn't captured, try to extract it
                    title_match = re.match(r'^(.+?)\s+(\d+)\s*$', subtopic_title)
                    if title_match:
                        subtopic_title = title_match.group(1).strip()
                        page_num = title_match.group(2)
                
                # Extract chapter number from subtopic prefix (e.g., "1.1" -> "1", "25.3" -> "25", "8.2" -> "8")
                # ALWAYS use the prefix for mapping - this ensures correct assignment even at page boundaries
                subtopic_chapter_num = str(subtopic_num.split('.')[0])
                
                # CRITICAL: Only process if this chapter exists in our lookup from brief_toc
                # This ensures subtopics are mapped to correct chapters based on their number prefix
                # Using string comparison for reliability
                if subtopic_chapter_num in chapter_numbers:
                    current_chapter_num = subtopic_chapter_num
                    current_subtopic_num = subtopic_num
                    
                    key = (subtopic_chapter_num, subtopic_num)
                    # Only create if doesn't exist (to preserve subsubtopics if already created)
                    if key not in all_subtopics:
                        all_subtopics[key] = {
                            "subtopic_number": subtopic_num,
                            "subtopic_title": subtopic_title,
                            "page_label": page_num,
                            "subsubtopics": []
                        }
                    else:
                        # Update existing (might have been created during preprocessing or subsubtopic collection)
                        if not all_subtopics[key]["subtopic_title"] or all_subtopics[key]["subtopic_title"] == "":
                            all_subtopics[key]["subtopic_title"] = subtopic_title
                        if page_num and not all_subtopics[key]["page_label"]:
                            all_subtopics[key]["page_label"] = page_num
                
                i += 1
                continue
            
            # Match subsubtopic pattern (unnumbered): "Measuring Energy 80" or "Life Requires Materials and Energy 2"
            # Subsubtopics: don't start with numbers (X.Y pattern), end with page number, can span multiple lines
            # IMPORTANT: After preprocessing, multi-line subsubtopics should be joined into single lines
            # Check if we have active context (a subtopic we're currently processing)
            if current_chapter_num and current_subtopic_num:
                # Verify current context is still valid (same chapter)
                current_context_valid = current_subtopic_num.split('.')[0] == current_chapter_num
                
                if current_context_valid:
                    # Check this is not a new subtopic (would have X.Y pattern like " 5.2")
                    is_not_new_subtopic = not re.match(r'^\s*\d+\.\d+\s+', original_line)
                    
                    # Check this is not a chapter marker, PART marker, etc.
                    is_not_special_marker = (
                        not re.match(r'^\s*CHAPTER', original_line, re.IGNORECASE) and
                        not self.part_pattern.match(line) and
                        not re.match(r'^[ivxlcdm]+$', line, re.IGNORECASE) and
                        line.upper() != "CONTENTS"
                    )
                    
                    if is_not_new_subtopic and is_not_special_marker:
                        # Check if it matches subsubtopic pattern:
                        # Subsubtopics: don't start with X.Y numbers, start with letter, end with page number
                        # Examples: "Measuring Energy 80", "Energy Laws 80", "Phases of Complete Glucose Breakdown 112"
                        # Pattern: optional whitespace, title (any chars), one or more spaces, page number
                        # Use .+? (non-greedy) to match title until space before page number
                        # This pattern works because .+? stops when it sees \s+(\d+)
                        subsubtopic_match = re.match(r'^\s*([A-Za-z].+?)\s+(\d+)\s*$', original_line)
                        
                        # Additional validation: must have actual meaningful content
                        if subsubtopic_match:
                            potential_title = subsubtopic_match.group(1).strip()
                            page_num = subsubtopic_match.group(2).strip()
                            
                            # Validate: title should have letters, be meaningful, and page number should be numeric
                            if (potential_title and 
                                re.search(r'[A-Za-z]', potential_title) and 
                                len(potential_title.strip()) > 2 and
                                not potential_title.strip().isdigit() and  # Not just a number
                                page_num.isdigit()):  # Page number must be digits
                                
                                subsubtopic_title = potential_title
                                
                                # Clean up title - remove trailing special characters and whitespace
                                subsubtopic_title = subsubtopic_title.rstrip('\xa0 \t,.:;-').strip()
                                
                                # Only add if we have a valid title after cleaning
                                if subsubtopic_title and len(subsubtopic_title) > 2:
                                    # Add to current subtopic's subsubtopics
                                    key = (current_chapter_num, current_subtopic_num)
                                    if key in all_subtopics:
                                        all_subtopics[key]["subsubtopics"].append({
                                            "subsubtopic_number": "",
                                            "subsubtopic_title": subsubtopic_title,
                                            "page_label": page_num
                                        })
                                    else:
                                        # Context mismatch - subtopic might not have been created yet
                                        # Create it now so we can add the subsubtopic
                                        all_subtopics[key] = {
                                            "subtopic_number": current_subtopic_num,
                                            "subtopic_title": "",  # Will be filled when we see the subtopic
                                            "page_label": "",
                                            "subsubtopics": [{
                                                "subsubtopic_number": "",
                                                "subsubtopic_title": subsubtopic_title,
                                                "page_label": page_num
                                            }]
                                        }
                        
                        i += 1
                        continue
                else:
                    # Context invalid - reset
                    current_chapter_num = None
                    current_subtopic_num = None
            
            
            i += 1
        
        # Second pass: Build chapters using brief_toc structure and assign subtopics
        # This ensures correct mapping: subtopics are matched by chapter number prefix
        # IMPORTANT: Include ALL chapters from brief_toc, even if they have no subtopics
        chapters = []
        if brief_toc:
            for ch_info in brief_toc:
                chapter_num = str(ch_info['chapter_number'])  # Ensure string type
                
                # Find all subtopics for this chapter (match by chapter number prefix from subtopic number)
                # e.g., subtopic "25.3" has prefix "25" -> belongs to chapter "25"
                # e.g., subtopic "8.2" has prefix "8" -> belongs to chapter "8"
                # e.g., subtopic "9.1" has prefix "9" -> belongs to chapter "9"
                chapter_subtopics = []
                for (ch_num, sub_num), subtopic_data in all_subtopics.items():
                    # Ensure both are strings for comparison
                    if str(ch_num) == str(chapter_num):
                        # Make a deep copy to preserve subsubtopics
                        subtopic_copy = subtopic_data.copy()
                        subtopic_copy["subsubtopics"] = subtopic_data.get("subsubtopics", [])[:]
                        chapter_subtopics.append(subtopic_copy)
                
                # Sort subtopics by subtopic number (numeric sorting: 8.1, 8.2, 8.10, not 8.1, 8.10, 8.2)
                try:
                    chapter_subtopics.sort(key=lambda sub: tuple(map(int, sub['subtopic_number'].split('.'))))
                except (ValueError, TypeError):
                    chapter_subtopics.sort(key=lambda sub: sub['subtopic_number'])
                
                # Ensure subsubtopics are preserved (don't sort them, keep their collection order)
                for subtopic in chapter_subtopics:
                    subsubtopics = subtopic.get('subsubtopics', [])
                    # Filter out any None or invalid entries, but preserve order
                    if subsubtopics:
                        # Only keep subsubtopics with valid titles (not empty strings)
                        valid_subsubtopics = [
                            s for s in subsubtopics 
                            if s and isinstance(s, dict) and s.get('subsubtopic_title', '').strip()
                        ]
                        subtopic['subsubtopics'] = valid_subsubtopics
                    else:
                        # Ensure it's an empty list, not None
                        subtopic['subsubtopics'] = []
                
                # Always create chapter entry, even if it has no subtopics (like Chapter 9 might not have subtopics in detailed TOC)
                chapter = {
                    "chapter_number": chapter_num,
                    "chapter_title": ch_info['chapter_title'],
                    "page_label": ch_info['page_label'],
                    "subtopics": chapter_subtopics
                }
                chapters.append(chapter)
        
        # If no brief_toc provided, fall back to parsing chapters from TOC
        if not chapters:
            chapters = self._parse_chapters_without_brief_toc(lines, all_subtopics)
            
        
        # Sort chapters by chapter_number (as integer for proper numeric sorting)
        try:
            chapters.sort(key=lambda ch: int(ch.get('chapter_number', 0)))
        except (ValueError, TypeError):
            # Fallback to string sorting if conversion fails
            chapters.sort(key=lambda ch: str(ch.get('chapter_number', '')))
        
        return chapters
    
    def _parse_chapters_without_brief_toc(self, lines: List[str], all_subtopics: dict) -> List[Dict]:
        """
        Fallback method to parse chapters directly from TOC when brief_toc is not available.
        """
        chapters = []
        current_chapter = None
        current_chapter_num = None
        
        # Extract unique chapter numbers from subtopics
        chapter_nums = set()
        for (ch_num, _) in all_subtopics.keys():
            chapter_nums.add(ch_num)
        
        # Parse chapter headers from lines
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            
            if line.upper() == "CHAPTER":
                i += 1
                if i < len(lines):
                    chapter_num = lines[i].strip()
                    if chapter_num in chapter_nums:
                        current_chapter_num = chapter_num
                        i += 1
                        if i < len(lines):
                            title_line = lines[i].strip()
                            title_match = re.match(r'^(.+?)\s+(\d+)\s*$', title_line)
                            if title_match:
                                chapter_title = title_match.group(1).strip()
                                page_num = title_match.group(2)
                            else:
                                chapter_title = title_line
                                page_num = ""
                            
                            # Find subtopics for this chapter
                            chapter_subtopics = []
                            for (ch_num, sub_num), subtopic_data in all_subtopics.items():
                                if ch_num == current_chapter_num:
                                    chapter_subtopics.append(subtopic_data.copy())
                            
                            try:
                                chapter_subtopics.sort(key=lambda sub: tuple(map(int, sub['subtopic_number'].split('.'))))
                            except (ValueError, TypeError):
                                chapter_subtopics.sort(key=lambda sub: sub['subtopic_number'])
                            
                            chapters.append({
                                "chapter_number": current_chapter_num,
                                "chapter_title": chapter_title,
                                "page_label": page_num,
                                "subtopics": chapter_subtopics
                            })
                            i += 1
                            continue
            i += 1
        
        return chapters
    
    def create_page_label_to_index_map(
        self, 
        documents: List[Document]
    ) -> Dict[str, int]:
        """
        Create a mapping from page_label to document index.
        
        Args:
            documents: List of all documents
            
        Returns:
            Dictionary mapping page_label to document index
        """
        page_map = {}
        for idx, doc in enumerate(documents):
            page_label = doc.metadata.get('page_label', '')
            if page_label:
                # Handle roman numerals and numeric labels
                page_map[str(page_label)] = idx
        return page_map
    
    def find_chapter_document_range(
        self,
        chapter_page_label: str,
        toc_chapters: List[Dict],
        page_label_map: Dict[str, int],
        documents: List[Document]
    ) -> Optional[Tuple[int, int]]:
        """
        Find the document index range for a specific chapter.
        
        Args:
            chapter_page_label: Page label where chapter starts (e.g., "1")
            toc_chapters: List of chapters from TOC
            page_label_map: Mapping from page_label to document index
            documents: List of all documents
            
        Returns:
            Tuple of (start_index, end_index) or None if not found
        """
        # Find chapter in TOC
        chapter_info = None
        for ch in toc_chapters:
            if str(ch.get('page_label', '')) == str(chapter_page_label):
                chapter_info = ch
                break
        
        if not chapter_info:
            return None
        
        # Find start index
        start_idx = page_label_map.get(str(chapter_page_label))
        if start_idx is None:
            return None
        
        # Find end index (next chapter or end of document)
        chapter_num = int(chapter_info['chapter_number'])
        next_chapter_page = None
        
        # Find next chapter in TOC
        for ch in toc_chapters:
            ch_num = int(ch.get('chapter_number', 0))
            if ch_num == chapter_num + 1:
                next_chapter_page = str(ch.get('page_label', ''))
                break
        
        if next_chapter_page and next_chapter_page in page_label_map:
            end_idx = page_label_map[next_chapter_page] - 1
        else:
            # Last chapter - go to end of documents
            end_idx = len(documents) - 1
        
        return (start_idx, end_idx)
    
    def save_toc_to_json(self, toc_data: Dict, output_path: str):
        """
        Save TOC data to JSON file.
        
        Args:
            toc_data: Dictionary containing TOC data (brief_toc, detailed_toc, page_label_map)
            output_path: Path to output JSON file (can be string or Path object)
        """
        import json
        import os
        
        # Convert Path object to string if needed
        if hasattr(output_path, '__str__'):
            output_path = str(output_path)
        
        # Create directory if it doesn't exist
        dir_path = os.path.dirname(output_path)
        if dir_path:
            os.makedirs(dir_path, exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(toc_data, f, indent=2, ensure_ascii=False)
        
        return toc_data
