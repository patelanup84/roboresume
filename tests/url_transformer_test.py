# python tests/test_url_transformer.py

from urllib.parse import urlparse, parse_qs

def transform_workopolis_url(url: str) -> str:
    """
    Checks if a URL is a Workopolis search URL and transforms it into a direct
    viewjob URL if it contains a 'job' parameter.

    Args:
        url: The input URL string.

    Returns:
        The transformed URL if applicable, otherwise the original URL.
    """
    try:
        # We only care about URLs that are for Workopolis searches
        if "workopolis.com/search" not in url:
            return url

        parsed_url = urlparse(url)
        query_params = parse_qs(parsed_url.query)

        # parse_qs returns a list of values for each key, so we get the first one.
        job_id = query_params.get('job', [None])[0]

        if job_id:
            # If we found a job ID, construct the new, proper URL
            new_url = f"https://www.workopolis.com/jobsearch/viewjob/{job_id}"
            return new_url
        else:
            # It's a search URL but has no job ID, so return it as is
            return url
            
    except Exception:
        # If any error occurs during parsing, just return the original url safely
        return url

# --- Test Cases ---
if __name__ == "__main__":
    test_cases = [
        {
            "name": "Improper Workopolis search URL",
            "input": "https://www.workopolis.com/search?q=mckinsey&l=ontario%252c%2520canada&job=4yNUscJPyZGwDf829xk0bCSMFkKqkUxD3Cw3_SFsOde9P6wHgM7OwKnlkzzC-3XB",
            "expected": "https://www.workopolis.com/jobsearch/viewjob/4yNUscJPyZGwDf829xk0bCSMFkKqkUxD3Cw3_SFsOde9P6wHgM7OwKnlkzzC-3XB"
        },
        {
            "name": "Proper Workopolis URL (should not change)",
            "input": "https://www.workopolis.com/jobsearch/viewjob/4yNUscJPyZGwDf829xk0bCSMFkKqkUxD3Cw3_SFsOde9P6wHgM7OwKnlkzzC-3XB",
            "expected": "https://www.workopolis.com/jobsearch/viewjob/4yNUscJPyZGwDf829xk0bCSMFkKqkUxD3Cw3_SFsOde9P6wHgM7OwKnlkzzC-3XB"
        },
        {
            "name": "Non-Workopolis URL (should not change)",
            "input": "https://www.linkedin.com/jobs/view/123456789",
            "expected": "https://www.linkedin.com/jobs/view/123456789"
        },
        {
            "name": "Workopolis search URL without job ID (should not change)",
            "input": "https://www.workopolis.com/search?q=software+engineer",
            "expected": "https://www.workopolis.com/search?q=software+engineer"
        },
        {
            "name": "Workopolis homepage (should not change)",
            "input": "https://www.workopolis.com/",
            "expected": "https://www.workopolis.com/"
        },
        {
            "name": "Empty string input",
            "input": "",
            "expected": ""
        }
    ]

    print("--- Running URL Transformer Tests ---")
    all_passed = True
    for i, test in enumerate(test_cases):
        print(f"\nTest {i+1}: {test['name']}")
        print(f"  Input:    {test['input']}")
        
        actual_output = transform_workopolis_url(test['input'])
        
        print(f"  Expected: {test['expected']}")
        print(f"  Actual:   {actual_output}")
        
        if actual_output == test['expected']:
            print("  Result:   ✅ PASSED")
        else:
            print("  Result:   ❌ FAILED")
            all_passed = False
    
    print("\n--- Test Summary ---")
    if all_passed:
        print("✅ All tests passed successfully!")
    else:
        print("❌ Some tests failed.")