const { loggers } = require('./logger.js');
const axios = require('axios');
const { Auth, WP_API_BASE } = require('./auth.js');
const extractLogger = loggers.extracting;

/**
 * Function to trim content and remove extra spaces
 * @param {*} text
 */
function parseText(text) {
    let parsedText = text.trim();
    parsedText = parsedText.replace(/\s+/g, ' ');
    return parsedText;
}

/**
 * Parse Post Tags with the format "post-tag: tags: tag1, tag2"
 * Support single tags and lists
 * @param {*} node
 * @returns
 */
function parsePostTag(node) {

    let returnPostTagValues = {
        inList: null,
        parsedTag: null
    };

    //ignore any span
    if (node.tagName.toLowerCase() === 'span') {
        return returnPostTagValues;
    }

    //split the text content by ':'
    const postTagContent = node.textContent.split(':');

    //check if we need a list to parse
    if (postTagContent[0] === 'post-tag' && postTagContent.length >= 3) {

        if (postTagContent[1] === 'tags' || postTagContent[1] === 'categories') {
            returnPostTagValues.inList = postTagContent[1];
        }

        else {
            returnPostTagValues.parsedTag = {
                [postTagContent[1]]: parseText(postTagContent[2])
            }
        }

        return returnPostTagValues;

    } else {
        return returnPostTagValues;
    }
}

/**
 * Parse the image tag and return the HTML for the image
 * @param {*} node
 * @param {*} filePath
 * @returns
 */
async function parseContentImageTag(node, filePath) {
    if (node.nodeType === 1) {
        const imageTagContent = node.textContent.split(':');

        // Check if the split result has at least 3 parts
        if ((imageTagContent[0]).toLowerCase() === 'content' && imageTagContent.length >= 3) {

            const imageName = imageTagContent[2].trim(); // Extract the image file name
            const imageAltText = imageTagContent[3] ? imageTagContent[3].trim() : '';

            try {
                // Make an API call to WordPress to search for the image by its name
                const response = await axios.get(
                    `${WP_API_BASE}/wp/v2/media?search=${encodeURIComponent(imageName)}`,
                    { auth: { ...Auth } }
                );

                if (response.data.length > 0) {
                    const image = response.data[0]; // Assuming the first result is the correct one
                    const imageId = image.id;
                    const imageUrl = image.source_url;

                    extractLogger.info(`Image Found: ${imageId} - ${imageUrl}`);

                    // Return the WordPress block for the image
                    return (
                        `<!-- wp:image {"id":${imageId}} -->`
                        + `<figure class="wp-block-image size-large"><img src="${imageUrl}" alt="${imageAltText || (image.alt_text || "image")}" class="wp-image-${imageId}"/></figure>`
                        + `<!-- /wp:image -->`
                    );
                } else {
                    extractLogger.error(`No image found for name: ${imageName} in ${filePath}`);
                    throw Error(`No image found for name: ${imageName} in ${filePath}`);
                }
            } catch (error) {
                extractLogger.error(`Error fetching image from WordPress: ${error.message} in ${filePath}`);
                throw Error(`Error fetching image from WordPress: ${error.message} in ${filePath}`);
            }
        } else {
            return ""; // Return an empty string if the tag format is invalid
        }
    } else {
        return ""; // Return an empty string if the node is not valid
    }
}

/**
 * Parses list blocks by recursively traversing the nodes in the list
 * starts by opening it and parsing children until it finds the closing tag
 * sets the values for the list based on the type of list [ tldr, categories, tags, etc]
 * @param {*} node
 * @param {*} list Recursive list variables
 * @param {*} listType One of the following: tldr, categories, tags
 */
function parseListBlock(node, list, listType) {

    //initialize recursive variables
    let items = list.items || [];
    let listParsed = list.listParsed || false;
    let lastNode = list.lastNode || null;

    if (node.tagName.toLowerCase() === 'ul') {
        lastNode = node.lastElementChild;
    }

    else if ((node.tagName.toLowerCase() === 'li')) {

        //ignore span inside of li blocks, since we already got the li
        if (node.tagName.toLowerCase() === 'li') {
            extractLogger.info(`open text inside of li block ${node.textContent.trim()} for ${listType}`);
            items.push(parseText(node.textContent.trim()));
        }

        // Check if this node is the last child of the ul
        if (node === lastNode || node.contains(lastNode)) {
            extractLogger.info(`close ul block for ${listType}`);
            listParsed = true;

            //parse all remaining children nodes
            for (const childNode of Array.from(node.childNodes)) {
                childNode._processed = true;
            }
        }
    }

    //return report
    return {
        ...list,
        items,
        listParsed,
        lastNode
    }
}

/**
 * Parses tables by recursively traversing the nodes in the table
 * starts by opening it and parsing children until it finds the closing tag
 * sets the values for the table based on the type of table [objectsReports or faq]
 * @param {*} node
 * @param {*} report Recursive report variables
 * @param {*} type One of the following: objectsReports, faq
 * @returns
 */
