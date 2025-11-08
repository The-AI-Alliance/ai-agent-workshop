// List available resources
export async function listResources(client) {
    try {
        const response = await client.listResources();
        return response;
    }
    catch (error) {
        throw new Error(`Failed to list resources: ${error instanceof Error ? error.message : String(error)}`);
    }
}
// Read a resource
export async function readResource(client, uri) {
    try {
        const response = await client.readResource({ uri });
        return response;
    }
    catch (error) {
        throw new Error(`Failed to read resource ${uri}: ${error instanceof Error ? error.message : String(error)}`);
    }
}
// List resource templates
export async function listResourceTemplates(client) {
    try {
        const response = await client.listResourceTemplates();
        return response;
    }
    catch (error) {
        throw new Error(`Failed to list resource templates: ${error instanceof Error ? error.message : String(error)}`);
    }
}
