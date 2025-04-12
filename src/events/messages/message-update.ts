import { Events, type Message, type OmitPartialGroupDMChannel, type PartialMessage } from "discord.js";
import type { BeeEvent } from "../../models/events";
import { updateMessage } from "../../database/bee-database";
import logger from "../../logger";

const MessageUpdateEvent: BeeEvent<Events.MessageUpdate> = {
  name: Events.MessageUpdate,
  once: false,
  async execute(
    oldMessage: OmitPartialGroupDMChannel<Message<boolean> | PartialMessage>,
    newMessage: OmitPartialGroupDMChannel<Message<boolean> | PartialMessage>
  ) {
    if (oldMessage.guildId === null || newMessage.guildId === null) return;
    if (oldMessage.author?.bot || newMessage.author?.bot) return;

    // Skip if content hasn't changed
    if (oldMessage.content === newMessage.content && oldMessage.attachments.equals(newMessage.attachments)) {
      return;
    }

    try {
      updateMessage(
        newMessage.guild!.id,
        oldMessage.id,
        newMessage.content || null,
        newMessage.attachments.first()?.url || null
      );
      logger.debug("Updated message %s from channel %s", newMessage.id, newMessage.channelId);
    } catch (error) {
      logger.error("Error updating message %s: %o", newMessage.id, error);
    }
  },
};

export default MessageUpdateEvent;
