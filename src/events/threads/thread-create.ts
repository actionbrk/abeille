import { Events, type AnyThreadChannel } from "discord.js";
import type { BeeEvent } from "../../models/events";
import logger from "../../logger";

const ThreadsCreateEvent: BeeEvent<Events.ThreadCreate> = {
  name: Events.ThreadCreate,
  once: false,
  async execute(thread: AnyThreadChannel, newlyCreate: boolean) {
    logger.info("Thread %s created in channel %s", thread.name, thread.parent?.name);

    if (newlyCreate) {
      // We join without awaiting to avoid blocking the event loop
      thread
        .join()
        .then(() => logger.info("Thread %s joined", thread.name))
        .catch((error) => logger.error("Error joining thread %s: %o", thread.name, error));
    } else {
      logger.info("Thread %s is not newly created. Doing nothing", thread.name);
    }
  },
};

export default ThreadsCreateEvent;
