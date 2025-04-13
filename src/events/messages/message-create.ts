import { Events, type Message } from "discord.js";
import type { BeeEvent } from "../../models/events";
import { saveMessage } from "../../database/bee-database";
import { fromDiscordMessage, messageHasContentOrUrl } from "../../models/database/message";
import logger from "../../logger";

const MessageCreateEvent: BeeEvent<Events.MessageCreate> = {
  name: Events.MessageCreate,
  once: false,
  async execute(message: Message) {
    if (message.guildId === null) return;
    if (message.author.bot) return;

    try {
      const dbMessage = fromDiscordMessage(message);

      if (messageHasContentOrUrl(dbMessage)) {
        saveMessage(message.guild!.id, dbMessage);
        logger.debug("Saved message %s from channel %s", message.id, message.channelId);
      }

    } catch (error) {
      logger.error("Error saving message %s: %o", message.id, error);
    }
  },
};

export default MessageCreateEvent;
