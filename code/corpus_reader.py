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
    
    def search_claude(self, query: str) -> List[Tuple[str, str, float]]:
        """Search Claude documentation for relevant content with scoring."""
        results = []
        query_lower = query.lower()
        query_words = [w for w in query_lower.split() if len(w) > 2]
        
        for filepath, content in self.claude_files.items():
            # Skip index files
            if filepath == "index.md":
                continue
                
            content_lower = content.lower()
            
            # Calculate relevance score
            score = 0
            for kw in query_words:
                # Count occurrences, not just presence
                count = content_lower.count(kw)
                if count > 0:
                    score += count * (1 if len(kw) > 4 else 0.5)
            
            # Also check title for strong match
            title_match = False
            lines = content.split('\n')
            for line in lines[:10]:
                if line.startswith('#') and any(kw in line.lower() for kw in query_words):
                    score *= 2  # Boost title matches
                    title_match = True
                    break
            
            if score >= 2:  # Lower threshold
                results.append((filepath, content, score))
        
        # Sort by score descending
        results.sort(key=lambda x: x[2], reverse=True)
        return [(r[0], r[1]) for r in results[:5]]
    
    def search_hackerrank(self, query: str) -> List[Tuple[str, str, float]]:
        """Search HackerRank documentation for relevant content with scoring."""
        results = []
        query_lower = query.lower()
        query_words = [w for w in query_lower.split() if len(w) > 2]
        
        for filepath, content in self.hackerrank_files.items():
            # Skip index files
            if filepath == "index.md":
                continue
                
            content_lower = content.lower()
            
            # Calculate relevance score
            score = 0
            for kw in query_words:
                count = content_lower.count(kw)
                if count > 0:
                    score += count * (1 if len(kw) > 4 else 0.5)
            
            # Boost title matches
            lines = content.split('\n')
            for line in lines[:10]:
                if line.startswith('#') and any(kw in line.lower() for kw in query_words):
                    score *= 2
                    break
            
            if score >= 2:
                results.append((filepath, content, score))
        
        # Sort by score descending
        results.sort(key=lambda x: x[2], reverse=True)
        return [(r[0], r[1]) for r in results[:5]]
    
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
        query_words = [w for w in query_lower.split() if len(w) > 3]
        
        best_match = None
        best_score = 0
        
        for filepath, content in search_results:
            # Skip index/summary files - look for actual content
            lines = content.split('\n')
            
            # Skip if this looks like an index file (has many links, minimal content)
            link_count = sum(1 for line in lines if '](' in line and line.strip().startswith('-'))
            if link_count > 10:
                continue
            
            relevant_lines = []
            score = 0
            
            for i, line in enumerate(lines):
                line_lower = line.lower()
                # Skip frontmatter and headers
                if line.startswith('---') or line.startswith('title:') or line.startswith('['):
                    continue
                    
                # Count keyword matches
                matches = sum(1 for kw in query_words if kw in line_lower)
                if matches > 0:
                    score += matches
                    # Capture this line and surrounding context
                    start = max(0, i - 2)
                    end = min(len(lines), i + 5)
                    relevant_lines.extend(lines[start:end])
            
            if score > best_score and relevant_lines:
                best_score = score
                # Remove duplicates while preserving order
                seen = set()
                unique_lines = []
                for line in relevant_lines:
                    line_stripped = line.strip()
                    if line_stripped and line_stripped not in seen and not line_stripped.startswith('---'):
                        seen.add(line_stripped)
                        unique_lines.append(line_stripped)
                best_match = '\n'.join(unique_lines[:15])
        
        return best_match
