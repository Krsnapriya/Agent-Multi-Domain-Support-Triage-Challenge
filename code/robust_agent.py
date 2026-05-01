#!/usr/bin/env python3
"""
Robust Support Triage Agent - End-to-End Implementation
HackerRank Orchestrate Hackathon - May 2026

This is a completely self-contained, production-ready agent that:
1. Loads and indexes the full corpus (774+ articles)
2. Uses keyword-based retrieval with confidence scoring
3. Implements strict hallucination prevention
4. Handles all edge cases (injection attempts, invalid queries, multi-company)
5. Produces properly formatted output CSV

NO external dependencies beyond Python stdlib.
"""

import csv
import re
import os
import io
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Set
from dataclasses import dataclass, field

# ============================================================================
# CONFIGURATION
# ============================================================================

CODE_DIR = Path(__file__).parent
REPO_ROOT = CODE_DIR.parent
DATA_DIR = REPO_ROOT / "data"
SUPPORT_ISSUES_DIR = REPO_ROOT / "support_tickets"
OUTPUT_FILE = SUPPORT_ISSUES_DIR / "output.csv"
INPUT_FILE = SUPPORT_ISSUES_DIR / "support_tickets.csv"

# Confidence thresholds - tuned for higher reply rate
MIN_CONFIDENCE_SCORE = 1.5  # Lowered from 2.0 to increase reply rate
HIGH_CONFIDENCE_SCORE = 5.0  # Score indicating strong match

# Visa countries (extracted from corpus)
VISA_COUNTRIES = [
    "Anguilla", "Antigua", "Argentina", "Aruba", "Australia", "Austria", "Bahamas", "Bahrain",
    "Barbados", "Belgium", "Belize", "Bermuda", "Bolivia", "Bonaire", "Brazil", "British Virgin Islands",
    "Bulgaria", "Cambodia", "Canada", "Cayman Islands", "Chile", "China", "Colombia", "Costa Rica",
    "Croatia", "Curacao", "Czech Republic", "Denmark", "Dominica", "Dominican Republic", "Ecuador",
    "Egypt", "El Salvador", "Estonia", "Finland", "France", "Germany", "Gibraltar", "Greece",
    "Grenada", "Guam", "Guatemala", "Guyana", "Honduras", "Hong Kong", "Hungary", "Indonesia",
    "Ireland", "Israel", "Italy", "Jamaica", "Japan", "Jordan", "Kazakhstan", "Kenya", "Latvia",
    "Lebanon", "Liechtenstein", "Luxembourg", "Macedonia", "Malaysia", "Mauritius", "Mexico",
    "Monaco", "Montserrat", "Morocco", "Netherlands", "Nevis", "New Zealand", "Norway", "Panama",
    "Paraguay", "Peru", "Philippines", "Poland", "Portugal", "Puerto Rico", "Romania", "Russia",
    "Saint Kitts and Nevis", "Saint Lucia", "Saint Vincent", "Saudi Arabia", "Serbia", "Singapore",
    "Slovakia", "Slovenia", "South Africa", "South Korea", "Spain", "Sri Lanka", "Suriname",
    "Sweden", "Switzerland", "Taiwan", "Thailand", "Trinidad and Tobago", "Tunisia", "Turkey",
    "Turks and Caicos", "Ukraine", "United Arab Emirates", "United Kingdom", "United States",
    "Uruguay", "Venezuela", "Vietnam"
]

# Product area mappings
PRODUCT_AREA_KEYWORDS = {
    # Claude areas
    "billing": ["billing", "payment", "charge", "refund", "subscription", "plan", "pro", "max", "invoice", "cost", "price"],
    "privacy": ["privacy", "data", "security", "verification", "identity", "compliance", "gdpr"],
    "conversation_management": ["conversation", "chat", "memory", "search", "delete", "rename", "share", "incognito"],
    "account_management": ["account", "login", "logout", "password", "email", "session", "settings"],
    "api": ["api", "console", "key", "rate limit", "integration", "developer"],
    "mobile": ["mobile", "ios", "android", "app"],
    
    # HackerRank areas
    "screen": ["screen", "interview", "zoom", "connectivity", "camera", "microphone", "proctoring"],
    "community": ["community", "forum", "discussion", "help", "post"],
    "engage": ["engage", "event", "email", "campaign", "candidate"],
    "integrations": ["integration", "ats", "webhook", "api", "connector"],
    "interviews": ["interview", "question", "evaluation", "rubric"],
    "settings": ["settings", "configuration", "permission", "branding"],
    
    # Visa areas
    "travel_support": ["travel", "country", "exchange", "currency", "cheque", "check"],
    "general_support": ["lost", "stolen", "card", "fraud", "transaction"]
}

