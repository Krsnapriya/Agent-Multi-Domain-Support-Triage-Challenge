#!/usr/bin/env python3
"""
Corpus Reader Module - Reads and indexes support documentation files
"""

import os
import re
from typing import Dict, List, Optional, Tuple
from pathlib import Path


class CorpusReader:
    """Reads and indexes the support documentation corpus."""
    
    def __init__(self, data_dir: str):
        self.data_dir = Path(data_dir)
        self.claude_files: Dict[str, str] = {}
        self.hackerrank_files: Dict[str, str] = {}
        self.visa_files: Dict[str, str] = {}
        self.visa_countries: set = set()
        self._load_corpus()
    
    def _load_corpus(self):
        """Load all markdown files from the corpus."""
        # Load Claude files
        claude_dir = self.data_dir / "claude"
        if claude_dir.exists():
            for md_file in claude_dir.rglob("*.md"):
                rel_path = str(md_file.relative_to(claude_dir))
                content = md_file.read_text(encoding='utf-8')
                self.claude_files[rel_path] = content
        
        # Load HackerRank files
        hackerrank_dir = self.data_dir / "hackerrank"
        if hackerrank_dir.exists():
            for md_file in hackerrank_dir.rglob("*.md"):
                rel_path = str(md_file.relative_to(hackerrank_dir))
                content = md_file.read_text(encoding='utf-8')
                self.hackerrank_files[rel_path] = content
        
        # Load Visa files
        visa_dir = self.data_dir / "visa"
        if visa_dir.exists():
            for md_file in visa_dir.rglob("*.md"):
                rel_path = str(md_file.relative_to(visa_dir))
                content = md_file.read_text(encoding='utf-8')
                self.visa_files[rel_path] = content
                
                # Extract country list from support.md
                if "support.md" in str(md_file):
                    self._extract_countries(content)
    
    def _extract_countries(self, content: str):
        """Extract country names from Visa support file."""
        # Look for the table with country names
        lines = content.split('\n')
        in_table = False
        for line in lines:
            if '| Country |' in line:
                in_table = True
                continue
            if in_table and '|' in line:
                parts = line.split('|')
                if len(parts) >= 2:
                    country = parts[1].strip()
                    if country and not country.startswith('-'):
                        self.visa_countries.add(country)
            if in_table and '---' in line and '|' not in line:
                in_table = False
    
    def search_claude(self, query: str) -> List[Tuple[str, str]]:
        """Search Claude documentation for relevant content."""
        results = []
        query_lower = query.lower()
        
        for filepath, content in self.claude_files.items():
            content_lower = content.lower()
            # Check if query keywords appear in content
            keywords = query_lower.split()
            matches = sum(1 for kw in keywords if len(kw) > 3 and kw in content_lower)
            
            if matches >= 2:  # At least 2 keyword matches
                results.append((filepath, content))
        
        return results[:5]  # Return top 5 results
    
    def search_hackerrank(self, query: str) -> List[Tuple[str, str]]:
        """Search HackerRank documentation for relevant content."""
        results = []
        query_lower = query.lower()
        
        for filepath, content in self.hackerrank_files.items():
            content_lower = content.lower()
            keywords = query_lower.split()
            matches = sum(1 for kw in keywords if len(kw) > 3 and kw in content_lower)
            
            if matches >= 2:
                results.append((filepath, content))
        
        return results[:5]
    
    def search_visa(self, query: str) -> List[Tuple[str, str]]:
        """Search Visa documentation for relevant content."""
        results = []
        query_lower = query.lower()
        
        for filepath, content in self.visa_files.items():
            content_lower = content.lower()
            keywords = query_lower.split()
            matches = sum(1 for kw in keywords if len(kw) > 3 and kw in content_lower)
            
            if matches >= 1:  # Visa corpus is smaller, be more lenient
                results.append((filepath, content))
        
        return results[:5]
    
    def get_country_phone(self, country: str) -> Optional[str]:
        """Get phone number for a specific country from Visa corpus."""
        country_lower = country.lower()
        
        for content in self.visa_files.values():
            lines = content.split('\n')
            for i, line in enumerate(lines):
                if country_lower in line.lower() and '|' in line:
                    parts = line.split('|')
                    if len(parts) >= 3:
                        phone = parts[2].strip()
                        if phone and any(c.isdigit() for c in phone):
                            return phone
        return None
    
    def extract_answer_context(self, search_results: List[Tuple[str, str]], 
                               query: str) -> Optional[str]:
        """Extract relevant answer context from search results."""
        if not search_results:
            return None
        
        query_lower = query.lower()
        
        for filepath, content in search_results:
            lines = content.split('\n')
            relevant_lines = []
            capture = False
            
            for line in lines:
                line_lower = line.lower()
                # Check if this line or nearby lines contain answer
                if any(kw in line_lower for kw in query_lower.split() if len(kw) > 3):
                    capture = True
                
                if capture:
                    relevant_lines.append(line)
                    if line.strip().endswith('.') or line.strip().endswith('!'):
                        # End of paragraph
                        if len(relevant_lines) > 5:
                            break
            
            if relevant_lines:
                return '\n'.join(relevant_lines[:10])
        
        return None
