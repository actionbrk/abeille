import { loadCommandsAsync, loadEventsAsync } from "./loaders";
import logger from "./logger";
import { Client, GatewayIntentBits, REST, Routes } from "discord.js";
import { LocaleHelper } from "./utils/locale-helper";
import { HashHelper } from "./utils/hash-helper";

const discordToken = process.env.DISCORD_TOKEN;

if (!discordToken) {
  logger.error("Discord token is not set. Please set the DISCORD_TOKEN environment variable.");
  process.exit(1);
}

await LocaleHelper.initLocalesAsync();
HashHelper.initialize();

const client = new Client({
  intents: [
    // Requirements for messageCreate event
    GatewayIntentBits.Guilds,
    GatewayIntentBits.GuildMessages,
    GatewayIntentBits.MessageContent,
    GatewayIntentBits.GuildMembers,
  ],
});

try {
  await loadEventsAsync(client);
  logger.info("Events loaded successfully.");
} catch (error) {
  logger.error("Error loading events: %s", error);
  process.exit(1);
}

try {
  client.commands = await loadCommandsAsync();
  logger.info("Commands loaded successfully.");
} catch (error) {
  logger.error("Error loading commands: %s", error);
  process.exit(1);
}

try {
  await client.login(discordToken);
  logger.info("Abeille is logged in.");
} catch (error) {
  logger.error("Error logging in: %s", error);
}

try {
  logger.info("Registering slash commands");
  const rest = new REST().setToken(discordToken);
  const commands = [...client.commands.values()];
  logger.info(`Started refreshing ${commands.length} application (/) commands.`);

  const clientApplicationId = client.application?.id;
  if (!clientApplicationId) {
    logger.error("Client application ID is not set. Please ensure the bot is logged in.");
    process.exit(1);
  }

  const serializedCommands = commands.map((command) => command.data.toJSON());

  // If a GUILD_ID is provided, the commands will be registered in that guild
  // This is useful for testing commands without having to wait for global command propagation
  // Global commands can take up to an hour to propagate, while guild commands are available immediately
  if (process.env.GUILD_ID) {
    // The put method is used to register commands in a specific guild
    const guildId = process.env.GUILD_ID;
    const data: unknown[] = (await rest.put(Routes.applicationGuildCommands(clientApplicationId, guildId), {
      body: serializedCommands,
    })) as unknown[];

    logger.info(`Successfully reloaded ${data.length} application (/) commands in the guild.`);
  } else {
    // The put method is used to fully refresh all commands in the guild with the current set
    const data: unknown[] = (await rest.put(Routes.applicationCommands(clientApplicationId), {
      body: [],
    })) as unknown[];

    logger.info(`Successfully reloaded ${data.length} application (/) commands.`);
  }
} catch (error) {
  logger.error("Error registering slash commands: %s", error);
}

process.once("beforeExit", async () => {
  logger.info("Abeille is shutting down.");
  await client.destroy();
});
process.once("exit", async () => {
  logger.info("Abeille exited.");
});