function parseTableBlock(node, report, type) {
    let parseReport = {
        title: '',
        column1: [],
        column1Hover: [],
        column2: [],
        column2Hover: [],
        heading1: '',
        heading2: '',
        lastNode: null,
        currentLeftRow: true,
        blockParsed: false,
        numOfCols: 0,
    };

    parseReport = { ...parseReport, ...report };

    // Check for title
    if (node.nodeType === 1 && node.tagName.toLowerCase() === 'h2') {
        parseReport.title = parseText(node.textContent.trim());
        extractLogger.info(`Found title: ${parseReport.title} for table: ${type}`);
    }

    // Check if we are in a table body
    if (node.tagName.toLowerCase() === 'tbody') {
        parseReport.lastNode = node.lastElementChild;
        extractLogger.info(`Found table body with last node: ${parseReport.lastNode.tagName} for ${type}`);
    }

    // Check for table row and determine the number of columns
    else if (node.tagName.toLowerCase() === 'tr' && parseReport.numOfCols === 0) {
        const cells = node.querySelectorAll('td, th');
        parseReport.numOfCols = cells.length;
        extractLogger.info(`Found table row with ${parseReport.numOfCols} columns for ${type}`);
    }

    // Grab the first 2 table headings
    else if (node.tagName.toLowerCase() === 'td' && (parseReport.heading1 === undefined || parseReport.heading2 === undefined)
        && type === 'objectsReports') {

        const cellText = node.textContent.trim();

        if (parseReport.heading1 === undefined) {
            parseReport.heading1 = cellText === "" ? cellText : parseText(cellText);
            extractLogger.info(`Found col 1 heading: ${parseReport.heading1} for ${type}`);
        } else if (parseReport.heading2 === undefined) {
            parseReport.heading2 = cellText === "" ? cellText : parseText(cellText);
            extractLogger.info(`Found col 2 heading: ${parseReport.heading2} for ${type}`);
        }
    }

    // Process table rows
    else if (node.tagName.toLowerCase() === 'td' && (type === 'objectsReports' || type === 'faq')) {
        let currCol = parseReport.currentLeftRow ? 'column1' : 'column2';
        let currColHover = parseReport.currentLeftRow ? 'column1Hover' : 'column2Hover';

        // Recursively process child nodes to handle lists, links, and bold text
        const parsedContent = processTableCellContent(node);

        // If items exceed 12, add to hover items
        if (type === 'objectsReports' && parseReport[currCol].length > 12 && parsedContent.trim().length > 0) {
            parseReport[currColHover].push(parsedContent);
            extractLogger.info(`Found table ${currColHover} hover item: ${parsedContent} for ${type}`);
        } else {
            // Add to the main column
            parseReport[currCol].push(parsedContent);
            extractLogger.info(`Found table ${currCol} item: ${parsedContent} for ${type}`);
        }

        // Toggle the current column if there are multiple columns
        if (parseReport.numOfCols > 1) {
            parseReport.currentLeftRow = !parseReport.currentLeftRow;
        }
    }

    // Process the last node
    else if (node === parseReport.lastNode) {
        if (node.tagName.toLowerCase() === 'tr') {
            const cells = Array.from(node.querySelectorAll('td'));
            parseReport.currentLeftRow = true;

            cells.forEach((cell) => {
                cell._processed = true;
                const parsedContent = processTableCellContent(cell);

                let currCol = parseReport.currentLeftRow ? 'column1' : 'column2';
                let currColHover = parseReport.currentLeftRow ? 'column1Hover' : 'column2Hover';

                if (type === 'objectsReports' && parseReport[currCol].length > 12 && parsedContent.trim().length > 0) {
                    parseReport[currColHover].push(parsedContent);
                    extractLogger.info(`Found table ${currColHover} hover item: ${parsedContent} for ${type}`);
                } else {
                    parseReport[currCol].push(parsedContent);
                    extractLogger.info(`Found table ${currCol} item: ${parsedContent} for ${type}`);
                }

                if (parseReport.numOfCols > 1) {
                    parseReport.currentLeftRow = !parseReport.currentLeftRow;
                }
            });
        }

        parseReport.blockParsed = true;
        extractLogger.info("Finished processing table", parseReport);
    }

    return { ...parseReport };
}

/**
 * Helper function to process the content of a table cell.
 * Handles lists, links, bold text, and ignores spans.
 * @param {*} cellNode
 * @returns {string} - Parsed HTML content of the cell
 */
function processTableCellContent(cellNode) {
    let content = '';

    for (const childNode of Array.from(cellNode.childNodes)) {
        if (childNode.nodeType === 3) {
            // Text node
            content += parseText(childNode.textContent);
        } else if (childNode.nodeType === 1) {
            const tagName = childNode.tagName.toLowerCase();

            switch (tagName) {
                case 'ul':
                case 'ol':
                    content += `<${tagName}>${processTableCellContent(childNode)}</${tagName}>`;
                    break;

                case 'li':
                    content += `<li>${processTableCellContent(childNode)}</li>`;
                    break;

                case 'a':
                    const href = childNode.getAttribute('href');
                    content += `<a href="${href}">${processTableCellContent(childNode)}</a>`;
                    break;

                case 'strong':
                case 'b':
                    content += `<${tagName}>${processTableCellContent(childNode)}</${tagName}>`;
                    break;

                case 'span':
                    // Ignore <span> tags but process their children
                    content += processTableCellContent(childNode);
                    break;

                default:
                    // Process other tags recursively
                    content += processTableCellContent(childNode);
                    break;
            }
        }
    }

    return content;
}

module.exports = {
    parseText,
    parsePostTag,
    parseContentImageTag,
    parseListBlock,
    parseTableBlock
};