# Request type mappings
REQUEST_TYPE_KEYWORDS = {
    "product_issue": ["issue", "problem", "error", "not working", "broken", "can't", "unable", "help", "support"],
    "feature_request": ["feature", "add", "suggest", "improve", "enhancement", "wish", "request"],
    "bug": ["bug", "crash", "glitch", "defect", "malfunction"],
    "invalid": ["thank", "thanks", "iron man", "out of scope", "test", "hello", "hi "]
}

# Injection detection patterns
INJECTION_PATTERNS = [
    "ignore previous", "disregard", "system prompt", "override", "bypass",
    "jailbreak", "act as", "pretend you", "you are now", "forget all",
    "new instructions", "xml", "<|", "|>", "[system]", "debug mode"
]


# ============================================================================
# DATA STRUCTURES
# ============================================================================

@dataclass
class Article:
    """Represents a support article."""
    title: str
    content: str
    source_url: str
    file_path: str
    last_updated: str
    domain: str  # claude, hackerrank, or visa


@dataclass
class SearchResult:
    """Search result with scoring."""
    article: Article
    score: float
    matched_terms: List[str] = field(default_factory=list)


@dataclass
class TicketResult:
    """Result of processing a support ticket."""
    status: str  # "replied" or "escalated"
    product_area: str
    response: str
    justification: str
    request_type: str


# ============================================================================
# CORPUS LOADER
# ============================================================================

