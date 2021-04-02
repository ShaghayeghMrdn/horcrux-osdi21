const chromeLauncher = require('chrome-launcher');
const chromeRI = require('chrome-remote-interface');
const fs = require('fs');
const program = require('commander');

/**
 * Uses chrome-remote-interface to load a page within a time limit (120s),
 * record the page load time if it did not time out,
 * save the needed information based on the given instrumentation mode
 * again within a time limit (120s).
 * @param {LaunchedChrome} chrome - chrome instance created by chrome-launcher
 */
async function navigate(chrome) {
    let client;
    const pageTimes = {};
    try {
        client = await chromeRI({
            port: chrome.port,
        });

        const {
            Emulation,
            Network,
            Page,
            Performance,
            Runtime,
        } = client;

        await Promise.all([
            Network.enable(),
            Page.enable(),
            Performance.enable(),
            Runtime.enable(),
        ]);

        // get the timestamp when load event is fired!
        Page.loadEventFired((params) => {
            pageTimes['fired'] = params.timestamp;
        });

        // Runtime.consoleAPICalled((loggedObject) => {
        //     if (loggedObject.type != 'log') return;
        //     if (typeof(loggedObject.args) != "undefined") {
        //         for (let i = 0; i < loggedObject.args.length; ++i) {
        //             const logOutput = loggedObject.args[i]["value"];
        //             // console.log(`Output in console.log: ${logOutput}`);
        //         }
        //     }
        // });

        await Network.setUserAgentOverride({
            userAgent: 'Mozilla/5.0 (Linux; Android 8.0.0; Pixel 2)' +
            ' AppleWebKit/537.36 (KHTML, like Gecko)' +
            ' Chrome/73.0.3683.90 Mobile Safari/537.36'});
        await Emulation.setDeviceMetricsOverride({
            width: 411,
            height: 731,
            mobile: true,
            deviceScaleFactor: 0,
        });
        if (program.throttle) {
            await Emulation.setCPUThrottlingRate({rate: 2.75});
        }

        const plTimer = setTimeout(function() {
            if (client) {
                client.close();
                chrome.kill();
            }
            throw new Error('Page load timed out!');
        }, 180000);

        await Page.navigate({
            url: program.url,
        });

        await Page.loadEventFired();
        // Pause the page to stop any further JavaScript computation
        Runtime.evaluate({expression: 'debugger;'});
        // console.log('Page has been paused!');
        clearTimeout(plTimer);

        const performanceResult = await Performance.getMetrics();
        // .metrics is an array of Metric objects {name, value}
        performanceResult.metrics.forEach(function(metric) {
            if (metric.name == 'NavigationStart') {
                pageTimes['start'] = metric.value;
            }
        });
        pageTimes['plt'] = pageTimes['fired'] - pageTimes['start'];
        console.log('page load time:', pageTimes['plt'])

        if (program.pltFile) {
            fs.writeFileSync(program.pltFile,
                JSON.stringify(pageTimes, null, 2));
        }

        const dataTimer = setTimeout(function() {
            if (client) {
                client.close();
                chrome.kill();
            }
            throw new Error('Writing to files timed out!');
        }, 180000);

        if (program.mode == 'light') {
            const rootInvocsProcess = await Runtime.evaluate({
                expression: '__tracer.getRootInvocs()',
                returnByValue: true,
            });
            fs.writeFileSync(program.outputFile,
                JSON.stringify(rootInvocsProcess.result, null, 2));

            if (program.callgraphFile) {
                const callGraphProcess = await Runtime.evaluate({
                    expression: '__tracer.getCallGraph()',
                    returnByValue: true,
                });
                fs.writeFileSync(program.callgraphFile,
                    JSON.stringify(callGraphProcess.result, null, 2));
            }
        } else if (program.mode == 'timing') {
            const timingInfo = await Runtime.evaluate({
                expression: '__tracer.getTimingInfo()',
                returnByValue: true,
            });
            fs.writeFileSync(program.outputFile,
                JSON.stringify(timingInfo.result, null, 2));
        } else if (program.mode == 'heavy') {
            await Runtime.evaluate({
                expression: '__tracer.processFinalSignature()',
                returnByValue: true,
            });
            const signature = await Runtime.evaluate({
                expression: '__tracer.getProcessedSignature()',
                returnByValue: true,
            });
            fs.writeFileSync(program.outputFile,
                JSON.stringify(signature.result, null, 2));
        }
        // console.log(`Wrote to ${program.outputFile}!`);

        clearTimeout(dataTimer);
        if (client && !program.keepAlive) {
            client.close();
            chrome.kill();
        }
    } catch (err) {
        console.error(err);
        chrome.kill();
    }
}

program
    .option('-u, --url <url>', 'The url to record/replay')
    .option('-m, --mode <mode>', 'Instrumentation mode: light/timing/heavy')
    .option('-o, --output-file <output>', 'The output file path')
    .option('-p, --port <port>', 'The port for chrome, default to 9222', '9222')
    .option('-g, --callgraph-file <callgraph>', 'File path to save call graph')
    .option('-l, --plt-file <pltfile>', 'File path to save page load time')
    .option('-t, --throttle', 'Enables CPU throttling')
    .option('-a, --keep-alive', 'Keeps the chrome instance alive')
    .parse(process.argv);

// check the required options
if (!program.url) {
    console.error('Error: The page URL is required!');
    process.exit(1);
} else if (program.mode && !program.outputFile) {
    console.error('Error: Output file path is not specified!');
    process.exit(1);
}
if (program.callgraphFile && program.mode != 'light') {
    console.error('Warning: --callgraph-file only works in "light" mode!');
}

const chromeDataDir = '/tmp/nonexistent' + (new Date).getTime();
chromeFlags = [
    '--allow-running-insecure-content',
    '--disable-extensions',
    '--disable-features=IsolateOrigins,site-per-process,' +
    'CrossSiteDocumentBlockingAlways,CrossSiteDocumentBlockingIfIsolating',
    '--disable-site-isolation-trials',
    '--disable-web-security',
    '--ignore-certificate-errors',
    '--no-default-browser-check',
    '--no-first-run',
    '--user-data-dir=' + chromeDataDir,
]
if (!program.keepAlive) {
    chromeFlags.push('--headless')
}

chromeLauncher.launch({
    port: Number(program.port),
    chromeFlags: chromeFlags,
}).then((chrome) => {
    navigate(chrome);
});
