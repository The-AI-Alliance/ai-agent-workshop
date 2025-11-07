import argparse
import asyncio
from pathlib import Path

from mcp_agent.app import MCPApp
from mcp_agent.agents.agent import Agent
from mcp_agent.workflows.llm.augmented_llm_openai import OpenAIAugmentedLLM

def parse_args():
    parser = argparse.ArgumentParser(description="Find synergies between members.")
    parser.add_argument(
        "--source",
        choices=["member", "sponsor", "venture"],
        help="Choose which group to evaluate: member, sponsor, or venture.",
    )
    args = parser.parse_args()
    if args.source is None:
        parser.print_help()
        raise SystemExit(1)
    return args


app = MCPApp(name="find-matches")


async def main(source: str):
    print(f"Program started with source: {source}")
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

            summaries_dir = (
                Path(__file__).resolve().parent.parent
                / "harvest-ai-alliance-network"
                / "data"
                / f"{source}-summaries"
            )

            data_dir = Path(__file__).parent / "data"
            synergies_dir = data_dir / f"{source}-synergies"
            synergies_dir.mkdir(parents=True, exist_ok=True)
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
    cli_args = parse_args()
    asyncio.run(main(cli_args.source))
