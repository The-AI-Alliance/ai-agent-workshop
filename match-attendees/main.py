import asyncio
from pathlib import Path

from mcp_agent.app import MCPApp
from mcp_agent.agents.agent import Agent
from mcp_agent.workflows.llm.augmented_llm_openai import OpenAIAugmentedLLM

app = MCPApp(name="find-matches")

async def main():
    async with app.run():
        agent = Agent(
            name="finder"
        )
        async with agent:
            # Load the prompt template
            prompt_path = Path(__file__).parent / "match-prompt.md"
            prompt_template = prompt_path.read_text().strip()
            print(f"Loaded prompt template: {prompt_template}")

            # load this users summary
            my_summary_path = Path(__file__).parent / "my-summary.md"
            my_summary = my_summary_path.read_text().strip()
            print(f"Loaded my summary: {my_summary}")

            data_dir = Path(__file__).parent / "data"
            summaries_dir = data_dir / "member-summaries"
            synergies_dir = data_dir / "synergies"
            synergies_dir.mkdir(parents=True, exist_ok=True)
            summaries_dir.mkdir(parents=True, exist_ok=True)
            summary_files = sorted(
                [path for path in summaries_dir.glob("*.md") if path.is_file()]
            )

            llm = await agent.attach_llm(OpenAIAugmentedLLM)

            for summary_file in summary_files:
                member_summary = summary_file.read_text().strip()
                if not member_summary:
                    print(f"Skipping empty summary file: {summary_file}")
                    continue

                prompt = prompt_template.format(
                    my_summary=my_summary,
                    member_summary=member_summary,
                )
                print(f"Submitting prompt for {summary_file.name}")
                answer = await llm.generate_str(prompt)
                print(answer)

                synergy_path = synergies_dir / summary_file.name
                synergy_path.write_text(answer.strip() + "\n")
                print(f"Saved synergy assessment to {synergy_path}")


if __name__ == "__main__":
    asyncio.run(main())
