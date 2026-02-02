const { parentPort } = require('worker_threads');
const axios = require("axios");
const fs = require('fs');
const { Auth, WP_API_BASE } = require('../util/auth.js');
const { loggers } = require('./../util/logger.js');
const publishLogger = loggers.publishing;
const path = require('path');


// Function to publish a blog post
async function publishPost(blogData, type, fileName) {

    let categoryIds = [];
    let termIds = [];
    let authorId = null;

    try {

        try {
            const authorResponse = await axios.get(
                `${WP_API_BASE}/wp/v2/users?search=${blogData.author}`,
                { auth: { ...Auth } }
            );

            if (authorResponse.data[0] && authorResponse.data[0].id) {
                publishLogger.info(`Author: ${blogData.author} set for ${fileName}`);
                authorId = authorResponse.data[0].id
            } else {
                publishLogger.error(`Author "${blogData.author}" not found for ${fileName}`);
                throw new Error(`Author not found for ${fileName}`);
            }
        } catch (error) {
            publishLogger.error(`Error fetching author: ${error.message} for ${fileName}`);
            throw new Error(error);
        }

        try {
            if (blogData.tags && blogData.tags.items) {
                termIds = await Promise.all(
                    blogData.tags.items.map(async (tag) => {
                        const termResponse = await axios.get(
                            `${WP_API_BASE}/wp/v2/playbook_tag?search=${encodeURIComponent(tag)}`,
                            { auth: { ...Auth } }
                        );

                        if (termResponse.data[0] && termResponse.data[0].id) {
                            return termResponse.data[0]?.id || null;
                        } else {
                            publishLogger.error(`Term "${tag}" not found for ${fileName}`);
                            throw new Error(`Term "${tag}" not found for ${fileName}`);
                        }
                    })
                ).then(ids => ids.filter(Boolean));
            }
        } catch (error) {
            publishLogger.error(`Error fetching terms: ${error.message} for ${fileName}`);
            throw new Error(error);
        }

        try {
            if (blogData.categories && blogData.categories.items) {
                categoryIds = await Promise.all(
                    blogData.categories.items.map(async (tag) => {
                        const termResponse = await axios.get(
                            `${WP_API_BASE}/wp/v2/playbook_category?search=${encodeURIComponent(tag)}`,
                            { auth: { ...Auth } }
                        );

                        if (termResponse.data[0] && termResponse.data[0].id) {
                            return termResponse.data[0]?.id || null;
                        } else {
                            publishLogger.error(`Taxonomy "${tag}" not found for ${fileName}`);
                            throw new Error(`Taxonomy "${tag}" not found for ${fileName}`);
                        }

                    })
                ).then(ids => ids.filter(Boolean));
            }
        } catch (error) {
            publishLogger.error(`Error fetching categories: ${error.message} in ${fileName}`);
            throw new Error(error);
        }

        let existingPost = null;
        if (blogData.url) {
            try {
                const queryParam = blogData.url
                    ? `slug=${encodeURIComponent(blogData.url)}`
                    : `search=${encodeURIComponent(blogData.title)}`;

                const existingPostResponse = await axios.get(
                    `${WP_API_BASE}/wp/v2/${type}?${queryParam}&status=any`,
                    { auth: { ...Auth } }
                );

                if (existingPostResponse.data.length > 0) {
                    existingPost = existingPostResponse.data[0];
                    publishLogger.warn(`Page with ${blogData.url ? `slug "${blogData.url}"` : `title "${blogData.title}"`} already exists. ID: ${existingPost.id} with status ${existingPost.status}`);
                } else {
                    publishLogger.warn(`No existing post found with slug "${blogData.url}"`);
                }
            } catch (error) {
                publishLogger.warn(`Error checking if page exists: ${error.message}`);
            }
        }

        //setup FAQ Data
        const faqData = {
            question_section_title: blogData.faq.title || "Frequently Asked Questions",
            _question_section_title: "field_6705288921412",
            question_list: blogData.faq.column1.map((question, index) => ({
                question_title: question || "",
                _question_title: "field_6705288923b78",
                question_answer: blogData.faq.column2[index] || "",
                _question_answer: "field_670528d58fad9",
                default_open: false,
                _default_open: "field_67053cf8c10ea"
            })),
            _question_list: "field_67052889218c6"
        };

        // Log the FAQ data for debugging
        publishLogger.info(`ACF to post: faq: ${faqData.question_list} & description: ${blogData.description}`);
        publishLogger.info(`tax to post: ${termIds, categoryIds}`);
        publishLogger.info(`${blogData.schema}`);

        let postResponse;
        if (existingPost !== null) {
            // Update the existing post
            postResponse = await axios.put(
                `${WP_API_BASE}/wp/v2/${type}/${existingPost.id}`,
                {
                    title: blogData.title,
                    status: existingPost.status,
                    type: type,
                    author: authorId,
                    content: blogData.postContent,
                    playbook_tag: termIds,
                    playbook_category: categoryIds,
                    slug: blogData.url,
                    acf: {
                        playbook_post_description: blogData.description || "",
                        custom_schema_json_toggle: blogData.schema ? true : false,
                        custom_schema_json: blogData.schema,
                        ...faqData
                    }
                },
                {
                    auth: { ...Auth },
                    headers: {
                        'Content-Type': 'application/json'
                    }
                }
            );
            publishLogger.info(`Post updated with ID: ${existingPost.id}`);
        } else {

            postResponse = await axios.post(
                `${WP_API_BASE}/wp/v2/${type}`,
                {
                    title: blogData.title,
                    status: 'draft',
                    type: type,
                    author: authorId,
                    content: blogData.postContent,
                    playbook_tag: termIds,
                    playbook_category: categoryIds,
                    slug: blogData.url,
                    acf: {
                        playbook_post_description: blogData.description || "",
                        custom_schema_json_toggle: blogData.schema ? true : false,
                        custom_schema_json: blogData.schema,
                        ...faqData
                    }
                },
                {
                    auth: { ...Auth },
                    headers: {
                        'Content-Type': 'application/json'
                    }
                }
            );

            const postId = postResponse.data.id;

            if (!postId) {
                console.log(postResponse.data);
                console.log(postResponse);
            }

            publishLogger.warn(`Post created with ID: ${postId}`);

        }

        return { success: true, postId: postResponse.data.id };

    } catch (error) {
        publishLogger.error(`Error publishing post: ${error.message}`);
        console.log(error);
        throw new Error(error);
    }
}

