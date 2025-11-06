"""a2cal package - Agent Calendar application."""

import click

from mmcp import server


@click.command()
@click.option('--run', 'command', default='mcp-server', help='Command to run')
@click.option(
    '--host',
    'host',
    default='localhost',
    help='Host on which the server is started or the client connects to',
)
@click.option(
    '--port',
    'port',
    default=10100,
    help='Port on which the server is started or the client connects to',
)
@click.option(
    '--transport',
    'transport',
    default='stdio',
    help='MCP Transport',
)
def main(command, host, port, transport) -> None:
    # TODO: Add other servers, perhaps dynamic port allocation
    if command == 'mcp-server':
        print("🚀 MCP server started")
        server.serve(host, port, transport)
        print("🚀 MCP server stopped")
    else:
        raise ValueError(f'Unknown run option: {command}')
    
if __name__ == '__main__':
    main()
    
