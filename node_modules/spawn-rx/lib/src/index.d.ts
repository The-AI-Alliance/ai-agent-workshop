import { Observable } from "rxjs";
import { SpawnOptions } from "child_process";
/**
 * Finds the actual executable and parameters to run on Windows. This method
 * mimics the POSIX behavior of being able to run scripts as executables by
 * replacing the passed-in executable with the script runner, for PowerShell,
 * CMD, and node scripts.
 *
 * This method also does the work of running down PATH, which spawn on Windows
 * also doesn't do, unlike on POSIX.
 *
 * @param  {string} exe           The executable to run
 * @param  {string[]} args   The arguments to run
 *
 * @return {Object}               The cmd and args to run
 * @property {string} cmd         The command to pass to spawn
 * @property {string[]} args The arguments to pass to spawn
 */
export declare function findActualExecutable(exe: string, args: string[]): {
    cmd: string;
    args: string[];
};
export type SpawnRxExtras = {
    stdin?: Observable<string>;
    echoOutput?: boolean;
    split?: boolean;
    jobber?: boolean;
    encoding?: BufferEncoding;
};
export type OutputLine = {
    source: "stdout" | "stderr";
    text: string;
};
/**
 * Spawns a process but detached from the current process. The process is put
 * into its own Process Group that can be killed by unsubscribing from the
 * return Observable.
 *
 * @param  {string} exe               The executable to run
 * @param  {string[]} params     The parameters to pass to the child
 * @param  {SpawnOptions & SpawnRxExtras} opts              Options to pass to spawn.
 *
 * @return {Observable<OutputLine>}       Returns an Observable that when subscribed
 *                                    to, will create a detached process. The
 *                                    process output will be streamed to this
 *                                    Observable, and if unsubscribed from, the
 *                                    process will be terminated early. If the
 *                                    process terminates with a non-zero value,
 *                                    the Observable will terminate with onError.
 */
export declare function spawnDetached(exe: string, params: string[], opts: SpawnOptions & SpawnRxExtras & {
    split: true;
}): Observable<OutputLine>;
/**
 * Spawns a process but detached from the current process. The process is put
 * into its own Process Group that can be killed by unsubscribing from the
 * return Observable.
 *
 * @param  {string} exe               The executable to run
 * @param  {string[]} params     The parameters to pass to the child
 * @param  {SpawnOptions & SpawnRxExtras} opts              Options to pass to spawn.
 *
 * @return {Observable<string>}       Returns an Observable that when subscribed
 *                                    to, will create a detached process. The
 *                                    process output will be streamed to this
 *                                    Observable, and if unsubscribed from, the
 *                                    process will be terminated early. If the
 *                                    process terminates with a non-zero value,
 *                                    the Observable will terminate with onError.
 */
export declare function spawnDetached(exe: string, params: string[], opts?: SpawnOptions & SpawnRxExtras & {
    split: false | undefined;
}): Observable<string>;
/**
 * Spawns a process attached as a child of the current process.
 *
 * @param  {string} exe               The executable to run
 * @param  {string[]} params     The parameters to pass to the child
 * @param  {SpawnOptions & SpawnRxExtras} opts              Options to pass to spawn.
 *
 * @return {Observable<OutputLine>}       Returns an Observable that when subscribed
 *                                    to, will create a child process. The
 *                                    process output will be streamed to this
 *                                    Observable, and if unsubscribed from, the
 *                                    process will be terminated early. If the
 *                                    process terminates with a non-zero value,
 *                                    the Observable will terminate with onError.
 */
export declare function spawn(exe: string, params: string[], opts: SpawnOptions & SpawnRxExtras & {
    split: true;
}): Observable<OutputLine>;
/**
 * Spawns a process attached as a child of the current process.
 *
 * @param  {string} exe               The executable to run
 * @param  {string[]} params     The parameters to pass to the child
 * @param  {SpawnOptions & SpawnRxExtras} opts              Options to pass to spawn.
 *
 * @return {Observable<string>}       Returns an Observable that when subscribed
 *                                    to, will create a child process. The
 *                                    process output will be streamed to this
 *                                    Observable, and if unsubscribed from, the
 *                                    process will be terminated early. If the
 *                                    process terminates with a non-zero value,
 *                                    the Observable will terminate with onError.
 */
export declare function spawn(exe: string, params: string[], opts?: SpawnOptions & SpawnRxExtras & {
    split: false | undefined;
}): Observable<string>;
/**
 * Spawns a process but detached from the current process. The process is put
 * into its own Process Group.
 *
 * @param  {string} exe               The executable to run
 * @param  {string[]} params     The parameters to pass to the child
 * @param  {SpawnOptions & SpawnRxExtras} opts              Options to pass to spawn.
 *
 * @return {Promise<[string, string]>}       Returns an Promise that represents a detached
 *                                 process. The value returned is the process
 *                                 output. If the process terminates with a
 *                                 non-zero value, the Promise will resolve with
 *                                 an Error.
 */
export declare function spawnDetachedPromise(exe: string, params: string[], opts: SpawnOptions & SpawnRxExtras & {
    split: true;
}): Promise<[string, string]>;
/**
 * Spawns a process but detached from the current process. The process is put
 * into its own Process Group.
 *
 * @param  {string} exe               The executable to run
 * @param  {string[]} params     The parameters to pass to the child
 * @param  {SpawnOptions & SpawnRxExtras} opts              Options to pass to spawn.
 *
 * @return {Promise<string>}       Returns an Promise that represents a detached
 *                                 process. The value returned is the process
 *                                 output. If the process terminates with a
 *                                 non-zero value, the Promise will resolve with
 *                                 an Error.
 */
export declare function spawnDetachedPromise(exe: string, params: string[], opts?: SpawnOptions & SpawnRxExtras & {
    split: false | undefined;
}): Promise<string>;
/**
 * Spawns a process as a child process.
 *
 * @param  {string} exe               The executable to run
 * @param  {string[]} params     The parameters to pass to the child
 * @param  {SpawnOptions & SpawnRxExtras} opts              Options to pass to spawn.
 *
 * @return {Promise<[string, string]>}       Returns an Promise that represents a child
 *                                 process. The value returned is the process
 *                                 output. If the process terminates with a
 *                                 non-zero value, the Promise will resolve with
 *                                 an Error.
 */
export declare function spawnPromise(exe: string, params: string[], opts: SpawnOptions & SpawnRxExtras & {
    split: true;
}): Promise<[string, string]>;
/**
 * Spawns a process as a child process.
 *
 * @param  {string} exe               The executable to run
 * @param  {string[]} params     The parameters to pass to the child
 * @param  {SpawnOptions & SpawnRxExtras} opts              Options to pass to spawn.
 *
 * @return {Promise<string>}       Returns an Promise that represents a child
 *                                 process. The value returned is the process
 *                                 output. If the process terminates with a
 *                                 non-zero value, the Promise will resolve with
 *                                 an Error.
 */
export declare function spawnPromise(exe: string, params: string[], opts?: SpawnOptions & SpawnRxExtras): Promise<string>;