/**
 * Moves a file from one directory to another.
 *
 * @param {string} fileName - The name to the original file.
 * @param {string} type - The type of the original file.
 * @param {function} callback - A callback function to handle the result (optional).
 */
function moveFile(fileName, type, callback) {

    const currentDirectory = process.cwd();
    const sourceFilePath = path.resolve(path.dirname(process.execPath), `playbook-drafts/${fileName}`);
    const destFilePath = path.resolve(path.dirname(process.execPath), `playbook-published/${fileName}`);


    publishLogger.warn(`move file from ${sourceFilePath} to ${destFilePath}`);


    fs.rename(sourceFilePath, destFilePath, (err) => {
        if (err) {
            if (err.code === 'EXDEV') {
                publishLogger.error("Cross Device Error: ", err);
            } else {
                publishLogger.info(err);
                if (callback) {
                    callback(err);
                }
            }
        } else {
            publishLogger.info("move was successful");
            if (callback) {
                callback();
            }
        }
    });
}

// Listen for messages from the parent thread
parentPort && parentPort.on('message', async (specs) => {

    const blogData = specs.input;
    const fileName = specs.fileName;
    const type = specs.type;
    let result = { success: false };

    try {
        result = await publishPost(blogData, type, fileName);

        //after the post has been published, move it to the published folder
        if (result.success) {
            moveFile(fileName, type);
        }

    } catch (error) {
        throw new Error(`Error in publishPost: ${error.message}`);
    }

    parentPort.postMessage(result);
});

module.exports = {
    publishPost
};
