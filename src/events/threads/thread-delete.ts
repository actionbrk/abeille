import { Events, type AnyThreadChannel } from "discord.js";
import type { BeeEvent } from "../../models/events";
import logger from "../../logger";
import { deleteMessagesFromChannel } from "../../database/bee-database";

const ThreadsDeleteEvent: BeeEvent<Events.ThreadDelete> = {
  name: Events.ThreadDelete,
  once: false,
  async execute(thread: AnyThreadChannel) {
    logger.info("Thread %s deleted in channel %s", thread.name, thread.parent?.name);
    deleteMessagesFromChannel(thread.guildId, thread.id);
    logger.info("Messages from thread %s deleted", thread.name);
  },
};

export default ThreadsDeleteEvent;
