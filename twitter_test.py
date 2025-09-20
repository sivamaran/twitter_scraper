import asyncio
import json
import sys
from pathlib import Path

# This helper function adds the project's root folder to Python's path,
# allowing us to import from the 'scrapers' folder.
def _setup_path():
    project_root = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(project_root))

_setup_path()

# This is the ONLY import the test script needs.
# It imports the main "manager" function from your main scraper.
from scrapers.twitter_scraper import main as run_twitter_scraper

async def run_test():
    """
    Reads URLs from 'twitter_urls.txt' and calls the main twitter_scraper.
    """
    print("--- Starting Twitter Test ---")

    tests_dir = Path(__file__).resolve().parent
    # Assume you have a 'twitter_urls.txt' in your 'tests' folder
    urls_file_path = tests_dir / "twitter_urls.txt"
    output_file_path = tests_dir / "twitter_output.json"

    try:
        with open(urls_file_path, 'r') as f:
            urls_to_scrape = [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        print(f"ERROR: The input file was not found at '{urls_file_path}'")
        print("Please create it and add some Twitter/X URLs.")
        return

    if not urls_to_scrape:
        print("No URLs found in 'twitter_urls.txt'. Test aborted.")
        return

    print(f"Found {len(urls_to_scrape)} URLs. Calling the main scraper...")
    # Call the main scraper function and wait for the combined results
    combined_results = await run_twitter_scraper(urls_to_scrape, headless=True)

    # Save the final results to a new file in the 'tests' folder
    with open(output_file_path, 'w', encoding='utf-8') as f:
        json.dump(combined_results, f, indent=2, ensure_ascii=False)

    print("\n--- Test Complete ---")
    print(f"Results have been saved to '{output_file_path}'")

# This makes the script runnable from the command line
if __name__ == "__main__":
    asyncio.run(run_test())
