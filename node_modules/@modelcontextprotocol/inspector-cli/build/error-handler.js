function formatError(error) {
    let message;
    if (error instanceof Error) {
        message = error.message;
    }
    else if (typeof error === "string") {
        message = error;
    }
    else {
        message = "Unknown error";
    }
    return message;
}
export function handleError(error) {
    const errorMessage = formatError(error);
    console.error(errorMessage);
    process.exit(1);
}