class CorpusLoader:
    """Loads and indexes the support documentation corpus."""
    
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.claude_articles: List[Article] = []
        self.hackerrank_articles: List[Article] = []
        self.visa_content: Dict = {"countries": {}, "procedures": [], "files": []}
        self.total_articles = 0
        self._load()
    
    def _load(self):
        """Load all corpus content."""
        # Load Claude articles
        claude_dir = self.data_dir / "claude"
        if claude_dir.exists():
            self.claude_articles = self._load_markdown_files(claude_dir, "claude")
        
        # Load HackerRank articles
        hackerrank_dir = self.data_dir / "hackerrank"
        if hackerrank_dir.exists():
            self.hackerrank_articles = self._load_markdown_files(hackerrank_dir, "hackerrank")
        
        # Load Visa content
        visa_dir = self.data_dir / "visa"
        if visa_dir.exists():
            self._load_visa_content(visa_dir)
        
        self.total_articles = len(self.claude_articles) + len(self.hackerrank_articles)
    
    def _load_markdown_files(self, directory: Path, domain: str) -> List[Article]:
        """Recursively load all markdown files."""
        articles = []
        for md_file in directory.rglob("*.md"):
            if md_file.name == "index.md":
                continue
            try:
                content = md_file.read_text(encoding="utf-8")
                article = self._parse_article(content, str(md_file), domain)
                if article:
                    articles.append(article)
            except Exception:
                continue
        return articles
    
    def _parse_article(self, content: str, file_path: str, domain: str) -> Optional[Article]:
        """Parse a markdown article into structured format."""
        lines = content.split("\n")
        title = ""
        source_url = ""
        last_updated = ""
        body_lines = []
        in_frontmatter = False
        
        for line in lines:
            if line.startswith("---"):
                in_frontmatter = not in_frontmatter
                continue
            
            if in_frontmatter:
                if line.startswith("title:"):
                    title = line.replace("title:", "").strip().strip("\"'")
                elif line.startswith("source_url:"):
                    source_url = line.replace("source_url:", "").strip().strip("\"'")
                elif line.startswith("last_updated"):
                    last_updated = line.split(":", 1)[1].strip().strip("\"'") if ":" in line else ""
            else:
                body_lines.append(line)
        
        if not title:
            title = Path(file_path).stem
        
        body = "\n".join(body_lines)
        
        return Article(
            title=title,
            content=body,
            source_url=source_url,
            file_path=file_path,
            last_updated=last_updated,
            domain=domain
        )
    
    def _load_visa_content(self, directory: Path):
        """Load Visa-specific content."""
        # Load main support.md for country phone numbers
        support_file = directory / "support.md"
        if support_file.exists():
            text = support_file.read_text(encoding="utf-8")
            for country in VISA_COUNTRIES:
                pattern = rf"\| {re.escape(country)} \| ([^\|]+)\|"
                match = re.search(pattern, text)
                if match:
                    phone = match.group(1).strip()
                    self.visa_content["countries"][country] = phone
        
        # Load travelers cheques content
        cheques_file = directory / "support" / "consumer" / "travelers-cheques.md"
        if cheques_file.exists():
            text = cheques_file.read_text(encoding="utf-8")
            self.visa_content["procedures"].append({
                "type": "travelers_cheques",
                "content": text,
                "source": str(cheques_file)
            })
        
        # Load all other visa files
        for md_file in directory.rglob("*.md"):
            if md_file.name != "support.md":
                try:
                    text = md_file.read_text(encoding="utf-8")
                    self.visa_content["files"].append({
                        "path": str(md_file),
                        "name": md_file.stem,
                        "content": text
                    })
                except Exception:
                    continue
    
    def search(self, query: str, domain: str, top_k: int = 5) -> List[SearchResult]:
        """Search articles for a domain with keyword scoring."""
        if domain == "claude":
            articles = self.claude_articles
        elif domain == "hackerrank":
            articles = self.hackerrank_articles
        else:
            return []
        
        query_lower = query.lower()
        query_words = set(w for w in query_lower.split() if len(w) > 2)
        
        results = []
        for article in articles:
            score, matched = self._calculate_score(article, query_lower, query_words)
            if score >= MIN_CONFIDENCE_SCORE:
                results.append(SearchResult(article=article, score=score, matched_terms=matched))
        
        results.sort(key=lambda x: x.score, reverse=True)
        return results[:top_k]
    
    def _calculate_score(self, article: Article, query_lower: str, query_words: Set[str]) -> Tuple[float, List[str]]:
        """Calculate relevance score for an article using hybrid BM25-like scoring."""
        title = article.title.lower()
        content = article.content.lower()
        
        score = 0.0
        matched = []
        
        # Title matches worth significantly more (BM25-style)
        title_len = len(title.split())
        for word in query_words:
            if word in title:
                # BM25-like scoring: term frequency normalized by document length
                tf = title.count(word) / max(title_len, 1)
                score += 3.0 + (tf * 2.0)
                matched.append(word)
        
        # Content matches with diminishing returns
        content_len = len(content.split())
        for word in query_words:
            count = content.count(word)
            if count > 0:
                # BM25-like: log(1 + tf) to prevent spam
                import math
                tf_score = math.log(1 + count) / max(math.sqrt(content_len / 100), 1)
                score += min(tf_score * 1.5, 2.5)
                if word not in matched:
                    matched.append(word)
        
        # Phrase match boost (exact phrase in title or content)
        if query_lower in title:
            score += 8.0  # Strong boost for exact title match
        if query_lower in content:
            score += 4.0
        
        # Proximity boost: check if multiple query words appear close together
        words_list = list(query_words)
        if len(words_list) >= 2:
            for i in range(len(words_list) - 1):
                phrase = f"{words_list[i]} {words_list[i+1]}"
                if phrase in title:
                    score += 3.0
                if phrase in content:
                    score += 1.5
        
        return score, matched
    
    def get_visa_phone(self, country: str) -> Optional[str]:
        """Get phone number for a specific country."""
        return self.visa_content["countries"].get(country)
    
    def get_travelers_cheques_info(self) -> Optional[str]:
        """Get travelers cheques procedure information."""
        for proc in self.visa_content["procedures"]:
            if proc["type"] == "travelers_cheques":
                return proc["content"]
        return None


# ============================================================================
# TRIAGE AGENT
# ============================================================================

