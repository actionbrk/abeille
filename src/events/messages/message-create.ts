import { Events, type Message } from "discord.js";
import type { BeeEvent } from "../../models/events";
import { saveMessage } from "../../database/bee-database";
import { fromDiscordMessage, filterSaveMessages } from "../../models/database/message";
import logger from "../../logger";
import { saveMessagesForGuild } from "../../commands/admin/save";

const MessageCreateEvent: BeeEvent<Events.MessageCreate> = {
  name: Events.MessageCreate,
  once: false,
  async execute(message: Message) {

    // Command !save {guild_id}, only from the bot owner in PM
    if (message.author.id === process.env.OWNER_ID && message.guildId === null && message.content?.startsWith("!save")) {
      const guildId = message.content.split(" ")[1];
      if (!guildId) {
        logger.error("Guild ID not provided in the command.");
        await message.reply("Invalid command format. Use !save {guild_id}.");
        return;
      }
      const guild = message.client.guilds.cache.get(guildId)!;
      if (guild) {
        await message.reply(`Start saving messages for guild ${guild.name}...`);
        await saveMessagesForGuild(guild);
        await message.reply("Messages saved successfully.");
      } else {
        await message.reply("Invalid guild ID or guild not found.");
      }
      return;
    }

    if (message.guildId === null) return;
    if (message.author.bot) return;

    try {
      const dbMessage = fromDiscordMessage(message);

      if (filterSaveMessages(dbMessage, message)) {
        saveMessage(message.guild!.id, dbMessage);
        logger.debug("Saved message %s from channel %s", message.id, message.channelId);
      }
    } catch (error) {
      logger.error("Error saving message %s: %o", message.id, error);
    }
  },
};

export default MessageCreateEvent;
