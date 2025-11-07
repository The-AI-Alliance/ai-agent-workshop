import argparse
import asyncio
import re
from pathlib import Path
from urllib.parse import urlparse

from mcp_agent.app import MCPApp
from mcp_agent.agents.agent import Agent
from mcp_agent.workflows.llm.augmented_llm_openai import OpenAIAugmentedLLM

app = MCPApp(name="harvest-ai-alliance-network")

async def main(mode="member", max_urls=None):
    async with app.run():

        agent = Agent(
            name="finder",
            instruction="Use fetch retrieve webpages to answer questions.",
            server_names=["fetch"],
        )
        async with agent:
            llm = await agent.attach_llm(OpenAIAugmentedLLM)

            # Determine input file and output directory based on mode
            if mode == "sponsor":
                urls_filename = "sponsor-urls.txt"
                summaries_dirname = "sponsor-summaries"
            else:  # default to "member"
                urls_filename = "member-urls.txt"
                summaries_dirname = "member-summaries"

            # Load the list of company URLs to harvest
            urls_path = Path(__file__).parent / "data" / urls_filename
            urls = []
            for raw_line in urls_path.read_text().splitlines():
                line = raw_line.strip()
                if not line:
                    break
                urls.append(line)
            print(f"Found {len(urls)} URLs to harvest from {urls_filename}")

            if max_urls is not None:
                urls = urls[:max_urls]
                print(f"Limiting to {len(urls)} URLs based on --max {max_urls}")

            # Load the prompt template
            prompt_path = Path(__file__).parent / "summarize-prompt.md"
            prompt_template = prompt_path.read_text().strip()
            print(f"Loaded prompt template: {prompt_template}")

            summaries_dir = Path(__file__).parent / "data" / summaries_dirname
            summaries_dir.mkdir(parents=True, exist_ok=True)

            for url in urls:
                # generate a filename for the summary
                parsed = urlparse(url)
                hostname = parsed.netloc or parsed.path.split("/")[0]
                hostname = re.sub(r"[^A-Za-z0-9._-]", "-", hostname)
                summary_path = summaries_dir / f"{hostname}.md"

                # Skip if summary already exists and is not empty
                if summary_path.exists() and summary_path.read_text().strip():
                    print(f"Summary already exists for {url}, skipping")
                    continue

                # Summarize the website
                print(f"Harvesting {url} and creating summary: {summary_path}")
                prompt = prompt_template.format(url=url)
                answer = await llm.generate_str(prompt)
                print(f"Harvested {url} and created summary: {answer}")

                summary_path.write_text(answer + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Harvest AI Alliance member or sponsor information",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py              # Process members (default)
  python main.py --mode member # Process members
  python main.py --mode sponsor # Process sponsors
        """
    )
    parser.add_argument(
        "--mode",
        choices=["member", "sponsor"],
        default="member",
        help="Process member URLs or sponsor URLs (default: member)"
    )
    parser.add_argument(
        "--max",
        type=int,
        metavar="N",
        help="Maximum number of URLs to process (default: no limit)"
    )
    args = parser.parse_args()

    if args.max is not None and args.max < 0:
        parser.error("--max must be a non-negative integer")

    asyncio.run(main(mode=args.mode, max_urls=args.max))
