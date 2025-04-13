import { Events, type Message, type OmitPartialGroupDMChannel, type PartialMessage } from "discord.js";
import type { BeeEvent } from "../../models/events";
import { deleteMessage } from "../../database/bee-database";
import logger from "../../logger";

const MessageDeleteEvent: BeeEvent<Events.MessageDelete> = {
  name: Events.MessageDelete,
  once: false,
  async execute(message: OmitPartialGroupDMChannel<Message<boolean> | PartialMessage>) {
    if (message.guildId === null) return;
    if (message.author?.bot) return;

    try {
      deleteMessage(message.guild!.id, message.id);
      logger.debug("Deleted message %s from channel %s", message.id, message.channelId);
    } catch (error) {
      logger.error("Error deleting message %s: %o", message.id, error);
    }
  },
};

export default MessageDeleteEvent;
