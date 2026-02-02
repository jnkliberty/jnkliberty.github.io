const fs = require('fs');
const { JSDOM } = require('jsdom');
const { parentPort } = require('worker_threads');
const { loggers } = require('./../util/logger.js');
const { parseText, parsePostTag, parseContentImageTag, parseListBlock, parseTableBlock } = require('../util/parsers.js');
const path = require('path');
const extractLogger = loggers.extracting;


/**
 * Helper Function that processes child nodes of a given node using a provided function.
 * @param {*} node
 */
async function processChildNodes(node, processFunction) {

  let returnProcess = {
    processedChild: false,
    parsedText: ''
  }

  //if there are children process them
  if (node.hasChildNodes() && node.childNodes.length > 0) {

    for (const childNode of Array.from(node.childNodes)) {

      extractLogger.info(`Processing child node: ${childNode.nodeType === 3 ? 'text' : childNode.tagName} : ${childNode.textContent}`);

      //for child nodes, parse inline
      if (childNode.nodeType === 1 && (['p', 'a', 'span', 'strong'].includes(childNode.tagName.toLowerCase()))) {
        childNode._childNode = true;
        let { parsedText: childHtml = '' } = await processFunction(childNode);
        returnProcess.parsedText += childHtml;
        returnProcess.processedChild = true;
      }

      //if its not recongnized, parse as a block
      else if (childNode.nodeType === 1) {
        await processFunction(childNode);
        returnProcess.processedChild = true;
      }

      // Check if the child node is a text node
      else if (childNode.nodeType === 3) {
        // Process the text content and mark it done
        returnProcess.parsedText += parseText(childNode.textContent);
        childNode._processed = true;
      }

    }
  } else { //if there are no children, render the text and return it
    returnProcess.parsedText = parseText(node.textContent);
  }

  //return set values
  return returnProcess;

}

/**
 * Function to extract data from an HTML file.
 * This function reads the HTML file, processes its content, and extracts relevant data such as title, author, description,
 * tags, categories, and post content. It also handles specific blocks like TLDR, objects-reports, and FAQ.
 * The extracted data is returned as an object.
 * @param {string} fileName - The name of the HTML file to be processed.
 * @param {string} type - The type of the file (e.g., 'blog', 'playbook').
 * @returns {object} - An object containing the extracted data:
 *
 */
