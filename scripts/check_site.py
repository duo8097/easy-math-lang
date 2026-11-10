#!/usr/bin/env python3
"""
Quality check script for the GitHub Pages site.

Verifies:
1. Every relative link and image in site/ resolves
2. Every data-i18n key exists in both en.json and vi.json (parity)
3. No external http(s) resources are loaded
4. Total site size stays under 3 MB

Usage:
  python3 scripts/check_site.py
"""

import os
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

def check_links_and_images():
    """Check that all relative links and images in site/ are valid."""
    site_dir = Path("site")
    
    issues = []
    
    # Check all HTML files for relative links
    for html_file in site_dir.rglob("*.html"):
        try:
            with open(html_file, 'r') as f:
                content = f.read()
            
            # Find all href attributes
            hrefs = re.findall(r'<[^>]*href=[\"\']([^\"\']*)[\"\']', content)
            
            for href in hrefs:
                # Skip fragment identifiers (e.g., #download, #docs)
                if href.startswith('#'):
                    continue
                # Skip external URLs
                if href.startswith('http'):
                    continue
                # Skip relative links with query parameters
                if '?' in href:
                    continue
                
                # Relative link - check if file exists
                if not (site_dir / href).exists():
                    if href.endswith('.png') or href.endswith('.jpg') or href.endswith('.jpeg'):
                        # Image file
                        issues.append(f"Missing image: {href} in {html_file}")
                    else:
                        # Other file, might be OK (like .nojekyll)
                        issues.append(f"Missing file: {href} in {html_file}")
        except Exception as e:
            issues.append(f"Error reading {html_file}: {e}")
    
    return issues

def check_i18n_parity():
    """Check that every data-i18n key exists in both en.json and vi.json."""
    site_dir = Path("site")
    
    issues = []
    
    # Load both translation files
    with open(site_dir / "i18n" / "en.json", 'r') as f:
        en_translations = json.load(f)
    
    with open(site_dir / "i18n" / "vi.json", 'r') as f:
        vi_translations = json.load(f)
    
    # Flatten the nested structures
    def flatten_dict(d, prefix=''):
        items = []
        for key, value in d.items():
            if isinstance(value, dict):
                items.extend(flatten_dict(value, f"{prefix}{key}."))
            else:
                items.append(f"{prefix}{key}")
        return items
    
    en_keys = set(flatten_dict(en_translations))
    vi_keys = set(flatten_dict(vi_translations))
    
    # Check for missing keys in either file
    missing_en = vi_keys - en_keys
    missing_vi = en_keys - vi_keys
    
    if missing_en:
        issues.append(f"Keys missing in en.json: {missing_en}")
    
    if missing_vi:
        issues.append(f"Keys missing in vi.json: {missing_vi}")
    
    # Check for data-i18n attributes in HTML that aren't in translation files
    for html_file in site_dir.rglob("*.html"):
        try:
            with open(html_file, 'r') as f:
                content = f.read()
            
            # Find all data-i18n attributes
            data_i18n = re.findall(r'data-i18n=[\"\']([^\"\']*)[\"\']', content)
            
            for key in data_i18n:
                if key not in en_keys:
                    issues.append(f"data-i18n key '{key}' in {html_file} not found in en.json")
                if key not in vi_keys:
                    issues.append(f"data-i18n key '{key}' in {html_file} not found in vi.json")
        
        except Exception as e:
            issues.append(f"Error reading {html_file}: {e}")
    
    return issues

