import { Events, Message } from "discord.js";
import logger from "../../logger";
import type { BeeEvent } from "../../models/events";
import { deleteMessage } from "../../database/bee-database";

const MessageDeleteEvent: BeeEvent = {
  name: Events.MessageDelete,
  async execute(message: Message) {
    if (message.guildId === null) return;
    if (message.author.bot) return;

    logger.debug("Message from %s delete: %s", message.author.id, message.content);

    deleteMessage(message.guildId, parseInt(message.id));
  },
};

export default MessageDeleteEvent;
