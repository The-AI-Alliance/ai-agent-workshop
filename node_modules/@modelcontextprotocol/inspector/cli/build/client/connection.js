export const validLogLevels = [
    "trace",
    "debug",
    "info",
    "warn",
    "error",
];
export async function connect(client, transport) {
    try {
        await client.connect(transport);
        if (client.getServerCapabilities()?.logging) {
            // default logging level is undefined in the spec, but the user of the
            // inspector most likely wants debug.
            await client.setLoggingLevel("debug");
        }
    }
    catch (error) {
        throw new Error(`Failed to connect to MCP server: ${error instanceof Error ? error.message : String(error)}`);
    }
}
export async function disconnect(transport) {
    try {
        await transport.close();
    }
    catch (error) {
        throw new Error(`Failed to disconnect from MCP server: ${error instanceof Error ? error.message : String(error)}`);
    }
}
// Set logging level
export async function setLoggingLevel(client, level) {
    try {
        const response = await client.setLoggingLevel(level);
        return response;
    }
    catch (error) {
        throw new Error(`Failed to set logging level: ${error instanceof Error ? error.message : String(error)}`);
    }
}
