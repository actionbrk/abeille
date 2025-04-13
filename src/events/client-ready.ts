import { Client, Collection, Events, REST, Routes } from "discord.js";
import type { BeeEvent } from "../models/events";
import { loadCommandsAsync } from "../loaders";
import logger from "../logger";
import type { Command } from "../models/command";
import { getLastMessageIdFromCache } from "../abeille-db-sync";
import { saveMessagesForGuild } from "../commands/admin/save";

const ClientReadyEvent: BeeEvent<Events.ClientReady> = {
  name: Events.ClientReady,
  once: true,
  async execute(client) {
    try {
      // Load all commands
      const commands = await loadCommandsAsync();

      await registerSlashsCommands(client, commands);

      syncMessagesOfGuilds(client)
        .then(() => {
          logger.info("Messages synced successfully");
        })
        .catch((error) => {
          logger.error("Error syncing messages: %s", error);
        });

      logger.info("Ready! Logged in as %s", client.user.tag);
    } catch (error) {
      logger.error("Error during client ready: %o", error);
    }
  },
};

export default ClientReadyEvent;

async function registerSlashsCommands(client: Client, allCommands: Collection<string, Command>): Promise<void> {
  try {
    logger.info("Registering slash commands");
    client.commands = allCommands;
    const rest = new REST().setToken(client.token!);
    const commands = Array.from(allCommands.values()).map((c) => c.data.toJSON());
    logger.info(`Started refreshing ${commands.length} application (/) commands.`);

    const clientApplicationId = client.application?.id;
    if (!clientApplicationId) {
      logger.error("Client application ID is not set. Please ensure the bot is logged in.");
      process.exit(1);
    }

    // If a GUILD_ID is provided, the commands will be registered in that guild
    // This is useful for testing commands without having to wait for global command propagation
    // Global commands can take up to an hour to propagate, while guild commands are available immediately
    if (process.env.GUILD_ID) {
      // The put method is used to register commands in a specific guild
      const guildId = process.env.GUILD_ID;
      const data: unknown[] = (await rest.put(Routes.applicationGuildCommands(clientApplicationId, guildId), {
        body: commands,
      })) as unknown[];

      logger.info(`Successfully reloaded ${data.length} application (/) commands in the guild.`);
    } else {
      // The put method is used to fully refresh all commands in the guild with the current set
      const data: unknown[] = (await rest.put(Routes.applicationCommands(clientApplicationId), {
        body: commands,
      })) as unknown[];

      logger.info(`Successfully reloaded ${data.length} application (/) commands.`);
    }
  } catch (error) {
    logger.error("Error registering slash commands: %s", error);
  }
}

async function syncMessagesOfGuilds(client: Client): Promise<void> {
  return new Promise((resolve, reject) => {
    try {
      client.guilds.cache.forEach((guild) => {
        logger.info("Connected to guild: %s (ID: %s)", guild.name, guild.id);

        logger.info("Retrieving messages from last message saved for the guild %s", guild.name);

        const lastMessageId = getLastMessageIdFromCache(guild.id);

        if (lastMessageId) {
          logger.info("Last message ID found for guild %s: %s", guild.name, lastMessageId);

          saveMessagesForGuild(guild, lastMessageId);
        } else {
          logger.info("No last message ID found for guild %s", guild.name);
        }
      });
    } catch (error) {
      logger.error("Error syncing messages for guilds: %s", error);
      reject(error);
    }

    resolve();
  });
}