def check_external_resources():
    """Check for external http(s) resources."""
    site_dir = Path("site")
    
    issues = []
    
    external_domains = []
    
    # List of allowed external domains (our own GitHub repo and GitHub Pages)
    allowed_domains = {
        "github.com",
        "github.io",
        "duo8097.github.io",
    }
    
    # Check CSS files
    for css_file in site_dir.rglob("*.css"):
        try:
            with open(css_file, 'r') as f:
                content = f.read()
            
            # Find @import statements and url() references
            imports = re.findall(r'@import[\"\'\s]*[\"\'](https?://[^\"\']*)[\"\']', content)
            urls = re.findall(r'url\([\"\'](https?://[^\"\']*)[\"\']\)', content)
            
            all_external = imports + urls
            
            for url in all_external:
                parsed = urlparse(url)
                if parsed.netloc and parsed.netloc not in allowed_domains:
                    external_domains.append(url)
        
        except Exception as e:
            issues.append(f"Error reading CSS file {css_file}: {e}")
    
    # Check JS files
    for js_file in site_dir.rglob("*.js"):
        try:
            with open(js_file, 'r') as f:
                content = f.read()
            
            # Find import statements and require statements
            imports = re.findall(r'import\s+[^\s*]*\s+from\s+[\"\'](https?://[^\"\']*)[\"\']', content)
            requires = re.findall(r'require\s*\(\s*[\"\'](https?://[^\"\']*)[\"\']\s*\)', content)
            
            all_external = imports + requires
            
            for url in all_external:
                parsed = urlparse(url)
                if parsed.netloc and parsed.netloc not in allowed_domains:
                    external_domains.append(url)
        
        except Exception as e:
            issues.append(f"Error reading JS file {js_file}: {e}")
    
    # Check HTML files for external links
    for html_file in site_dir.rglob("*.html"):
        try:
            with open(html_file, 'r') as f:
                content = f.read()
            
            # Find src and href attributes
            srcs = re.findall(r'<[^>]*src=[\"\'](https?://[^\"\']*)[\"\']', content)
            hrefs = re.findall(r'<[^>]*href=[\"\'](https?://[^\"\']*)[\"\']', content)
            
            all_external = srcs + hrefs
            
            for url in all_external:
                parsed = urlparse(url)
                if parsed.netloc and parsed.netloc not in allowed_domains:
                    external_domains.append(url)
        
        except Exception as e:
            issues.append(f"Error reading HTML file {html_file}: {e}")
    
    # Deduplicate external domains
    external_domains = list(set(external_domains))
    
    if external_domains:
        issues.append(f"Found external resources: {external_domains}")
    
    return issues

def check_site_size():
    """Check that total site size stays under 3 MB."""
    site_dir = Path("site")
    
    # Calculate total size
    total_size = 0
    for file in site_dir.rglob("*"):
        if file.is_file():
            total_size += file.stat().st_size
    
    total_size_kb = total_size / 1024
    
    issues = []
    
    if total_size_kb > 3072:  # 3 MB in KB
        issues.append(f"Site size is {total_size_kb:.1f} KB (exceeds 3 MB limit)")
    
    return issues, total_size_kb

def main():
    print("=== Easy Math Lang Site Quality Check ===\n")
    
    site_dir = Path("site")
    
    # Check 1: Links and images
    print("1. Checking links and images...")
    link_issues = check_links_and_images()
    if link_issues:
        print(f"  Found {len(link_issues)} issues:")
        for issue in link_issues[:10]:  # Show first 10 issues
            print(f"    - {issue}")
        if len(link_issues) > 10:
            print(f"    ... and {len(link_issues) - 10} more issues")
    else:
        print("  OK: All links and images are valid")
    
    # Check 2: i18n parity
    print("\n2. Checking i18n parity...")
    i18n_issues = check_i18n_parity()
    if i18n_issues:
        print(f"  Found {len(i18n_issues)} issues:")
        for issue in i18n_issues[:10]:  # Show first 10 issues
            print(f"    - {issue}")
        if len(i18n_issues) > 10:
            print(f"    ... and {len(i18n_issues) - 10} more issues")
    else:
        print("  OK: All i18n keys exist in both en.json and vi.json")
    
    # Check 3: External resources
    print("\n3. Checking external resources...")
    external_issues = check_external_resources()
    if external_issues:
        print(f"  Found {len(external_issues)} issues:")
        for issue in external_issues:
            print(f"    - {issue}")
    else:
        print("  OK: No external http(s) resources found")
    
    # Check 4: Site size
    print("\n4. Checking site size...")
    size_issues, total_size_kb = check_site_size()
    if size_issues:
        print(f"  Found {len(size_issues)} issues:")
        for issue in size_issues:
            print(f"    - {issue}")
    else:
        print(f"  OK: Site size is {total_size_kb:.1f} KB (under 3 MB limit)")
    
    # Summary
    all_issues = link_issues + i18n_issues + external_issues + size_issues
    
    print(f"\n=== Summary ===")
    print(f"Total issues found: {len(all_issues)}")
    
    if all_issues:
        print("\nIssues found:")
        for i, issue in enumerate(all_issues, 1):
            print(f"{i}. {issue}")
        
        print(f"\n{len(all_issues)} quality checks failed.")
        return False
    else:
        print("All quality checks passed!")
        return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)