async function extractData(fileName, type) {

  //setup the return object
  let returnPostValues = {
    //post tags
    title: '',
    author: '',
    description: '',
    schema: '',

    // list tags/blocks
    tldr: { items: [], listParsed: false, lastNode: null },
    tags: { items: [], listParsed: false, lastNode: null },
    categories: { items: [], listParsed: false, lastNode: null },

    //table block
    objectsReports: {
      title: '',
      heading1: undefined,
      column1: [],
      column1Hover: [],
      heading2: undefined,
      column2: [],
      column2Hover: [],
      lastNode: null,
      currentLeftRow: true,
      blockParsed: false,
      numOfCols: 0
    },

    //table block
    faq: {
      title: '',
      column1: [],
      column2: [],
      lastNode: null,
      currentLeftRow: true,
      blockParsed: false,
      numOfCols: 0
    },

    //post content
    postContent: '',
  }

  let document = null;

  try {

    const sourceFilePath = path.resolve(path.dirname(process.execPath), `playbook-drafts/${fileName}`);

    extractLogger.warn(`Reading file: ${fileName}`);
    const htmlContent = fs.readFileSync(sourceFilePath, 'utf-8');
    const dom = new JSDOM(htmlContent);
    document = dom.window.document;

  } catch (error) {
    extractLogger.error(`Error reading file ${fileName}: ${error.message}`);
    throw new Error(`Error reading file ${fileName}: ${error.message}`);
  }

  try {
    //tracking vaulues
    let inTable = null;
    let inList = null;

    // Helper recursive function to process nodes
    async function processNode(node) {

      //dont process if not node or we have already processed
      if (!node) return;
      if (node._processed) return;

      //if the node has not already been processed, process it
      node._processed = true;

      //in almost all cases we only care about nodetype 1 (Element)
      try {
        if (node.nodeType === 1 && node.tagName.toLowerCase() !== 'body' && node._childNode !== true) {

          /** Parse Open Blocks: First Priority */

          if (inList) {

            //parse the list
            returnPostValues[inList] = parseListBlock(node, returnPostValues[inList], inList);

            //check if the blocks is parsed
            if (returnPostValues[inList].listParsed === true) {
              extractLogger.info(`Finished processing block ${inList}`);

              //add to the post content
              switch (inList) {
                case 'tldr':
                  if (returnPostValues.tldr.items.length > 0) {

                    const tldrItems = returnPostValues.tldr.items.map((item, index) => {
                      //parse and remove any invalid chars from json
                      let parsedText = item.replace(/"/g, '');
                      parsedText = parsedText.replace(/'/g, '');
                      return `"content_list_${index}_list_item":"${parsedText}","_content_list_${index}_list_item":"field_6706bfb470c46"`;
                    }).join(',');

                    extractLogger.info(`Adding TLDR items to block: ${tldrItems}`);

                    const tldrBlock = `
                    <!-- wp:acf/hub-and-spoke-tldr {"name":"acf/hub-and-spoke-tldr","data":{"list_item_prefix":"Step","_list_item_prefix":"field_6706bff770c47",${tldrItems},"content_list":${returnPostValues.tldr.items.length},"_content_list":"field_6706bf56b9cb3"},"mode":"auto"} /-->
                  `;

                    returnPostValues.postContent += tldrBlock;
                  }
                  break;
                default:
                  break;
              }

              inList = null;
            }
          }

          //parse any open tables
          else if (inTable) {

            //parse the objects-reports block
            returnPostValues[inTable] = parseTableBlock(node, returnPostValues[inTable], inTable);

            //check if the blocks is parsed
            if (returnPostValues[inTable].blockParsed === true) {
              extractLogger.info(`Finished processing block ${inTable}`);

              //add to the post content
              switch (inTable) {
                case 'objectsReports':

                  const objectsReports = returnPostValues.objectsReports;

                  // Transform column data to line-break separated strings
                  const column1String = objectsReports.column1.filter(item => item).join('\r\n');
                  const column2String = objectsReports.column2.filter(item => item).join('\r\n');


                  //Build ACF data object
                  const acfData = {
                    "name": "acf/playbook-objects-reports",
                    "data": {
                      "field_67ca12053d9f5": objectsReports.title,
                      "field_67d1e5999642e": objectsReports.heading1,
                      "field_67ca12053e1e8": column1String,
                      "field_67d1e5b896430": objectsReports.heading2,
                      "field_67ca12053ed84": column2String,
                      "field_67ca12053e5e3": objectsReports.column1Hover.join(', '),
                      "field_67ca12053f169": objectsReports.column2Hover.join(', '),
                    },
                    "mode": "auto"
                  };

                  // Convert ACF data to a JSON string, then escape special characters for the WP block
                  const acfDataJSON = JSON.stringify(acfData);

                  // Create the ACF block comment
                  returnPostValues.postContent += `\n<!-- wp:acf/playbook-objects-reports ${acfDataJSON} /-->\n`;
                  break;
                case 'faq':
                  break;
                default:
                  break;
              }

              inTable = null;
            }
          }

          /** Parse Post Tags: Second Priority */

          //check for title
          else if (node.tagName.toLowerCase() === 'h1') {
            extractLogger.info(`Found title: ${node.textContent.trim()}`);
            returnPostValues.title = parseText(node.textContent);

            //parse children to mark done
            for (const childNode of Array.from(node.childNodes)) {
              childNode._processed = true;
            }
          }

          //check for custom post-tag
          else if (node.textContent.includes('post-tag:')) {

            if (node.tagName.toLowerCase() === 'h2' || node.tagName.toLowerCase() === 'h3' || node.tagName.toLowerCase() === 'h4') {

              const parsedTag = parsePostTag(node);
              const postTag = parsedTag.parsedTag;
              const postTagInList = parsedTag.inList;

              if (postTagInList !== null) {
                inList = postTagInList;
              }

              if (node.textContent.includes('post-tag:schema:')) {
                // Extract everything after 'post-tag:schema:'
                const schemaMatch = node.textContent.match(/post-tag:schema:({[\s\S]*})$/);
                if (schemaMatch && schemaMatch[1]) {
                  const schemaJson = schemaMatch[1].trim();

                  // After extracting schemaJson as a string
                  try {
                    const parsed = JSON.parse(schemaJson);
                     extractLogger.info(`Parsed schema post-tag: ${parsed}`);
                    returnPostValues.schema = JSON.stringify(parsed); // minified string
                  } catch (e) {
                    extractLogger.warn(`Schema is not valid JSON: ${e}`);
                    returnPostValues.schema = '';
                  }

                } else {
                  extractLogger.warn(`Could not parse schema post-tag: ${node.textContent.trim()}`);
                }
              }

              else if (postTag !== null) {
                extractLogger.info(`Parsed post-tag: ${node.textContent.trim()}`);
                returnPostValues = { ...returnPostValues, ...postTag };
              }

              else {
                extractLogger.warn(`Invalid post-tag format: ${node.textContent.trim()}`);
              }
            }
          }

          //check for image, stop worker if not found
          else if ((node.textContent.toLowerCase()).includes('content:image')) {
            if (node.tagName.toLowerCase() === 'h2' || node.tagName.toLowerCase() === 'h3' || node.tagName.toLowerCase() === 'h4') {
              try {
                const parsedImage = await parseContentImageTag(node, fileName);
                returnPostValues.postContent += parsedImage;
              } catch (e) {
                throw e;
              }
            }
          }

          /** Parse Blocks: Third Priority */

          //check for tldr block
          else if (node.textContent.includes('block:tldr')) {
            if (node.tagName.toLowerCase() === 'h2' || node.tagName.toLowerCase() === 'h3' || node.tagName.toLowerCase() === 'h4') {
              inList = 'tldr';
            }
          }

          //check for objects and reports block
          else if (node.textContent.includes('block:objects-reports')) {
            if (node.tagName.toLowerCase() === 'h2' || node.tagName.toLowerCase() === 'h3' || node.tagName.toLowerCase() === 'h4') {
              inTable = 'objectsReports';
            }
          }

          //check for faq block
          else if (node.textContent.includes('block:faq')) {
            if (node.tagName.toLowerCase() === 'h2' || node.tagName.toLowerCase() === 'h3' || node.tagName.toLowerCase() === 'h4') {
              inTable = 'faq';
            }
          }

          //check for block:youtube-embed
          else if (node.textContent.includes('block:youtube-embed:')) {
            if (
              node.tagName.toLowerCase() === 'h2' ||
              node.tagName.toLowerCase() === 'h3' ||
              node.tagName.toLowerCase() === 'h4'
            ) {
              // Extract the YouTube URL from the text content
              const match = node.textContent.match(/block:youtube-embed:(https?:\/\/[^\s]+)/);
              if (match && match[1]) {
                const youtubeUrl = match[1].trim();
                const youtubeEmbedBlock = `
<!-- wp:embed {"url":"${youtubeUrl}","type":"video","providerNameSlug":"youtube","responsive":true,"className":"wp-embed-aspect-16-9 wp-has-aspect-ratio"} -->
<figure class="wp-block-embed is-type-video is-provider-youtube wp-block-embed-youtube wp-embed-aspect-16-9 wp-has-aspect-ratio"><div class="wp-block-embed__wrapper">
${youtubeUrl}
</div></figure>
<!-- /wp:embed -->
`;
                returnPostValues.postContent += youtubeEmbedBlock;
              }
            }
          }

          /** Parse Content: Fourth Priority */

          //check for blog content parent nodes
          else if (
            node.nodeType === 1 &&
            ['p', 'a', 'h2', 'h3', 'h4', 'ul', 'ol', 'li', 'table', 'tbody', 'thead', 'tfoot', 'tr', 'th', 'td'].includes(node.tagName.toLowerCase())
          ) {
            const tagName = node.tagName.toLowerCase();

            // Wrap content in appropriate WP block format
            switch (tagName) {

              case 'h2':
                returnPostValues.postContent += `<!-- wp:heading {"level":2} -->\n<h2>`;

                //handle parsing of children nodes
                let { parsedText: parsedH2 } = await processChildNodes(node, processNode);
                returnPostValues.postContent += parsedH2;

                returnPostValues.postContent += `</h2>\n<!-- /wp:heading -->\n`;
                break;

              case 'h3':
                returnPostValues.postContent += `<!-- wp:heading {"level":3} -->\n<h3>`;

                //handle parsing of children nodes
                let { parsedText: parsedH3 } = await processChildNodes(node, processNode);
                returnPostValues.postContent += parsedH3;


                returnPostValues.postContent += `</h3>\n<!-- /wp:heading -->\n`;
                break;

              case 'h4':
                returnPostValues.postContent += `<!-- wp:heading {"level":4} -->\n<h4>`;

                //handle parsing of children nodes
                let { parsedText: parsedH4 } = await processChildNodes(node, processNode);
                returnPostValues.postContent += parsedH4;

                returnPostValues.postContent += `</h4>\n<!-- /wp:heading -->\n`;
                break;

              //handle cases where there could be children nodes
              case 'p':
                returnPostValues.postContent += `<!-- wp:paragraph -->\n<p>`;

                //handle parsing of children nodes
                let { parsedText: parsedP } = await processChildNodes(node, processNode);
                returnPostValues.postContent += parsedP;

                returnPostValues.postContent += `</p>\n<!-- /wp:paragraph -->\n`;
                break;

              case 'a':
                const href = node.getAttribute('href');
                const text = parseText(node.textContent.trim());
                returnPostValues.postContent += `<!-- wp:paragraph -->\n<p><a href="${href}">${text}</a></p>\n<!-- /wp:paragraph -->\n`;
                break;

              case 'ul':
                returnPostValues.postContent += `<!-- wp:list {"className":"wp-block-list"} -->\n<ul class="wp-block-list">\n`;

                let { parsedText: parsedUl } = await processChildNodes(node, processNode);
                returnPostValues.postContent += parsedUl;


                returnPostValues.postContent += `</ul>\n<!-- /wp:list -->\n`;
                break;

              case 'ol':
                returnPostValues.postContent += `<!-- wp:list {"ordered":true} -->\n<ol class="wp-block-list">\n`;

                let { parsedText: parsedOl } = await processChildNodes(node, processNode);
                returnPostValues.postContent += parsedOl;

                returnPostValues.postContent += `</ol>\n<!-- /wp:list -->\n`;
                break;

              case 'li':
                returnPostValues.postContent += `<!-- wp:list-item -->\n<li>`;

                let { parsedText: parsedLi } = await processChildNodes(node, processNode);
                returnPostValues.postContent += parsedLi;

                returnPostValues.postContent += `</li><!-- /wp:list-item -->\n`;
                break;

              //parse table scenarios
              case 'table':
                returnPostValues.postContent += '<!-- wp:table -->\n<figure class="wp-block-table"><table>\n';

                let { parsedText: parseTable } = await processChildNodes(node, processNode);
                returnPostValues.postContent += parseTable;


                returnPostValues.postContent += '</table></figure>\n<!-- /wp:table -->\n';
                break;

              case 'tbody':
              case 'thead':
              case 'tfoot':
                // Pass the tag to the content, then parse its children
                returnPostValues.postContent += `<${tagName}>\n`;

                let { parsedText: parsedTableProps } = await processChildNodes(node, processNode);
                returnPostValues.postContent += parsedTableProps;


                returnPostValues.postContent += `</${tagName}>\n`;
                break;

              case 'tr':
                returnPostValues.postContent += '<tr>\n';
                let { parsedText: parsedTr } = await processChildNodes(node, processNode);
                returnPostValues.postContent += parsedTr;
                returnPostValues.postContent += '</tr>\n';
                break;

              case 'td':
                returnPostValues.postContent += `<td>\n`;

                let { parsedText: parsedTd } = await processChildNodes(node, processNode);
                returnPostValues.postContent += parsedTd;

                returnPostValues.postContent += `</td>\n`;
                break;

              case 'th':
                returnPostValues.postContent += `<td>\n`;

                let { parsedText: parsedTh } = await processChildNodes(node, processNode);
                returnPostValues.postContent += parsedTh;

                returnPostValues.postContent += `</td>\n`;
                break;

              default:
                break;
            }
          }

        }

        //process child nodes from the supported list of child nodes
        else if (node.nodeType === 1 && node._childNode && ['p', 'a', 'span', 'strong'].includes(node.tagName.toLowerCase())) {

          const tagName = node.tagName.toLowerCase();

          // Wrap content in appropriate WP block format
          switch (tagName) {

            //handle cases where there could be children nodes
            case 'p':
              let { parsedText: parsedP } = await processChildNodes(node, processNode);
              return { parsedText: `<p>${parsedP}</p>` };

            //in the case of a span, ignore the tag and just parse its children or if there are none, parse the text
            case 'span':
              let { parsedText: parsedS } = await processChildNodes(node, processNode);
              returnPostValues.postContent += parsedS;
              return { parsedText: `${parsedText}` };

            case 'strong':
              let { parsedText: parsedTextStrong } = await processChildNodes(node, processNode);
              return { parsedText: ` <strong>${parsedTextStrong}</strong> ` };

            //for the link tag, return inline html if its a child
            case 'a':
              const href = node.getAttribute('href');
              let { parsedText: linkText } = await processChildNodes(node, processNode);
              return { parsedText: ` <a href="${href}">${linkText}</a> ` };

            default:
              break;
          }
        }

      } catch (error) {
        extractLogger.error(`Error processing node: ${error.message} \nStack Trace: ${error.stack}`);
        throw error; // Rethrow the error to stop processing
      }

      // Recursively process child nodes
      const childNodes = Array.from(node.childNodes);
      for (const childNode of childNodes) {
        await processNode(childNode); // Ensure child nodes are processed asynchronously
      }

    }

    // Start processing from the root of the document
    await processNode(document.body);
    extractLogger.warn(`Completed Processing Nodes in Doc: ${returnPostValues.title}`);
    return returnPostValues;

  } catch (error) {
    extractLogger.error(`Error extracting input for file ${fileName}: \nStack Trace: ${error.stack}`);
    throw error;
  }
}

// Listen for messages from the parent thread
parentPort && parentPort.on('message', async (specs) => {

  //get job specs
  const fileName = specs.fileName;
  const type = specs.type;
  let draftFile = null;

  //start job and wait for completion
  try {
    draftFile = await extractData(fileName, type);
  }
  catch (error) {
    throw new Error(`Error in extractData: ${error.message}`);
  }

  parentPort.postMessage(draftFile);

});

module.exports = {
  processChildNodes,
  extractData
};
