import { Client, GatewayIntentBits, Partials } from "discord.js";
import { loadEventsAsync } from "./loaders";
import { LocaleHelper } from "./utils/locale-helper";
import logger from "./logger";
import { HashHelper } from "./utils/hash-helper";
import path from "path";
import fs from "fs";
import { getDbFolder } from "./database/bee-database";
import { cacheLastEntriesOfDatabases } from "./abeille-db-sync";

const TOKEN = process.env.DISCORD_TOKEN;
if (!TOKEN) {
  logger.error("No Discord token provided. Please set the DISCORD_TOKEN environment variable.");
  process.exit(1);
}

const client = new Client({
  intents: [
    GatewayIntentBits.Guilds,
    GatewayIntentBits.GuildMessages,
    GatewayIntentBits.GuildMembers,
    GatewayIntentBits.MessageContent,
  ],
  partials: [Partials.Message, Partials.Channel, Partials.GuildMember],
});

async function main() {
  try {
    // Initialize translation system
    await LocaleHelper.initLocalesAsync();

    // Initialize hash helper
    HashHelper.initialize();

    // Ensure db folder exists
    const dbFolder = getDbFolder();
    const dbDir = path.resolve(dbFolder);
    if (!fs.existsSync(dbDir)) {
      fs.mkdirSync(dbDir, { recursive: true });
    }

    cacheLastEntriesOfDatabases();

    // Load event handlers
    await loadEventsAsync(client);

    // Login to Discord
    await client.login(TOKEN);
  } catch (error) {
    logger.error("Fatal error during startup: %o", error);
    process.exit(1);
  }
}

main();
