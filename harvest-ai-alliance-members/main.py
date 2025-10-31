import asyncio
import re
from pathlib import Path
from urllib.parse import urlparse

from mcp_agent.app import MCPApp
from mcp_agent.agents.agent import Agent
from mcp_agent.workflows.llm.augmented_llm_openai import OpenAIAugmentedLLM

app = MCPApp(name="harvest-ai-alliance-members")

async def main():
    async with app.run():

        agent = Agent(
            name="finder",
            instruction="Use fetch retrieve webpages to answer questions.",
            server_names=["fetch"],
        )
        async with agent:
            llm = await agent.attach_llm(OpenAIAugmentedLLM)

            # Load the list of company URLs to harvest
            urls_path = Path(__file__).parent / "data" / "member-urls.txt"
            urls = [line.strip() for line in urls_path.read_text().splitlines() if line.strip()]
            print(f"Found {len(urls)} URLs to harvest")

            # Load the prompt template
            prompt_path = Path(__file__).parent / "summarize-prompt.md"
            prompt_template = prompt_path.read_text().strip()
            print(f"Loaded prompt template: {prompt_template}")

            summaries_dir = Path(__file__).parent / "data" / "member-summaries"
            summaries_dir.mkdir(parents=True, exist_ok=True)

            for url in urls[:10]:
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
    asyncio.run(main())
