const WP_API_BASE = process.env.WP_API_BASE;
const WP_USERNAME = process.env.WP_USERNAME;
const WP_PASSWORD = process.env.WP_PASSWORD;

const Auth = {
    username: WP_USERNAME,
    password: WP_PASSWORD
}

module.exports = { Auth, WP_API_BASE };
