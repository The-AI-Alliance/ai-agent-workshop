"use strict";
var __assign = (this && this.__assign) || function () {
    __assign = Object.assign || function(t) {
        for (var s, i = 1, n = arguments.length; i < n; i++) {
            s = arguments[i];
            for (var p in s) if (Object.prototype.hasOwnProperty.call(s, p))
                t[p] = s[p];
        }
        return t;
    };
    return __assign.apply(this, arguments);
};
var __rest = (this && this.__rest) || function (s, e) {
    var t = {};
    for (var p in s) if (Object.prototype.hasOwnProperty.call(s, p) && e.indexOf(p) < 0)
        t[p] = s[p];
    if (s != null && typeof Object.getOwnPropertySymbols === "function")
        for (var i = 0, p = Object.getOwnPropertySymbols(s); i < p.length; i++) {
            if (e.indexOf(p[i]) < 0 && Object.prototype.propertyIsEnumerable.call(s, p[i]))
                t[p[i]] = s[p[i]];
        }
    return t;
};
var __spreadArray = (this && this.__spreadArray) || function (to, from, pack) {
    if (pack || arguments.length === 2) for (var i = 0, l = from.length, ar; i < l; i++) {
        if (ar || !(i in from)) {
            if (!ar) ar = Array.prototype.slice.call(from, 0, i);
            ar[i] = from[i];
        }
    }
    return to.concat(ar || Array.prototype.slice.call(from));
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.findActualExecutable = findActualExecutable;
exports.spawnDetached = spawnDetached;
exports.spawn = spawn;
exports.spawnDetachedPromise = spawnDetachedPromise;
exports.spawnPromise = spawnPromise;
/* eslint-disable @typescript-eslint/no-explicit-any */
var path = require("path");
var net = require("net");
var sfs = require("fs");
var rxjs_1 = require("rxjs");
var operators_1 = require("rxjs/operators");
var child_process_1 = require("child_process");
var debug_1 = require("debug");
var isWindows = process.platform === "win32";
var d = (0, debug_1.default)("spawn-rx"); // tslint:disable-line:no-var-requires
/**
 * stat a file but don't throw if it doesn't exist
 *
 * @param  {string} file The path to a file
 * @return {Stats}       The stats structure
 *
 * @private
 */
function statSyncNoException(file) {
    try {
        return sfs.statSync(file);
    }
    catch (_a) {
        return null;
    }
}
/**
 * Search PATH to see if a file exists in any of the path folders.
 *
 * @param  {string} exe The file to search for
 * @return {string}     A fully qualified path, or the original path if nothing
 *                      is found
 *
 * @private
 */
function runDownPath(exe) {
    // NB: Windows won't search PATH looking for executables in spawn like
    // Posix does
    // Files with any directory path don't get this applied
    if (exe.match(/[\\/]/)) {
        d("Path has slash in directory, bailing");
        return exe;
    }
    var target = path.join(".", exe);
    if (statSyncNoException(target)) {
        d("Found executable in currect directory: ".concat(target));
        // XXX: Some very Odd programs decide to use args[0] as a parameter
        // to determine what to do, and also symlink themselves, so we can't
        // use realpathSync here like we used to
        return target;
    }
    var haystack = process.env.PATH.split(isWindows ? ";" : ":");
    for (var _i = 0, haystack_1 = haystack; _i < haystack_1.length; _i++) {
        var p = haystack_1[_i];
        var needle = path.join(p, exe);
        if (statSyncNoException(needle)) {
            // NB: Same deal as above
            return needle;
        }
    }
    d("Failed to find executable anywhere in path");
    return exe;
}
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
function findActualExecutable(exe, args) {
    // POSIX can just execute scripts directly, no need for silly goosery
    if (process.platform !== "win32") {
        return { cmd: runDownPath(exe), args: args };
    }
    if (!sfs.existsSync(exe)) {
        // NB: When you write something like `surf-client ... -- surf-build` on Windows,
        // a shell would normally convert that to surf-build.cmd, but since it's passed
        // in as an argument, it doesn't happen
        var possibleExts = [".exe", ".bat", ".cmd", ".ps1"];
        for (var _i = 0, possibleExts_1 = possibleExts; _i < possibleExts_1.length; _i++) {
            var ext = possibleExts_1[_i];
            var possibleFullPath = runDownPath("".concat(exe).concat(ext));
            if (sfs.existsSync(possibleFullPath)) {
                return findActualExecutable(possibleFullPath, args);
            }
        }
    }
    if (exe.match(/\.ps1$/i)) {
        var cmd = path.join(process.env.SYSTEMROOT, "System32", "WindowsPowerShell", "v1.0", "PowerShell.exe");
        var psargs = [
            "-ExecutionPolicy",
            "Unrestricted",
            "-NoLogo",
            "-NonInteractive",
            "-File",
            exe,
        ];
        return { cmd: cmd, args: psargs.concat(args) };
    }
    if (exe.match(/\.(bat|cmd)$/i)) {
        var cmd = path.join(process.env.SYSTEMROOT, "System32", "cmd.exe");
        var cmdArgs = __spreadArray(["/C", exe], args, true);
        return { cmd: cmd, args: cmdArgs };
    }
    if (exe.match(/\.(js)$/i)) {
        var cmd = process.execPath;
        var nodeArgs = [exe];
        return { cmd: cmd, args: nodeArgs.concat(args) };
    }
    // Dunno lol
    return { cmd: exe, args: args };
}
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
function spawnDetached(exe, params, opts) {
    var _a = findActualExecutable(exe, params !== null && params !== void 0 ? params : []), cmd = _a.cmd, args = _a.args;
    if (!isWindows) {
        return spawn(cmd, args, Object.assign({}, opts || {}, { detached: true }));
    }
    var newParams = [cmd].concat(args);
    var target = path.join(__dirname, "..", "..", "vendor", "jobber", "Jobber.exe");
    var options = __assign(__assign({}, (opts !== null && opts !== void 0 ? opts : {})), { detached: true, jobber: true });
    d("spawnDetached: ".concat(target, ", ").concat(newParams));
    return spawn(target, newParams, options);
}
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
function spawn(exe, params, opts) {
    opts = opts !== null && opts !== void 0 ? opts : {};
    var spawnObs = new rxjs_1.Observable(function (subj) {
        // eslint-disable-next-line @typescript-eslint/no-unused-vars
        var stdin = opts.stdin, jobber = opts.jobber, split = opts.split, encoding = opts.encoding, spawnOpts = __rest(opts, ["stdin", "jobber", "split", "encoding"]);
        var _a = findActualExecutable(exe, params), cmd = _a.cmd, args = _a.args;
        d("spawning process: ".concat(cmd, " ").concat(args.join(), ", ").concat(JSON.stringify(spawnOpts)));
        var proc = (0, child_process_1.spawn)(cmd, args, spawnOpts);
        var bufHandler = function (source) { return function (b) {
            if (b.length < 1) {
                return;
            }
            if (opts.echoOutput) {
                (source === "stdout" ? process.stdout : process.stderr).write(b);
            }
            var chunk = "<< String sent back was too long >>";
            try {
                if (typeof b === "string") {
                    chunk = b.toString();
                }
                else {
                    chunk = b.toString(encoding || "utf8");
                }
            }
            catch (_a) {
                chunk = "<< Lost chunk of process output for ".concat(exe, " - length was ").concat(b.length, ">>");
            }
            subj.next({ source: source, text: chunk });
        }; };
        var ret = new rxjs_1.Subscription();
        if (opts.stdin) {
            if (proc.stdin) {
                ret.add(opts.stdin.subscribe({
                    next: function (x) { return proc.stdin.write(x); },
                    error: subj.error.bind(subj),
                    complete: function () { return proc.stdin.end(); },
                }));
            }
            else {
                subj.error(new Error("opts.stdio conflicts with provided spawn opts.stdin observable, 'pipe' is required"));
            }
        }
        var stderrCompleted = null;
        var stdoutCompleted = null;
        var noClose = false;
        if (proc.stdout) {
            stdoutCompleted = new rxjs_1.AsyncSubject();
            proc.stdout.on("data", bufHandler("stdout"));
            proc.stdout.on("close", function () {
                stdoutCompleted.next(true);
                stdoutCompleted.complete();
            });
        }
        else {
            stdoutCompleted = (0, rxjs_1.of)(true);
        }
        if (proc.stderr) {
            stderrCompleted = new rxjs_1.AsyncSubject();
            proc.stderr.on("data", bufHandler("stderr"));
            proc.stderr.on("close", function () {
                stderrCompleted.next(true);
                stderrCompleted.complete();
            });
        }
        else {
            stderrCompleted = (0, rxjs_1.of)(true);
        }
        proc.on("error", function (e) {
            noClose = true;
            subj.error(e);
        });
        proc.on("close", function (code) {
            noClose = true;
            var pipesClosed = (0, rxjs_1.merge)(stdoutCompleted, stderrCompleted).pipe((0, operators_1.reduce)(function (acc) { return acc; }, true));
            if (code === 0) {
                pipesClosed.subscribe(function () { return subj.complete(); });
            }
            else {
                pipesClosed.subscribe(function () {
                    var e = new Error("Failed with exit code: ".concat(code));
                    e.exitCode = code;
                    e.code = code;
                    subj.error(e);
                });
            }
        });
        ret.add(new rxjs_1.Subscription(function () {
            if (noClose) {
                return;
            }
            d("Killing process: ".concat(cmd, " ").concat(args.join()));
            if (opts.jobber) {
                // NB: Connecting to Jobber's named pipe will kill it
                net.connect("\\\\.\\pipe\\jobber-".concat(proc.pid));
                setTimeout(function () { return proc.kill(); }, 5 * 1000);
            }
            else {
                proc.kill();
            }
        }));
        return ret;
    });
    return opts.split ? spawnObs : spawnObs.pipe((0, operators_1.map)(function (x) { return x === null || x === void 0 ? void 0 : x.text; }));
}
function wrapObservableInPromise(obs) {
    return new Promise(function (res, rej) {
        var out = "";
        obs.subscribe({
            next: function (x) { return (out += x); },
            error: function (e) {
                var err = new Error("".concat(out, "\n").concat(e.message));
                if ("exitCode" in e) {
                    err.exitCode = e.exitCode;
                    err.code = e.exitCode;
                }
                rej(err);
            },
            complete: function () { return res(out); },
        });
    });
}
function wrapObservableInSplitPromise(obs) {
    return new Promise(function (res, rej) {
        var out = "";
        var err = "";
        obs.subscribe({
            next: function (x) { return (x.source === "stdout" ? (out += x.text) : (err += x.text)); },
            error: function (e) {
                var error = new Error("".concat(out, "\n").concat(e.message));
                if ("exitCode" in e) {
                    error.exitCode = e.exitCode;
                    error.code = e.exitCode;
                    error.stdout = out;
                    error.stderr = err;
                }
                rej(error);
            },
            complete: function () { return res([out, err]); },
        });
    });
}
/**
 * Spawns a process but detached from the current process. The process is put
 * into its own Process Group.
 *
 * @param  {string} exe               The executable to run
 * @param  {string[]} params     The parameters to pass to the child
 * @param  {Object} opts              Options to pass to spawn.
 *
 * @return {Promise<string>}       Returns an Promise that represents a detached
 *                                 process. The value returned is the process
 *                                 output. If the process terminates with a
 *                                 non-zero value, the Promise will resolve with
 *                                 an Error.
 */
function spawnDetachedPromise(exe, params, opts) {
    if (opts === null || opts === void 0 ? void 0 : opts.split) {
        return wrapObservableInSplitPromise(spawnDetached(exe, params, __assign(__assign({}, (opts !== null && opts !== void 0 ? opts : {})), { split: true })));
    }
    else {
        return wrapObservableInPromise(spawnDetached(exe, params, __assign(__assign({}, (opts !== null && opts !== void 0 ? opts : {})), { split: false })));
    }
}
/**
 * Spawns a process as a child process.
 *
 * @param  {string} exe               The executable to run
 * @param  {string[]} params     The parameters to pass to the child
 * @param  {Object} opts              Options to pass to spawn.
 *
 * @return {Promise<string>}       Returns an Promise that represents a child
 *                                 process. The value returned is the process
 *                                 output. If the process terminates with a
 *                                 non-zero value, the Promise will resolve with
 *                                 an Error.
 */
function spawnPromise(exe, params, opts) {
    if (opts === null || opts === void 0 ? void 0 : opts.split) {
        return wrapObservableInSplitPromise(spawn(exe, params, __assign(__assign({}, (opts !== null && opts !== void 0 ? opts : {})), { split: true })));
    }
    else {
        return wrapObservableInPromise(spawn(exe, params, __assign(__assign({}, (opts !== null && opts !== void 0 ? opts : {})), { split: false })));
    }
}
//# sourceMappingURL=index.js.map