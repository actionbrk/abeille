import { Events, Message } from "discord.js";
import logger from "../../logger";
import type { BeeEvent } from "../../models/events";
import { updateMessage } from "../../database/bee-database";
import { fromDiscordMessage } from "../../models/database/message";

const MessageUpdateEvent: BeeEvent = {
  name: Events.MessageUpdate,
  async execute(message: Message) {
    if (message.guildId === null) return;
    if (message.author.bot) return;

    // Log the message content and author
    logger.debug("Message from %s edited: %s", message.author.id, message.content);

    const beeMessage = fromDiscordMessage(message);

    updateMessage(message.guildId, beeMessage);
  },
};

export default MessageUpdateEvent;
