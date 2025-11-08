export async function listTools(client) {
    try {
        const response = await client.listTools();
        return response;
    }
    catch (error) {
        throw new Error(`Failed to list tools: ${error instanceof Error ? error.message : String(error)}`);
    }
}
function convertParameterValue(value, schema) {
    if (!value) {
        return value;
    }
    if (schema.type === "number" || schema.type === "integer") {
        return Number(value);
    }
    if (schema.type === "boolean") {
        return value.toLowerCase() === "true";
    }
    if (schema.type === "object" || schema.type === "array") {
        try {
            return JSON.parse(value);
        }
        catch (error) {
            return value;
        }
    }
    return value;
}
function convertParameters(tool, params) {
    const result = {};
    const properties = tool.inputSchema.properties || {};
    for (const [key, value] of Object.entries(params)) {
        const paramSchema = properties[key];
        if (paramSchema) {
            result[key] = convertParameterValue(value, paramSchema);
        }
        else {
            // If no schema is found for this parameter, keep it as string
            result[key] = value;
        }
    }
    return result;
}
export async function callTool(client, name, args) {
    try {
        const toolsResponse = await listTools(client);
        const tools = toolsResponse.tools;
        const tool = tools.find((t) => t.name === name);
        let convertedArgs = args;
        if (tool) {
            // Convert parameters based on the tool's schema, but only for string values
            // since we now accept pre-parsed values from the CLI
            const stringArgs = {};
            for (const [key, value] of Object.entries(args)) {
                if (typeof value === "string") {
                    stringArgs[key] = value;
                }
            }
            if (Object.keys(stringArgs).length > 0) {
                const convertedStringArgs = convertParameters(tool, stringArgs);
                convertedArgs = { ...args, ...convertedStringArgs };
            }
        }
        const response = await client.callTool({
            name: name,
            arguments: convertedArgs,
        });
        return response;
    }
    catch (error) {
        throw new Error(`Failed to call tool ${name}: ${error instanceof Error ? error.message : String(error)}`);
    }
}
