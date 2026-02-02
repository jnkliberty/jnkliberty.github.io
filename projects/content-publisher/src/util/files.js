const fs = require('fs');
const path = require('path');

/**
 * Gets all the files in the given directory
 * @param {*} dirPath
 * @returns
 */
function getFilesInDirectory(dirPath) {
    try {
        const files = fs.readdirSync(dirPath);
        return files.filter(file => fs.statSync(path.join(dirPath, file)).isFile());
    } catch (err) {
        console.error(`Error reading directory ${dirPath}:`, err);
        return [];
    }
}

module.exports = { getFilesInDirectory };
