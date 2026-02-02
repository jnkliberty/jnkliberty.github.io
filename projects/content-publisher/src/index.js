const { Worker } = require('worker_threads');
const { getFilesInDirectory } = require('./util/files.js');
const { loggers } = require('./util/logger.js');
const path = require('path');
const dotenv = require('dotenv');
const fs = require('fs');
const workerLogger = loggers.worker;

// Resolve the path to the .env file relative to the executable
const envPath = path.resolve(path.dirname(process.execPath), '.env');

// Load the .env file
dotenv.config({ path: envPath });

// Start the worker thread
function startWorker(task, specs) {
    return new Promise((resolve, reject) => {

        const workerPath = path.resolve(path.dirname(process.execPath), `workers/${task}.js`);

        const worker = new Worker(workerPath);
        worker.on('message', resolve);
        worker.on('error', (error) => workerLogger.error(`Worker for job ${task} with ${specs.fileName} failed with error: ${error}`));
        worker.on('exit', (code) => {
            if (code !== 0) reject(new Error(`Worker for job ${task} with ${specs.fileName} ${code}`));
        });

        worker.postMessage(specs);
    });
}

// Event Handler
(async () => {

    let extractedFiles = [];

    try {

        const args = process.argv.slice(2);

        const playbookDir = path.resolve(path.dirname(process.execPath), 'playbook-drafts');

        // Ensure the directory exists
        if (!fs.existsSync(playbookDir)) {
            console.error(`Error: Directory ${playbookDir} does not exist.`);
            process.exit(1);
        }

        const type = 'playbook';
        const files = getFilesInDirectory(playbookDir);

        console.log("files: ", files);

        if (files.length === 0) {
            console.log(`No files found in ${playbookDir}.`);
            return;
        }

        // Concurrent extraction with max 4 workers
        const maxConcurrentWorkers = 4;
        const processingQueue = [...files];
        let activeWorkers = 0;

        const processFile = async (file) => {
            try {
                const extractDoc = await startWorker('extract-input', { fileName: file, type: type });
                extractedFiles.push({ fileName: file, extractDoc });
            } catch (error) {
                // logged by worker
            } finally {
                activeWorkers--;
                processNext();
            }
        };

        const publishSequentially = async () => {
            for (const { fileName, extractDoc } of extractedFiles) {
                try {
                    const publishResult = await startWorker('publish-draft', { input: extractDoc, fileName: fileName, type: type });
                    console.log(`Published post for file: ${fileName}`, publishResult);
                } catch (error) {
                    // logged by worker
                }
            }
            console.log("All posts have been published. Exiting program...");
            process.exit(0);
        };

        const processNext = () => {
            if (processingQueue.length > 0 && activeWorkers < maxConcurrentWorkers) {
                const file = processingQueue.shift();
                activeWorkers++;
                processFile(file);
            }
            else if (processingQueue.length === 0 && activeWorkers === 0) {
                console.log("All input extraction complete. Starting sequential publishing...");
                publishSequentially();
            }
        };

        for (let i = 0; i < Math.min(files.length, maxConcurrentWorkers); i++) {
            processNext();
        }

    } catch (error) {
        workerLogger.error(`Error in Event Handler processing worker: ${error.message}`)
    }
})();
