import re

class ContentParser:
    
    def __init__(self):
        pass
    
    @staticmethod
    def clean_content(content: str) -> str:
        """
        Clean content by removing unnecessary newlines and quotes.
        
        Rules:
        - Remove \n that is not after sentence/paragraph ending punctuation (. , ? or :)
        - If next line starts with a number, "Figure" or "Section", leave \n
        - Remove beginning and ending ' of each line
        - If a line ends with -, remove the - and join next line without space
        - If a line is a single letter and space (e.g., "p "), remove space and join next line without space
        - If a line is camel case (main words are capitalized), leave it on its own line
        """
        if not content:
            return content
        
        lines = content.split('\n')
        if not lines:
            return content
        
        cleaned_lines = []
        
        for i in range(len(lines)):
            current_line = lines[i]
            
            # Remove beginning and ending ' of each line
            current_line = current_line.strip("'")
            
            # Skip empty lines but preserve structure
            if not current_line.strip():
                if cleaned_lines and cleaned_lines[-1].strip():
                    # Only add empty line if previous line ended with punctuation
                    if cleaned_lines[-1].rstrip() and cleaned_lines[-1].rstrip()[-1] in '.?!:,':
                        cleaned_lines.append('')
                continue
            
            # Check if we should keep the newline before this line
            if i > 0 and cleaned_lines:
                prev_line_original = cleaned_lines[-1]
                prev_line = prev_line_original.rstrip()
                
                # Check if previous line ends with hyphen (-)
                if prev_line and prev_line.endswith('-'):
                    # Remove the hyphen and join without space
                    cleaned_lines[-1] = prev_line[:-1].rstrip() + current_line.strip()
                    continue
                
                # Check if previous line is a single letter followed by space (e.g., "p ")
                # Check original line before rstrip to see if it ends with space
                if prev_line_original and len(prev_line.strip()) == 1 and prev_line_original.endswith(' '):
                    # Remove the space and join without space
                    cleaned_lines[-1] = prev_line.strip() + current_line.strip()
                    continue
                
                # Check if current line is camel case (main words are capitalized)
                current_stripped = current_line.strip()
                words = current_stripped.split()
                # Check if line has multiple capitalized words (camel case/title case)
                capitalized_words = [w for w in words if w and w[0].isupper()]
                is_camel_case = len(capitalized_words) >= 2 and len(words) > 1
                
                # If line is camel case, keep it on its own line
                if is_camel_case:
                    cleaned_lines.append(current_line)
                    continue
                
                # Check if current line starts with number, Figure, or Section
                starts_with_special = (
                    bool(re.match(r'^\d+', current_stripped)) or
                    current_stripped.startswith('Figure') or
                    current_stripped.startswith('Section')
                )
                
                # If previous line ends with sentence-ending punctuation (. , ? or :), keep newline
                if prev_line and prev_line[-1] in '.?!:,':
                    if starts_with_special:
                        cleaned_lines.append(current_line)
                    else:
                        # Join with previous line (no newline)
                        cleaned_lines[-1] += ' ' + current_line
                else:
                    # Previous line doesn't end with punctuation
                    if starts_with_special:
                        cleaned_lines.append(current_line)
                    else:
                        # Join with previous line (no newline)
                        cleaned_lines[-1] += ' ' + current_line
            else:
                # First line
                cleaned_lines.append(current_line)
        
        return '\n'.join(cleaned_lines)
    
    def parse_chapter_title_page(self, page_content: str, title: str) -> dict[str, str]:
        """
        Parse the chapter title page from the given page content.
        
        Args:
            page_content: The raw page content text
            title: The chapter title
            
        Returns:
            A dictionary containing:
            - title: The chapter title
            - prerequisites: prerequisites text
            - introduction: The introduction text
        """
        result = {
            'title': title,
            'prerequisites': '',
            'introduction': ''
        }
    
        
        # Find OUTLINE section
        outline_match = re.search(r'OUTLINE\n(.+?)(?=\nBEFORE YOU BEGIN\n)', page_content, re.DOTALL)
        
        # Find BEFORE YOU BEGIN section (prerequisites)
        # Prerequisites end when we find the introduction text (usually a capitalized title or sentence)
        before_begin_match = re.search(r'BEFORE YOU BEGIN\n(.+?)(?=\n[A-Z][a-z]{3,})', page_content, re.DOTALL)
        if before_begin_match:
            prerequisites_content = before_begin_match.group(1).strip()
            result['prerequisites'] = self.clean_content(prerequisites_content)
            
            # Find introduction text (everything after prerequisites)
            # Introduction starts after the prerequisites section
            prereq_end_pos = before_begin_match.end()
            introduction_content = page_content[prereq_end_pos:].strip()
            
            # Clean up: remove any leading newlines and find the actual start
            # Introduction usually starts with a capitalized word (title or first sentence)
            intro_match = re.search(r'^[A-Z][a-zA-Z\s]{10,}', introduction_content, re.MULTILINE)
            if intro_match:
                intro_start_pos = intro_match.start()
                introduction_content = introduction_content[intro_start_pos:].strip()
            
            result['introduction'] = self.clean_content(introduction_content)
        else:
            # Fallback: try to find text after "BEFORE YOU BEGIN" section
            after_prereq_match = re.search(r'BEFORE YOU BEGIN\n(.+?)(\n\n[A-Z][a-zA-Z\s]{10,})', page_content, re.DOTALL)
            if after_prereq_match:
                prerequisites_content = after_prereq_match.group(1).strip()
                result['prerequisites'] = self.clean_content(prerequisites_content)
                
                # Get introduction from the match
                intro_start = after_prereq_match.end(1)
                introduction_content = page_content[intro_start:].strip()
                result['introduction'] = self.clean_content(introduction_content)
        
        return result


    def parse_subtopic_content(self, page_content: str, subtopic_title: str, first_subsubtopic_title: str) -> dict[str, str]:
        """
        Extract the content of a subtopic from the given page content.
        
        Args:
            page_content: The raw page content text
            subtopic_title: The subtopic title
            first_subsubtopic_title: The title of the first subsubtopic (marks end of introduction)
        
        Returns:
            A dictionary containing:
            - learning_outcomes: Content from "Learning Outcomes" section
            - subtopic_introduction: Introduction text between learning outcomes and first subsubtopic
        """
        result = {
            'learning_outcomes': '',
            'subtopic_introduction': '',
        }
        
        # Find Learning Outcomes section
        # Learning outcomes typically end when we see text that's not a numbered list item
        # Look for content until we see a capitalized word that's not part of a numbered list
        learning_outcomes_match = re.search(r'Learning Outcomes\n(.+?)(?=\n[A-Z][a-z]{3,}[^0-9\n])', page_content, re.DOTALL)
        if learning_outcomes_match:
            learning_outcomes_content = learning_outcomes_match.group(1).strip()
            result['learning_outcomes'] = self.clean_content(learning_outcomes_content)
            
            # Find introduction text (everything after learning outcomes until first subsubtopic)
            learning_outcomes_end_pos = learning_outcomes_match.end()
            remaining_content = page_content[learning_outcomes_end_pos:].strip()
            
            # Find the first subsubtopic title to mark the end of introduction
            # Escape special regex characters in the title
            escaped_title = re.escape(first_subsubtopic_title)
            # Look for the title - it might be on a new line or have newlines before it
            intro_match = re.search(f'(.+?)(?=\n{escaped_title}|\n\n{escaped_title}|^{escaped_title})', remaining_content, re.DOTALL | re.MULTILINE)
            
            if intro_match:
                introduction_content = intro_match.group(1).strip()
                # Clean up: remove any leading text that's still part of learning outcomes format
                # Introduction should start with actual text, not numbers or "Upon completion"
                intro_clean_match = re.search(r'([A-Z][a-zA-Z\s]{10,})', introduction_content, re.MULTILINE)
                if intro_clean_match:
                    intro_start_pos = intro_clean_match.start()
                    introduction_content = introduction_content[intro_start_pos:].strip()
                
                result['subtopic_introduction'] = self.clean_content(introduction_content)
            else:
                # Fallback: if title not found, take all remaining content
                result['subtopic_introduction'] = self.clean_content(remaining_content)
        else:
            # If no Learning Outcomes section found, try to find introduction directly
            # Look for content between subtopic title and first subsubtopic
            escaped_subtopic = re.escape(subtopic_title)
            escaped_subsubtopic = re.escape(first_subsubtopic_title)
            
            # Try to find content between subtopic and first subsubtopic
            content_match = re.search(f'{escaped_subtopic}.*?({escaped_subsubtopic})', page_content, re.DOTALL)
            if content_match:
                # Extract content before the first subsubtopic
                intro_start = page_content.find(subtopic_title) + len(subtopic_title)
                intro_end = page_content.find(first_subsubtopic_title, intro_start)
                if intro_end > intro_start:
                    introduction_content = page_content[intro_start:intro_end].strip()
                    result['subtopic_introduction'] = self.clean_content(introduction_content)
        
        return result
    
    def parse_subsubtopic_content(self, page_contents: list[str], subsubtopic_title: str, next_subsubtopic_title: str) -> str:
        """
        Extract the content of a subsubtopic from the given page contents.
        
        Args:
            page_contents: The list of page contents
            subsubtopic_title: The subsubtopic title
            next_subsubtopic_title: The title of the next subsubtopic (marks end of current subsubtopic)
        
        Returns:
            The cleaned content of the subsubtopic
        """
        if not page_contents:
            return ''
        
        # Escape special regex characters in titles
        escaped_current_title = re.escape(subsubtopic_title)
        escaped_next_title = re.escape(next_subsubtopic_title)
        
        # Combine all page contents to search across pages
        combined_content = '\n'.join(page_contents)
        
        # Find the start position of the current subsubtopic title
        # Look for the title, possibly with newlines before it
        current_title_match = re.search(f'(\n|^){escaped_current_title}(\n|$)', combined_content, re.MULTILINE)
        
        if not current_title_match:
            # Title not found, return empty string
            return ''
        
        # Find the start of content (after the title)
        content_start_pos = current_title_match.end()
        
        # Find the next subsubtopic title to mark the end
        # Search from the content start position
        remaining_content = combined_content[content_start_pos:]
        next_title_match = re.search(f'(\n|^){escaped_next_title}(\n|$)', remaining_content, re.MULTILINE)
        
        if next_title_match:
            # Extract content up to the next subsubtopic title
            subsubtopic_content = remaining_content[:next_title_match.start()].strip()
        else:
            # No next title found, take all remaining content
            subsubtopic_content = remaining_content.strip()
        
        # Clean and return the content
        return self.clean_content(subsubtopic_content)
    
    def extract_figure_detailed_content(self, page_content: str, chapter_number: str) -> list[dict[str, str]]:
        """
        Extract the content of all figures in a page from the given page content.
        
        Args:
            page_content: The raw page content text
            chapter_number: The chapter number (e.g., "18")
        
        Returns:
            A list of dictionaries, each containing:
            - chapter_number: The chapter number
            - figure_number: The figure number (e.g., "18.1")
            - figure_title: The title of the figure
            - figure_description: The description of the figure
        """
        figures = []
        
        # Pattern to match "Figure chapter_number.x" followed by title
        # Captures: figure number after dot, and title
        # Title may be on the same line or continue to next line(s) until description starts
        escaped_chapter = re.escape(chapter_number)
        figure_pattern = rf'Figure\s+{escaped_chapter}\.(\d+)\s+(.+?)(?=\n[A-Z][a-z]|\n\n|$)'
        
        # Find all figure matches
        figure_matches = list(re.finditer(figure_pattern, page_content, re.DOTALL | re.MULTILINE))
        
        if not figure_matches:
            return figures
        
        # Process each figure
        for idx, figure_match in enumerate(figure_matches):
            result = {
                'chapter_number': chapter_number,
                'figure_number': '',
                'figure_title': '',
                'figure_description': '',
            }
            
            # Extract figure number after the dot
            figure_subnumber = figure_match.group(1)
            
            # Extract full figure number (e.g., "18.1")
            result['figure_number'] = f"{chapter_number}.{figure_subnumber}"
            
            # Extract figure title (text after "Figure xx.x" until description starts)
            # Description typically starts with a capitalized word or new paragraph
            figure_title = figure_match.group(2).strip()
            # Clean up title - remove trailing newlines and extra spaces
            figure_title = re.sub(r'\n+', ' ', figure_title).strip()
            result['figure_title'] = self.clean_content(figure_title)
            
            # Find the start position of the description (after the title)
            description_start_pos = figure_match.end()
            
            # Determine the end position: either next figure or end of content
            if idx < len(figure_matches) - 1:
                # There's a next figure in the same chapter, description ends before it
                next_figure_start = figure_matches[idx + 1].start()
                potential_description = page_content[description_start_pos:next_figure_start].strip()
            else:
                # This is the last figure, check for any next figure from other chapters or use all remaining content
                remaining_content = page_content[description_start_pos:].strip()
                next_figure_match = re.search(r'\nFigure\s+\d+\.\d+', remaining_content)
                if next_figure_match:
                    # Content up to next Figure (from any chapter)
                    potential_description = remaining_content[:next_figure_match.start()].strip()
                else:
                    # All remaining content
                    potential_description = remaining_content.strip()
            
            # Check if there's a copyright symbol © in the description
            # Find the last line containing ©
            lines = potential_description.split('\n')
            last_copyright_line_idx = -1
            
            for i in range(len(lines) - 1, -1, -1):
                if '©' in lines[i]:
                    last_copyright_line_idx = i
                    break
            
            if last_copyright_line_idx >= 0:
                # Include all lines up to and including the line with ©
                description_text = '\n'.join(lines[:last_copyright_line_idx + 1])
            else:
                # No copyright symbol found, use all potential description text
                description_text = potential_description
            
            # Clean and set the description
            result['figure_description'] = self.clean_content(description_text)
            
            figures.append(result)
        
        return figures