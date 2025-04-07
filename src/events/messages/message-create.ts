import { Events, Message } from "discord.js";
import logger from "../../logger";
import type { BeeEvent } from "../../models/events";
import { fromDiscordMessage } from "../../models/database/message";
import { saveMessage } from "../../database/bee-database";

const MessageCreateEvent: BeeEvent = {
  name: Events.MessageCreate,
  async execute(message: Message) {
    if (message.guildId === null) return;
    if (message.author.bot) return;

    logger.debug("Message from %s created: %s", message.author.id, message.content);

    const beeMessage = fromDiscordMessage(message);

    saveMessage(message.guildId, beeMessage);
  },
};

export default MessageCreateEvent;
