# pubmed_pharma_finder.py
import argparse
import csv
import re
import time
import json
import sys
from datetime import datetime
import xml.etree.ElementTree as ET
from urllib.parse import quote_plus
import requests


class PubMedPharmaFinder:
    """Fetch PubMed articles and identify pharmaceutical/biotech company affiliations."""

    # Base URLs for PubMed API (E-utilities)
    ESEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    EFETCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"

    # Academic keywords to identify non-pharma/biotech affiliations
    ACADEMIC_KEYWORDS = [
        'university', 'college', 'institute', 'school',
        'center for', 'centre for', 'hospital', 'medical center',
        'medical centre', 'clinic', 'foundation', 'academy',
        'national', 'federal', 'ministry', 'department of health'
    ]

    # Keywords that might indicate pharma/biotech companies
    COMPANY_KEYWORDS = [
        'inc', 'llc', 'ltd', 'limited', 'corp', 'corporation',
        'pharmaceuticals', 'pharmaceutical', 'pharma', 'biotech',
        'biosciences', 'therapeutics', 'laboratories', 'labs', 'biopharm',
        'biomed', 'biopharma', 'bio-pharm', 'bio-tech', 'life sciences'
    ]

    def __init__(self, email="user@example.com", api_key=None, retries=3, delay=1, debug=False):
        """
        Initialize the PubMed finder with optional API key for higher rate limits.

        Args:
            email (str): User email for PubMed API identification
            api_key (str, optional): NCBI API key for higher rate limits
            retries (int): Number of retries for failed requests
            delay (int): Delay between requests in seconds
            debug (bool): Whether to print debug information
        """
        self.email = email
        self.api_key = api_key
        self.retries = retries
        self.delay = delay
        self.debug = debug

    def _debug_print(self, message):
        """Print debug message if debug mode is enabled"""
        if self.debug:
            print(f"DEBUG: {message}")

    def search(self, query, max_results=100):
        """
        Search PubMed for articles matching the query.

        Args:
            query (str): PubMed search query (supports full PubMed syntax)
            max_results (int): Maximum number of results to return

        Returns:
            list: PubMed IDs matching the query
        """
        params = {
            'db': 'pubmed',
            'term': query,
            'retmax': max_results,
            'usehistory': 'y',  # Use history server
            'retmode': 'json',  # Get JSON response
            'sort': 'relevance',
            'tool': 'PubMedPharmaFinder',
            'email': self.email,
        }

        if self.api_key:
            params['api_key'] = self.api_key

        self._debug_print(f"Search params: {params}")

        for attempt in range(self.retries):
            try:
                self._debug_print(f"Making request to {self.ESEARCH_URL}")
                response = requests.get(self.ESEARCH_URL, params=params)
                response.raise_for_status()

                # Parse JSON response
                self._debug_print("Parsing JSON response")
                data = json.loads(response.text)
                self._debug_print(f"Response data keys: {data.keys() if isinstance(data, dict) else 'Not a dictionary'}")

                id_list = data.get('esearchresult', {}).get('idlist', [])
                self._debug_print(f"Found {len(id_list)} IDs")

                return id_list

            except (requests.RequestException, json.JSONDecodeError) as e:
                print(f"Search attempt {attempt+1} failed: {e}")
                if attempt < self.retries - 1:
                    time.sleep(self.delay)
                else:
                    print("All search attempts failed")
                    return []

    def fetch_article_details(self, pmid_list):
        """
        Fetch detailed information about articles by their PubMed IDs.

        Args:
            pmid_list (list): List of PubMed IDs

        Returns:
            list: Article details with pharma/biotech affiliations
        """
        if not pmid_list:
            return []

        # Process in batches to avoid large requests
        batch_size = 50
        results = []

        for i in range(0, len(pmid_list), batch_size):
            batch_pmids = pmid_list[i:i + batch_size]

            params = {
                'db': 'pubmed',
                'id': ','.join(batch_pmids),
                'retmode': 'xml',
                'tool': 'PubMedPharmaFinder',
                'email': self.email,
            }

            if self.api_key:
                params['api_key'] = self.api_key

            self._debug_print(f"Fetching details for batch {i // batch_size + 1} ({len(batch_pmids)} articles)")

            for attempt in range(self.retries):
                try:
                    response = requests.get(self.EFETCH_URL, params=params)
                    response.raise_for_status()

                    # Parse XML response
                    self._debug_print("Parsing XML response")
                    root = ET.fromstring(response.text)
                    articles = root.findall(".//PubmedArticle")
                    self._debug_print(f"Found {len(articles)} articles in XML")

                    for article in articles:
                        article_data = self._parse_article(article)
                        if article_data and article_data['has_pharma_author']:
                            self._debug_print(f"Found pharma author in article {article_data['pmid']}")
                            results.append(article_data)

                    # Be nice to the API
                    time.sleep(self.delay)
                    break

                except (requests.RequestException, ET.ParseError) as e:
                    print(f"Fetch attempt {attempt+1} failed: {e}")
                    if attempt < self.retries - 1:
                        time.sleep(self.delay * 2)  # Longer delay on error
                    else:
                        print(f"All fetch attempts failed for batch {i}")

        return results

    def _is_company_affiliation(self, affiliation):
        """
        Check if an affiliation string likely represents a company.

        Args:
            affiliation (str): Author affiliation text

        Returns:
            bool: True if likely a company, False otherwise
        """
        if not affiliation:
            return False

        affiliation = affiliation.lower()

        # Check for academic keywords
        for keyword in self.ACADEMIC_KEYWORDS:
            if keyword in affiliation:
                self._debug_print(f"Academic keyword found: {keyword} in '{affiliation}'")
                return False

        # Check for company indicators
        for keyword in self.COMPANY_KEYWORDS:
            if keyword in affiliation:
                self._debug_print(f"Company keyword found: {keyword} in '{affiliation}'")
                return True

        # Check for company naming patterns (like "X, Inc." or "X Ltd.")
        company_patterns = [
            r'\b[A-Za-z]+,?\s+Inc\.?',
            r'\b[A-Za-z]+,?\s+Ltd\.?',
            r'\b[A-Za-z]+,?\s+LLC',
            r'\b[A-Za-z]+,?\s+Corp\.?',
            r'\b[A-Za-z]+\s+Pharmaceuticals',
            r'\b[A-Za-z]+\s+Biotech',
        ]

        for pattern in company_patterns:
            if re.search(pattern, affiliation, re.IGNORECASE):
                self._debug_print(f"Company pattern match: {pattern} in '{affiliation}'")
                return True

        return False

    def _parse_article(self, article_elem):
        """
        Parse article XML element and extract relevant information.

        Args:
            article_elem (Element): XML element representing a PubMed article

        Returns:
            dict: Article information including pharma/biotech affiliations
        """
        try:
            # Extract PMID
            pmid_elem = article_elem.find(".//PMID")
            if pmid_elem is None:
                self._debug_print("No PMID found for article")
                return None

            pmid = pmid_elem.text
            self._debug_print(f"Processing article PMID: {pmid}")

            # Extract title
            title_elem = article_elem.find(".//ArticleTitle")
            title = title_elem.text if title_elem is not None and title_elem.text else "Unknown Title"

            # Extract publication date
            pub_date = "Unknown Date"
            pub_date_elem = article_elem.find(".//PubDate")
            if pub_date_elem is not None:
                year = pub_date_elem.find("Year")
                month = pub_date_elem.find("Month")
                day = pub_date_elem.find("Day")

                year_text = year.text if year is not None else ""
                month_text = month.text if month is not None else ""
                day_text = day.text if day is not None else ""

                if year_text:
                    if month_text:
                        if day_text:
                            pub_date = f"{year_text}-{month_text}-{day_text}"
                        else:
                            pub_date = f"{year_text}-{month_text}"
                    else:
                        pub_date = year_text

            # Extract authors and their affiliations
            authors = article_elem.findall(".//Author")
            self._debug_print(f"Found {len(authors)} authors")

            pharma_authors = []
            company_affiliations = []
            corresponding_email = ""
            has_pharma_author = False

            for author in authors:
                last_name = author.find("LastName")
                fore_name = author.find("ForeName")

                if last_name is not None and fore_name is not None:
                    author_name = f"{fore_name.text} {last_name.text}"
                elif last_name is not None:
                    author_name = last_name.text
                else:
                    continue

                # Check affiliations
                affiliations = []
                aff_elems = author.findall(".//Affiliation")

                for aff in aff_elems:
                    if aff.text:
                        affiliations.append(aff.text)

                        # Look for email address
                        email_match = re.search(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', aff.text)
                        if email_match and not corresponding_email:
                            corresponding_email = email_match.group(0)
                            self._debug_print(f"Found email: {corresponding_email}")

                # Check if any affiliation is a company
                is_company_author = any(self._is_company_affiliation(aff) for aff in affiliations)

                if is_company_author:
                    self._debug_print(f"Company author found: {author_name}")
                    has_pharma_author = True
                    pharma_authors.append(author_name)
                    company_affiliations.extend([aff for aff in affiliations if self._is_company_affiliation(aff)])

            if has_pharma_author:
                return {
                    'pmid': pmid,
                    'title': title,
                    'pub_date': pub_date,
                    'pharma_authors': '; '.join(pharma_authors),
                    'company_affiliations': '; '.join(set(company_affiliations)),
                    'corresponding_email': corresponding_email,
                    'has_pharma_author': has_pharma_author
                }
            else:
                return None

        except Exception as e:
            pmid_text = article_elem.find('.//PMID').text if article_elem.find('.//PMID') is not None else 'unknown'
            print(f"Error parsing article (PMID possibly {pmid_text}): {e}")
            if self.debug:
                import traceback
                traceback.print_exc()
            return None

    def export_to_csv(self, articles, filename=None):
        """
        Export article information to a CSV file or print to console.

        Args:
            articles (list): List of article dictionaries
            filename (str, optional): Output CSV filename. If None, print to console.
        """
        if not articles:
            print("No articles with pharmaceutical/biotech affiliations found")
            return

        fieldnames = ['pmid', 'title', 'pub_date', 'pharma_authors',
                      'company_affiliations', 'corresponding_email']

        if filename:
            with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

                writer.writeheader()
                for article in articles:
                    # Remove the has_pharma_author field which is only for internal use
                    article_copy = article.copy()
                    article_copy.pop('has_pharma_author', None)
                    writer.writerow(article_copy)

                print(f"Exported {len(articles)} articles to {filename}")
        else:
            # Print to console in a tabular format
            print("\n" + "="*100)
            print(f"Found {len(articles)} articles with pharmaceutical/biotech company affiliations:")
            print("="*100)

            for article in articles:
                print(f"PubMed ID: {article['pmid']}")
                print(f"Title: {article['title']}")
                print(f"Publication Date: {article['pub_date']}")
                print(f"Pharma/Biotech Authors: {article['pharma_authors']}")
                print(f"Company Affiliations: {article['company_affiliations']}")
                if article['corresponding_email']:
                    print(f"Corresponding Email: {article['corresponding_email']}")
                print("-"*100)

def main():
    parser = argparse.ArgumentParser(
        description='Find PubMed papers with pharmaceutical/biotech company authors',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
    get-papers-list "asthma" --email your@email.com
    get-papers-list "cancer AND clinical trial" -d -f results.csv
    get-papers-list "diabetes" --max-results 200
        '''
    )
    parser.add_argument('query', help='PubMed search query (supports full PubMed syntax)')
    parser.add_argument('-e', '--email', default='user@example.com', help='Email for PubMed API identification')
    parser.add_argument('-k', '--api-key', help='NCBI API key for higher rate limits')
    parser.add_argument('-m', '--max-results', type=int, default=100, help='Maximum number of results to process')
    parser.add_argument('-d', '--debug', action='store_true', help='Print debug information during execution')
    parser.add_argument('-f', '--file', help='Specify the file name to store results. If not provided, print to console.')

    args = parser.parse_args()

    if args.debug:
        print(f"Running in debug mode")
        print(f"Args: {args}")

    print(f"Searching PubMed for: {args.query}")
    finder = PubMedPharmaFinder(email=args.email, api_key=args.api_key, debug=args.debug)

    pmids = finder.search(args.query, max_results=args.max_results)
    print(f"Found {len(pmids)} matching articles, analyzing for pharma/biotech affiliations...")

    articles = finder.fetch_article_details(pmids)

    # Export results to file or print to console
    finder.export_to_csv(articles, args.file)

    print(f"Analysis complete. Found {len(articles)} articles with pharmaceutical/biotech company affiliations.")


if __name__ == "__main__":
    main()