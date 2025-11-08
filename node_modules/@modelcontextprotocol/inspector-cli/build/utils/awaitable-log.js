export function awaitableLog(logValue) {
    return new Promise((resolve) => {
        process.stdout.write(logValue, () => {
            resolve();
        });
    });
}