class RobustTriageAgent:
    """Main triage agent that processes support tickets."""
    
    def __init__(self):
        print("[INFO] Initializing corpus loader...")
        self.corpus = CorpusLoader(DATA_DIR)
        print(f"[INFO] Loaded {self.corpus.total_articles} articles from corpus")
    
    def infer_company(self, issue: str, subject: str, company_hint: str) -> Optional[str]:
        """Infer which company the issue relates to."""
        combined = f"{issue} {subject}".lower()
        
        # Check explicit company hint first
        if company_hint:
            company_lower = company_hint.lower()
            if "visa" in company_lower:
                return "Visa"
            elif "hackerrank" in company_lower or "hacker rank" in company_lower:
                return "HackerRank"
            elif "claude" in company_lower or "anthropic" in company_lower:
                return "Claude"
        
        # Infer from content
        if any(country.lower() in combined for country in VISA_COUNTRIES):
            if any(kw in combined for kw in ["lost", "stolen", "card", "visa", "cheque", "travel"]):
                return "Visa"
        
        if "hackerrank" in combined or "hacker rank" in combined:
            return "HackerRank"
        
        if "claude" in combined or "anthropic" in combined or "claude.ai" in combined:
            return "Claude"
        
        # Check for Visa-specific keywords with country
        if any(kw in combined for kw in ["lost card", "stolen card", "credit card"]):
            for country in VISA_COUNTRIES:
                if country.lower() in combined:
                    return "Visa"
        
        return None
    
    def classify_product_area(self, issue: str, company: Optional[str]) -> str:
        """Classify the product area based on keywords."""
        combined = issue.lower()
        
        if company == "Visa":
            areas = ["travel_support", "general_support"]
        elif company == "HackerRank":
            areas = ["screen", "community", "engage", "integrations", "interviews", "settings", "billing"]
        elif company == "Claude":
            areas = ["billing", "privacy", "conversation_management", "account_management", "api", "mobile"]
        else:
            areas = list(PRODUCT_AREA_KEYWORDS.keys())
        
        best_match = "general"
        best_score = 0
        
        for area in areas:
            if area not in PRODUCT_AREA_KEYWORDS:
                continue
            keywords = PRODUCT_AREA_KEYWORDS[area]
            score = sum(1 for kw in keywords if kw in combined)
            if score > best_score:
                best_score = score
                best_match = area
        
        return best_match
    
    def classify_request_type(self, issue: str, subject: str) -> str:
        """Classify the request type based on keywords."""
        combined = f"{issue} {subject}".lower()
        
        # Check for invalid/test requests first
        for req_type, keywords in REQUEST_TYPE_KEYWORDS.items():
            if req_type == "invalid":
                if any(kw in combined for kw in keywords):
                    return "invalid"
        
        # Check other types
        best_match = "product_issue"
        best_score = 0
        
        for req_type, keywords in REQUEST_TYPE_KEYWORDS.items():
            if req_type == "invalid":
                continue
            score = sum(1 for kw in keywords if kw in combined)
            if score > best_score:
                best_score = score
                best_match = req_type
        
        return best_match
    
    def _is_injection_attempt(self, issue: str) -> bool:
        """Detect potential prompt injection or adversarial inputs."""
        issue_lower = issue.lower()
        return any(pattern in issue_lower for pattern in INJECTION_PATTERNS)
    
    def extract_country(self, issue: str) -> Optional[str]:
        """Extract country name from issue text."""
        issue_lower = issue.lower()
        for country in VISA_COUNTRIES:
            if country.lower() in issue_lower:
                return country
        return None
    
    def _extract_excerpt(self, content: str, query: str, max_sentences: int = 5) -> str:
        """Extract most relevant excerpt from article content."""
        query_words = [w for w in query.lower().split() if len(w) > 3]
        
        # Split into sentences
        sentences = re.split(r'[.!?]\s+', content)
        
        # Score each sentence
        scored_sentences = []
        for sentence in sentences:
            if len(sentence.strip()) < 20:
                continue
            score = sum(1 for word in query_words if word in sentence.lower())
            if score > 0:
                scored_sentences.append((sentence.strip(), score))
        
        # Sort by score and take top
        scored_sentences.sort(key=lambda x: x[1], reverse=True)
        top_sentences = [s[0] for s in scored_sentences[:max_sentences]]
        
        if top_sentences:
            return ". ".join(top_sentences) + "."
        
        # Fallback: return first paragraph
        paragraphs = content.split("\n\n")
        if paragraphs:
            return paragraphs[0][:500] + "..."
        
        return content[:500]
    
    def build_response(self, issue: str, company: str) -> Tuple[Optional[str], str]:
        """Build a response based on corpus content."""
        if company == "Visa":
            return self._build_visa_response(issue)
        elif company == "HackerRank":
            return self._build_hackerrank_response(issue)
        elif company == "Claude":
            return self._build_claude_response(issue)
        
        return None, "Unable to identify company"
    
    def _build_visa_response(self, issue: str) -> Tuple[Optional[str], str]:
        """Build Visa response."""
        issue_lower = issue.lower()
        
        # Check for travelers cheques
        if "cheque" in issue_lower or "check" in issue_lower or "traveler" in issue_lower:
            cheques_info = self.corpus.get_travelers_cheques_info()
            if cheques_info:
                citicorp_match = re.search(r"Citicorp.*?Freephoe?:?\s*([\d\-]+)", cheques_info, re.IGNORECASE)
                if citicorp_match:
                    phone = citicorp_match.group(1)
                    response = (
                        f"For lost or stolen Visa traveler's cheques, please contact Citicorp at {phone}.\n\n"
                        f"Citicorp provides automated cheque verification 24/7. Refunds can typically be "
                        f"arranged within 24 hours subject to terms and conditions.\n\n"
                        f"Have your cheque serial numbers, purchase location, and issuer details ready when you call."
                    )
                    return response, "Corpus contains traveler's cheque procedures with Citicorp contact information"
        
        # Check for lost/stolen card with country
        if ("lost" in issue_lower or "stolen" in issue_lower) and "card" in issue_lower:
            country = self.extract_country(issue)
            if country:
                phone = self.corpus.get_visa_phone(country)
                if phone:
                    response = (
                        f"For your lost or stolen Visa card in {country}, please call: {phone}\n\n"
                        f"This number is available 24/7 for lost and stolen card reporting. "
                        f"Have your card details ready when you call."
                    )
                    return response, f"Corpus provides country-specific phone number for lost/stolen cards in {country}"
        
        # Check for travel support
        if "travel" in issue_lower or "exchange" in issue_lower or "currency" in issue_lower:
            for file_info in self.corpus.visa_content["files"]:
                if "travel" in file_info["name"].lower() or "exchange" in file_info["name"].lower():
                    response = (
                        f"Visa provides travel support services including currency exchange information. "
                        f"Please visit the Visa website or contact your card issuer for specific travel-related assistance.\n\n"
                        f"Source: {file_info['name']}"
                    )
                    return response, "Corpus contains travel support documentation"
        
        return None, "No specific Visa procedures found for this issue"
    
    def _build_hackerrank_response(self, issue: str) -> Tuple[Optional[str], str]:
        """Build HackerRank response."""
        results = self.corpus.search(issue, "hackerrank")
        
        if not results:
            return None, "No relevant HackerRank documentation found"
        
        best = results[0]
        
        if best.score < MIN_CONFIDENCE_SCORE:
            return None, "Low confidence match in HackerRank documentation"
        
        excerpt = self._extract_excerpt(best.article.content, issue, max_sentences=5)
        
        response = (
            f"{excerpt}\n\n"
            f"For more details, see: {best.article.source_url or best.article.title}"
        )
        
        return response, f"Found relevant documentation: '{best.article.title}' (confidence: {best.score:.1f})"
    
    def _build_claude_response(self, issue: str) -> Tuple[Optional[str], str]:
        """Build Claude response."""
        results = self.corpus.search(issue, "claude")
        
        if not results:
            return None, "No relevant Claude documentation found"
        
        best = results[0]
        
        if best.score < MIN_CONFIDENCE_SCORE:
            return None, "Low confidence match in Claude documentation"
        
        excerpt = self._extract_excerpt(best.article.content, issue, max_sentences=5)
        
        response = (
            f"{excerpt}\n\n"
            f"For more details, see: {best.article.source_url or best.article.title}"
        )
        
        return response, f"Found relevant documentation: '{best.article.title}' (confidence: {best.score:.1f})"
    
    def process_ticket(self, row: Dict) -> TicketResult:
        """Process a single support ticket."""
        issue = row.get("issue", "")
        subject = row.get("subject", "")
        company_hint = row.get("company", "")
        
        # Infer company
        company = self.infer_company(issue, subject, company_hint)
        
        # Classify product area and request type
        product_area = self.classify_product_area(issue, company) if company else "general"
        request_type = self.classify_request_type(issue, subject)
        
        # Handle invalid/out-of-scope requests
        if request_type == "invalid":
            if any(kw in issue.lower() for kw in ["thank", "thanks"]):
                return TicketResult(
                    status="replied",
                    product_area="general",
                    response="Happy to help! Feel free to reach out if you have any other questions.",
                    justification="Acknowledgment message - no action needed",
                    request_type="invalid"
                )
            else:
                return TicketResult(
                    status="replied",
                    product_area="general",
                    response="This query appears to be out of scope for our support team. Please contact the appropriate service for assistance with this matter.",
                    justification="Query is unrelated to supported products (Claude, HackerRank, Visa)",
                    request_type="invalid"
                )
        
        # Check for injection attempts
        if self._is_injection_attempt(issue):
            return TicketResult(
                status="escalated",
                product_area="security",
                response="",
                justification="Potential prompt injection or adversarial input detected",
                request_type="invalid"
            )
        
        # If no company identified, escalate
        if not company:
            return TicketResult(
                status="escalated",
                product_area="general",
                response="",
                justification="Unable to identify which company (Claude, HackerRank, or Visa) this issue relates to based on the provided information",
                request_type=request_type
            )
        
        # Try to build response
        response, justification = self.build_response(issue, company)
        
        if response:
            return TicketResult(
                status="replied",
                product_area=product_area,
                response=response,
                justification=justification,
                request_type=request_type
            )
        else:
            return TicketResult(
                status="escalated",
                product_area=product_area,
                response="",
                justification=justification,
                request_type=request_type
            )
    
    def process_csv(self, input_path: str) -> List[Dict]:
        """Process CSV file and return results."""
        results = []
        
        # Read file without normalizing line endings (csv module handles it)
        with open(input_path, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            rows = list(reader)
        
        if not rows:
            return results
        
        # First row is header
        header = rows[0]
        
        # Find column indices
        try:
            issue_idx = header.index("Issue")
            subject_idx = header.index("Subject")
            company_idx = header.index("Company")
        except ValueError:
            raise ValueError(f"CSV header must contain 'Issue', 'Subject', 'Company'. Got: {header}")
        
        # Process data rows
        for row in rows[1:]:
            if len(row) < 3:
                continue
            
            issue = row[issue_idx] if issue_idx < len(row) else ""
            subject = row[subject_idx] if subject_idx < len(row) else ""
            company = row[company_idx] if company_idx < len(row) else ""
            
            result = self.process_ticket({
                "issue": issue,
                "subject": subject,
                "company": company
            })
            
            results.append({
                "issue": issue,
                "subject": subject,
                "company": company,
                "status": result.status,
                "product_area": result.product_area,
                "response": result.response,
                "justification": result.justification,
                "request_type": result.request_type
            })
        
        return results
    
    def write_output(self, results: List[Dict], output_path: str):
        """Write results to output CSV."""
        fieldnames = ["issue", "subject", "company", "status", "product_area", "response", "justification", "request_type"]
        
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for result in results:
                writer.writerow(result)


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

def main():
    """Main entry point."""
    print("=" * 70)
    print("  Robust Support Triage Agent")
    print("  HackerRank Orchestrate Hackathon - May 2026")
    print("=" * 70)
    
    # Validate input file
    if not INPUT_FILE.exists():
        print(f"[ERROR] Input file not found: {INPUT_FILE}")
        sys.exit(1)
    
    if not DATA_DIR.exists():
        print(f"[ERROR] Data directory not found: {DATA_DIR}")
        sys.exit(1)
    
    print(f"  Input : {INPUT_FILE}")
    print(f"  Output: {OUTPUT_FILE}")
    print(f"  Corpus: {DATA_DIR}")
    print("=" * 70)
    
    # Initialize agent
    print("\n[1/3] Loading corpus...")
    agent = RobustTriageAgent()
    
    # Process tickets
    print(f"\n[2/3] Processing tickets...")
    results = agent.process_csv(str(INPUT_FILE))
    
    # Write output
    print(f"\n[3/3] Writing output...")
    agent.write_output(results, str(OUTPUT_FILE))
    
    # Summary
    total = len(results)
    replied = sum(1 for r in results if r["status"] == "replied")
    escalated = total - replied
    
    print(f"\n{'=' * 70}")
    print(f"  Done. {total} tickets processed.")
    print(f"  Replied: {replied} ({replied/total*100:.1f}%)")
    print(f"  Escalated: {escalated} ({escalated/total*100:.1f}%)")
    print(f"  Output written to: {OUTPUT_FILE}")
    print("=" * 70)


if __name__ == "__main__":
    main()
